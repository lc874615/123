"""Reject an uploaded reference copied into the generated-image output."""
import hashlib,io
from pathlib import Path
from PIL import Image,ImageOps

def pixels(data):
 with Image.open(io.BytesIO(data)) as image:
  return ImageOps.exif_transpose(image).convert('RGB').resize((32,32),Image.Resampling.LANCZOS).tobytes()

def reject_reference(data,references):
 digest=hashlib.sha256(data).digest();sample=None
 for row in references:
  path=Path(row['path'])
  if not path.is_file():continue
  original=path.read_bytes()
  if hashlib.sha256(original).digest()==digest:raise ValueError('采集到上传参考图，已拒绝保存；仅允许助手新生成图片')
  if sample is None:sample=pixels(data)
  reference=pixels(original)
  if sum(abs(a-b) for a,b in zip(sample,reference))/len(sample)<=0.5:
   raise ValueError('采集图片与上传参考图相同或仅缩放转码，已拒绝保存')
