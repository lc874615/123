"""Persistent local pairing. Windows uses the current user's DPAPI protection."""
import os,secrets
from pathlib import Path

def token(data):
 root=Path(data);root.mkdir(parents=True,exist_ok=True);windows=os.name=='nt';path=root/('pairing.dpapi' if windows else 'pairing.local')
 def encode(raw,decrypt=False):
  if windows:
   from hosting_credentials import protect
   return protect(raw,decrypt=decrypt)
  return raw
 if path.exists():
  value=encode(path.read_bytes(),True).decode()
  if len(value)<32 or len(value)>128:raise ValueError('本机配对信息损坏，请在设置中重置配对')
  return value
 value=secrets.token_urlsafe(32);path.write_bytes(encode(value.encode()))
 if not windows:path.chmod(0o600)
 return value

class InstanceLock:
 def __init__(self,data):self.path=Path(data)/'instance.lock';self.file=None
 def acquire(self):
  self.path.parent.mkdir(parents=True,exist_ok=True);self.file=self.path.open('a+b');self.file.seek(0);self.file.write(b'0');self.file.flush();self.file.seek(0)
  try:
   if os.name=='nt':
    import msvcrt
    msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
   else:
    import fcntl
    fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except OSError:self.file.close();self.file=None;raise ValueError('本地工具已经运行，请使用已有窗口') from None
 def release(self):
  if self.file:self.file.close();self.file=None
