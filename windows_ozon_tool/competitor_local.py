"""Local, direct collection of public Ozon characteristics.

This deliberately does not use Edge, browser cookies, or the ChatGPT VPN path.
Only the canonical public product URL is requested and only exact labels from
the already loaded official category schema are returned to the reference gate.
"""
import html,json,re,socket,ssl,threading,urllib.error,urllib.request
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,urlencode
from secure_http import contexts
from competitor_reference import normalize_url,claim,receive

class CaptureError(ValueError):
 def __init__(self,message,code='transient'):
  super().__init__(message);self.code=code

def _proxy_url(value):
 value=str(value or '').strip()
 if not value:return ''
 parts=urlsplit(value)
 if parts.scheme not in ('http','https') or not parts.hostname or parts.username or parts.password or parts.path not in ('','/') or parts.query or parts.fragment:raise ValueError('备用 Ozon 网络出口仅支持不含账号密码的 http://主机:端口 或 https://主机:端口')
 return value.rstrip('/')

def discover_local_proxies():
 """Find listening local HTTP-proxy candidates without touching the network."""
 candidates=[]
 for value in urllib.request.getproxies().values():
  try:value=_proxy_url(value)
  except ValueError:continue
  if value not in candidates:candidates.append(value)
 for port in (7890,7897,10809,10808,1080,2080,8080):
  try:
   with socket.create_connection(('127.0.0.1',port),timeout=.18):pass
   value='http://127.0.0.1:'+str(port)
   if value not in candidates:candidates.append(value)
  except OSError:pass
 return candidates

class _NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def _product_api_url(canonical):
 return 'https://www.ozon.ru/api/composer-api.bx/page/json/v2?'+urlencode({'url':urlsplit(canonical).path})

