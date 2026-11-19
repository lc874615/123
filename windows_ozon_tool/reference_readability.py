"""Lossless input-only detail regions, derived exclusively from verified originals.
Full originals always remain present; crops introduce no product facts.
"""
import hashlib,json,math
from pathlib import Path
from PIL import Image,ImageOps

def detail_regions(store,task,references,budget):
 candidates=[]
 for ref in references:
  if ref.get('purpose') not in ('shared_detail','shared_information','shared_gallery'):continue
  with Image.open(ref['path']) as image:
   w,h=image.size
   if image.getexif().get(274) in (5,6,7,8):w,h=h,w
  if w<500 or h<1600 or h/w<1.8:continue
  count=min(4,max(2,math.ceil(h/(w*1.45))));span=math.ceil(h/count);overlap=max(24,round(span*.06));regions=[]
  for i in range(count):
   regions.append((0,max(0,i*span-overlap),w,min(h,(i+1)*span+overlap)))
  candidates.append((ref,regions))
 result=[];folder=store.folder/'products'/task['sku']/'reference_regions'
 # Round-robin ensures one very long original cannot consume all region slots.
 for turn in range(4):
  for ref,regions in candidates:
   if len(result)>=budget:return result
   if turn>=len(regions):continue
   box=regions[turn];raw=Path(ref['path']).read_bytes();source_hash=hashlib.sha256(raw).hexdigest()
   if source_hash!=ref.get('reference_sha256'):raise ValueError('原始资料在读取区域期间变化，未使用旧参考')
   identity=hashlib.sha256(json.dumps([source_hash,box]).encode()).hexdigest();folder.mkdir(parents=True,exist_ok=True);path=folder/(identity+'.png')
   with Image.open(ref['path']) as original:
    normalized=ImageOps.exif_transpose(original)
    if normalized.mode not in ('RGB','RGBA','L','LA','P'):normalized=normalized.convert('RGB')
    crop=normalized.crop(box);crop.save(path,'PNG');crop.close()
   if path.stat().st_size>3*1024*1024:continue
   label=f'第{turn+1}区域（共{len(regions)}区）'
   result.append({'path':str(path),'name':str(ref.get('sku') or task['sku'])+'_region_'+identity[:12]+'.png','sku':ref.get('sku'),'purpose':ref['purpose'],'mime':'image/png','reference_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_path':str(ref['path']),'source_sha256':source_hash,'source_sku':Path(ref['path']).resolve().relative_to((store.folder/'products').resolve()).parts[0],'source_name':ref.get('name'),'region':label,'crop_box':list(box)})
 return result
