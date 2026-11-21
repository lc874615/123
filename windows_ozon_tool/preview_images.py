"""Bounded decoded preview cache; file IO and PIL work stay off the UI thread."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

class PreviewImages:
 def __init__(self,limit=48):
  self.limit=limit;self.cache=OrderedDict();self.lock=threading.Lock();self.executor=ThreadPoolExecutor(max_workers=2,thread_name_prefix='preview-image')
 def load(self,path,size):
  from PIL import Image,ImageOps
  path=Path(path);stat=path.stat();key=(str(path.resolve()),stat.st_mtime_ns,stat.st_size,tuple(size))
  with self.lock:
   if key in self.cache:self.cache.move_to_end(key);return self.cache[key]
  with Image.open(path) as source:
   source.thumbnail(size);image=ImageOps.contain(ImageOps.exif_transpose(source).convert('RGB'),size)
  with self.lock:
   self.cache[key]=image
   while len(self.cache)>self.limit:self.cache.popitem(last=False)
  return image
 def request(self,widget,path,size,callback):
  def work():
   try:image=self.load(path,size)
   except (OSError,ValueError):image=None
   def done():
    if widget.winfo_exists():callback(image)
   try:widget.after(0,done)
   except RuntimeError:pass
  self.executor.submit(work)
 def close(self):self.executor.shutdown(wait=False,cancel_futures=True)
