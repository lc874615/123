"""Durable Ozon import -> selected rFBS warehouse stock -> platform status.
Only begin() is invoked by the explicit Submit button. Resume never replays an
unknown import or stock write. No API keys are persisted in receipts.
"""
import hashlib,json,os,secrets,threading,time,urllib.error,urllib.request
from pathlib import Path
from group_service import revision,preview_changes
from pricing_service import read,write
from listing_preview import export_preview

class Rejected(ValueError):pass
def explicit_true(value):return value is True or (isinstance(value,str) and value.strip().casefold()=='true')
def warehouse_label(row):
 kind=str(row.get('warehouse_type') or ('rFBS' if explicit_true(row.get('is_rfbs')) else '未标明类型'))
 state=str(row.get('status') or '未提供状态')
 return str(row.get('name') or row['warehouse_id'])+' ['+kind+'，'+state+'] / '+str(row['warehouse_id'])
READ_PATHS={'/v2/warehouse/list','/v1/product/import/info','/v3/product/info/list','/v2/product/info/stocks-by-warehouse/fbs'}
WRITE_PATHS={'/v3/product/import','/v2/products/stocks','/v1/product/import/prices'}
def account():
 if not os.environ.get('OZON_CLIENT_ID') or not os.environ.get('OZON_API_KEY'):raise ValueError('请连接具有商品和库存写入权限的Ozon API')
 return os.environ['OZON_CLIENT_ID']
