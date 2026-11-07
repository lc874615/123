"""Durable Ozon import -> selected rFBS warehouse stock -> platform status.
Only begin() is invoked by the explicit Submit button. Resume never replays an
unknown import or stock write. No API keys are persisted in receipts.
"""
import hashlib,json,os,secrets,threading,time,urllib.error,urllib.request
from pathlib import Path
from group_service import revision
from pricing_service import read,write
from listing_preview import export_preview

class Rejected(ValueError):pass
READ_PATHS={'/v2/warehouse/list','/v1/product/import/info','/v3/product/info/list','/v2/product/info/stocks-by-warehouse/fbs'}
WRITE_PATHS={'/v3/product/import','/v2/products/stocks'}
def account():
 if not os.environ.get('OZON_CLIENT_ID') or not os.environ.get('OZON_API_KEY'):raise ValueError('请连接具有商品和库存写入权限的Ozon API')
 return os.environ['OZON_CLIENT_ID']
def request(path,body):
 account()
 if path not in READ_PATHS|WRITE_PATHS:raise ValueError('接口不在本上架流程内')
 req=urllib.request.Request('https://api-seller.ozon.ru'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Client-Id':os.environ['OZON_CLIENT_ID'],'Api-Key':os.environ['OZON_API_KEY']})
 try:
  with urllib.request.urlopen(req,timeout=35) as response:value=json.load(response)
 except urllib.error.HTTPError as exc:
  if 400<=exc.code<500 and exc.code!=408:raise Rejected('Ozon拒绝请求（HTTP '+str(exc.code)+'），请检查权限或参数') from None
  raise ValueError('Ozon响应异常，写入结果需要核对') from None
 except (OSError,ValueError):raise ValueError('Ozon请求未完成，写入结果需要核对') from None
 if not isinstance(value,dict):raise ValueError('Ozon响应格式异常')
 return value

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
TERMINAL={'on_sale','completed_zero_stock','partial_failed','rejected','failed','superseded','cancelled_followup'}
class PublicationService:
 def __init__(self,data,store_lock,caller=request,account_getter=account):
  self.data=Path(data);self.root=self.data/'publications';self.root.mkdir(parents=True,exist_ok=True)
  self.lock=store_lock;self.mutex=threading.RLock();self.caller=caller;self.account_getter=account_getter;self.wake=threading.Event();self.status='尚未提交'
 def warehouses(self):
  result=[];cursor='';seen=set()
  for _ in range(100):
   response=self.caller('/v2/warehouse/list',{'limit':200,**({'cursor':cursor} if cursor else {})})
   rows=response.get('warehouses')
   if not isinstance(rows,list):raise ValueError('仓库列表响应异常，未选择任何仓库')
   result.extend(r for r in rows if r.get('is_rfbs') is True and r.get('status')=='created' and not r.get('is_karantin') and type(r.get('warehouse_id')) is int)
   if not response.get('has_next'):return result
   cursor=response.get('cursor','')
   if not cursor or cursor in seen:raise ValueError('仓库分页未完整读取，请重试')
   seen.add(cursor)
  raise ValueError('仓库列表超过分页限制')
 def jobs(self):
  values=[]
  for path in self.root.glob('*.json'):
   try:
    job=read(path)
    if isinstance(job,dict) and job.get('id'):values.append(job)
   except (OSError,ValueError):continue
  return sorted(values,key=lambda j:j.get('created_at',0),reverse=True)
 def active(self,offers):
  return next((j for j in self.jobs() if j.get('state') not in TERMINAL and not j.get('writes_complete') and set(offers)&set(j.get('items',{}))),None)
 def _save(self,job):job['updated_at']=time.time();write(self.root/(job['id']+'.json'),job);self.status=job.get('message',job['state'])
 def begin(self,coordinator,expected):
  with self.mutex:
   merchant=self.account_getter()
   for path in coordinator.paths:coordinator.attributes.refresh(path,force=True)
   coordinator.pricing.calculate_all()
   warehouses={r['warehouse_id']:r for r in self.warehouses()}
   with self.lock:
    bundles=[read(p) for p in coordinator.paths]
    if revision(bundles)!=expected:raise ValueError('预览已变化，请核对最新参数、价格和库存后再次提交')
    offers=[b['sku'] for b in bundles];existing=self.active(offers)
    if existing:return existing
    stocks={}
    for b in bundles:
     setting=b.get('fulfillment') or {};wid=setting.get('warehouse_id')
     if wid not in warehouses or setting.get('account_id')!=merchant:raise ValueError(b['sku']+'：请重新选择本店铺当前可用的rFBS仓库')
     raw=str((b.get('variant_parameters') or {}).get('stock','')).strip()
     if not raw.isdigit() or int(raw)>2147483647:raise ValueError(b['sku']+'：库存必须是有效的非负整数')
     stocks[b['sku']]={'warehouse_id':wid,'warehouse_name':warehouses[wid]['name'],'stock':int(raw),'stock_revision':b.get('stock_revision','initial')}
    # Clicking Submit approves the exact visible, validated group, not hidden stale values.
   settings=[b.get('export_settings') or {} for b in bundles]
   for setting in settings:
    if setting.get('currency_code')!='CNY' or not setting.get('currency_confirmed'):raise ValueError('请先确认店铺币种为CNY')
   vats={s.get('vat') for s in settings}
   if any(v not in ('0','0.05','0.07','0.1','0.2','0.22') for v in vats):raise ValueError('请先填写各变体实际税率')
   from listing_preview import attribute_errors
   with self.lock:
    latest=[read(p) for p in coordinator.paths]
    if revision(latest)!=expected:raise ValueError('资料已变化，请刷新后提交')
    for b in latest:
     errors=attribute_errors(b)
     if errors:raise ValueError(b['sku']+'：'+'；'.join(errors))
     if not (b.get('category') or {}).get('confirmed'):raise ValueError('类目尚未确认')
    from attribute_service import review_hash
    for path,b in zip(coordinator.paths,latest):
     b['attribute_draft'].update(confirmed=True,confirmed_values_hash=review_hash(b['attribute_draft']))
     b['pricing_confirmed_fingerprint']=b.get('pricing_fingerprint');b['pricing_confirmed_price']=b.get('price_cny');write(path,b)
   report=export_preview([p.parent for p in coordinator.paths],self.root/'staging',self.lock)
   if not report['ready']:raise ValueError('；'.join(r['offer_id']+'：'+'；'.join(r['missing']) for r in report['items'] if not r['ready']))
   payload=read(self.root/'staging'/'ozon_import_preview.json')
   with self.lock:
    if any(hashlib.sha256(Path(r['bundle_file']).read_bytes()).hexdigest()!=r['sha256'] for r in report['source_checksums']):raise ValueError('校验期间资料已更新，请刷新后提交')
    sealed_revision=revision([read(p) for p in coordinator.paths])
   plan_hash=digest([merchant,payload,stocks])
   for previous in self.jobs():
    if previous.get('plan_hash')==plan_hash and (previous.get('state') in ('on_sale','completed_zero_stock') or previous.get('writes_complete')):
     previous['source_revision']=sealed_revision;self._save(previous);return self.step(previous['id'],refresh=True)
   job={'id':secrets.token_hex(12),'account_id':merchant,'created_at':time.time(),'state':'prepared','plan_hash':plan_hash,'payload':payload,'source_paths':[str(p) for p in coordinator.paths],'source_revision':sealed_revision,'stocks':stocks,'items':{},'message':'整组资料已冻结，准备提交'}
   history=[j for j in self.jobs() if j.get('account_id')==merchant]
   for item in payload['items']:
    offer=item['offer_id'];item_hash=digest(item);stock_sig=digest([merchant,stocks[offer]])
    prior_item=next((j['items'][offer] for j in history if offer in j.get('items',{}) and j['items'][offer].get('item_hash')==item_hash and j['items'][offer].get('import_state')=='imported'),None)
    prior_stock=next((j['items'][offer] for j in history if offer in j.get('items',{}) and j['items'][offer].get('stock_signature')==stock_sig and j['items'][offer].get('stock_state')=='done'),None)
    job['items'][offer]={'item_hash':item_hash,'stock_signature':stock_sig,'import_state':'imported' if prior_item else 'pending','product_id':prior_item.get('product_id') if prior_item else None,'stock_state':'done' if prior_stock else 'pending','status':'等待提交','errors':[]}
   self._save(job)
   pending=[i for i in payload['items'] if job['items'][i['offer_id']]['import_state']!='imported']
   if pending:
    job.update(state='import_intent',message='正在提交商品，勿重复操作');self._save(job)
    try:
     result=self.caller('/v3/product/import',{'items':pending});task_id=(result.get('result') or {}).get('task_id')
     if type(task_id) is not int or task_id<=0:raise ValueError('未返回明确任务ID')
     job.update(task_id=task_id,state='importing',message='商品已受理，自动查询导入状态')
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
   for item in job['items'].values():
    if item.get('stock_state')=='intent':item.update(stock_state='uncertain',status='重启后库存结果待核对，不自动重写')
   if job.get('task_id'):
    response=self.caller('/v1/product/import/info',{'task_id':job['task_id']})
    for row in (response.get('result') or {}).get('items',[]):
     offer=row.get('offer_id')
     if offer not in job['items']:continue
     target=job['items'][offer];errors=row.get('errors') or []
     if row.get('status') in ('failed','error') or any(e.get('level','ERROR').upper()=='ERROR' for e in errors):target.update(import_state='failed',errors=errors,status='导入失败')
     elif row.get('status')=='imported' and row.get('product_id'):target.update(import_state='imported',product_id=row['product_id'],errors=[],status='已导入')
   current=[read(p) for p in job['source_paths']]
   if revision(current)!=job['source_revision']:
    job.update(state='superseded' if job.get('writes_complete') else 'local_changed',message='本地资料已有新版本；原写入结果保留，旧任务停止后续写入');self._save(job);return job
   eligible={r['warehouse_id']:r for r in self.warehouses()};offers=list(job['items'])
   info=self.caller('/v3/product/info/list',{'offer_id':offers});products={r['offer_id']:r for r in info.get('items',[])}
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
    if setting['warehouse_id'] not in eligible:item['status']='所选仓库已不可用，未写入库存';continue
    stock_rows.append({'offer_id':offer,'product_id':item['product_id'],'warehouse_id':setting['warehouse_id'],'stock':setting['stock']})
   if stock_rows:
    for row in stock_rows:job['items'][row['offer_id']]['stock_state']='intent'
    job.update(state='stock_intent',message='商品已创建，正在设置所选仓库库存');self._save(job)
    try:
     response=self.caller('/v2/products/stocks',{'stocks':stock_rows});results={r.get('offer_id'):r for r in response.get('result',[])}
     for row in stock_rows:
      target=job['items'][row['offer_id']];result=results.get(row['offer_id'])
      if result and result.get('warehouse_id')==row['warehouse_id'] and result.get('updated') is True and not result.get('errors'):target.update(stock_state='done',status='库存已设置')
      elif result and result.get('updated') is False:target.update(stock_state='rejected',errors=result.get('errors') or [],status='库存未设置，稍后重试',stock_retry_at=time.time()+120)
      else:target.update(stock_state='uncertain',status='库存响应不完整，自动核对但不重复写入')
    except Rejected as exc:
     for row in stock_rows:job['items'][row['offer_id']].update(stock_state='rejected',status=str(exc),stock_retry_at=time.time()+120)
    except Exception:
     for row in stock_rows:job['items'][row['offer_id']].update(stock_state='uncertain',status='库存结果不确定，核对中，不自动重写')
    self._save(job)
   response=self.caller('/v2/product/info/stocks-by-warehouse/fbs',{'offer_id':offers,'limit':1000});stock_data=list(response.get('products') or []);cursor=response.get('cursor');seen=set()
   while response.get('has_next'):
    if not cursor or cursor in seen:raise ValueError('库存分页响应异常')
    seen.add(cursor);response=self.caller('/v2/product/info/stocks-by-warehouse/fbs',{'offer_id':offers,'limit':1000,'cursor':cursor});stock_data.extend(response.get('products') or []);cursor=response.get('cursor')
   for offer,item in job['items'].items():
    setting=job['stocks'][offer];stock=next((r for r in stock_data if r.get('offer_id')==offer and r.get('warehouse_id')==setting['warehouse_id']),None)
    if item['stock_state'] in ('intent','uncertain') and stock and stock.get('free_stock')==setting['stock']:item.update(stock_state='done',status='库存写入已通过查询核对')
    product=products.get(offer) or {};visible=any(a.get('availability')=='AVAILABLE' for a in product.get('availabilities',[]))
    item['platform_status']=product.get('statuses') or {};item['current_free_stock']=stock.get('free_stock') if stock else None
    expected_item=next(r for r in job['payload']['items'] if r['offer_id']==offer)
    from decimal import Decimal,InvalidOperation
    try:price_matches=Decimal(str(product.get('price')))==Decimal(expected_item['price']) and product.get('currency_code')==expected_item['currency_code']
    except InvalidOperation:price_matches=False
    approved=(product.get('statuses') or {}).get('moderate_status')=='approved'
    item['on_sale']=bool(item['import_state']=='imported' and item['stock_state']=='done' and stock and stock.get('free_stock',0)>0 and visible and approved and price_matches and not product.get('is_archived') and not product.get('is_autoarchived') and (product.get('visibility_details') or {}).get('has_price'))
    if item['on_sale']:item['status']='平台返回可售'
    elif item['stock_state']=='done':item['status']='库存已设置，等待平台审核/可售状态' if setting['stock'] else '库存为0，未可售'
   values=list(job['items'].values())
   job['writes_complete']=all(i['import_state']=='failed' or (i['import_state']=='imported' and i['stock_state']=='done') for i in values)
   if all(i.get('on_sale') for i in values):job.update(state='on_sale',message='整组商品已导入，所选仓库有库存，平台返回可售')
   elif all(i.get('on_sale') or (i['stock_state']=='done' and job['stocks'][o]['stock']==0 and i.get('current_free_stock')==0) for o,i in job['items'].items()):job.update(state='completed_zero_stock',message='流程完成；库存为0的变体不会可售')
   elif all(i['import_state']=='failed' for i in values):job.update(state='failed',message='整组导入失败，请修改错误项后重新提交')
   elif all(i['import_state']=='failed' or i.get('on_sale') for i in values):job.update(state='partial_failed',message='部分变体失败，已成功变体保留，详见逐条状态')
   else:job.update(state='waiting_platform',message='自动跟进导入、库存及平台可售状态')
   self._save(job);return job
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
   for job in self.jobs():
    if stop.is_set():return
    if job['state'] in TERMINAL or job.get('next_poll_at',0)>time.time():continue
    try:
     if job['state']=='local_changed':continue
     self.step(job['id'])
    except Exception as exc:
     current=read(self.root/(job['id']+'.json'));current['message']='查询待重试：'+str(exc)[:180];self._save(current)
    current=read(self.root/(job['id']+'.json'));current['next_poll_at']=time.time()+30;self._save(current)
   self.wake.wait(15);self.wake.clear()
