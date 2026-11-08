"""Platform-issued product barcodes, persisted before writes and confirmed by reads.
No locally invented EANs. Uncertain or accepted writes are never regenerated.
"""
import time
from publication_service import Rejected

def barcodes(product):
 values=product.get('barcodes') or []
 if not isinstance(values,list):values=[]
 if product.get('barcode'):values=values+[product['barcode']]
 return list(dict.fromkeys(v.strip() for v in values if isinstance(v,str) and v.strip()))

def product_id(value):
 if isinstance(value,str) and value.isdigit():value=int(value)
 return value if type(value) is int and value>0 else None

def history(service):
 from pricing_service import read
 rows=service.jobs()
 for path in (service.root/'cleared').glob('*.json'):
  try:
   row=read(path)
   if isinstance(row,dict):rows.append(row)
  except (OSError,ValueError):continue
 return rows

def sync(service,job,products):
 records=history(service);candidates=[]
 for offer,item in job['items'].items():
  if item['import_state']!='imported':continue
  product=products.get(offer) or {};pid=product_id(product.get('id'))
  if not pid or pid!=product_id(item.get('product_id')) or not (product.get('statuses') or {}).get('is_created'):
   item.setdefault('barcode_state','waiting_creation');item['barcode_status']='等待商品创建完成，再核对条形码';continue
  if item.get('barcode_product_id')!=pid:
   item.update(barcode_product_id=pid,barcode_state='pending',barcodes=[],barcode_errors=[])
   prior=[r['items'][offer] for r in records if r.get('id')!=job['id'] and r.get('account_id')==job['account_id'] and offer in r.get('items',{}) and r['items'][offer].get('barcode_product_id')==pid and r['items'][offer].get('barcode_state') in ('intent','uncertain','accepted','done')]
   if prior:item.update(barcode_state='uncertain',barcode_status='已有条形码申请记录，自动核对，不重复生成')
  values=barcodes(product)
  if values:
   item.update(barcode_state='done',barcodes=values,barcode_errors=[],barcode_status='条形码已确认');continue
  state=item.get('barcode_state','pending')
  if state=='done':
   item.update(barcode_state='uncertain',barcode_status='平台暂未返回已有条形码，自动复查，不重复生成');continue
  if state=='intent':item.update(barcode_state='uncertain',barcode_status='条形码请求结果待核对，自动查询，不重复生成')
  if item['barcode_state'] in ('accepted','uncertain'):continue
  if product.get('is_archived') or product.get('is_autoarchived'):
   item['barcode_status']='商品已归档，等待解除后生成条形码';continue
  if item.get('barcode_retry_at',0)>time.time():continue
  candidates.append((offer,pid))
 service._save(job)
 # Limit to one 100-product batch per pass and space writes across persisted jobs.
 last=max((j.get('barcode_attempt_at',0) for j in records if j.get('account_id')==job['account_id']),default=0)
 if candidates and time.time()-last<3.2:
  for offer,pid in candidates:job['items'][offer]['barcode_status']='条形码生成排队中，遵守平台调用间隔'
  service._save(job);return
 batch=candidates[:100]
 if not batch:return
 for offer,pid in batch:job['items'][offer].update(barcode_state='intent',barcode_status='正在请求Ozon生成条形码')
 job.update(barcode_attempt_at=time.time(),message='正在为缺少条形码的变体申请Ozon条形码');service._save(job)
 try:
  response=service.call_for(job['account_id'],'/v1/barcode/generate',{'product_ids':[pid for offer,pid in batch]})
  errors=response.get('errors')
  if not isinstance(errors,list) or any(not isinstance(e,dict) or product_id(e.get('product_id')) not in [pid for offer,pid in batch] for e in errors):raise ValueError('条形码生成回执不完整')
  for offer,pid in batch:
   item=job['items'][offer];failure=[e for e in errors if product_id(e.get('product_id'))==pid]
   if failure:item.update(barcode_state='rejected',barcode_errors=failure,barcode_retry_at=time.time()+120,barcode_status='条形码生成被拒绝，详见平台错误；稍后复查')
   else:item.update(barcode_state='accepted',barcode_errors=[],barcode_status='条形码生成已受理，等待平台回填')
 except Rejected as exc:
  for offer,pid in batch:job['items'][offer].update(barcode_state='rejected',barcode_errors=[{'message':str(exc)}],barcode_retry_at=time.time()+120,barcode_status='条形码生成被拒绝：'+str(exc)+('；请为API密钥开启Barcode权限' if '403' in str(exc) else ''))
 except Exception:
  for offer,pid in batch:job['items'][offer].update(barcode_state='uncertain',barcode_status='条形码生成结果不确定，自动查询，不重复申请')
 service._save(job)
 # A successful HTTP reply is not proof of a barcode; confirm its actual value.
 try:
  fresh=service.call_for(job['account_id'],'/v3/product/info/list',{'offer_id':[offer for offer,pid in batch]})
  rows={r.get('offer_id'):r for r in fresh.get('items',[]) if isinstance(r,dict)}
  for offer,pid in batch:
   row=rows.get(offer) or {};values=barcodes(row)
   if product_id(row.get('id'))==pid and values:job['items'][offer].update(barcode_state='done',barcodes=values,barcode_errors=[],barcode_status='条形码已确认')
 except Exception:pass
 service._save(job)

def migrate(service):
 """Resume pre-barcode successful receipts without replaying import/stock writes."""
 for job in service.jobs():
  if job.get('state') in ('on_sale','completed_zero_stock','partial_failed') and any(not i.get('barcode_state') for i in job.get('items',{}).values() if i.get('import_state')=='imported'):
   job.update(state='waiting_platform',writes_complete=False,message='原上架记录保留，自动补查并生成缺失条形码')
   for item in job['items'].values():item['on_sale']=False
   service._save(job)
