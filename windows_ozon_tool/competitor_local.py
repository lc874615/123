"""Local, direct collection of public Ozon characteristics.

This deliberately does not use Edge, browser cookies, or the ChatGPT VPN path.
Only the canonical public product URL is requested and only exact labels from
the already loaded official category schema are returned to the reference gate.
"""
import html,json,re,ssl,threading,urllib.error,urllib.request
from html.parser import HTMLParser
from urllib.parse import urlsplit
from secure_http import contexts
from competitor_reference import normalize_url,claim,receive

class CaptureError(ValueError):
 def __init__(self,message,code='transient'):
  super().__init__(message);self.code=code

def _direct_read(url,limit=3_000_000,timeout=18):
 """HTTPS only, with environment proxy variables intentionally disabled."""
 canonical=normalize_url(url);last=None
 for context in contexts():
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context))
  request=urllib.request.Request(canonical,headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121 Safari/537.36','Accept-Language':'ru-RU,ru;q=0.9','Accept':'text/html,application/xhtml+xml'})
  try:
   with opener.open(request,timeout=timeout) as response:
    final=normalize_url(response.geturl())
    if final!=canonical:raise CaptureError('竞品页面跳转到其他商品，未采用参数','redirect')
    raw=response.read(limit+1)
   if len(raw)>limit:raise CaptureError('竞品页面过大，未读取参数')
   return raw.decode('utf-8','replace')
  except CaptureError:raise
  except (urllib.error.HTTPError,urllib.error.URLError,ssl.SSLError) as exc:
   last=exc
   text=str(exc).casefold()
   if any(x in text for x in ('403','429','captcha','forbidden')):raise CaptureError('公开竞品页要求验证或限制访问，请稍后重试或在 Ozon 页面核对','verification') from exc
  except OSError as exc:last=exc
 raise CaptureError('本地直连未能读取竞品公开页：'+str(last)[:120])

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
  for child in value.values():_walk(child,labels,rows,depth+1)

def extract(html_text,fields):
 labels={_key(f.get(k)) for f in fields for k in ('name','name_ru') if f.get(k)}
 parser=_Rows(labels);parser.feed(html_text);rows=list(parser.rows)
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
 def __init__(self,store):self.store=store;self.wake=threading.Event()
 def run_once(self):
  with self.store.lock:job=claim(self.store).get('job')
  if not job:return False
  try:
   page=_direct_read(job['url']);rows=extract(page,job['fields'])
   body={'token':job['token'],'url':job['url'],'rows':rows,'diagnostics':{'collector':'local_direct','full_sections':1}}
   if not rows:body.update(error='本地公开页未找到与当前类目相同名称的参数，未预填',error_code='empty')
  except CaptureError as exc:body={'token':job['token'],'error':str(exc),'error_code':exc.code}
  except Exception as exc:body={'token':job['token'],'error':'本地采集异常：'+str(exc)[:160],'error_code':'transient'}
  with self.store.lock:receive(self.store,body)
  return True
 def worker(self,stop):
  while not stop.is_set():
   try:
    if self.run_once():continue
   except Exception:pass
   self.wake.wait(2);self.wake.clear()
