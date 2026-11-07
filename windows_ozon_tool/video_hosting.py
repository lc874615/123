"""Use the existing COS connection to host each variant's local eight-second MP4."""
import hashlib,threading,time
from pathlib import Path
from cos_host import HostingError,validate_settings
from hosting_service import WaitingForAssets
from pricing_service import read,write
from video_inspect import inspect_mp4

class VideoHostingService:
 def __init__(self,hosting):
  self.hosting=hosting;self.status='等待视频及图片链接就绪';self.wake=threading.Event();self.retry_at={};self.messages={}
 def scan_once(self,stop=None):
  with self.hosting.run_lock:self._scan_once(stop)
 def _scan_once(self,stop):
  source=self.hosting;config,credentials=source.settings()
  if not config.get('enabled'):self.status='视频托管未启用或已暂停';return
  validate_settings(config,credentials);target=source.target(config);client=source.host_factory(config,credentials)
  cache_path=source.root/'cache.json';cache=read(cache_path) if cache_path.exists() else {};done=0;pending=0
  for path in (source.data/'products').glob('*/listing_bundle.json'):
   if stop and stop.is_set():return
   if source.active_skus is not None and path.parent.name not in source.active_skus():continue
   if self.retry_at.get(str(path),0)>time.time():pending+=1;continue
   try:
    with source.lock:
     bundle=read(path);identity=source.identity(path.parent,bundle)
    if (bundle.get('hosting') or {}).get('state')!='done' or (bundle.get('hosting') or {}).get('target')!=target:raise WaitingForAssets('等待8张图片链接完成后自动上传视频')
    video=path.parent/'video'/'product_8s.mp4'
    if not video.is_file():raise WaitingForAssets('等待本地8秒MP4生成；可在工具中重新合成视频')
    if video.stat().st_size>100*1024*1024:raise HostingError('视频超过100MB，请重新合成')
    if video.stat().st_mtime+2<max(Path(filename).stat().st_mtime for _,filename,_ in identity):raise WaitingForAssets('图片已更新，等待新视频合成后上传')
    raw=video.read_bytes();info=inspect_mp4(raw);digest=hashlib.sha256(raw).hexdigest();key=target+':video:'+digest;asset=cache.get(key)
    if not asset or asset.get('sha256')!=digest:
     self.status=path.parent.name+'：正在上传并校验8秒视频';asset=client.upload_video(raw,digest);cache[key]=asset;write(cache_path,cache)
    elif time.time()-asset.get('verified_at',0)>86400:
     client.verify_video(asset['https_url'],digest,len(raw));asset['verified_at']=time.time();write(cache_path,cache)
    fresh,_=source.settings()
    if not fresh.get('enabled') or source.target(fresh)!=target:return
    if source.active_skus is not None and path.parent.name not in source.active_skus():return
    with source.lock:
     latest=read(path)
     if source.identity(path.parent,latest)!=identity or hashlib.sha256(video.read_bytes()).hexdigest()!=digest:raise HostingError('上传中视频或图片已变化，等待新视频完成')
     value={'local_file':'video/product_8s.mp4','exists':True,'https_url':asset['https_url'],'sha256':digest,'hosting_target':target,'hosting_verified_at':asset['verified_at'],'image_hashes':[r[2] for r in identity],**info}
     state={'state':'done','message':'8秒视频链接已校验并回填','sha256':digest,'target':target}
     if latest.get('video')!=value or latest.get('video_hosting')!=state:
      latest.update(video=value,video_hosting=state);latest['blockers']=[b for b in latest.get('blockers',[]) if b!='视频HTTPS链接待校验'];write(path,latest)
    done+=1;self.retry_at.pop(str(path),None);self.messages.pop(str(path),None)
   except (OSError,ValueError,TypeError,KeyError,AttributeError) as exc:
    message=str(exc) if isinstance(exc,(HostingError,ValueError)) else '视频文件或草稿读取失败'
    self.messages[str(path)]=path.parent.name+'：'+message
    with source.lock:
     try:latest=read(path)
     except (OSError,ValueError):latest=None
     if isinstance(latest,dict):
      latest['video_hosting']={'state':'waiting' if isinstance(exc,WaitingForAssets) else 'pending','message':message}
      if '视频HTTPS链接待校验' not in latest.get('blockers',[]):latest.setdefault('blockers',[]).append('视频HTTPS链接待校验')
      write(path,latest)
    pending+=1;self.retry_at[str(path)]=time.time()+(15 if isinstance(exc,WaitingForAssets) else 60)
  self.status=f'视频链接就绪 {done} 个，待处理 {pending} 个'+('；'+next(iter(self.messages.values())) if pending and self.messages else '')
 def worker(self,stop):
  while not stop.is_set():
   try:self.scan_once(stop)
   except Exception:self.status='视频托管未完成，请检查COS连接与本地视频'
   self.wake.wait(15);self.wake.clear()
