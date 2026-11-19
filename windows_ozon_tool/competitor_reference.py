"""Read-only public Ozon references matched to the selected official schema.
No competitor value becomes a product fact or a submitted attribute automatically.
"""
import hashlib,json,re,secrets,time
from urllib.parse import urlsplit
from pricing_service import read,write
from attribute_service import field_key,category_key


def normalize_url(value):
 value=str(value or '').strip()
 if not value:return ''
 try:
  u=urlsplit(value)
  if u.scheme!='https' or u.hostname not in ('ozon.ru','www.ozon.ru') or u.username or u.password or u.port not in (None,443):raise ValueError()
  if not re.fullmatch(r'/product/(?:[^/\s?#]+-)?[0-9]+/?',u.path) or len(value)>2048:raise ValueError()
 except (ValueError,TypeError):raise ValueError('竞品链接请填写 https://www.ozon.ru/product/… 的商品页面地址')
 return 'https://www.ozon.ru'+u.path.rstrip('/')+'/'


def norm(value):return re.sub(r'[\W_]+',' ',str(value).casefold().replace('ё','е')).strip()

# Fields tied to the seller, legal declarations or a different physical package
# must never be borrowed. Names are checked in BOTH official languages.
DENY=('упаков','包装','брутто','бренд','品牌','модель','型号','артикул','货号','штрих','barcode','сертифик','认证','证书','декларац','гаранти','质保','гарантия','страна','产地','производител','制造商','изготовител','продав','поставщик','налог','税','ндс','маркиров','标记','комплект','套装','每套件数','销售数量','количество в упаковке','количество предметов','количество товара','медицин','医疗','безопас','安全','идентификатор','ссылка','链接','фото','图片','видео','视频','название','名称','описание','描述','аннотац','цен','价格','скид','折扣','остат','库存','тег','标签','серия','系列','срок','有效期','инструкц','说明书','pdf','rich','html','url')
DENY_IDS={85,8229,4180,4191,21841,21837,21845}


def eligible(field):
 if field.get('id') in DENY_IDS or field.get('attribute_complex_id'):return False
 names=' '.join(str(field.get(k) or '').casefold() for k in ('name','name_ru'))
 return bool(names.strip()) and not any(s in names for s in DENY)


