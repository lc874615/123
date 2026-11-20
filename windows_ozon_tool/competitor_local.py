"""Local, direct collection of public Ozon characteristics.

This deliberately does not use Edge, browser cookies, or the ChatGPT VPN path.
Only the canonical public product URL is requested and only exact labels from
the already loaded official category schema are returned to the reference gate.
"""
import html,json,os,re,shutil,socket,ssl,subprocess,tempfile,threading,urllib.error,urllib.request
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

def _browser_executable():
 candidates=[]
 for root in (os.environ.get('PROGRAMFILES',''),os.environ.get('PROGRAMFILES(X86)',''),os.environ.get('LOCALAPPDATA','')):
  if root:candidates.extend([Path(root)/'Google'/'Chrome'/'Application'/'chrome.exe',Path(root)/'Microsoft'/'Edge'/'Application'/'msedge.exe'])
 candidates.sort(key=lambda path:path.name!='chrome.exe')
 for path in candidates:
  if path.is_file():return str(path)
 return next((shutil.which(name) for name in ('chrome','google-chrome','chromium','msedge','microsoft-edge') if shutil.which(name)),None)

def _browser_read(url,timeout=30,proxy_url=''):
 """Use an isolated local Chromium process only after public HTTP fails.

 It never attaches to the ChatGPT tab or a user's browser profile.  The goal is
 to use the same normal browser network stack that can open Ozon on the local
 machine, while keeping collection in the desktop background service.
 """
 executable=_browser_executable()
 if not executable:raise CaptureError('未找到 Microsoft Edge 或 Chrome，无法使用本机浏览器回退读取 Ozon。','network')
 canonical=normalize_url(url)
 with tempfile.TemporaryDirectory(prefix='ozon-competitor-browser-') as profile:
  command=[executable,'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-crash-reporter','--virtual-time-budget=8000','--user-data-dir='+profile,'--dump-dom',canonical]
  proxy_url=_proxy_url(proxy_url)
  command.insert(1,'--proxy-server='+proxy_url if proxy_url else '--no-proxy-server')
  if os.name!='nt':command.insert(1,'--no-sandbox')
  try:result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=False)
  except (OSError,subprocess.SubprocessError) as exc:raise CaptureError('本机浏览器读取 Ozon 失败：'+str(exc)[:160],'network') from exc
 if result.returncode!=0:raise CaptureError('本机浏览器未能打开 Ozon：'+result.stderr.decode('utf-8','replace')[:160],'network')
 page=result.stdout.decode('utf-8','replace')
 if len(page)<200:raise CaptureError('本机浏览器未返回可解析的 Ozon 页面。','network')
 return page

def _visible_rows(text,fields):
 """Extract only an exact official label followed by its rendered value."""
 labels={_key(f.get(k)):str(f.get(k)) for f in fields for k in ('name_ru','name') if f.get(k)}
 lines=[' '.join(line.split()) for line in str(text).splitlines() if line.strip()]
 rows=[]
 for index,line in enumerate(lines):
  key=_key(line)
  if key not in labels:continue
  for value in lines[index+1:index+5]:
   value_key=_key(value)
   if not value_key or value_key in labels:continue
   if len(value)>800 or value.casefold() in ('характеристики','все характеристики','показать все'):continue
   rows.append({'name':labels[key],'value':value});break
 return rows

