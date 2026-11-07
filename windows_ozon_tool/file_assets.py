"""Read numbered image assets without extracting untrusted archive paths."""
import base64,hashlib,io,re,zipfile
from pathlib import PurePosixPath
from PIL import Image
from asset_guard import reject_reference
LIMIT=20*1024*1024

def validate_images(images,expected,references):
 if len(images)!=expected:raise ValueError(f'文件中需要{expected}张独立图片，实际{len(images)}张')
 seen=set()
 for data in images:
  if len(data)>LIMIT:raise ValueError('单张图片超过20MB')
  with Image.open(io.BytesIO(data)) as image:
   image.verify();fmt=image.format
  with Image.open(io.BytesIO(data)) as image:
   if min(image.size)<512:raise ValueError('下载图片分辨率不足')
  if fmt not in ('PNG','JPEG','WEBP'):raise ValueError('下载文件不是支持的商品图片')
  reject_reference(data,references)
  digest=hashlib.sha256(data).hexdigest()
  if digest in seen:raise ValueError('下载文件包含重复图片')
  seen.add(digest)
 return [base64.b64encode(data).decode() for data in images]

def decode(data,extension,expected,references):
 if extension!='zip':return validate_images([data],1,references)
 images=[]
 with zipfile.ZipFile(io.BytesIO(data)) as archive:
  entries=archive.infolist()
  if len(entries)>64:raise ValueError('压缩包文件过多')
  for item in entries:
   path=PurePosixPath(item.filename)
   if path.is_absolute() or '..' in path.parts or '\\' in item.filename or ':' in item.filename or (item.external_attr>>16)&0o170000==0o120000:raise ValueError('压缩包包含不安全路径')
   if item.is_dir() or path.suffix.lower() not in ('.jpg','.jpeg','.png','.webp'):continue
   if item.file_size>LIMIT:raise ValueError('压缩包中的图片过大')
   match=re.match(r'^0*([1-8])(?:[_ .-]|$)',path.stem)
   if not match:raise ValueError('压缩包图片须有01至08顺序编号，避免误认主图')
   images.append((int(match.group(1)),item))
  if len(images)!=expected or sorted(n for n,_ in images)!=list(range(1,expected+1)):raise ValueError('压缩包图片编号或数量不完整')
  return validate_images([archive.read(item) for _,item in sorted(images,key=lambda x:x[0])],expected,references)
