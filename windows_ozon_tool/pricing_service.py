"""Local pricing sources and reproducible, per-variant CNY estimates."""
import datetime as dt
import hashlib
import json
import threading
import urllib.request
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path
from pricing_core import D,Package,solve
from pricing_sources import import_ogl,import_commissions,select_commission,tiers,OFFICIAL_COMMISSION_URL

FX_URL='https://www.cbr.ru/scripts/XML_daily.asp'

def read(path):
 return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_suffix('.pricing.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf-8');tmp.replace(path)

def parse_fx(raw,today=None):
 if len(raw)>2_000_000:raise ValueError('央行汇率响应过大')
 root=ET.fromstring(raw)
 date=dt.datetime.strptime(root.attrib['Date'],'%d.%m.%Y').date()
 today=today or dt.datetime.now(dt.timezone.utc).date()
 if not 0<=(today-date).days<=7:raise ValueError('央行参考汇率日期异常或超过7天')
 item=next((v for v in root.findall('Valute') if v.findtext('CharCode')=='CNY'),None)
 if item is None:raise ValueError('央行响应未包含人民币')
 rate=D(item.findtext('Value').replace(',','.'))/D(item.findtext('Nominal'))
 if rate<=0:raise ValueError('央行人民币参考汇率无效')
 return {'rub_per_cny':str(rate),'date':date.isoformat(),'source':'俄罗斯央行 CBR','url':FX_URL,'fetched_at':dt.datetime.now(dt.timezone.utc).isoformat()}

def fetch(url,limit):
 req=urllib.request.Request(url,headers={'User-Agent':'OzonLocalPricing/0.26'})
 with urllib.request.urlopen(req,timeout=12) as response:
  raw=response.read(limit+1)
 if len(raw)>limit:raise ValueError('来源文件超过大小限制')
 return raw

