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
 result=set()
 for task in store.tasks:
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
