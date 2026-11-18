"""Read-only shop fee observations. Preserve base table and uncovered price brackets."""
import copy,datetime as dt,hashlib,json,threading,time
from decimal import Decimal
from pathlib import Path
from pricing_core import D,CommissionBand
INTERVAL=6*3600
MAX_AGE=24*3600

def location(root,merchant):return Path(root)/('shop-commissions-'+hashlib.sha256(str(merchant).encode()).hexdigest()[:20]+'.json')
def post(path,body,credentials):
 import urllib.request,urllib.error
 if path not in ('/v5/product/info/prices','/v3/product/info/list','/v1/description-category/tree'):raise ValueError('不支持的佣金读取接口')
 merchant,key=credentials
 if not merchant or not key:raise ValueError('请先连接店铺Ozon API')
 req=urllib.request.Request('https://api-seller.ozon.ru'+path,data=json.dumps(body).encode(),headers={'Client-Id':merchant,'Api-Key':key,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=25) as response:value=json.load(response)
 except urllib.error.HTTPError as e:raise ValueError('佣金读取HTTP '+str(e.code)+'，请检查API权限') from None
 if not isinstance(value,dict):raise ValueError('佣金接口响应格式异常')
 return value

def collect(call,merchant,fx):
 prices=[];cursor='';seen=set()
 for _ in range(1000):
  value=call('/v5/product/info/prices',{'cursor':cursor,'filter':{'visibility':'ALL'},'limit':100})
  if not isinstance(value.get('items'),list):raise ValueError('价格接口缺少items，未覆盖原有校准结果')
  prices.extend(value['items']);nxt=value.get('cursor') or ''
  if not nxt or not value['items']:break
  if nxt in seen:raise ValueError('价格接口游标重复，未覆盖原有校准结果')
  seen.add(nxt);cursor=nxt
 else:raise ValueError('商品分页超过限制，未覆盖原有校准结果')
 details={}
 for start in range(0,len(prices),100):
  batch=prices[start:start+100];value=call('/v3/product/info/list',{'product_id':[str(r['product_id']) for r in batch]})
  if not isinstance(value.get('items'),list):raise ValueError('商品信息响应不完整')
  for r in value['items']:details[str(r['id'])]=r
 from category_match import leaves
 tree=call('/v1/description-category/tree',{'language':'RU'})
 if not isinstance(tree.get('result'),list):raise ValueError('类目树响应不完整')
 names={str(r['type_id']):r['name'] for r in leaves(tree['result'])}
 groups={};skipped=0
 for item in prices:
  try:
   detail=details[str(item['product_id'])];typ=int(detail['type_id']);cat=int(detail['description_category_id']);price=item['price'];amount=D(price['price']);currency=price.get('currency_code');rate=D(item['commissions']['sales_percent_rfbs'])/100
   if typ<=0 or cat<=0 or not rate.is_finite() or not 0<=rate<1 or not amount.is_finite() or amount<=0:raise ValueError()
   if currency=='RUB':rub=amount
   elif currency=='CNY' and fx and D(fx['rub_per_cny'])>0 and 0<=(dt.datetime.now(dt.timezone.utc).date()-dt.date.fromisoformat(fx['date'])).days<=7:rub=amount*D(fx['rub_per_cny'])
   else:raise ValueError()
   band=0 if rub<=1500 else 1 if rub<=5000 else 2
   # A reference FX near a breakpoint cannot establish the price bracket reliably.
   if currency!='RUB' and any(abs(rub-bound)/bound<Decimal('.03') for bound in (Decimal(1500),Decimal(5000))):raise ValueError()
   key=str(cat)+':'+str(typ)+':'+str(band);groups.setdefault(key,[]).append({'product_id':str(item['product_id']),'rate':str(rate),'price_rub':str(rub),'currency':currency,'type_name':names.get(str(typ),''),'description_category_id':cat,'type_id':typ,'band':band})
  except (KeyError,TypeError,ValueError,ArithmeticError):skipped+=1
 cells=[];conflicts=[]
 for key,rows in groups.items():
  if len({r['rate'] for r in rows})!=1:conflicts.append({'key':key,'samples':rows});continue
  cells.append({**rows[0],'samples':rows})
 fetched=time.time()
 for cell in cells:cell['fetched_at']=fetched
 return {'account_id':str(merchant),'fetched_at':fetched,'source':'/v5/product/info/prices sales_percent_rfbs','coverage':'仅店铺已有商品覆盖的类目与价格档；未覆盖档位保留导入表','cells':cells,'conflicts':conflicts,'skipped':skipped,'products':len(prices)}

def bands_for(snapshot,category,base):
 if not snapshot or not 0<=time.time()-snapshot.get('fetched_at',0)<=MAX_AGE:return base
 cells=[c for c in snapshot.get('cells',[]) if c['type_id']==category.get('type_id') and c['description_category_id']==category.get('description_category_id')]
 result=list(base)
 for cell in cells:
  if not 0<=time.time()-cell.get('fetched_at',snapshot['fetched_at'])<=MAX_AGE:continue
  n=cell['band'];lower=(0,1500,5000)[n];upper=(1500,5000,1000000000)[n]
  source='店铺API校准 / '+str(snapshot['fetched_at'])+' / products '+','.join(r['product_id'] for r in cell['samples'])
  result=[b for b in result if not (b.lower_rub==D(lower) and b.upper_rub==D(upper))]
  result.append(CommissionBand(lower,upper,cell['rate'],source,'RFBS'))
 return sorted(result,key=lambda b:b.lower_rub)

def preserve_uncovered(snapshot,previous):
 """Keep uncovered historical cells with their original expiry, never refresh their age."""
 if previous.get('account_id')!=snapshot.get('account_id'):return snapshot
 key=lambda c:(c['description_category_id'],c['type_id'],c['band'])
 covered={key(c) for c in snapshot['cells']}
 covered.update(key(c) for conflict in snapshot['conflicts'] for c in conflict['samples'])
 for c in previous.get('cells',[]):
  if key(c) not in covered:snapshot['cells'].append({**c,'fetched_at':c.get('fetched_at',previous['fetched_at'])})
 return snapshot

def compare(snapshot,config):
 from pricing_sources import select_commission
 result=copy.deepcopy(snapshot)
 for cell in result['cells']:
  try:base=select_commission(config,cell['type_name'])[cell['band']].rate
  except ValueError:base=None
  cell['imported_rate']=str(base) if base is not None else None;cell['changed']=base is None or base!=D(cell['rate'])
 return result

def export_table(config,snapshot,dest):
 from openpyxl import Workbook
 book=Workbook();sheet=book.active;sheet.title='导入佣金基准'
 sheet.append(['商品类型RU','商品类型ZH','所属类目','品牌','≤1500 RUB','1500–5000 RUB','>5000 RUB','来源行'])
 for r in config['records']:sheet.append([r['type_ru'],r.get('type_zh',''),r.get('category_ru',''),r['brand'],*[float(D(v)) for v in r['rates']],r['source_row']])
 live=book.create_sheet('店铺API校准');live.append(['类目ID','类型ID','商品类型','价格档序号0至2','基准比例','校准比例','是否变更','商品ID依据','采集时间UTC'])
 for c in (snapshot or {}).get('cells',[]):live.append([c['description_category_id'],c['type_id'],c['type_name'],c['band'],c.get('imported_rate'),c['rate'],str(c.get('changed')),','.join(r['product_id'] for r in c['samples']),dt.datetime.fromtimestamp(c.get('fetched_at',snapshot['fetched_at']),dt.timezone.utc).isoformat()])
 effective=book.create_sheet('有效佣金表');effective.append(['类目ID','类型ID','商品类型','≤1500 RUB','1500–5000 RUB','>5000 RUB','说明'])
 from pricing_sources import select_commission
 types={(c['description_category_id'],c['type_id'],c['type_name']) for c in (snapshot or {}).get('cells',[])}
 for cat,typ,name in sorted(types):
  try:base=select_commission(config,name)
  except ValueError:base=[]
  bands=bands_for(snapshot,{'type_id':typ,'description_category_id':cat},base);rates={b.lower_rub:str(b.rate) for b in bands}
  effective.append([cat,typ,name,*[rates.get(D(n),'未覆盖') for n in (0,1500,5000)],'店铺局部校准；未覆盖档位沿用基准，不能证明全平台最新'])
 meta=book.create_sheet('来源与覆盖');meta.append(['基准版本',config.get('effective_note','')]);meta.append(['基准SHA256',config.get('sha256','')]);meta.append(['范围',(snapshot or {}).get('coverage','尚未同步店铺')]);meta.append(['冲突组数',len((snapshot or {}).get('conflicts',[]))]);meta.append(['提醒','导出为核对报告，不可作为Full ChinaHK原始表重新导入。API观察值最长使用24小时；程序运行时每6小时同步，失败保留历史。'])
 for ws,columns in ((sheet,(5,6,7)),(live,(5,6)),(effective,(4,5,6))):
  for row in ws.iter_rows(min_row=2):
   for column in columns:
    cell=row[column-1]
    if cell.value is not None:
     try:cell.value=float(D(cell.value));cell.number_format='0.##%'
     except (ValueError,ArithmeticError):pass
 for ws in book:
  ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
  for col in ws.columns:ws.column_dimensions[col[0].column_letter].width=24
 book.save(dest)
