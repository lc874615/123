"""Back up only identifiable automation drafts before clearing the active composer."""
import hashlib,re,secrets,time
from pathlib import Path
from pricing_service import read,write

def backup(store,identifier,text,attachments):
 if not isinstance(text,str) or not 0<len(text)<=120000:raise ValueError('输入框内容为空或过长，未自动清空')
 if identifier.startswith('copy:'):
  owner=next((t for t in store.tasks if t['sku']==identifier[5:]),None)
  if owner is None:raise ValueError('文案任务不存在，未清空')
 else:owner=store.find(identifier)
 sku=owner['sku'];known={owner['id'],owner.get('restarted_from')};copy_markers={owner.get('copy_request_marker')}
 root_owner=next((t for t in store.tasks if t['sku']==sku),owner);group=root_owner.get('copy_leader',sku)
 def related(task):
  if task.get('sku')==sku or any(t.get('sku')==sku for t in task.get('targets',[])):return True
  return task.get('copy_leader',task.get('sku'))==group and task.get('state') in ('saved','cancelled','approved','needs_attention','queued')
 for task in store.tasks+store.image_jobs.jobs:
  if related(task):
   known.add(task['id']);known.add(task.get('restarted_from'));copy_markers.add(task.get('copy_request_marker'))
 for path in sorted((store.folder/'queue_restarts').glob('*/queue_task.json'),reverse=True)[:30]:
  row=read(path)
  if related(row):known.add(row.get('id'));copy_markers.add(row.get('copy_request_marker'))
 markers=re.findall(r'【OZON_(TASK|COPY):([^】\r\n]+)】',text)
 allowed=bool(markers) and all(value in known if kind=='TASK' else '【OZON_COPY:'+value+'】' in copy_markers for kind,value in markers)
 exact_previous=owner.get('previous_unsent_copy_prompt_hash')==hashlib.sha256(text.encode()).hexdigest()
 normalize=lambda value:str(value or '').replace('\r\n','\n').strip()
 exact_current=bool(owner.get('prompt')) and normalize(text)==normalize(owner['prompt'])
 if not allowed and not exact_previous and not exact_current:raise ValueError('输入框不是可确认的本任务遗留草稿，已保留原内容；不会清空手写内容')
 root=store.folder/'composer_backups'/hashlib.sha256(identifier.encode()).hexdigest();root.mkdir(parents=True,exist_ok=True)
 path=root/(str(time.time_ns())+'-'+secrets.token_hex(3)+'.json')
 write(path,{'task_id':identifier,'sku':sku,'text':text,'attachment_labels':[str(v)[:200] for v in (attachments or [])][:20],'references':owner.get('references') or [],'created_at':time.time()})
 return {'ok':True,'backup':str(path)}
