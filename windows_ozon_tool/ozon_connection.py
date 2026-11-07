"""Optional per-Windows-user Ozon API credentials; no plaintext fallback."""
import json,os
from pathlib import Path
from hosting_credentials import protect

def save(data,client_id,api_key,remember=False):
 client_id=client_id.strip();api_key=api_key.strip()
 if not client_id or not api_key:raise ValueError('请填写Client-Id和Api-Key')
 path=Path(data)/'ozon_api.dpapi'
 if remember:
  raw=protect(json.dumps({'client_id':client_id,'api_key':api_key}).encode());temp=path.with_suffix('.tmp');temp.write_bytes(raw);temp.replace(path)
 elif path.exists():path.unlink()
 os.environ['OZON_CLIENT_ID']=client_id;os.environ['OZON_API_KEY']=api_key

def restore(data):
 if os.environ.get('OZON_CLIENT_ID') and os.environ.get('OZON_API_KEY'):return True
 path=Path(data)/'ozon_api.dpapi'
 if not path.exists():return False
 try:
  value=json.loads(protect(path.read_bytes(),decrypt=True))
  if not isinstance(value,dict) or not value.get('client_id') or not value.get('api_key'):return False
  os.environ['OZON_CLIENT_ID']=value['client_id'];os.environ['OZON_API_KEY']=value['api_key'];return True
 except (OSError,ValueError,TypeError):return False
