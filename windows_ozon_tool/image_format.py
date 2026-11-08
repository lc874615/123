"""Normalize WEBP at ingestion; retain original bytes for recovery."""
import io,hashlib
from pathlib import Path
from PIL import Image,ImageOps

def normalize(raw,backup_folder=None):
 with Image.open(io.BytesIO(raw)) as source:
  if source.format!='WEBP':return raw,{'PNG':'png','JPEG':'jpg'}.get(source.format,'')
  if backup_folder is not None:
   folder=Path(backup_folder);folder.mkdir(parents=True,exist_ok=True);target=folder/(hashlib.sha256(raw).hexdigest()+'.webp')
   if not target.exists():target.write_bytes(raw)
  image=ImageOps.exif_transpose(source).convert('RGB');output=io.BytesIO();image.save(output,'JPEG',quality=95,subsampling=0);return output.getvalue(),'jpg'