def context(bundle,account):
 url=normalize_url((bundle.get('variant_parameters') or {}).get('competitor_url'))
 state=bundle.get('attribute_draft') or {}
 if not url or not account or not (bundle.get('category') or {}).get('confirmed'):return None
 try:cat=list(category_key(bundle))
 except (ValueError,TypeError):return None
 if state.get('category_key')!=cat or not state.get('fields') or not state.get('schema_hash'):return None
 fields=[{k:f.get(k) for k in ('id','attribute_complex_id','name','name_ru','type','dictionary_id','is_required','is_collection','max_value_count')} for f in state['fields'] if eligible(f)]
 fingerprint=hashlib.sha256(json.dumps([str(account),url,cat,state['schema_hash'],fields],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
 return {'fingerprint':fingerprint,'url':url,'category_key':cat,'schema_hash':state['schema_hash'],'fields':fields}


def proposals(bundle):
 """Only missing official cells, preserving all own facts and manual decisions."""
 from attribute_service import suggested_value
 result={};snapshot=bundle.get('competitor_reference') or {};state=bundle.get('attribute_draft') or {}
 if snapshot.get('state')!='ready':return result
 try:
  from account_context import credentials
  current=context(bundle,credentials()[0])
 except ValueError:return result
 if not current or snapshot.get('fingerprint')!=current['fingerprint']:return result
 decisions=bundle.get('reference_decisions') or {};fields={field_key(f):f for f in state.get('fields',[]) if eligible(f)}
 for key,item in (snapshot.get('suggestions') or {}).items():
  f=fields.get(key)
  if not f or (state.get('values') or {}).get(key) or key in (state.get('manual_keys') or []):continue
  # Even a locally supplied value whose dictionary resolution is still pending
  # takes precedence over a competitor's value.
  if suggested_value(f,bundle) not in (None,'',[]):continue
  source=snapshot['fingerprint']+':'+snapshot.get('result_hash','')
  if (decisions.get(key) or {}).get('source')==source:continue
  result[key]={'key':key,'field':f,'kind':'competitor','suggested':item['value'],'display':item['value']+' · 竞品待核对','confidence':'竞品参考，非本商品事实','required':bool(f.get('is_required')),'evidence':snapshot['url']+' | '+item['name']+'：'+item['value'],'note':'仅在与你的商品一致时采用；采用时校验官方字典。不会自动用于作图或上架。','reference_source':source}
 return result


def match(fields,rows):
 """Exact bilingual label matching only; no inferred facts or loose similarity."""
 index={};multi={}
 if not isinstance(rows,list):raise ValueError('竞品参数格式无效')
 for row in rows[:400]:
  if not isinstance(row,dict):continue
  name=row.get('name');value=row.get('value')
  if not isinstance(name,str) or not isinstance(value,str) or not 0<len(name)<=180 or not 0<len(value)<=800:continue
  if any(c in value for c in ('<','>','\x00')) or re.search(r'https?://',value,re.I):continue
  index.setdefault(norm(name),set()).add(value.strip())
  options=row.get('values')
  if isinstance(options,list) and 0<len(options)<=100 and all(isinstance(v,str) and 0<len(v.strip())<=800 and not any(c in v for c in ('<','>','\x00')) and not re.search(r'https?://',v,re.I) for v in options):multi.setdefault(norm(name),set()).add(tuple(sorted(set(v.strip() for v in options))))
 result={}
 for f in fields:
  if not eligible(f):continue
  values=set()
  for label in (f.get('name'),f.get('name_ru')):values.update(index.get(norm(label),set()))
  if len(values)!=1:continue
  value=values.pop()
  if not value:continue
  if f.get('is_collection'):
   sets=set()
   for label in (f.get('name'),f.get('name_ru')):sets.update(multi.get(norm(label),set()))
   if len(sets)>1:continue
   options=list(sets.pop()) if sets else [value]
   if len(options)>int(f.get('max_value_count') or 100):continue
   result[field_key(f)]={'name':f.get('name_ru') or f.get('name'),'value':'；'.join(options),'values':options};continue
  # Numerical units must already match the official field's unit. Never
  # guess cm/mm, package vs product, or convert an ambiguous compound value.
  if str(f.get('type')).lower() in ('integer','decimal'):
   units={'см':('см','cm'),'мм':('мм','mm'),'кг':('кг','kg'),'г':('г','g'),'мл':('мл','ml'),'л':('л','l'),'вт':('вт','w'),'в':('в','v')}
   labels=' '+norm(f.get('name_ru') or f.get('name'))+' '
   for unit,aliases in units.items():
    if ' '+unit+' ' in labels:
     value=re.sub(r'\s*(?:'+('|'.join(aliases))+r')$', '',value,flags=re.I).strip();break
   if not re.fullmatch(r'\d+(?:[.,]\d+)?',value):continue
   if str(f.get('type')).lower()=='integer' and not re.fullmatch(r'\d+',value):continue
  if str(f.get('type')).lower()=='boolean':
   converted={'да':'true','нет':'false','true':'true','false':'false'}.get(value.casefold())
   if converted is None:continue
   value=converted
  result[field_key(f)]={'name':f.get('name_ru') or f.get('name'),'value':value.replace(',','.') if str(f.get('type')).lower() in ('integer','decimal') else value}
 return result


def _bundles(store):
 for task in store.tasks:
  path=store.folder/'products'/task['sku']/'listing_bundle.json'
  if task.get('state')=='cancelled' or not path.is_file():continue
  try:
   b=read(path)
   if b.get('status') in ('published','cancelled'):continue
   yield path,b
  except (OSError,ValueError):continue


def claim(store):
 from account_context import credentials
 account=credentials()[0]
 now=time.time();candidates=[]
 for path,b in _bundles(store):
  try:c=context(b,account)
  except ValueError:continue
  if not c:continue
  previous=b.get('competitor_reference') or {}
  if previous.get('fingerprint')==c['fingerprint']:
   if previous.get('state')=='ready':continue
   if previous.get('state')=='failed':
    if previous.get('attempts',0)>=3 or previous.get('error_code') in ('verification','redirect'):continue
    if previous.get('attempts') and previous.get('retry_at',0)>now:continue
   elif previous.get('retry_at',0)>now:continue
  candidates.append((path,b,c))
 waiting={t.get('copy_leader',t['sku']) for t in store.tasks if (t.get('competitor_wait') or {}).get('state')=='waiting'}
 priority={t['sku'] for t in store.tasks if t.get('copy_leader',t['sku']) in waiting}
 candidates.sort(key=lambda row:row[1].get('sku') not in priority)
 if not candidates:return {'job':None}
 target=candidates[0][2];token=secrets.token_hex(16)
 # One lease per URL/schema/shop. It also prevents two service-worker wakes
 # from dispatching duplicate browser reads; lease survives extension restart.
 cached=None
 for _,b in _bundles(store):
  s=b.get('competitor_reference') or {}
  if s.get('fingerprint')==target['fingerprint'] and (s.get('state')=='ready' or (s.get('state')=='reading' and s.get('retry_at',0)>now)):cached=s;break
 for path,b,c in candidates:
  if c['fingerprint']!=target['fingerprint']:continue
  b['competitor_reference']=dict(cached) if cached else {'fingerprint':c['fingerprint'],'url':c['url'],'state':'reading','token':token,'attempts':(int((b.get('competitor_reference') or {}).get('attempts',0)) if (b.get('competitor_reference') or {}).get('fingerprint')==c['fingerprint'] else 0)+1,'retry_at':now+180,'message':'正在读取竞品公开参数，按已选类目官方字段匹配'}
  write(path,b)
 if cached:return {'job':None}
 return {'job':{**target,'token':token}}


def receive(store,body):
 from account_context import credentials
 account=credentials()[0];matches=[]
 for path,b in _bundles(store):
  s=b.get('competitor_reference') or {}
  try:c=context(b,account)
  except ValueError:continue
  if c and s.get('state')=='reading' and s.get('token')==body.get('token') and s.get('fingerprint')==c['fingerprint']:matches.append((path,b,c))
 if not matches:return {'ok':True,'stale':True}
 c=matches[0][2];error=str(body.get('error') or '')[:200]
 if not error:
  if normalize_url(body.get('url'))!=c['url']:raise ValueError('竞品页面已跳转，未采用其他商品参数')
  suggestions=match(c['fields'],body.get('rows'))
  if not body.get('rows'):error='页面未读取到公开参数，未预填；可打开原链接核对。'
 else:suggestions={}
 attempts=max(int((b.get('competitor_reference') or {}).get('attempts',1)) for _,b,_ in matches);code=body['error_code'] if error and body.get('error_code') in ('verification','redirect') else 'transient' if error else '';retryable=bool(error and code not in ('verification','redirect') and attempts<3)
 result={'attempts':attempts,'error_code':code,'retryable':retryable,'raw_count':len(body.get('rows') or []) if not error else 0,'unmatched_names':[str(r.get('name',''))[:180] for r in (body.get('rows') or [])[:400] if isinstance(r,dict) and norm(r.get('name')) not in {norm(f.get(k)) for f in c['fields'] for k in ('name','name_ru')}][:12],'fingerprint':c['fingerprint'],'url':c['url'],'state':'failed' if error else 'ready','suggestions':suggestions,'fetched_at':time.time(),'retry_at':time.time()+ (5 if attempts==1 else 15) if retryable else time.time()+86400,'message':(error+('；将自动重试（第'+str(attempts)+'/3次）' if retryable else '；请完成页面验证后重新读取' if code=='verification' else '；请核对链接及页面后重新读取' if code=='redirect' else '；自动重试已停止，请点击重新读取')) if error else f'已匹配 {len(suggestions)} 项竞品参考；只补空白，核对后采用','result_hash':hashlib.sha256(json.dumps(suggestions,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
 for path,b,_ in matches:b['competitor_reference']=dict(result);write(path,b)
 from competitor_flow import signal
 signal(store)
 return {'ok':True,'matched':len(suggestions)}


def status(bundle):
 if not (bundle.get('variant_parameters') or {}).get('competitor_url'):return ''
 from competitor_flow import describe
 return describe(bundle)['label']