def _browser_rendered_rows(url,fields,timeout=35,proxy_url=''):
 """Read rendered Ozon characteristics through the installed Playwright stack."""
 try:from playwright.sync_api import sync_playwright
 except ImportError as exc:raise CaptureError('本机缺少浏览器渲染依赖，请运行“修复依赖.bat”后重试。','network') from exc
 executable=_browser_executable()
 if not executable:raise CaptureError('未找到 Microsoft Edge 或 Chrome，无法读取渲染后的 Ozon 特征。','network')
 try:
  with sync_playwright() as playwright:
   proxy_url=_proxy_url(proxy_url)
   options={'proxy':{'server':proxy_url}} if proxy_url else {}
   args=['--disable-gpu','--no-first-run']
   if not proxy_url:args.append('--no-proxy-server')
   browser=playwright.chromium.launch(headless=True,executable_path=executable,args=args,**options)
   try:
    page=browser.new_page(viewport={'width':1440,'height':1400},locale='ru-RU')
    page.goto(normalize_url(url),wait_until='domcontentloaded',timeout=timeout*1000)
    page.wait_for_timeout(5000)
    for label in ('Все характеристики','Характеристики'):
     try:
      page.get_by_text(label,exact=False).first.click(timeout=1200)
      page.wait_for_timeout(1200)
      break
     except Exception:pass
    rows=[]
    rendered=''
    for attempt in range(8):
     rendered=page.locator('body').inner_text(timeout=5000)
     if re.search(r'похоже[\s,，]*нет\s+соединения',rendered,re.I):
      route=proxy_url or '直连'
      raise CaptureError('Ozon 返回连接错误页；浏览器='+Path(executable).name+'；出口='+route,'network')
     if re.search(r'captcha|доступ ограничен|подтвердите.*человек',rendered,re.I):
      raise CaptureError('Ozon 页面要求验证，参数区尚未加载。','verification')
     # Read semantic name/value pairs before applying official-name matching.
     pairs=page.evaluate(r"""() => {
      const rows=[];
      for(const term of document.querySelectorAll('dt')){
       const value=term.nextElementSibling||term.parentElement?.querySelector('dd');
       if(value?.tagName==='DD')rows.push({name:term.innerText,value:value.innerText});
      }
      for(const section of document.querySelectorAll('[data-widget*="Characteristics"],[data-widget*="characteristics"]')){
       for(const name of section.querySelectorAll('span')){
        const label=name.innerText?.trim();
        const parent=name.parentElement?.parentElement;
        if(!label||label.length>180||!parent)continue;
        const lines=parent.innerText.split('\n').map(s=>s.trim()).filter(Boolean);
        if(lines.length===2&&lines[0]===label)rows.push({name:label,value:lines[1]});
       }
      }
      for(const row of document.querySelectorAll('table tr')){
       const cells=row.querySelectorAll('th,td');
       if(cells.length===2)rows.push({name:cells[0].innerText,value:cells[1].innerText});
      }
      return rows.filter(r=>r.name&&r.value&&r.name.length<=180&&r.value.length<=800).slice(0,400);
     }""")
     structured=extract(page.content(),fields)
     rows=pairs+structured+_visible_rows(rendered,fields)
     if rows:break
     page.evaluate('window.scrollBy(0, Math.max(600, innerHeight * .7))')
     page.wait_for_timeout(1500)
    if not rows and re.search(r'captcha|доступ ограничен|подтвердите.*человек',rendered,re.I):
     raise CaptureError('Ozon 页面要求验证，公开参数尚未返回。','verification')
    if not rows:
     title=page.title()[:100]
     widgets=page.locator('[data-widget*="Characteristics"],[data-widget*="characteristics"]').count()
     raise CaptureError('采集版本=proxy-check-2；浏览器='+Path(executable).name+'；出口='+(proxy_url or '直连')+'；参数为0；标题='+title+'；组件='+str(widgets)+'；正文='+str(len(rendered)),'transient')
    unique={}
    for row in rows:
     key=(str(row.get('name','')).strip(),str(row.get('value','')).strip())
     if all(key):unique[key]={'name':key[0],'value':key[1]}
    return list(unique.values())[:400]
   finally:
    browser.close()
   # Ozon often places the full characteristics behind this expandable block.
 except CaptureError:raise
 except Exception as exc:
  code='script' if 'SyntaxError' in str(exc) else 'network'
  raise CaptureError('本机浏览器渲染 Ozon 页面失败：'+str(exc)[:180],code) from exc

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
 def read_with_fallback(self,url):
  try:return self.read_page(url),'local_direct'
  except CaptureError as direct_error:
   if direct_error.code!='network':raise
   return _browser_read(url,proxy_url=self.network_settings()['proxy_url']),'local_browser_fallback'
 def proxy_candidates(self):return discover_local_proxies()
 def run_once(self):
  with self.store.lock:job=claim(self.store).get('job')
  if not job:return False
  try:
   attempts=[]
   rows=[]
   collector='local_direct'
   try:
    page,collector=self.read_with_fallback(job['url'])
    rows=extract(page,job['fields'])
    attempts.append({'stage':collector,'matched':len(rows)})
   except CaptureError as exc:
    attempts.append({'stage':'http_browser','error':str(exc),'code':exc.code})
   # A plain HTTP response can be a location shell with no characteristics.
   # Render it once through the local browser before declaring that the page
   # lacks the current category's fields.
   if not rows:
    try:
     rows=_browser_rendered_rows(job['url'],job['fields'],proxy_url=self.network_settings()['proxy_url']);collector='local_browser_rendered'
     attempts.append({'stage':collector,'matched':len(rows)})
    except CaptureError as exc:
     attempts.append({'stage':'local_browser_rendered','error':str(exc),'code':exc.code})
     raise CaptureError('；'.join(str(item.get('error')) for item in attempts if item.get('error')),exc.code) from exc
   body={'token':job['token'],'url':job['url'],'rows':rows,'diagnostics':{'collector':collector,'full_sections':1,'attempts':attempts}}
   if not rows:body.update(error='参数区未成功提取名称与数值，尚未进行官方字段匹配',error_code='transient')
  except CaptureError as exc:
   self.status='本地竞品采集失败：'+str(exc);body={'token':job['token'],'error':str(exc),'error_code':exc.code,'diagnostics':{'collector':'local_browser_rendered' if attempts else collector,'attempts':attempts}}
  except Exception as exc:body={'token':job['token'],'error':'本地采集异常：'+str(exc)[:160],'error_code':'transient'}
  with self.store.lock:receive(self.store,body)
  if not body.get('error'):self.status='本地竞品采集正常：已读取公开 Ozon 页面'+('（本机浏览器回退）' if body.get('diagnostics',{}).get('collector')=='local_browser_fallback' else '')
  return True
 def worker(self,stop):
  while not stop.is_set():
   try:
    if self.run_once():continue
   except Exception:pass
   self.wake.wait(2);self.wake.clear()
