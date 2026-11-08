"""Verified HTTPS with Mozilla roots plus Windows native chain resolution."""
import ssl,sys,urllib.error,urllib.parse,urllib.request

def contexts():
 result=[]
 try:context=ssl.create_default_context()
 except (OSError,ssl.SSLError):context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
 try:
  import certifi
  context.load_verify_locations(cafile=certifi.where())
 except (ImportError,OSError,ssl.SSLError):pass
 result.append(context)
 if sys.platform=='win32':
  try:
   import truststore
   native=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
   native.check_hostname=True;native.verify_mode=ssl.CERT_REQUIRED;result.append(native)
  except (ImportError,OSError,ssl.SSLError):pass
 return result

def certificate_error(error):
 reason=error.reason if isinstance(error,urllib.error.URLError) else error
 return isinstance(reason,ssl.SSLCertVerificationError) or 'CERTIFICATE_VERIFY_FAILED' in str(reason)

def read(request,limit,timeout=12):
 url=request.full_url if isinstance(request,urllib.request.Request) else str(request)
 if urllib.parse.urlsplit(url).scheme!='https':raise ValueError('来源必须使用HTTPS')
 last=None
 for context in contexts():
  try:
   with urllib.request.urlopen(request,context=context,timeout=timeout) as response:
    if urllib.parse.urlsplit(response.geturl()).scheme!='https':raise ValueError('来源重定向到非HTTPS地址，未采用数据')
    raw=response.read(limit+1)
   if len(raw)>limit:raise ValueError('来源文件超过大小限制')
   return raw
  except (urllib.error.URLError,ssl.SSLError) as error:
   if not certificate_error(error):raise
   last=error
 raise ValueError('HTTPS证书链校验失败。请运行“修复依赖.bat”更新证书组件；若仍失败，请检查电脑日期时间、Windows根证书或代理的可信证书。未关闭证书校验。') from last
