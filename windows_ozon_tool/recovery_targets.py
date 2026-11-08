"""Read-only recovery identities from this SKU's own validated task backups."""
import json
from pathlib import Path
from asset_state import differs,VISUAL

def markers(folder,task):
 result=['【OZON_TASK:'+str(task['id'])+'】'];paths=[]
 for name in ('recovery_backups','auto_recovery','regeneration_backups'):
  paths.extend((Path(folder)/name).glob('*/task.json'))
 paths.sort(key=lambda p:p.stat().st_mtime_ns,reverse=True)
 for path in paths:
  try:old=json.loads(path.read_text(encoding='utf-8-sig'))
  except (OSError,ValueError):continue
  if not isinstance(old,dict) or old.get('sku')!=task['sku'] or not isinstance(old.get('id'),str) or not old['id']:continue
  if any(c in old['id'] for c in ('【','】','\n','\r')):continue
  if bool(old.get('gallery_source'))!=bool(task.get('gallery_source')):continue
  a=old.get('variant_parameters') or {};b=task.get('variant_parameters') or {}
  if not isinstance(a,dict) or not isinstance(b,dict):continue
  if a or b:
   if differs(a,b,VISUAL):continue
  elif not old.get('facts') or old.get('facts')!=task.get('facts'):continue
  before={r.get('sku'):r.get('variant_parameters') or {} for r in old.get('group_variants') or [] if isinstance(r,dict)}
  after={r.get('sku'):r.get('variant_parameters') or {} for r in task.get('group_variants') or [] if isinstance(r,dict)}
  if not task.get('gallery_source') and (before or after) and (set(before)!=set(after) or any(differs(before[k],after[k],VISUAL) for k in before)):continue
  marker='【OZON_TASK:'+old['id']+'】'
  if marker not in result:result.append(marker)
  if len(result)>=16:break
 return result
