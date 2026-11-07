"""Tencent COS XML signed PUT + anonymous original-image verification."""
import base64,hashlib,hmac,io,re,time
import urllib.error,urllib.parse,urllib.request
from PIL import Image

LIMIT=20*1024*1024
class HostingError(ValueError):pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def validate_settings(config,credentials):
 if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,49}-[0-9]{5,20}',config.get('bucket','')):raise HostingError('请填写完整Bucket名称，包含末尾的APPID，例如商品桶名-1250000000')
 if not re.fullmatch(r'(?:ap|eu|na|sa|me)-[a-z]+(?:-[0-9]+)?',config.get('region','')):raise HostingError('请填写存储桶实际地域，例如ap-hongkong或ap-guangzhou')
 if not re.fullmatch(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*',config.get('prefix','')):raise HostingError('托管目录仅支持字母、数字、横线和下划线')
 if not credentials.get('secret_id') or not credentials.get('secret_key'):raise HostingError('请在图片托管设置中填写SecretId与SecretKey')

def authorization(method,path,headers,secret_id,secret_key,now=None):
 now=int(time.time() if now is None else now);key_time=str(now-60)+';'+str(now+600)
 normalized={k.lower():str(v).strip() for k,v in headers.items()}
 quote=lambda value:urllib.parse.quote(value,safe='-_.~')
 names=sorted(normalized);canonical='&'.join(quote(k)+'='+quote(normalized[k]) for k in names)
 http_string=method.lower()+'\n'+urllib.parse.unquote(path)+'\n\n'+canonical+'\n'
 string_to_sign='sha1\n'+key_time+'\n'+hashlib.sha1(http_string.encode()).hexdigest()+'\n'
 sign_key=hmac.new(secret_key.encode(),key_time.encode(),hashlib.sha1).hexdigest()
 digest=hmac.new(sign_key.encode(),string_to_sign.encode(),hashlib.sha1).hexdigest()
 return 'q-sign-algorithm=sha1&q-ak='+secret_id+'&q-sign-time='+key_time+'&q-key-time='+key_time+'&q-header-list='+';'.join(names)+'&q-url-param-list=&q-signature='+digest

class CosHost:
 def __init__(self,config,credentials):
  validate_settings(config,credentials);self.config=dict(config);self.credentials=dict(credentials)
  self.hostname=config['bucket']+'.cos.'+config['region']+'.myqcloud.com'
  self.base='https://'+self.hostname;self.opener=urllib.request.build_opener(NoRedirect())
 def verify(self,url,digest,size):
  parsed=urllib.parse.urlsplit(url)
  if parsed.scheme!='https' or parsed.hostname!=self.hostname or parsed.port not in (None,443) or parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.path.startswith('/'+self.config['prefix']+'/'):raise HostingError('公开链接不是当前COS存储桶的固定HTTPS原图地址')
  request=urllib.request.Request(url,headers={'User-Agent':'OzonLocalHosting/0.27','Accept':'image/*'})
  try:
   with self.opener.open(request,timeout=30) as response:
    raw=response.read(LIMIT+1)
    if not response.headers.get('Content-Type','').lower().startswith('image/'):raise HostingError('COS公开链接未返回图片，请检查对象Content-Type')
  except urllib.error.HTTPError as exc:raise HostingError('COS原图匿名读取失败（HTTP '+str(exc.code)+'），请检查公有读私有写权限、防盗链空Referer和账户状态；未回填链接') from None
  except (urllib.error.URLError,TimeoutError,OSError):raise HostingError('COS原图公开读取超时或网络不可达，稍后自动重试') from None
  if len(raw)!=size or len(raw)>LIMIT or not hmac.compare_digest(hashlib.sha256(raw).hexdigest(),digest):raise HostingError('COS远端图片与本地原图不一致，未回填链接')
  return True
 def upload(self,raw,digest):
  if len(raw)>LIMIT:raise HostingError('单张图片超过20MB，请检查生成图文件')
  if hashlib.sha256(raw).hexdigest()!=digest:raise HostingError('待上传图片校验值变化')
  with Image.open(io.BytesIO(raw)) as image:
   fmt=image.format;image.verify()
  extension,mime={'JPEG':('jpg','image/jpeg'),'PNG':('png','image/png'),'WEBP':('webp','image/webp')}.get(fmt,(None,None))
  if not extension:raise HostingError('托管仅支持JPG、PNG、WEBP图片')
  key=self.config['prefix']+'/'+digest+'.'+extension;path='/'+key;url=self.base+path
  headers={'Host':self.hostname,'Content-Type':mime,'Content-Length':str(len(raw)),'Content-MD5':base64.b64encode(hashlib.md5(raw).digest()).decode(),'x-cos-storage-class':'STANDARD','x-cos-forbid-overwrite':'true','Cache-Control':'public, max-age=31536000, immutable'}
  headers['Authorization']=authorization('PUT',path,headers,self.credentials['secret_id'],self.credentials['secret_key'])
  request=urllib.request.Request(url,data=raw,headers=headers,method='PUT')
  try:
   with self.opener.open(request,timeout=60) as response:response.read(4096)
  except urllib.error.HTTPError as exc:
   if exc.code!=409:
    reason='密钥、地域或上传权限错误，请同时检查系统时间' if exc.code in (401,403) else '额度或请求限制，请检查COS账户控制台' if exc.code in (402,420,429) else 'COS拒绝上传，请检查Bucket、地域和账户状态'
    raise HostingError(reason+'（HTTP '+str(exc.code)+'）') from None
   # A previous attempt may have succeeded. Verify the immutable object rather than overwrite.
  except (urllib.error.URLError,TimeoutError,OSError):raise HostingError('COS上传超时或网络不可达，保留已完成进度，稍后重试') from None
  self.verify(url,digest,len(raw))
  return {'https_url':url,'object_key':key,'provider':'tencent_cos','sha256':digest,'size':len(raw),'verified_at':time.time()}
