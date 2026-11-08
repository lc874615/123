"""Read-only live Ozon category schemas and evidence-backed local attributes."""
import re
import copy,hashlib,json,os,threading,time,urllib.error,urllib.request
from pathlib import Path
from decimal import Decimal
from pricing_service import read,write

API='https://api-seller.ozon.ru'
def field_key(field):return str(field.get('attribute_complex_id') or 0)+':'+str(field['id'])
def category_key(bundle):
 category=bundle.get('category') or {}
 if not category.get('description_category_id') or not category.get('type_id'):raise ValueError('请先匹配并确认上架类目')
 return (int(category['description_category_id']),int(category['type_id']))
def source_fingerprint(bundle):
 values={k:v for k,v in (bundle.get('variant_parameters') or {}).items() if k not in ('cost','margin','stock')}
 copy=bundle.get('copy') or {}
 evidence=bundle.get('reference_attributes') or {};stats=[]
 for ref in evidence.get('references') or []:
  try:stat=Path(ref['path']).stat();stats.append([stat.st_size,stat.st_mtime_ns])
  except OSError:stats.append(None)
 return hashlib.sha256(json.dumps([values,{k:copy.get(k) for k in ('title_ru','description_ru','tags_ru')},evidence,stats,bundle.get('model'),bundle.get('brand'),[{k:r.get(k) for k in ('order','role','https_url','sha256')} for r in bundle.get('images') or []]],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def review_hash(state):
 return hashlib.sha256(json.dumps([state.get('schema_hash'),state.get('source_fingerprint'),state.get('values')],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def api(path,body):
 if not os.environ.get('OZON_CLIENT_ID') or not os.environ.get('OZON_API_KEY'):raise ValueError('请先在本地连接Ozon API，才能读取真实必填属性')
 req=urllib.request.Request(API+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Client-Id':os.environ['OZON_CLIENT_ID'],'Api-Key':os.environ['OZON_API_KEY']})
 try:
  with urllib.request.urlopen(req,timeout=25) as response:value=json.load(response)
 except urllib.error.HTTPError as exc:raise ValueError('Ozon属性接口返回HTTP '+str(exc.code)+'，请检查API权限和类目') from None
 except (OSError,ValueError):raise ValueError('Ozon属性读取失败，请检查网络后重试') from None
 if not isinstance(value,dict) or not isinstance(value.get('result'),list):raise ValueError('Ozon属性响应格式异常')
 return value

AUTOFILL_VERSION=6
def normalized_name(field):
 return re.sub(r'\s+',' ',(field.get('name_ru') or field.get('name','')).casefold().replace('ё','е').replace('#','')).strip()
def audience(bundle):
 p=bundle.get('variant_parameters') or {}
 text=' '.join(str(p.get(k,'')) for k in ('name','size','extra'))+' '+str((bundle.get('category') or {}).get('name',''))
 if any(w in text.casefold() for w in ('儿童','婴儿','детск','малыш','婴幼')):return 'Для детей'
 return 'Для взрослых'
def suggested_value(field,bundle):
 """Only declared facts; dictionary values still require an exact official match."""
 name=normalized_name(field);identifier=int(field['id']);p=bundle.get('variant_parameters') or {};copy=bundle.get('copy') or {}
 from prefill_rules import value_for,field_kind
 value=value_for(field,bundle)
 if value is not None:return value
 if field_kind(field) or name in ('цвет товара','цвет','颜色','商品颜色','название цвета','颜色名称'):return None
 from rich_content import is_rich_field,generate
 if is_rich_field(field):return generate(bundle)
 from tag_rules import is_tag_field,is_series_field,normalize_tags
 if is_series_field(field):return '1'
 if is_tag_field(field):
  tags=normalize_tags(copy.get('tags_ru') or []);return tags if field.get('is_collection') else ' '.join(tags)
 if name.startswith('количество товара'):return p.get('quantity')
 if name in ('комплектация','配套','套装内容'):
  quantity=str(p.get('quantity') or '').strip();category=(bundle.get('category') or {}).get('name') or 'Товар'
  return category+' — '+quantity+' шт.' if quantity.isdigit() and int(quantity)>0 else None
 if name in ('вес товара, г','商品重量，克','商品重量, 克'):return p.get('net_weight')
 if name in ('количество в упаковке, шт','количество товара в единице измерения','единиц в одном товаре','количество товара','每包数量,pcs','一个商品中的件数'):return p.get('quantity')
 if name in ('количество заводских упаковок','原厂包装数量'):return '1'
 if name in ('название','名称'):return copy.get('title_ru')
 if name in ('код продавца','卖家代码'):return bundle.get('offer_id') or bundle.get('sku')
 if name in ('гарантия','保证'):return 'Без гарантии'
 if name in ('целевая аудитория','目标受众'):return audience(bundle)
 if name in ('название цвета','颜色名称'):
  return suggested_value({'id':0,'name_ru':'Цвет товара'},bundle)
 if identifier==85 or name in ('бренд','品牌'):return 'Нет бренда'
 if identifier==9048 or name in ('название модели','модель','型号','型号名称'):return bundle.get('model')
 if identifier==4191 or name in ('аннотация','описание товара','商品描述','简介'):return copy.get('description_ru')
 if name in ('страна-изготовитель','страна производства','生产国','原产国','产地'):return {'中国':'Китай'}.get(p.get('origin'),p.get('origin'))
 if name in ('цвет товара','цвет','颜色','商品颜色'):return {'金色':'золотой','红色':'красный','灰色':'серый','浅灰色':'светло-серый','黑色':'черный','白色':'белый','蓝色':'синий','绿色':'зеленый','米色':'бежевый'}.get(p.get('color'),p.get('color'))
 if name in ('материал','основной материал','主体材质','主要材质'):return {'聚丙烯':'Полипропилен','纸板':'Картон','金属':'Металл','塑料':'Пластик'}.get(p.get('material'),p.get('material'))
 if name in ('материал подкладки','内衬材质'):return {'纸板':'Картон','聚丙烯':'Полипропилен'}.get(p.get('accessory_material'),p.get('accessory_material'))
 if name in ('количество предметов в комплекте','количество в упаковке','套装件数','包装件数'):return p.get('quantity')
 if name in ('размер','规格','размер изделия'):return p.get('size')
 for key,words in [('length',('длина, см','商品长(cm)')),('width',('ширина, см','商品宽(cm)')),('height',('высота, см','商品高(cm)'))]:
  if name in words:return p.get(key)
 from group_service import binding
 link=binding(field)
 if link and p.get(link[0]):
  try:return str(Decimal(p[link[0]])/link[1])
  except Exception:return None
 return None

def validate_values(field,values):
 if not isinstance(values,list) or not values:raise ValueError('属性值不能为空')
 maximum=int(field.get('max_value_count') or (100 if field.get('is_collection') else 1))
 if len(values)>maximum or (not field.get('is_collection') and len(values)>1):raise ValueError('属性值数量超过该字段允许范围')
 for row in values:
  if field.get('dictionary_id'):
   if not isinstance(row.get('dictionary_value_id'),int) or row['dictionary_value_id']<=0:raise ValueError('请从官方字典选项中选择，不可手填字典ID')
  else:
   value=row.get('value')
   if not isinstance(value,str) or not value.strip():raise ValueError('属性值不能为空')
   if len(value)>20000:raise ValueError('属性值过长')
   kind=str(field.get('type','')).casefold()
   if kind in ('boolean','bool') and value.casefold() not in ('true','false'):raise ValueError('布尔属性请填true或false')
   if kind in ('decimal','integer','number','float','int','double'):
    try:number=Decimal(value)
    except Exception:raise ValueError('此属性要求数值') from None
    if not number.is_finite() or (kind in ('integer','int') and number!=number.to_integral_value()):raise ValueError('此属性要求有效数值')
 return values

class AttributeService:
 def __init__(self,data,lock=None,caller=api,active_skus=None):
  self.data=Path(data);self.root=self.data/'attributes';self.root.mkdir(parents=True,exist_ok=True);self.lock=lock or threading.Lock();self.io_lock=threading.RLock();self.caller=caller;self.active_skus=active_skus;self.schema_cache={};self.status='等待类目确认后读取必填属性';self.wake=threading.Event();self.retry_at={}
 def dictionary(self,bundle,field,query='',last_value_id=0,force=False):
  category,type_id=category_key(bundle);base={'attribute_id':field['id'],'description_category_id':category,'type_id':type_id}
  with self.io_lock:
   cache_path=self.root/f'{category}-{type_id}-{field["id"]}-queries.json'
   try:cached=read(cache_path) if cache_path.exists() else {}
   except (OSError,ValueError):cached={}
   if not isinstance(cached,dict):cached={}
   cache_key=json.dumps([query.strip(),last_value_id,'ZH_HANS',field.get('dictionary_id')],ensure_ascii=False);entry=cached.get(cache_key) or {}
   if not isinstance(entry,dict):entry={}
   if not force and 0<=time.time()-entry.get('fetched_at',0)<86400 and isinstance((entry.get('response') or {}).get('result'),list):return copy.deepcopy(entry['response'])
   self.status='正在读取官方选项：'+(field.get('name') or field.get('name_ru') or str(field['id']))
   if query:
    if len(query.strip())<2:raise ValueError('官方字典关键词至少2个字符')
    response=self.caller('/v1/description-category/attribute/values/search',{**base,'value':query.strip(),'limit':100})
   else:response=self.caller('/v1/description-category/attribute/values',{**base,'language':'ZH_HANS','last_value_id':last_value_id,'limit':200})
   path=self.root/(f'{category}-{type_id}-{field["id"]}.json');known=read(path) if path.exists() else {}
   for row in response['result']:
    if isinstance(row.get('id'),int) and row['id']>0:known[str(row['id'])]=row
   write(path,known);cached[cache_key]={'fetched_at':time.time(),'response':response};write(cache_path,cached);return response
 def migrate(self,bundle,old,fields):
  previous={field_key(f):f for f in old.get('fields',[])};values={};pending={};old_values=old.get('values') or {}
  for field in fields:
   key=field_key(field);prior=previous.get(key)
   if prior is None:
    candidates=[f for f in old.get('fields',[]) if (f.get('name_ru') or f.get('name','')).strip().casefold()==(field.get('name_ru') or field.get('name','')).strip().casefold()]
    if len(candidates)==1:prior=candidates[0]
   if prior is None:continue
   kept=old_values.get(field_key(prior))
   if not kept:continue
   if field.get('dictionary_id'):
    matched=[]
    for value in kept:
     label=value.get('value','')
     try:
      result=self.dictionary(bundle,field,label)['result'] if len(label.strip())>=2 else []
      matches={r['id']:r for r in result if str(r.get('value','')).strip().casefold()==label.strip().casefold()}
      if len(matches)!=1:
       result=self.dictionary(bundle,field)['result'];matches={r['id']:r for r in result if str(r.get('value','')).strip().casefold()==label.strip().casefold()}
      if len(matches)!=1:break
      row=next(iter(matches.values()));matched.append({'dictionary_value_id':row['id'],'value':row['value']})
     except ValueError:break
    if len(matched)==len(kept):
     try:validate_values(field,matched);values[key]=matched;continue
     except ValueError:pass
   elif not prior.get('dictionary_id') and str(prior.get('type','')).casefold()==str(field.get('type','')).casefold() and (prior.get('name_ru') or prior.get('name','')).strip().casefold()==(field.get('name_ru') or field.get('name','')).strip().casefold():
    try:validate_values(field,kept);values[key]=copy.deepcopy(kept);continue
    except ValueError:pass
   pending[key]=copy.deepcopy(kept)
  return values,pending
 def resolve_suggestion(self,bundle,field,suggestion,force=False):
  from prefill_rules import aliases,color_values
  def lookup(value):
   accepted=aliases(field,value)
   if normalized_name(field)=='гарантия':accepted.update(('без гарантии','нет гарантии','без гарантий','无担保','无保修'))
   if normalized_name(field)=='целевая аудитория':accepted.update(('взрослая','взрослые','成人') if value=='Для взрослых' else ('детская','дети','儿童'))
   result=self.dictionary(bundle,field,str(value) if len(str(value))>=2 else '',force=force)['result']
   exact={r['id']:r for r in result if str(r.get('value','')).casefold().replace('ё','е')==str(value).casefold().replace('ё','е')}
   if len(exact)==1:return next(iter(exact.values()))
   found={r['id']:r for r in result if str(r.get('value','')).casefold().replace('ё','е') in accepted}
   if len(found)!=1:
    result=self.dictionary(bundle,field,force=force)['result'];found={r['id']:r for r in result if str(r.get('value','')).casefold().replace('ё','е') in accepted}
   if len(found)!=1:raise ValueError('官方选项未唯一匹配：'+str(value))
   return next(iter(found.values()))
  requested=suggestion if isinstance(suggestion,list) else [suggestion]
  if len(requested)>1 and (not field.get('is_collection') or int(field.get('max_value_count') or 100)<len(requested)):
   if normalized_name(field) not in ('цвет товара','цвет','颜色','商品颜色'):raise ValueError('官方字段不支持多个值')
   label=', '.join(requested);rows=self.dictionary(bundle,field,label,force=force)['result']
   rows+=self.dictionary(bundle,field,force=force)['result']
   expected={x.casefold().replace('ё','е') for x in requested}
   matches={r['id']:r for r in rows if {x.casefold().replace('ё','е') for x in (color_values(r.get('value')) or [])}==expected}
   if len(matches)!=1:raise ValueError('该颜色字段只允许一个选项，未找到同时包含全部颜色的官方组合；原始双颜色完整保留')
   rows=list(matches.values())
  else:rows=[lookup(v) for v in requested]
  values=[{'dictionary_value_id':r['id'],'value':r['value']} for r in rows]
  validate_values(field,values);return values
 def refresh(self,path,force=True):
  path=Path(path)
  with self.lock:
   bundle=read(path)
   from prefill_rules import fixed_settings
   if fixed_settings(bundle):write(path,bundle)
   from tag_rules import normalize_tags
   copy_value=bundle.get('copy') or {};normalized=normalize_tags(copy_value.get('tags_ru'))
   if copy_value.get('tags_ru')!=normalized:
    bundle['copy']={**copy_value,'tags_ru':normalized}
    from listing_bundle import copy_hash
    if bundle.get('copy_shared_hash'):bundle['copy_shared_hash']=copy_hash(bundle['copy'])
    write(path,bundle)
  category,type_id=category_key(bundle)
  if not (bundle.get('category') or {}).get('confirmed'):raise ValueError('类目仍待确认，请先确认或修改类目')
  with self.io_lock:
   base={'description_category_id':category,'type_id':type_id}
   cached=self.schema_cache.get((category,type_id))
   prior=bundle.get('attribute_draft') or bundle.get('attribute_history') or {}
   if not force and (not cached or time.time()-cached[0]>=86400) and prior.get('category_key')==[category,type_id] and prior.get('fields') and 0<=time.time()-prior.get('fetched_at',0)<86400:
    zh=copy.deepcopy(prior['fields']);ru=[{**f,'name':f.get('name_ru',f.get('name',''))} for f in zh];cached=(prior['fetched_at'],zh,ru);self.schema_cache[(category,type_id)]=cached
   if not force and cached and 0<=time.time()-cached[0]<86400:zh,ru=copy.deepcopy(cached[1:]);schema_time=cached[0]
   else:
    zh=self.caller('/v1/description-category/attribute',{**base,'language':'ZH_HANS'})['result'];ru=self.caller('/v1/description-category/attribute',{**base,'language':'RU'})['result'];schema_time=time.time();self.schema_cache[(category,type_id)]=(schema_time,copy.deepcopy(zh),copy.deepcopy(ru))
   russian={field_key(f):f for f in ru}
   fields=[{**f,'name_ru':russian.get(field_key(f),{}).get('name',f.get('name',''))} for f in zh]
   if not fields:raise ValueError('该类目未返回属性，暂不视为校验通过')
   digest=hashlib.sha256(json.dumps([category,type_id,fields],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
   old=bundle.get('attribute_draft') or bundle.get('attribute_history') or {};same=old.get('schema_hash')==digest
   source=source_fingerprint(bundle);manual=set(old.get('manual_keys') or []);unchanged=old.get('source_fingerprint')==source
   values={k:v for k,v in (old.get('values') or {}).items() if (unchanged and old.get('autofill_version')==AUTOFILL_VERSION) or k in manual} if same else {};pending=copy.deepcopy(old.get('migration_pending') or {}) if same else {}
   if not same and old:values,pending=self.migrate(bundle,old,fields)
   archive=(bundle.get('attribute_archives') or {}).get(str(category)+':'+str(type_id))
   if not same and archive:
    restored,unresolved=self.migrate(bundle,archive,[f for f in fields if field_key(f) not in values])
    values.update(restored);pending.update(unresolved);manual.update(k for k in restored if k in (archive.get('manual_keys') or []))
    for k in restored:pending.pop(k,None)
   for k in old.get('auto_reference_keys') or []:
    if k not in manual:values.pop(k,None)
   suggestions={};prefill_notes={}
   for field in fields:
    key=field_key(field)
    from rich_content import is_rich_field
    from tag_rules import is_tag_field,is_series_field
    if is_rich_field(field) or is_tag_field(field) or (is_series_field(field) and old.get('autofill_version',0)<5):values.pop(key,None);manual.discard(key)
    if key in values or field['id'] in (8229,21841,21837,21845):continue
    suggestion=suggested_value(field,bundle)
    if suggestion is None or suggestion=='':continue
    suggestions[key]=suggestion
    if field.get('dictionary_id'):
     old_values=(old.get('values') or {}).get(key)
     if same and 0<=time.time()-old.get('fetched_at',0)<86400 and (old.get('suggestions') or {}).get(key)==suggestion and old_values:
      try:validate_values(field,old_values);values[key]=copy.deepcopy(old_values);continue
      except ValueError:pass
     try:values[key]=self.resolve_suggestion(bundle,field,suggestion)
     except ValueError as error:prefill_notes[key]=str(error)
    else:
     proposed=[{'value':str(v)} for v in (suggestion if isinstance(suggestion,list) else [suggestion])]
     try:validate_values(field,proposed);values[key]=proposed
     except ValueError:pass
   from assisted_fields import inline_references
   provisional={**bundle,'attribute_draft':{'fields':fields,'values':values,'manual_keys':list(manual)}}
   auto_references={}
   for key,reference in inline_references(provisional).items():
    if not reference['suggested']:continue
    field=reference['field'];proposed=[{'value':reference['suggested']}]
    if field.get('dictionary_id'):
     try:
      label=reference['suggested'];rows=self.dictionary(bundle,field,label if len(label)>=2 else '')['result'];matches=[r for r in rows if str(r.get('value','')).casefold()==label.casefold()]
      if len(matches)!=1:continue
      proposed=[{'dictionary_value_id':matches[0]['id'],'value':matches[0]['value']}]
     except ValueError:continue
    try:validate_values(field,proposed)
    except ValueError:continue
    values[key]=proposed;auto_references[key]={k:reference[k] for k in ('suggested','evidence','confidence','note','kind')}
   from prefill_rules import annotation
   for field in fields:
    key=field_key(field);reference=annotation(field,bundle)
    if reference and key in values and key not in manual:auto_references[key]=reference
   for k in values:pending.pop(k,None)
   state={'autofill_version':AUTOFILL_VERSION,'prefill_notes':prefill_notes,'auto_reference_keys':sorted(auto_references),'auto_references':auto_references,'category_key':[category,type_id],'schema_hash':digest,'fields':fields,'values':values,'suggestions':suggestions,'fetched_at':schema_time,'confirmed':bool(same and unchanged and old.get('autofill_version')==AUTOFILL_VERSION and old.get('confirmed')),'source_fingerprint':source,'manual_keys':sorted(manual) if same else [k for k in values if k in manual],'migration_pending':pending}
   with self.lock:
    latest=read(path)
    if category_key(latest)!=(category,type_id) or source_fingerprint(latest)!=source or not latest['category'].get('confirmed'):raise ValueError('读取期间类目已变化，请重新读取')
    # Do not discard edits made while a network request was in progress.
    current=latest.get('attribute_draft') or {}
    if current.get('schema_hash')==digest:
     for k,v in (current.get('values') or {}).items():
      if (k not in auto_references or k in (current.get('manual_keys') or [])) and not any(field_key(f)==k and (is_rich_field(f) or is_tag_field(f) or (is_series_field(f) and current.get('autofill_version',0)<5)) for f in fields) and ((current.get('source_fingerprint')==source and current.get('autofill_version')==AUTOFILL_VERSION) or k in (current.get('manual_keys') or [])):state['values'][k]=v
     for k in (current.get('manual_keys') or []):
      state['auto_references'].pop(k,None)
     state['auto_reference_keys']=sorted(state['auto_references'])
     state['manual_keys']=[k for k in (current.get('manual_keys') or []) if not any(field_key(f)==k and (is_rich_field(f) or is_tag_field(f) or (is_series_field(f) and current.get('autofill_version',0)<5)) for f in fields)]
     state['confirmed']=bool(current.get('source_fingerprint')==source and current.get('autofill_version')==AUTOFILL_VERSION and current.get('confirmed'))
     if state['confirmed']:state['confirmed_values_hash']=current.get('confirmed_values_hash')
    if old.get('category_key'):
     archive_key=':'.join(str(v) for v in old['category_key']);latest.setdefault('attribute_archives',{})[archive_key]=old
    latest['attribute_draft']=state;latest.pop('attribute_history',None)
    if not state.get('confirmed') and '必填属性待核对' not in latest.get('blockers',[]):latest.setdefault('blockers',[]).append('必填属性待核对')
    write(path,latest)
   return state
 def prepare_values(self,bundle,key,values):
  state=bundle.get('attribute_draft') or {}
  if list(category_key(bundle))!=state.get('category_key'):raise ValueError('类目已变化，请重新读取属性')
  field=next((f for f in state['fields'] if field_key(f)==key),None)
  if field is None:raise ValueError('此属性不属于当前官方类目')
  if not values:return []
  validate_values(field,values)
  if field.get('dictionary_id'):
   category,type_id=category_key(bundle);known_path=self.root/f'{category}-{type_id}-{field["id"]}.json';known=read(known_path) if known_path.exists() else {}
   if any(str(v['dictionary_value_id']) not in known for v in values):raise ValueError('字典值未经当前类目官方接口验证，请重新选择')
   values=[{'dictionary_value_id':v['dictionary_value_id'],'value':known[str(v['dictionary_value_id'])]['value']} for v in values]
  return values
 def save_values(self,path,key,values):return self.save_many([(path,key,values)])
 def save_many(self,changes):
  prepared=[]
  with self.lock:
   for name,key,values in changes:
    path=Path(name);bundle=read(path);values=self.prepare_values(bundle,key,values);state=bundle['attribute_draft']
    state.setdefault('values',{})[key]=values;state['manual_keys']=sorted(set(state.get('manual_keys') or [])|{key});state['confirmed']=False
    (state.get('migration_pending') or {}).pop(key,None);prepared.append((path,bundle))
   for path,bundle in prepared:write(path,bundle)
  return len(prepared)
 def confirm(self,path,vat,currency_confirmed):return self.confirm_many([path],vat,currency_confirmed)
 def confirm_many(self,paths,vat,currency_confirmed,expected=None):
  from listing_preview import attribute_errors
  if vat!='0':raise ValueError('按你的固定规则，增值税率只能为0')
  if not currency_confirmed:raise ValueError('请确认店铺结算币种为CNY')
  if not paths:raise ValueError('没有可确认的变体任务')
  prepared=[]
  with self.lock:
   for name in paths:
    path=Path(name);bundle=read(path);errors=attribute_errors(bundle)
    if not (bundle.get('category') or {}).get('confirmed'):errors.append('类目待确认')
    if expected is not None and expected.get(str(path))!=review_hash(bundle.get('attribute_draft') or {}):errors.append('查看整组预览后属性发生变化，请重新核对')
    if errors:raise ValueError(path.parent.name+'：\n'+'\n'.join(errors))
    prepared.append((path,bundle))
   for path,bundle in prepared:
    state=bundle['attribute_draft'];state['confirmed']=True;state['confirmed_values_hash']=review_hash(state)
    bundle['category']['attributes_revalidation_required']=False;bundle['blockers']=[b for b in bundle.get('blockers',[]) if b not in ('类目及必填属性待匹配','必填属性待核对')]
    bundle['export_settings']={'currency_code':'CNY','currency_confirmed':True,'vat':vat};write(path,bundle)
  return len(prepared)
 def worker(self,stop):
  while not stop.is_set():
   for path in (self.data/'products').glob('*/listing_bundle.json'):
    if stop.is_set():return
    if self.active_skus is not None and path.parent.name not in self.active_skus():continue
    if self.retry_at.get(str(path),0)>time.time():continue
    try:
     with self.lock:bundle=read(path)
     if not (bundle.get('category') or {}).get('confirmed'):continue
     state=bundle.get('attribute_draft') or {}
     if state.get('autofill_version')==AUTOFILL_VERSION and state.get('category_key')==list(category_key(bundle)) and state.get('source_fingerprint')==source_fingerprint(bundle) and time.time()-state.get('fetched_at',0)<86400:
      self.status='当前类目属性已缓存，可核对或导出';continue
     self.status=path.parent.name+'：正在读取官方必填属性';self.refresh(path,force=False);self.status='必填属性已读取，待核对缺失项'
    except Exception as exc:self.status='属性待处理：'+str(exc)[:160];self.retry_at[str(path)]=time.time()+60
   self.wake.wait(15);self.wake.clear()