class PricingService:
 def __init__(self,data,store_lock=None):
  self.data=Path(data);self.root=self.data/'pricing';self.root.mkdir(parents=True,exist_ok=True)
  self.lock=store_lock or threading.Lock();self.source_lock=threading.Lock();self.calculation_lock=threading.Lock();self.status='等待定价配置'
 def import_ogl(self,path):
  config=import_ogl(path)
  config['boundary_policy']='uploaded_labels'
  config['boundary_policy_note']='用户确认采用表中文字：重量、货值与三边上限均按文字说明'
  with self.source_lock:write(self.root/'ogl.json',config)
 def import_commissions(self,path):
  config=import_commissions(path)
  with self.source_lock:write(self.root/'commissions.json',config)
 def update_commissions(self):
  # Explicitly versioned official file; do not claim automatic discovery of the latest tariff.
  raw=fetch(OFFICIAL_COMMISSION_URL,25_000_000)
  path=self.root/'official_commission_download.xlsx';path.write_bytes(raw)
  self.import_commissions(path)
 def update_fx(self):
  value=parse_fx(fetch(FX_URL,2_000_000))
  with self.source_lock:write(self.root/'fx.json',value)
  return value
 def sources(self):
  with self.source_lock:
   configs={name:read(self.root/(name+'.json')) for name in ('ogl','commissions','fx')}
   overrides=read(self.root/'type_mapping.json') if (self.root/'type_mapping.json').exists() else {}
  date=dt.date.fromisoformat(configs['fx']['date'])
  if not 0<=(dt.datetime.now(dt.timezone.utc).date()-date).days<=7:raise ValueError('央行汇率超过7天，请更新后定价')
  return configs,overrides
 def map_type(self,type_id,type_name,source_row=None,commission_sha256=None):
  with self.source_lock:
   path=self.root/'type_mapping.json';value=read(path) if path.exists() else {};value[str(type_id)]={'type_name':type_name,'source_row':source_row,'commission_sha256':commission_sha256} if source_row is not None else type_name;write(path,value)
 def quote(self,bundle,configs,mapping):
  params=bundle.get('variant_parameters') or {};category=bundle.get('category') or {}
  if not category.get('type_id'):raise ValueError('尚未匹配商品类目/类型：'+bundle.get('category_match_status','请连接Ozon API重新匹配，或打开类目窗口选择') )
  selected=mapping.get(str(category['type_id']))
  if isinstance(selected,dict):
   if selected.get('commission_sha256')!=configs['commissions']['sha256']:raise ValueError('佣金表已更新，请重新确认中文列表中对应的佣金类型')
   name=selected['type_name'];record=selected['source_row']
  else:name=selected or category.get('name','');record=None
  bands=select_commission(configs['commissions'],name,record)
  required=('cost','margin','pack_weight','pack_length','pack_width','pack_height')
  if any(not str(params.get(k,'')).strip() for k in required):raise ValueError('请完整填写每套成本、目标利润率、包装重量及三边')
  package=Package(*(params[k] for k in ('pack_weight','pack_length','pack_width','pack_height')))
  args=(params['cost'],D(params['margin'])/100,configs['fx']['rub_per_cny'],package,bands)
  policy=configs['ogl'].get('boundary_policy')
  if policy not in ('uploaded_labels','uploaded_formula'):raise ValueError('请确认OGL边界口径后重新导入运费表')
  candidates=solve(*args,tiers(configs['ogl'],policy=='uploaded_labels'))
  if not candidates:raise ValueError('没有同时满足包裹限制、货值和目标利润率的物流方案')
  result=candidates[0]
  return json.loads(json.dumps({**result,'currency':'CNY','fulfillment':'RFBS','target_margin':str(D(params['margin'])/100),'fx':configs['fx'],'boundary_policy_note':configs['ogl'].get('boundary_policy_note',''),'ogl_sha256':configs['ogl']['workbook_sha256'],'commission_sha256':configs['commissions']['sha256'],'commission_version':configs['commissions']['effective_note'],'type_name':name,'category_confirmed':bool(category.get('confirmed')),'estimated':True},default=str))
 def calculate_all(self):
  with self.calculation_lock:self._calculate_all()
 def _calculate_all(self):
  try:configs,mapping=self.sources();source_error=None
  except Exception as exc:configs=None;mapping={};source_error=str(exc)
  done=0;pending=0;failures=[]
  for path in (self.data/'products').glob('*/listing_bundle.json'):
   try:
    with self.lock:bundle=read(path)
    if not isinstance(bundle,dict):raise ValueError('商品草稿必须是JSON对象')
    inputs={k:bundle.get(k) for k in ('variant_parameters','category','category_match_status')}
    fingerprint=hashlib.sha256(json.dumps([inputs,configs,mapping,source_error],sort_keys=True,default=str).encode()).hexdigest()
    if bundle.get('pricing_fingerprint')==fingerprint:continue
    try:
     if source_error:raise ValueError('定价来源未就绪：'+source_error)
     result=self.quote(bundle,configs,mapping);error=None
    except Exception as exc:result=None;error=str(exc)
    with self.lock:
     latest=read(path)
     if {k:latest.get(k) for k in inputs}!=inputs:continue
     # A manually edited price is preserved; automatic estimates are separately retained.
     previous=latest.get('auto_pricing')
     if previous is not None and not isinstance(previous,dict):raise ValueError('历史估价格式异常，请检查该商品草稿')
     prior=(previous or {}).get('price_cny')
     manual=latest.get('price_cny') is not None and str(latest['price_cny'])!=str(prior)
     latest.update(pricing_fingerprint=fingerprint,pricing_status=error or ('自动估算，类目待确认' if not result['category_confirmed'] else '自动估算完成，待上架确认'))
     latest['auto_pricing']=result
     latest.pop('pricing_confirmed_fingerprint',None)
     if not manual:latest['price_cny']=result['price_cny'] if result else None
     blockers=[x for x in (latest.get('blockers') or []) if x not in ('实际定价待核验','自动定价未完成','售价估算待确认')]
     blockers.append('售价估算待确认' if result else '自动定价未完成');latest['blockers']=blockers
     write(path,latest)
    done+=bool(result);pending+=not bool(result)
   except (OSError,ValueError,TypeError,KeyError,AttributeError) as exc:failures.append(path.parent.name+'：'+str(exc))
  if failures:self.status=f'本轮定价完成 {done}，待补充 {pending}；失败 {len(failures)}：'+failures[0][:160]
  elif done or pending:self.status=f'本轮定价完成 {done}，待补充 {pending}'
 def worker(self,stop):
  while not stop.is_set():
   try:
    from category_match import repair_groups
    repair_groups(self.data/'products',self.lock)
   except Exception as exc:self.status='类目补查失败：'+str(exc)[:120]
   try:
    path=self.root/'fx.json';old=read(path) if path.exists() else {}
    if old.get('fetched_at','')[:10]!=dt.datetime.now(dt.timezone.utc).date().isoformat():self.update_fx()
   except Exception as exc:self.status='央行汇率更新失败：'+str(exc)[:120]
   self.calculate_all()
   # Network retries are bounded to once every ten minutes; local inputs checked every 15s.
   for _ in range(40):
    if stop.wait(15):return
    try:repair_groups(self.data/'products',self.lock,allow_network=False)
    except (OSError,ValueError):pass
    self.calculate_all()
