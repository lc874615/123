"""Read local publication receipts to retire historical production blockers.
No platform requests and no task/file deletion. Explicit new work always wins.
"""
import json,os
from asset_state import pending

def completed_skus(store):
 merchant=os.environ.get('OZON_CLIENT_ID','').strip()
 if not merchant:return set()
 jobs=[]
 for path in (store.folder/'publications').glob('*.json'):
  try:
   job=json.loads(path.read_text(encoding='utf-8-sig'))
   if isinstance(job,dict) and str(job.get('account_id',''))==merchant:jobs.append(job)
  except (OSError,ValueError):continue
 latest={}
 for job in sorted(jobs,key=lambda j:j.get('created_at',0),reverse=True):
  items=job.get('items')
  if isinstance(items,dict):
   for sku,item in items.items():latest.setdefault(sku,item)
 result=set()
 for task in store.tasks:
  if not task.get('set_mode'):continue
  sku=task['sku']
  if not isinstance(latest.get(sku),dict) or latest[sku].get('on_sale') is not True:continue
  if task.get('state') not in ('saved','needs_attention','review'):continue
  if task.get('recollection_requested') or task.get('pause_requested') or task.get('copy_state')=='running':continue
  if task.get('copy_state')=='needs_attention' and task.get('copy_phase')=='generating':continue
  members=[t['sku'] for t in store.tasks if t.get('copy_leader',t['sku'])==task.get('copy_leader',sku)]
  if store.image_jobs.active(members):continue
  try:
   b=json.loads((store.folder/'products'/sku/'listing_bundle.json').read_text(encoding='utf-8-sig'))
   if pending(b) or b.get('recollection_pending'):continue
  except (OSError,ValueError):continue
  result.add(sku)
 return result

def optional_failure_skus(store):
 """Optional enrichment is not required production copy; keep its failure intact."""
 from listing_bundle import copy_complete
 from reference_prefill import recoverable_failure
 result=set()
 for task in store.tasks:
  if recoverable_failure(task):continue
  if task.get('state')!='saved' or task.get('copy_mode')!='attributes' or task.get('copy_state')!='needs_attention':continue
  if task.get('recollection_requested') or len(task.get('received_images') or [])!=8:continue
  members=[t['sku'] for t in store.tasks if t.get('copy_leader',t['sku'])==task.get('copy_leader',task['sku'])]
  if store.image_jobs.active(members):continue
  try:
   bundle=json.loads((store.folder/'products'/task['sku']/'listing_bundle.json').read_text(encoding='utf-8-sig'))
   if copy_complete(bundle.get('copy')) and not pending(bundle) and not bundle.get('recollection_pending'):result.add(task['sku'])
  except (OSError,ValueError):continue
 return result

def reconcile_idle_attributes(store):
 """An idle extension reports no owned request. Defer orphan enrichment, never resend."""
 changed=False
 for task in store.tasks:
  if task.get('state')=='saved' and task.get('copy_mode')=='attributes' and task.get('copy_state')=='running':
   task['copy_state']='needs_attention'
   task['attribute_deferred_reason']='插件当前没有执行任务，已保留属性读取上下文；可选属性读取暂缓，不重新发送'
   changed=True
 if changed:store.save()

def retire_legacy_attribute_save_error(store):
 """Retire this known optional save bug only after actual required assets pass audit."""
 import copy,time
 from asset_audit import inspect
 from listing_bundle import copy_complete
 from prefill_rules import VERSION,basis
 from reference_prefill import parameters,category_context
 changed=False
 for task in store.tasks:
  if task.get('state')!='saved' or task.get('copy_mode')!='attributes' or task.get('copy_state')!='needs_attention':continue
  known_error=any(e in str(task.get('message','')) for e in ("'list' object has no attribute 'get'","'str' object has no attribute 'get'","kQuotaBytes"))
  if not known_error and not task.get('quota_recovery_requested'):continue
  if task.get('recollection_requested') or task.get('pause_requested') or len(task.get('received_images') or [])!=8:continue
  members=[t['sku'] for t in store.tasks if t.get('copy_leader',t['sku'])==task.get('copy_leader',task['sku'])]
  if store.image_jobs.active(members):continue
  folder=store.folder/'products'/task['sku']
  try:
   bundle=json.loads((folder/'listing_bundle.json').read_text(encoding='utf-8-sig'))
   if not inspect(folder)['verified'] or not copy_complete(bundle.get('copy')) or pending(bundle) or bundle.get('recollection_pending'):continue
   history=folder/'attribute_failure_history.json';rows=json.loads(history.read_text()) if history.exists() else []
   if not isinstance(rows,list):continue
   rows.append({'retired_at':time.time(),'reason':'legacy_optional_save_bug','task':{k:copy.deepcopy(task.get(k)) for k in ('id','copy_state','copy_mode','copy_phase','message','copy_request_marker','attribute_context','resume_mode')}})
   from pricing_service import write
   write(history,rows)
   # This only marks mandatory copy ready; attribute enrichment stays explicitly deferred.
   task.update(copy_state='done',copy_phase='done',attribute_extract_state='deferred',attribute_deferred_reason='旧版属性保存异常已归档，已有图片和文案已核验，可继续预览上架',message='图片和共用文案已核验；可选属性补充暂缓，待预览提交')
   task.pop('copy_mode',None);task.pop('resume_mode',None)
   for member in store.tasks:
    if member['sku'] in members:
     fields,digest=category_context(store,member);member['attribute_attempt']={'version':VERSION,'basis':basis(parameters(store,member)),'schema_basis':digest}
   changed=True
  except (OSError,ValueError,TypeError,KeyError):continue
 if changed:store.save()
 return changed
