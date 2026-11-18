"""Read-only task summaries and search for the desktop dashboard."""
def task_bucket(task,jobs=(),stages=None):
 label=(stages or {}).get(task.get("id"))
 if label=="已上架":return "已上架"
 if label and label.startswith(("需处理","需修改","图片待核对","素材待","待确认类目","待补充定价资料","等待较久")):return "需处理"
 states=[task.get('state')]
 states.extend(j.get('state') for j in jobs if j.get('state') not in ('saved','cancelled') and any(t.get('sku')==task.get('sku') for t in j.get('targets',[])))
 if 'needs_attention' in states or task.get('copy_state')=='needs_attention':return '需处理'
 if any(s in ('claimed','sending','waiting','processing','committing') for s in states) or task.get('copy_state')=='running':return '制作中'
 if 'queued' in states:return '排队中'
 if task.get('state') in ('saved','approved','review'):return '素材已保存'
 return '其他'

def task_summary(tasks,jobs=(),stages=None):
 live=[t for t in tasks if t.get('state')!='cancelled'];buckets=[task_bucket(t,jobs,stages) for t in live]
 return {'total':len(live),'queued':buckets.count('排队中'),'running':buckets.count('制作中'),'attention':buckets.count('需处理')}

def matches(task,query='',mode='全部任务',jobs=(),stages=None):
 if mode!='全部任务' and task_bucket(task,jobs,stages)!=mode:return False
 p=task.get('variant_parameters') or {};text=' '.join(str(v or '') for v in (task.get('sku'),task.get('base_article'),task.get('copy_leader'),p.get('name'),p.get('color'),task.get('message'),(stages or {}).get(task.get('id')))).casefold()
 return all(word in text for word in query.casefold().split())


def partition_task_rows(groups):
 """Archive only final on-sale rows. Regeneration/review stages remain visible."""
 active={};published=[]
 for group,items in groups.items():
  for task,row in items:
   if row[-1]=='已上架':published.append((group,task,row))
   else:active.setdefault(group,[]).append((task,row))
 return active,published
