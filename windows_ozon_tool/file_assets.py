"""Read numbered image assets from individual downloaded files."""
import base64,hashlib,io
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
 if extension not in ('jpg','jpeg','png','webp'):raise ValueError('只支持独立图片，不读取压缩包')
 return validate_images([data],1,references)