def _direct_read(url,limit=3_000_000,timeout=18,proxy_url=''):
 """HTTPS only, with global proxy variables intentionally disabled.

 ``proxy_url`` is an explicit Ozon-only fallback supplied by the local user.
 It is never inherited from the browser/ChatGPT VPN environment.
 """
 canonical=normalize_url(url);last=None
 try:proxy_url=_proxy_url(proxy_url)
 except ValueError as exc:raise CaptureError(str(exc),'network') from exc
 for context in contexts():
  routes={'http':proxy_url,'https':proxy_url} if proxy_url else {}
  opener=urllib.request.build_opener(urllib.request.ProxyHandler(routes),urllib.request.HTTPSHandler(context=context),_NoRedirect())
  request=urllib.request.Request(canonical,headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121 Safari/537.36','Accept-Language':'ru-RU,ru;q=0.9','Accept':'text/html,application/xhtml+xml'})
  try:
   with opener.open(request,timeout=timeout) as response:
    final=normalize_url(response.geturl())
    if final!=canonical:raise CaptureError('竞品页面跳转到其他商品，未采用参数','redirect')
    raw=response.read(limit+1)
   if len(raw)>limit:raise CaptureError('竞品页面过大，未读取参数')
   return raw.decode('utf-8','replace')
  except CaptureError:raise
  except urllib.error.HTTPError as exc:
   last=exc
   text=str(exc).casefold()
   if exc.code in (301,302,303,307,308):
    # Product HTML can be region-redirected in mainland networks. Try the
    # same-origin public page-data endpoint before treating the route as bad.
    try:
     api=urllib.request.Request(_product_api_url(canonical),headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121 Safari/537.36','Accept':'application/json','Accept-Language':'ru-RU,ru;q=0.9','x-o3-app-name':'d'})
     with opener.open(api,timeout=timeout) as response:raw=response.read(limit+1)
     if len(raw)>limit:raise CaptureError('Ozon 商品数据响应过大，未读取参数')
     return raw.decode('utf-8','replace')
    except CaptureError:raise
    except (urllib.error.HTTPError,urllib.error.URLError,ssl.SSLError,OSError) as api_exc:
     last=api_exc;raise CaptureError('Ozon 商品网页重复跳转，且公开数据接口不可用：'+str(api_exc)[:120]+'。请切换为可访问 Ozon 的本地出口后重试。','network') from api_exc
   if any(x in text for x in ('403','429','captcha','forbidden')):raise CaptureError('公开竞品页要求验证或限制访问，请稍后重试或在 Ozon 页面核对','verification') from exc
  except (urllib.error.URLError,ssl.SSLError) as exc:
   last=exc
   text=str(exc).casefold()
   if any(x in text for x in ('403','429','captcha','forbidden')):raise CaptureError('公开竞品页要求验证或限制访问，请稍后重试或在 Ozon 页面核对','verification') from exc
  except OSError as exc:last=exc
 route='备用 Ozon 网络出口' if proxy_url else '本地直连网络';detail=str(last)[:120]
 if 'connection refused' in detail.casefold():raise CaptureError(route+'无法连接 Ozon（连接被拒绝）。请让 VPN 对 ozon.ru 走直连，或配置仅用于 Ozon 的备用出口。','network')
 raise CaptureError(route+'未能读取竞品公开页：'+detail,'network')

def _key(value):return re.sub(r'[^\w]+',' ',str(value or '').casefold().replace('ё','е')).strip()

class _Rows(HTMLParser):
 def __init__(self,labels):
  super().__init__(convert_charrefs=True);self.labels=labels;self.stack=[];self.current=[];self.rows=[];self.scripts=[];self.in_script=False
 def handle_starttag(self,tag,attrs):
  self.stack.append(tag)
  if tag=='script':self.in_script=True;self.current=[]
  elif tag in ('tr','dl'):self.current=[]
 def handle_endtag(self,tag):
  if tag=='script':self.in_script=False;self.scripts.append(''.join(self.current));self.current=[]
  elif tag in ('tr','dl'):
   text=' '.join(''.join(self.current).split())
   parts=[p.strip() for p in re.split(r'\s{2,}|\n+',text) if p.strip()]
   if len(parts)>=2 and _key(parts[0]) in self.labels:self.rows.append({'name':parts[0],'value':' '.join(parts[1:])})
   self.current=[]
  if self.stack:self.stack.pop()
 def handle_data(self,data):
  if self.in_script or any(x in ('tr','dl','dt','dd','th','td') for x in self.stack):self.current.append(data)

def _walk(value,labels,rows,depth=0):
 if depth>12 or len(rows)>=400:return
 if isinstance(value,list):
  for item in value[:500]:_walk(item,labels,rows,depth+1)
 elif isinstance(value,dict):
  name=next((value.get(k) for k in ('name','title','label','key') if isinstance(value.get(k),str) and _key(value[k]) in labels),None)
  raw=next((value.get(k) for k in ('value','values','text','description') if value.get(k) not in (None,'')),None)
  if name and isinstance(raw,(str,int,float,bool)):
   rows.append({'name':name,'value':str(raw)})
  elif name and isinstance(raw,list) and raw and all(isinstance(x,(str,int,float)) for x in raw):
   rows.append({'name':name,'value':'；'.join(str(x) for x in raw),'values':[str(x) for x in raw]})
  for child in value.values():
   if isinstance(child,str) and len(child)<=1_500_000 and child.lstrip()[:1] in ('{','['):
    try:_walk(json.loads(child),labels,rows,depth+1)
    except (ValueError,TypeError):pass
   _walk(child,labels,rows,depth+1)

def extract(html_text,fields):
 labels={_key(f.get(k)) for f in fields for k in ('name','name_ru') if f.get(k)}
 parser=_Rows(labels);parser.feed(html_text);rows=list(parser.rows)
 try:_walk(json.loads(html_text),labels,rows)
 except (ValueError,TypeError):pass
 for script in parser.scripts:
  if len(script)>1_500_000:continue
  try:_walk(json.loads(script),labels,rows)
  except (ValueError,TypeError):continue
 seen=set();out=[]
 for row in rows:
  name=' '.join(str(row.get('name','')).split());value=' '.join(str(row.get('value','')).split())
  if _key(name) not in labels or not name or not value:continue
  token=(_key(name),value)
  if token not in seen:seen.add(token);out.append({**row,'name':name,'value':value})
 return out[:400]

class LocalCompetitorService:
 def __init__(self,store):self.store=store;self.wake=threading.Event();self.status='本地直连 Ozon（不使用插件或 ChatGPT VPN）'
 @property
 def network_path(self):return Path(self.store.folder)/'competitor_network.json'
 def network_settings(self):
  try:value=json.loads(self.network_path.read_text(encoding='utf-8'))
  except (OSError,ValueError):value={}
  return {'proxy_url':_proxy_url(value.get('proxy_url','')) if value.get('proxy_url') else ''}
 def configure_proxy(self,proxy_url):
  proxy_url=_proxy_url(proxy_url)
  self.network_path.write_text(json.dumps({'proxy_url':proxy_url},ensure_ascii=False),encoding='utf-8')
  self.status=('本地 Ozon 采集：使用独立备用出口' if proxy_url else '本地直连 Ozon（不使用插件或 ChatGPT VPN）');self.wake.set()
 def read_page(self,url):return _direct_read(url,proxy_url=self.network_settings()['proxy_url'])
 def proxy_candidates(self):return discover_local_proxies()
 def run_once(self):
  with self.store.lock:job=claim(self.store).get('job')
  if not job:return False
  try:
   page=self.read_page(job['url']);rows=extract(page,job['fields'])
   body={'token':job['token'],'url':job['url'],'rows':rows,'diagnostics':{'collector':'local_direct','full_sections':1}}
   if not rows:body.update(error='本地公开页未找到与当前类目相同名称的参数，未预填',error_code='empty')
  except CaptureError as exc:
   self.status='本地竞品采集失败：'+str(exc);body={'token':job['token'],'error':str(exc),'error_code':exc.code}
  except Exception as exc:body={'token':job['token'],'error':'本地采集异常：'+str(exc)[:160],'error_code':'transient'}
  with self.store.lock:receive(self.store,body)
  if not body.get('error'):self.status='本地竞品采集正常：已读取公开 Ozon 页面'
  return True
 def worker(self,stop):
  while not stop.is_set():
   try:
    if self.run_once():continue
   except Exception:pass
   self.wake.wait(2);self.wake.clear()
