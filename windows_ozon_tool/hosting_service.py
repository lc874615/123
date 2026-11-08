"""Resumable generated-image hosting, shared by image content, not by SKU."""
import hashlib,json,os,threading,time
from pathlib import Path
from cos_host import CosHost,HostingError,validate_settings
from pricing_service import read,write
from asset_audit import inspect

class WaitingForAssets(HostingError):pass

class HostingService:
 def __init__(self,data,store_lock=None,host_factory=CosHost,active_skus=None):
  self.data=Path(data);self.root=self.data/'hosting';self.root.mkdir(parents=True,exist_ok=True)
  self.lock=store_lock or threading.Lock();self.settings_lock=threading.Lock();self.run_lock=threading.Lock();self.wake=threading.Event()
  self.active_skus=active_skus;self.host_factory=host_factory;self.memory_credentials={};self.status='未配置图片托管';self.reference_checked=set();self.retry_at={};self.failures={}
 def settings(self):
  with self.settings_lock:
   path=self.root/'config.json';config=read(path) if path.exists() else {'provider':'tencent_cos','region':os.environ.get('COS_REGION',''),'bucket':os.environ.get('COS_BUCKET',''),'prefix':'ozon-images','enabled':False}
   if not isinstance(config,dict):raise HostingError('托管配置格式异常，请在设置中重新填写')
   credentials=dict(self.memory_credentials)
   if not credentials and (self.root/'credentials.dpapi').exists():
    from hosting_credentials import protect
    try:credentials=json.loads(protect((self.root/'credentials.dpapi').read_bytes(),decrypt=True))
    except (OSError,ValueError):raise HostingError('托管密钥无法在当前Windows账户解密，请重新填写') from None
   if not credentials:credentials={'secret_id':os.environ.get('COS_SECRET_ID',''),'secret_key':os.environ.get('COS_SECRET_KEY','')}
  return config,credentials
 def configure(self,region,bucket,secret_id,secret_key,remember=False):
  config={'provider':'tencent_cos','region':region.strip(),'bucket':bucket.strip(),'prefix':'ozon-images','enabled':True,'remember':bool(remember)}
  credentials={'secret_id':secret_id.strip(),'secret_key':secret_key.strip()};validate_settings(config,credentials)
  encrypted=None
  if remember:
   from hosting_credentials import protect
   encrypted=protect(json.dumps(credentials).encode())
  with self.settings_lock:
   path=self.root/'credentials.dpapi'
   if encrypted is not None:
    temp=path.with_suffix('.tmp');temp.write_bytes(encrypted);temp.replace(path)
   elif path.exists():path.unlink()
   write(self.root/'config.json',config);self.memory_credentials=credentials
  self.retry_at.clear();self.failures.clear();self.status='已配置，等待自动上传';self.wake.set()
 def set_enabled(self,enabled):
  with self.settings_lock:
   path=self.root/'config.json'
   if not path.exists():raise HostingError('请先配置腾讯云COS存储桶')
   config=read(path);config['enabled']=bool(enabled);write(path,config)
  self.retry_at.clear();self.failures.clear();self.wake.set()
 @staticmethod
 def target(config):
  return hashlib.sha256(json.dumps({k:config.get(k) for k in ('provider','region','bucket','prefix')},sort_keys=True).encode()).hexdigest()
 def identity(self,folder,bundle):
  if not isinstance(bundle,dict):raise HostingError('商品草稿不是JSON对象，已跳过；其他商品继续处理')
  if bundle.get('image_regeneration_jobs'):raise WaitingForAssets('图片正在重做，等待新图替换完成后自动上传')
  if bundle.get('recollection_pending'):raise WaitingForAssets('图片正在重新采集，等待完成后自动上传')
  audit=inspect(folder)
  if not audit['verified']:raise WaitingForAssets('等待8张生成图校验完成：'+audit['reason'])
  manifest=read(folder/'image_manifest.json');rows=bundle.get('images')
  if not isinstance(rows,list) or len(rows)!=8:raise WaitingForAssets('上架草稿尚未包含8张图片')
  prepared=[]
  for n,(row,item) in enumerate(zip(rows,manifest),1):
   expected='primary' if n==1 else 'gallery'
   if row.get('order')!=n or row.get('role')!=expected or item.get('role')!=expected or row.get('sha256')!=item.get('sha256'):raise HostingError('草稿图片顺序或校验值与生成图清单不一致')
   relative=str(row.get('local_file','')).replace('\\','/')
   path=(folder/relative).resolve()
   if path.parent!=(folder/'images').resolve() or path.name!=Path(str(item['file']).replace('\\','/')).name:raise HostingError('拒绝上传生成图目录以外的图片或参考图')
   prepared.append((n,path,row['sha256']))
  return tuple((n,str(p),digest) for n,p,digest in prepared)
 def reject_references(self,folder,bundle,raw,digest):
  folders={folder}
  leader=bundle.get('copy_source')
  if isinstance(leader,str) and leader not in ('','.','..') and Path(leader).name==leader:
   other=(folder.parent/leader).resolve()
   if other.parent==folder.parent.resolve():folders.add(other)
  references=[];fingerprint=[]
  for root in folders:
   for name in ('references','shared_references'):
    for path in sorted((root/name).glob('*')):
     if path.is_file() and path.suffix.lower() in ('.png','.jpg','.jpeg','.webp'):
      stat=path.stat();references.append({'path':str(path)});fingerprint.append((str(path),stat.st_size,stat.st_mtime_ns))
  key=(digest,tuple(sorted(fingerprint)))
  if key in self.reference_checked:return
  from asset_guard import reject_reference
  try:reject_reference(raw,references)
  except ValueError as exc:raise HostingError(str(exc)) from None
  self.reference_checked.add(key)
 def progress(self,path,identity,index,asset,target):
  with self.lock:
   latest=read(path)
   if self.identity(path.parent,latest)!=identity:raise HostingError('图片清单已变化，稍后按新清单重新上传')
   latest['images'][index-1].update(https_url=asset['https_url'],hosting_sha256=asset['sha256'],hosting_target=target,hosting_verified_at=asset['verified_at'])
   count=sum(r.get('hosting_target')==target and r.get('hosting_sha256')==r.get('sha256') and bool(r.get('https_url')) and time.time()-r.get('hosting_verified_at',0)<86400 for r in latest['images'])
   complete=count==8
   latest['hosting']={'provider':'tencent_cos','state':'done' if complete else 'uploading','verified_images':count,'expected_images':8,'target':target,'message':'8张原图链接已校验并回填' if complete else f'已校验并回填 {count}/8 张图','updated_at':time.time()}
   blockers=[v for v in (latest.get('blockers') or []) if v not in ('图片HTTPS托管未配置','图片HTTPS链接待校验')]
   if not complete:blockers.append('图片HTTPS链接待校验')
   latest['blockers']=blockers;write(path,latest)
  self.status=latest['hosting']['message']
 def failure(self,path,message,waiting=False):
  with self.lock:
   latest=read(path)
   if not isinstance(latest,dict):return
   previous=latest.get('hosting') or {}
   latest['hosting']={**previous,'state':'waiting' if waiting else 'pending','message':message,'updated_at':time.time()}
   blockers=latest.get('blockers') or []
   if '图片HTTPS链接待校验' not in blockers:blockers.append('图片HTTPS链接待校验')
   latest['blockers']=blockers;write(path,latest)
 def scan_once(self,stop=None):
  with self.run_lock:self._scan_once(stop)
 def _scan_once(self,stop):
  try:
   config,credentials=self.settings()
   if not config.get('enabled'):self.status='图片托管已暂停' if config.get('bucket') else '未配置图片托管';return
   validate_settings(config,credentials);target=self.target(config);client=self.host_factory(config,credentials)
   cache_path=self.root/'cache.json';cache=read(cache_path) if cache_path.exists() else {}
   if not isinstance(cache,dict):raise HostingError('托管缓存格式异常，请检查本地文件')
  except (OSError,ValueError):self.status='请在图片托管设置中补齐账号和密钥';return
  done_count=0;pending_count=0;last_error=''
  for path in (self.data/'products').glob('*/listing_bundle.json'):
   if self.active_skus is not None and path.parent.name not in self.active_skus():continue
   if stop and stop.is_set():return
   if self.retry_at.get(str(path),0)>time.time():pending_count+=1;continue
   try:
    with self.lock:bundle=read(path);identity=self.identity(path.parent,bundle)
    if not bundle.get('price_cny'):raise WaitingForAssets('等待类目匹配与售价计算完成后自动上传图片')
    for index,filename,digest in identity:
     if stop and stop.is_set():return
     fresh_config,_=self.settings()
     if not fresh_config.get('enabled') or self.target(fresh_config)!=target:return
     if self.active_skus is not None and path.parent.name not in self.active_skus():return
     key=target+':'+digest;cached=cache.get(key);cached=cached if isinstance(cached,dict) else None;raw=Path(filename).read_bytes()
     if hashlib.sha256(raw).hexdigest()!=digest:raise HostingError('上传前发现图片已变化，等待生成图重新校验')
     self.reject_references(path.parent,bundle,raw,digest)
     if cached and cached.get('sha256')==digest and cached.get('size')==len(raw):
      if time.time()-cached.get('verified_at',0)>86400:
       client.verify(cached['https_url'],digest,len(raw));cached['verified_at']=time.time();write(cache_path,cache)
     else:
      self.status=path.parent.name+f'：正在上传并校验 {index}/8'
      cached=client.upload(raw,digest);cache[key]=cached;write(cache_path,cache)
     fresh_config,_=self.settings()
     if not fresh_config.get('enabled') or self.target(fresh_config)!=target:return
     if self.active_skus is not None and path.parent.name not in self.active_skus():return
     # Merge into the newest draft. Pricing/copy edits made during a network request survive.
     with self.lock:
      latest=read(path);row=latest['images'][index-1]
      already=row.get('https_url')==cached['https_url'] and row.get('hosting_sha256')==digest and row.get('hosting_target')==target and row.get('hosting_verified_at')==cached['verified_at'] and (latest.get('hosting') or {}).get('state')=='done'
     if not already:self.progress(path,identity,index,cached,target)
    self.retry_at.pop(str(path),None);self.failures.pop(str(path),None);done_count+=1
   except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:
    # Transport errors deliberately never include credentials or signed request bodies.
    message=str(exc) if isinstance(exc,HostingError) else '托管草稿或图片读取失败，请检查本地文件；其他商品继续处理'
    last_error=path.parent.name+'：'+message;self.status=last_error;pending_count+=1
    try:self.failure(path,message,isinstance(exc,WaitingForAssets))
    except (OSError,ValueError):pass
    if isinstance(exc,WaitingForAssets):
     self.retry_at[str(path)]=time.time()+15;continue
    tries=self.failures.get(str(path),0)+1;self.failures[str(path)]=tries
    self.retry_at[str(path)]=time.time()+min(600,60*2**min(tries-1,4))
  if done_count or pending_count:self.status=f'链接就绪 {done_count} 个商品，待处理 {pending_count} 个'+('；'+last_error if last_error else '')
  else:self.status='已配置COS，等待当前任务的生成图与售价就绪'
 def worker(self,stop):
  while not stop.is_set():
   try:self.scan_once(stop)
   except Exception:self.status='托管后台未完成；已有链接保留，请在设置中重试'
   self.wake.wait(15);self.wake.clear()