def request(path,body,expected_account=None):
 from account_context import credentials
 client,key=credentials()
 if not client or not key:raise ValueError('请先连接Ozon API')
 if expected_account is not None and client!=expected_account:raise ValueError('店铺已切换，原店铺任务暂停写入')
 if path not in READ_PATHS|WRITE_PATHS:raise ValueError('接口不在本上架流程内')
 req=urllib.request.Request('https://api-seller.ozon.ru'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Client-Id':client,'Api-Key':key})
 try:
  with urllib.request.urlopen(req,timeout=35) as response:value=json.load(response)
 except urllib.error.HTTPError as exc:
  if 400<=exc.code<500 and exc.code!=408:
   message=''
   try:
    body=json.loads(exc.read(32768));message=str(body.get('message',''))[:1000] if isinstance(body,dict) else ''
    for key in ('OZON_API_KEY','COS_SECRET_KEY'):
     secret=os.environ.get(key,'')
     if secret:message=message.replace(secret,'[已隐藏]')
   except (OSError,ValueError):pass
   raise Rejected('Ozon拒绝请求（HTTP '+str(exc.code)+'）'+('：'+message if message else '，请检查权限或参数')) from None
  raise ValueError('Ozon响应异常，写入结果需要核对') from None
 except (OSError,ValueError):raise ValueError('Ozon请求未完成，写入结果需要核对') from None
 if not isinstance(value,dict):raise ValueError('Ozon响应格式异常')
 return value

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
TERMINAL={'on_sale','completed_zero_stock','partial_failed','rejected','failed','superseded','cancelled_followup','validation_failed'}
class PublicationService:
 def __init__(self,data,store_lock,caller=request,account_getter=account,initial_stock=None):
  if initial_stock is not None and (type(initial_stock) is not int or not 0<=initial_stock<=2147483647):raise ValueError('初始库存配置无效')
  self.initial_stock=initial_stock
  self.data=Path(data);self.root=self.data/'publications';self.root.mkdir(parents=True,exist_ok=True)
  self.lock=store_lock;self.mutex=threading.RLock();self.caller=caller;self.account_getter=account_getter;self.wake=threading.Event();self.status='尚未提交'
  self.relocate_receipts()
 def relocate_receipts(self):
  for job in self.jobs():
   changed=False;paths=[]
   for source in job.get('source_paths') or []:
    sku=Path(str(source).replace('\\','/')).parent.name;target=self.data/'products'/sku/'listing_bundle.json'
    if sku in job.get('items',{}) and target.exists():paths.append(str(target));changed=changed or str(target)!=source
    else:paths.append(source)
   if changed:job['source_paths']=paths;write(self.root/(job['id']+'.json'),job)
 def call_for(self,merchant,path,body):
  if self.account_getter()!=merchant:raise ValueError('店铺已切换，原店铺任务暂停；切回对应店铺后继续')
  return request(path,body,expected_account=merchant) if self.caller is request else self.caller(path,body)
 def warehouses(self,merchant=None):
  merchant=merchant or self.account_getter()
  result=[];cursor='';seen=set();ids=set();diagnostic={'endpoint':'/v2/warehouse/list','scope':'all_shop_warehouses','pages':[],'listed_count':0};self.warehouse_diagnostic=diagnostic
  for _ in range(100):
   try:response=self.call_for(merchant,'/v2/warehouse/list',{'limit':200,**({'cursor':cursor} if cursor else {})})
   except Exception as exc:
    diagnostic['error_type']=type(exc).__name__;self.save_warehouse_diagnostic();raise
   container=response.get('result') if isinstance(response.get('result'),dict) else response
   rows=container.get('warehouses')
   if not isinstance(rows,list):
    diagnostic['response_keys']=sorted(response.keys());self.save_warehouse_diagnostic();raise ValueError('仓库列表响应异常；请导出仓库诊断，未选择任何仓库')
   diagnostic['pages'].append({'count':len(rows),'rows':[{'keys':sorted(r.keys()),'status':r.get('status'),'is_rfbs':r.get('is_rfbs'),'warehouse_type':r.get('warehouse_type'),'quarantined':r.get('is_karantin'),'id_type':type(r.get('warehouse_id')).__name__} for r in rows if isinstance(r,dict)]})
   for row in rows:
    if not isinstance(row,dict):continue
    r=dict(row);wid=r.get('warehouse_id')
    if isinstance(wid,str) and wid.isdigit():wid=int(wid)
    if type(wid) is int and wid>0 and wid not in ids:
     r['warehouse_id']=wid;r['name']=r.get('name') or str(wid);result.append(r);ids.add(wid)
   more=container.get('has_next',False)
   if more is False or more is None or str(more).casefold() in ('false','0',''):
    diagnostic['listed_count']=len(result);self.save_warehouse_diagnostic();return result
   if more is not True and str(more).casefold() not in ('true','1'):raise ValueError('仓库分页标志异常，请重试')
   cursor=container.get('cursor','')
   if not cursor or cursor in seen:raise ValueError('仓库分页未完整读取，请重试')
   seen.add(cursor)
  raise ValueError('仓库列表超过分页限制')
 def save_warehouse_diagnostic(self):
  path=self.data/'warehouse_diagnostic.json';write(path,getattr(self,'warehouse_diagnostic',{'message':'尚未读取仓库'}));return path
 def warehouse_summary(self):
  data=getattr(self,'warehouse_diagnostic',{});rows=[r for page in data.get('pages',[]) for r in page.get('rows',[])]
  states={str(r.get('status') or '未提供'):sum(str(x.get('status') or '未提供')==str(r.get('status') or '未提供') for x in rows) for r in rows}
  return '接口返回 '+str(len(rows))+' 个仓库，已列出 '+str(data.get('listed_count',len(rows)))+' 个。平台状态：'+('、'.join(k+' '+str(v)+'个' for k,v in states.items()) or '无')+'。显示全部类型和状态；库存写入结果以平台API回执为准。'
 def jobs(self):
  values=[]
  for path in self.root.glob('*.json'):
   try:
    job=read(path)
    if isinstance(job,dict) and job.get('id'):values.append(job)
   except (OSError,ValueError):continue
  return sorted(values,key=lambda j:j.get('created_at',0),reverse=True)
 def active(self,offers):
  try:merchant=self.account_getter()
  except ValueError:return None
  return next((j for j in self.jobs() if j.get('account_id')==merchant and j.get('state') not in TERMINAL and not j.get('writes_complete') and set(offers)&set(j.get('items',{}))),None)
 def _save(self,job):
  now=time.time();signature=digest({o:{k:i.get(k) for k in ('import_state','price_state','price_errors','stock_state','stock_errors','on_sale','errors','platform_status','current_free_stock')} for o,i in job.get('items',{}).items()})
  if signature!=job.get('progress_fingerprint'):job['last_progress_at']=now;job['progress_fingerprint']=signature
  limit=1800 if job.get('writes_complete') else 600
  job['needs_attention']=now-job.get('last_progress_at',now)>limit and job.get('state') not in TERMINAL
  job['updated_at']=now;write(self.root/(job['id']+'.json'),job);self.status=job.get('message',job['state'])
 def begin(self,coordinator,expected,on_progress=None,visible_bundles=None):
  progress=on_progress or (lambda message:None);progress('等待本地提交队列')
  with self.mutex:
   merchant=self.account_getter()
   initial=coordinator.load()
   if revision(initial)!=expected:
    changes=preview_changes(visible_bundles,initial,allow_automatic=True) if visible_bundles is not None else ['预览版本已更新']
    if changes:raise ValueError('预览已变化，请核对后再提交：\n'+'\n'.join(changes))
    expected=revision(initial)
   existing=self.active([b['sku'] for b in initial])
   if existing:return existing
   from attribute_service import AUTOFILL_VERSION,source_fingerprint,category_key
   for path,b in zip(coordinator.paths,initial):
    state=b.get('attribute_draft') or {}
    fresh=state.get('autofill_version')==AUTOFILL_VERSION and state.get('category_key')==list(category_key(b)) and state.get('source_fingerprint')==source_fingerprint(b) and bool(state.get('fields')) and 0<=time.time()-state.get('fetched_at',0)<=86400
    if not fresh:
     progress(path.parent.name+'：刷新已过期或变化的官方属性');coordinator.attributes.refresh(path,force=False)
   progress('核对整组自动售价');coordinator.pricing.calculate_all()
   progress('重新核对店铺可用仓库');warehouses={r['warehouse_id']:r for r in self.warehouses(merchant)}
   with self.lock:
    bundles=[read(p) for p in coordinator.paths]
    changes=preview_changes(initial,bundles,allow_automatic=True)
    if changes:raise ValueError('提交前发现实际内容变化，已刷新预览，请核对后再次提交：\n'+'\n'.join(changes))
    # Refreshing source evidence with identical visible content is not a new approval.
    expected=revision(bundles)
    offers=[b['sku'] for b in bundles];existing=self.active(offers)
    if existing:return existing
    stocks={}
    for b in bundles:
     setting=b.get('fulfillment') or {};wid=setting.get('warehouse_id')
     if wid not in warehouses or setting.get('account_id')!=merchant:raise ValueError(b['sku']+'：请重新选择当前店铺返回的仓库')
     raw=str((b.get('variant_parameters') or {}).get('stock','')).strip()
     if self.initial_stock is not None and raw!=str(self.initial_stock):raise ValueError('新商品初始库存固定为'+str(self.initial_stock)+'，请刷新整组预览')
     if not raw.isdigit() or int(raw)>2147483647:raise ValueError(b['sku']+'：库存必须是有效的非负整数')
     stocks[b['sku']]={'warehouse_id':wid,'warehouse_name':warehouses[wid]['name'],'stock':int(raw),'stock_revision':b.get('stock_revision','initial')}
    # Clicking Submit approves the exact visible, validated group, not hidden stale values.
   settings=[b.get('export_settings') or {} for b in bundles]
   for setting in settings:
    if setting.get('currency_code')!='CNY' or not setting.get('currency_confirmed'):raise ValueError('请先确认店铺币种为CNY')
   vats={s.get('vat') for s in settings}
   if vats!={'0'}:raise ValueError('实际增值税率固定为0，请刷新预览自动填入')
   from listing_preview import attribute_errors
   with self.lock:
    latest=[read(p) for p in coordinator.paths]
    changes=preview_changes(bundles,latest,allow_automatic=True)
    if changes:raise ValueError('资料已变化，请核对后再提交：\n'+'\n'.join(changes))
    expected=revision(latest)
    for b in latest:
     errors=attribute_errors(b)
     if errors:raise ValueError(b['sku']+'：'+'；'.join(errors))
     if not (b.get('category') or {}).get('confirmed'):raise ValueError('类目尚未确认')
    from attribute_service import review_hash
    for path,b in zip(coordinator.paths,latest):
     b['attribute_draft'].update(confirmed=True,confirmed_values_hash=review_hash(b['attribute_draft']))
     b['pricing_confirmed_fingerprint']=b.get('pricing_fingerprint');b['pricing_confirmed_price']=b.get('price_cny');write(path,b)
   progress('校验必填属性、8图、视频和实际提交载荷')
   report=export_preview([p.parent for p in coordinator.paths],self.root/'staging',self.lock)
   if not report['ready']:raise ValueError('；'.join(r['offer_id']+'：'+'；'.join(r['missing']) for r in report['items'] if not r['ready']))
   payload=read(self.root/'staging'/'ozon_import_preview.json')
   with self.lock:
    if any(hashlib.sha256(Path(r['bundle_file']).read_bytes()).hexdigest()!=r['sha256'] for r in report['source_checksums']):raise ValueError('校验期间资料已更新，请刷新后提交')
    sealed_revision=revision([read(p) for p in coordinator.paths])
   from listing_prices import listing_prices
   price_settings=[listing_prices(read(p)) for p in coordinator.paths]
   plan_hash=digest([merchant,payload,stocks,price_settings])
   for previous in self.jobs():
    if previous.get('plan_hash')==plan_hash and (previous.get('state') in ('on_sale','completed_zero_stock') or previous.get('writes_complete')):
     previous['source_revision']=sealed_revision;self._save(previous);return self.step(previous['id'],refresh=True)
   job={'id':secrets.token_hex(12),'account_id':merchant,'created_at':time.time(),'state':'prepared','plan_hash':plan_hash,'payload':payload,'source_paths':[str(p) for p in coordinator.paths],'source_revision':sealed_revision,'revision_version':2,'stocks':stocks,'items':{},'message':'整组资料已冻结，准备提交'}
   job['price_settings']=price_settings
   history=[j for j in self.jobs() if j.get('account_id')==merchant]
   for item in payload['items']:
    offer=item['offer_id'];item_hash=digest(item);stock_sig=digest([merchant,stocks[offer]])
    prior_item=next((j['items'][offer] for j in history if offer in j.get('items',{}) and j['items'][offer].get('item_hash')==item_hash and j['items'][offer].get('import_state')=='imported' and not j['items'][offer].get('validation_blocked')),None)
    prior_stock=next((j['items'][offer] for j in history if offer in j.get('items',{}) and j['items'][offer].get('stock_signature')==stock_sig and j['items'][offer].get('stock_state')=='done'),None)
    job['items'][offer]={'item_hash':item_hash,'stock_signature':stock_sig,'import_state':'imported' if prior_item else 'pending','product_id':prior_item.get('product_id') if prior_item else None,'stock_state':'done' if prior_stock else 'pending','status':'等待提交','errors':[]}
   self._save(job)
   pending=[i for i in payload['items'] if job['items'][i['offer_id']]['import_state']!='imported']
   if pending:
    job.update(state='import_intent',message='正在提交商品，勿重复操作');self._save(job);progress('正在调用Ozon导入接口，等待任务ID')
    try:
     result=self.call_for(merchant,'/v3/product/import',{'items':pending});task_id=(result.get('result') or {}).get('task_id')
     if isinstance(task_id,str) and task_id.isdigit():task_id=int(task_id)
     if type(task_id) is not int or task_id<=0:raise ValueError('未返回明确任务ID')
     job.update(task_id=task_id,state='importing',message='商品已受理，等待平台创建；自动查询导入状态')
     for row in pending:job['items'][row['offer_id']]['status']='已受理，等待平台创建'
    except Rejected as exc:job.update(state='rejected',message=str(exc))
    except Exception:job.update(state='import_uncertain',message='提交结果不确定，不自动重发；请在Ozon后台核对')
   else:job.update(state='stock_pending',message='已导入的内容保持不变，继续核对库存')
   self._save(job);self.wake.set();return job
 def step(self,job_id,refresh=False):
  with self.mutex:
   job=read(self.root/(job_id+'.json'))
   if job['state'] in TERMINAL and not (refresh and job['state'] in ('on_sale','completed_zero_stock')):return job
   if self.account_getter()!=job['account_id']:raise ValueError('API店铺已切换，未继续原店铺的写入')
   if job['state'] in ('prepared','import_intent','import_uncertain'):
    job.update(state='import_uncertain',message='没有明确导入任务ID，保留记录，不自动重发');self._save(job);return job
   tasks=self.data/'tasks.json'
   if tasks.exists():
    active={t.get('sku') for t in read(tasks) if t.get('state')!='cancelled'}
    if not set(job['items'])<=active:
     job.update(state='cancelled_followup',message='本地任务已移除/取消，停止后续写入；平台已受理的操作保留');self._save(job);return job
   for item in job['items'].values():
    if item.get('stock_state')=='intent':item.update(stock_state='uncertain',status='重启后库存结果待核对，不自动重写')
   if job.get('task_id'):
    response=self.call_for(job['account_id'],'/v1/product/import/info',{'task_id':job['task_id']});job['last_success_at']=time.time()
    for row in (response.get('result') or {}).get('items',[]):
     offer=row.get('offer_id')
     if offer not in job['items']:continue
     target=job['items'][offer];errors=row.get('errors') or []
     if row.get('status') in ('failed','error') or any(str(e.get('level','ERROR')).upper() in ('ERROR','ERROR_LEVEL_ERROR','ERROR_LEVEL_INTERNAL','INTERNAL') for e in errors):target.update(import_state='failed',errors=errors,status='导入失败')
     elif row.get('status') in ('imported','skipped') and row.get('product_id'):target.update(import_state='imported',product_id=row['product_id'],errors=[],status='已导入')
     elif target['import_state']!='imported':target.update(status='平台正在处理导入，等待创建完成',errors=errors)
   self._save(job)
   current=[read(p) for p in job['source_paths']]
   if not job.get('revision_version') and revision(current,legacy=True)==job['source_revision']:
    job['source_revision']=revision(current);job['revision_version']=2
   if revision(current)!=job['source_revision']:
    job.update(state='superseded' if job.get('writes_complete') else 'local_changed',message='本地资料已有新版本；原写入结果保留，旧任务停止后续写入');self._save(job);return job
   visible_offers=[o for o,item in job['items'].items() if item['import_state']!='failed']
   products={}
   if visible_offers:
    try:
     info=self.call_for(job['account_id'],'/v3/product/info/list',{'offer_id':visible_offers});products={r['offer_id']:r for r in info.get('items',[])};job['last_success_at']=time.time()
    except Rejected as exc:
     if 'product creation incomplete' not in str(exc).casefold():raise
   blocking=False
   for offer,item in job['items'].items():
    product=products.get(offer) or {};status=product.get('statuses') or {};errors=product.get('errors') or []
    item['platform_status']=status;item['platform_errors']=errors;item['error_summary']='；'.join(self.error_text(e) for e in errors);item['card_exists']=bool(product.get('id'))
    fatal=[e for e in errors if str(e.get('level','')).upper() in ('ERROR','ERROR_LEVEL_ERROR','ERROR_LEVEL_INTERNAL','INTERNAL')]
    invalid=str(status.get('validation_status','')).casefold() in ('failed','invalid','error','validation_failed')
    if fatal or invalid:
     item.update(validation_blocked=True,errors=fatal or errors,status='商品卡片已创建，但校验不通过；请修改后重新提交');blocking=True
    elif item['import_state']=='pending':item['status']='商品卡片已存在，等待本次导入结果' if item['card_exists'] else '平台正在处理导入，等待创建完成'
   if blocking:
    job.update(state='validation_failed',message='平台商品校验不通过，具体错误已回填；请修正参数后更新同货号商品，无需重复创建')
    self._save(job);return job
   offers=[o for o,item in job['items'].items() if item['import_state']=='imported']
   if not offers:
    failed=all(i['import_state']=='failed' for i in job['items'].values())
    job.update(state='failed' if failed else 'importing',message='整组导入失败，请查看逐变体错误' if failed else '正在等待本次导入结果，卡片创建与导入校验分别跟踪，不重复提交')
    self._save(job);return job
   price_rows=[r for r in job.get('price_settings',[]) if r['offer_id'] in offers and ((products.get(r['offer_id']) or {}).get('statuses') or {}).get('is_created') and job['items'][r['offer_id']].get('price_state')!='done' and job['items'][r['offer_id']].get('price_retry_at',0)<=time.time()]
   if price_rows:
    job.update(message='正在同步最高价格、划线价、促销最低限制和成本');self._save(job)
    response=self.call_for(job['account_id'],'/v1/product/import/prices',{'prices':price_rows})
    results={r.get('offer_id'):r for r in response.get('result',[])}
    for row in price_rows:
     result=results.get(row['offer_id']) or {};item=job['items'][row['offer_id']]
     item['price_state']='done' if result.get('updated') is True and not result.get('errors') else 'pending'
     item['price_errors']=result.get('errors') or []
     if item['price_state']!='done':
      item['price_retry_count']=item.get('price_retry_count',0)+1
      item['price_retry_at']=time.time()+min(900,120*2**min(item['price_retry_count']-1,3))
      item['status']='四项价格同步未完成；等待间隔重试'
    self._save(job)
   if any(job['items'][r['offer_id']].get('price_state')!='done' for r in job.get('price_settings',[]) if r['offer_id'] in offers):
    job.update(state='waiting_platform',message='等待同步四项价格；错误详见变体价格回执');self._save(job);return job
   shop_warehouses={r['warehouse_id']:r for r in self.warehouses(job['account_id'])}
   stock_rows=[]
   for offer,item in job['items'].items():
    if item['import_state']!='imported' or item['stock_state'] in ('done','uncertain','intent') or item.get('stock_retry_at',0)>time.time():continue
    product=products.get(offer) or {};statuses=product.get('statuses') or {}
    if not statuses.get('is_created') or product.get('is_archived') or product.get('is_autoarchived'):item['status']='等待商品创建完成或解除归档';continue
    desired=next(r for r in job['payload']['items'] if r['offer_id']==offer)
    from decimal import Decimal,InvalidOperation
    try:matching=Decimal(str(product.get('price')))==Decimal(desired['price']) and product.get('currency_code')==desired['currency_code']
    except InvalidOperation:matching=False
    if not matching or product.get('description_category_id')!=desired['description_category_id'] or product.get('type_id')!=desired['type_id']:item['status']='等待平台应用本次价格与类目';continue
    setting=job['stocks'][offer]
    if setting['warehouse_id'] not in shop_warehouses:item['status']='所选仓库已不在当前店铺返回列表，未写入库存';continue
    stock_rows.append({'offer_id':offer,'product_id':item['product_id'],'warehouse_id':setting['warehouse_id'],'stock':setting['stock']})
   if stock_rows:
    for row in stock_rows:job['items'][row['offer_id']]['stock_state']='intent'
    job.update(state='stock_intent',message='商品已创建，正在设置所选仓库库存');self._save(job)
    try:
     response=self.call_for(job['account_id'],'/v2/products/stocks',{'stocks':stock_rows});results={r.get('offer_id'):r for r in response.get('result',[])}
     for row in stock_rows:
      target=job['items'][row['offer_id']];result=results.get(row['offer_id'])
      if result and result.get('warehouse_id')==row['warehouse_id'] and result.get('updated') is True and not result.get('errors'):target.update(stock_state='done',stock_errors=[],status='库存已设置')
      elif result and result.get('updated') is False:target.update(stock_state='rejected',errors=result.get('errors') or [],stock_errors=result.get('errors') or [],status='库存未设置，稍后重试',stock_retry_at=time.time()+120)
      else:target.update(stock_state='uncertain',status='库存响应不完整，自动核对但不重复写入')
    except Rejected as exc:
     for row in stock_rows:job['items'][row['offer_id']].update(stock_state='rejected',stock_errors=[{'message':str(exc)}],status=str(exc),stock_retry_at=time.time()+120)
    except Exception:
     for row in stock_rows:job['items'][row['offer_id']].update(stock_state='uncertain',status='库存结果不确定，核对中，不自动重写')
    self._save(job)
   ready=[o for o in offers if ((products.get(o) or {}).get('statuses') or {}).get('is_created') and not (products.get(o) or {}).get('is_archived') and not (products.get(o) or {}).get('is_autoarchived')]
   stock_data,not_ready=self.read_created_stocks(ready,job['account_id']) if ready else ([],set())
   for offer,item in job['items'].items():
    setting=job['stocks'][offer];stock=next((r for r in stock_data if r.get('offer_id')==offer and r.get('warehouse_id')==setting['warehouse_id']),None)
    if item['stock_state'] in ('intent','uncertain') and stock and stock.get('free_stock')==setting['stock']:item.update(stock_state='done',stock_errors=[],status='库存写入已通过查询核对')
    product=products.get(offer) or {};visible=any(a.get('availability')=='AVAILABLE' for a in product.get('availabilities',[]))
    item['platform_status']=product.get('statuses') or {};item['current_free_stock']=stock.get('free_stock') if stock else None
    expected_item=next(r for r in job['payload']['items'] if r['offer_id']==offer)
    from decimal import Decimal,InvalidOperation
    try:price_matches=Decimal(str(product.get('price')))==Decimal(expected_item['price']) and product.get('currency_code')==expected_item['currency_code']
    except InvalidOperation:price_matches=False
    approved=(product.get('statuses') or {}).get('moderate_status')=='approved'
    item['on_sale']=bool(item['import_state']=='imported' and item['stock_state']=='done' and stock and stock.get('free_stock',0)>0 and visible and approved and price_matches and not product.get('is_archived') and not product.get('is_autoarchived') and (product.get('visibility_details') or {}).get('has_price'))
    if item['on_sale']:item['status']='平台返回可售'
    elif offer in not_ready:item['status']='库存已设置，等待平台库存查询服务就绪' if item['stock_state']=='done' else '商品库存服务尚未就绪，自动等待'
    elif item['stock_state']=='done':item['status']='库存已设置，等待平台审核/可售状态' if setting['stock'] else '库存为0，未可售'
    elif item['import_state']=='pending':item['status']='商品卡片已存在，等待本次导入结果' if item.get('card_exists') else '平台正在处理导入，等待创建完成'
   values=list(job['items'].values())
   job['writes_complete']=all(i['import_state']=='failed' or (i['import_state']=='imported' and i['stock_state']=='done') for i in values)
   if all(i.get('on_sale') for i in values):job.update(state='on_sale',message='整组商品已导入，所选仓库有库存，平台返回可售')
   elif all(i.get('on_sale') or (i['stock_state']=='done' and job['stocks'][o]['stock']==0 and i.get('current_free_stock')==0) for o,i in job['items'].items()):job.update(state='completed_zero_stock',message='流程完成；库存为0的变体不会可售')
   elif all(i['import_state']=='failed' for i in values):job.update(state='failed',message='整组导入失败，请修改错误项后重新提交')
   elif all(i['import_state']=='failed' or i.get('on_sale') for i in values):job.update(state='partial_failed',message='部分变体失败，已成功变体保留，详见逐条状态')
   elif any(i['import_state']=='pending' for i in values):job.update(state='importing',message='部分商品仍在创建中；已就绪变体继续库存流程，不重复提交')
   elif not_ready:job.update(state='waiting_creation',message='商品已受理，平台库存查询尚未就绪；自动等待重试，不重复提交')
   else:job.update(state='waiting_platform',message='自动跟进商品创建、库存及平台审核/可售状态')
   job['last_success_at']=time.time();job['retry_count']=0;self._save(job);return job
 def read_created_stocks(self,offers,merchant=None):
  merchant=merchant or self.account_getter()
  def fetch(batch):
   rows=[];cursor='';seen=set()
   for _ in range(100):
    response=self.call_for(merchant,'/v2/product/info/stocks-by-warehouse/fbs',{'offer_id':batch,'limit':1000,**({'cursor':cursor} if cursor else {})});rows.extend(response.get('products') or [])
    more=response.get('has_next',False)
    if more is False or more is None or str(more).casefold() in ('false','0',''):return rows
    cursor=response.get('cursor','')
    if not cursor or cursor in seen:raise ValueError('库存分页响应异常')
    seen.add(cursor)
   raise ValueError('库存分页超过限制')
  if not offers:return [],set()
  try:return fetch(offers),set()
  except Rejected as exc:
   if 'product creation incomplete' not in str(exc).casefold():raise
   if len(offers)==1:return [],set(offers)
  # The product index and stock index are eventually consistent. One not-yet-ready
  # item must not prevent the other variants from being queried.
  rows=[];waiting=set()
  for offer in offers:
   try:rows.extend(fetch([offer]))
   except Rejected as exc:
    if 'product creation incomplete' not in str(exc).casefold():raise
    waiting.add(offer)
  return rows,waiting
 @staticmethod
 def error_text(error):
  texts=error.get('texts') or {};detail=error.get('message') or error.get('description') or texts.get('message') or texts.get('description') or error.get('code','')
  attribute=str(error.get('attribute_id',''))
  if attribute=='22390':return '组合成类似产品：系列名称最多255字符，本版默认1。'+str(detail)
  if attribute=='23171':return '主题标签：须以#开头，字母/数字/下划线，标签用空格分隔。'+str(detail)
  return str(detail)
 def resume_account(self,merchant):
  with self.mutex:
   for job in self.jobs():
    if job.get('account_id')==merchant and job.get('state') not in TERMINAL:
     job['next_poll_at']=0;job['retry_count']=0;self._save(job)
  self.wake.set()
 def clear_group(self,offers):
  # Serialize against the worker: wait for any current request before archiving.
  # Only local follow-up is removed. Platform effects and assets are untouched.
  with self.mutex:
   merchant=self.account_getter()
   selected=[j for j in self.jobs() if j.get('account_id')==merchant and set(offers)&set(j.get('items',{}))]
   backup=self.root/'cleared';backup.mkdir(exist_ok=True)
   for job in selected:
    job.update(state='cancelled_followup',message='用户清空本地进度，停止后续跟进；平台商品未删除',cleared_at=time.time())
    write(backup/(job['id']+'.json'),job)
    (self.root/(job['id']+'.json')).unlink(missing_ok=True)
   return len(selected)
 def resolve_no_import(self,job_id):
  with self.mutex:
   job=read(self.root/(job_id+'.json'))
   if job['state']!='import_uncertain':raise ValueError('只有导入结果不确定的任务可人工解除')
   if self.account_getter()!=job['account_id']:raise ValueError('请先连接原店铺API')
   job.update(state='rejected',message='用户已在后台确认未受理，允许重新提交',manual_resolution_at=time.time());self._save(job)
   return job
 def retry_uncertain_stock(self,job_id):
  with self.mutex:
   job=read(self.root/(job_id+'.json'))
   if job['state']=='local_changed':raise ValueError('本地资料已变，不能直接重写旧库存')
   if self.account_getter()!=job['account_id']:raise ValueError('请先连接原店铺API')
   changed=False
   for item in job['items'].values():
    if item['stock_state'] in ('uncertain','intent'):item.update(stock_state='rejected',stock_retry_at=0,status='用户确认按预览目标重设库存');changed=True
   if not changed:raise ValueError('没有结果不确定的库存项')
   job['message']='已授权重新设置结果不确定的库存';self._save(job);self.wake.set()
   return job
 def cancel_followup(self,job_id):
  with self.mutex:
   job=read(self.root/(job_id+'.json'))
   if job['state'] in ('import_intent','import_uncertain') or any(i['stock_state'] in ('intent','uncertain') for i in job['items'].values()):raise ValueError('写入结果仍不确定，请先核对，不能以取消掩盖未知平台操作')
   job.update(state='cancelled_followup',message='已停止后续自动操作；已受理导入与已写库存不会撤销');self._save(job);return job
 def worker(self,stop):
  while not stop.is_set():
   for snapshot in self.jobs():
    if stop.is_set():return
    with self.mutex:
     path=self.root/(snapshot['id']+'.json')
     if not path.exists():continue
     job=read(path)
     if job['state'] in TERMINAL or job.get('next_poll_at',0)>time.time() or job['state']=='local_changed':continue
     try:self.step(job['id'])
     except Exception as exc:
      if not path.exists():continue
      current=read(path);current['message']='安全查询待重试：'+str(exc)[:180];current['retry_count']=current.get('retry_count',0)+1;self._save(current)
     if path.exists():
      current=read(path);current['next_poll_at']=time.time()+min(600,30*2**min(current.get('retry_count',0),4));self._save(current)
   self.wake.wait(15);self.wake.clear()
