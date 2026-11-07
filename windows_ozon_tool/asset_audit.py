"""Read-only checks of the images actually present in a product directory."""
import hashlib,json
from pathlib import Path

def inspect(folder):
 folder=Path(folder)
 try:
  rows=json.loads((folder/'image_manifest.json').read_text(encoding='utf-8-sig'))
  if not isinstance(rows,list) or len(rows)!=8 or [r.get('order') for r in rows]!=list(range(1,9)):return {'verified':False,'reason':'图片清单顺序或数量不完整'}
  if rows[0].get('role')!='primary' or any(r.get('role')!='gallery' for r in rows[1:]):return {'verified':False,'reason':'主图或详情图角色异常'}
  hashes=[]
  for row in rows:
   name=Path(row['file'].replace('\\','/')).name;path=folder/'images'/name
   if not path.is_file():return {'verified':False,'reason':'图片文件缺失'}
   digest=hashlib.sha256(path.read_bytes()).hexdigest()
   if digest!=row['sha256']:return {'verified':False,'reason':'图片文件与清单校验值不一致'}
   hashes.append(digest)
  return {'verified':True,'primary_order':1,'primary_hash':hashes[0],'gallery_hashes':hashes[1:]}
 except (OSError,ValueError,TypeError,KeyError):return {'verified':False,'reason':'无法读取完整图片清单'}
