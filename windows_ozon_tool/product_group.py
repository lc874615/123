"""Stable model per group; shared galleries and copy, distinct offer IDs."""
import json,secrets,shutil,hashlib
from pathlib import Path

def configure(tasks,base):
 group=sorted([t for t in tasks if t.get('base_article')==base],key=lambda t:t['variant_index'])
 model='M-'+secrets.token_hex(6).upper()
 all_facts='\n'.join(t['sku']+'：'+t['facts'] for t in group)
 for i,t in enumerate(group):
  t.update(model=model,group_facts=all_facts,group_variants=[{'sku':r['sku'],'variant_parameters':r.get('variant_parameters',{}),'facts':r['facts']} for r in group],copy_leader=group[0]['sku'])
  if i:
   t['expected_images']=1;t['gallery_source']=group[0]['sku']
  else:
   t['expected_images']=8
  from image_prompts import generation_prompt
  t['prompt']=generation_prompt(t['facts'],all_facts,t['expected_images'])
 return group

def reuse_gallery(folder,task):
 folder=Path(folder);source=folder.parent/task['gallery_source'];rows=json.loads((source/'image_manifest.json').read_text(encoding='utf-8-sig'))
 if len(rows)!=8 or [r['order'] for r in rows]!=list(range(1,9)):raise ValueError('首变体详情清单不完整')
 prepared=[]
 for row in rows[1:]:
  src=source/'images'/Path(row['file'].replace('\\','/')).name;dst=folder/'images'/src.name
  if hashlib.sha256(src.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('共用详情已变化，请重新审核')
  prepared.append((row,src,dst))
 # Validate every source before copying or changing the task's saved-image list.
 for row,src,dst in prepared:shutil.copy2(src,dst)
 task['received_images'].extend({**row,'file':str(dst),'shared_from':task['gallery_source']} for row,src,dst in prepared)
