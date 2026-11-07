"""Stable model per group; shared galleries and copy, distinct offer IDs."""
import json,secrets,shutil
from pathlib import Path

def configure(tasks,base):
 group=sorted([t for t in tasks if t.get('base_article')==base],key=lambda t:t['variant_index'])
 model='M-'+secrets.token_hex(6).upper()
 all_facts='\n'.join(t['sku']+'：'+t['facts'] for t in group)
 for i,t in enumerate(group):
  t.update(model=model,group_facts=all_facts,copy_leader=group[0]['sku'])
  if i:
   t['expected_images']=1;t['gallery_source']=group[0]['sku']
   t['prompt']='仅生成一张独立商品主图，3:4竖版，自然俄文，准确展示本变体颜色、规格和销售数量。严禁使用其他变体外观。当前变体：'+t['facts']
  else:
   t['expected_images']=8;t['prompt']+='。同组全部变体资料：'+all_facts+'。第2至8张为全组共用详情图：不同颜色和尺寸须标明变体对应关系，无法兼容的细节不要误标成全组通用。'
 return group

def reuse_gallery(folder,task):
 folder=Path(folder);source=folder.parent/task['gallery_source'];rows=json.loads((source/'image_manifest.json').read_text(encoding='utf-8-sig'))
 for row in rows[1:]:
  src=source/'images'/Path(row['file'].replace('\\','/')).name;dst=folder/'images'/src.name;shutil.copy2(src,dst)
  task['received_images'].append({**row,'file':str(dst),'shared_from':task['gallery_source']})
