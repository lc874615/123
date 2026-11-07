"""Import the seller's OGL workbook and official rFBS table. No Excel eval."""
import hashlib,re
from pathlib import Path
from decimal import Decimal,ROUND_CEILING,ROUND_FLOOR
from pricing_core import D,OglTier,CommissionBand

OFFICIAL_COMMISSION_URL='https://cdn.ozone.ru/s3/ozon-disk-api/global-education/ru/commissions/ozon-fees/comissions/Tarifs_CN_01_12_2025_1761720496.xlsx'
OFFICIAL_COMMISSION_PAGE='https://global-help.ozon.com/zh/commissions/ozon-fees/commissions/?region=CHN'

def bounds(formula,cell,unit,initial_low,initial_high):
 low,high=D(initial_low),D(initial_high)
 for op,number in re.findall(re.escape(cell)+r'\s*(<=|>=|<|>)\s*([0-9.]+)',formula):
  n=D(number)*D(unit)
  if op=='<':low=max(low,n)
  elif op=='<=':low=max(low,n+(1 if unit==1000 else D('.01')))
  elif op=='>':high=min(high,n)
  elif op=='>=':high=min(high,n-(1 if unit==1000 else D('.01')))
 return low,high

def import_ogl(path,service='Economy'):
 from openpyxl import load_workbook
 path=Path(path);book=load_workbook(path,data_only=False,read_only=True)
 try:
  if '1111' not in book.sheetnames or 'OGL渠道计算' not in book.sheetnames:raise ValueError('OGL表结构无法识别，需要包含1111及OGL渠道计算工作表')
  source=book['1111'];labels={};category=''
  for row in book['OGL渠道计算'].iter_rows(values_only=True):
   if row[1]:category=str(row[1]).split('\n')[0].strip()
   if str(row[2] or '').split('\n')[0].strip()==service and category:labels[category]=row
  current='';rows=[]
  for cells in source.iter_rows():
   values=[c.value for c in cells]
   if values[0]:current=str(values[0]).split('\n')[0].strip()
   if values[1]!=service or not isinstance(values[5],(int,float,Decimal)) or not isinstance(values[6],(int,float,Decimal)):continue
   # PUDO and Courier copies have the same price; one row per category is enough.
   if any(r['name']==current for r in rows):continue
   formula=str(values[7] or '')
   if not formula.startswith('=IF(') or not re.search(r'ROUNDUP\([^)]*,2\)',formula):raise ValueError('OGL运费公式结构变更，请核对后导入')
   minimum,maximum=bounds(formula,'$Q$2',1000,1,30000)
   pmin,pmax=bounds(formula,'$K$2',1,0,250000)
   sum_ref=re.search(r'\$(T)\$(\d+)',formula);side_ref=re.search(r'\$(W)\$([12])',formula)
   if not sum_ref or not side_ref:raise ValueError('OGL尺寸限制公式无法识别')
   sum_formula=str(source['T'+sum_ref[2]].value);side=source['W'+side_ref[2]].value;side_formula=str(getattr(side,'text',side))
   total=re.search(r'\$P\$2\s*(>=|>)\s*(\d+)',sum_formula);longest=re.search(r'\$L\$2:\$N\$2\s*>\s*(\d+)',side_formula)
   if not total or not longest:raise ValueError('OGL三边限制无法识别')
   unit_volume='$W$5' in formula
   if unit_volume and '/12000' not in str(source['W5'].value):raise ValueError('OGL体积重系数发生变化，请核对模板')
   base={'name':current,'fixed_cny':str(values[6]),'per_gram_cny':str(D(values[5])/1000),'min_g':str(minimum),'max_g':str(maximum),'min_rub':str(pmin),'max_rub':str(pmax),'max_side_cm':longest[1],'sum_limit_cm':total[2],'volumetric':unit_volume,'source':path.name+' / 1111!H'+str(cells[0].row),'profile':'uploaded_formula'}
   if total[1]!='>=':raise ValueError('当前OGL尺寸边界公式有变化，请核对规则')
   label=next((v for k,v in labels.items() if k.replace('XY ','').replace('  ',' ')==current.replace('XY ','').replace('  ',' ')),None)
   other=dict(base,profile='uploaded_labels')
   if label is None:raise ValueError('未找到匹配的OGL文字说明，不能使用未核验的边界')
   if label:
    weight=[str(D(n)*(1000 if u.lower() in ('千克','kg') else 1)) for n,u in re.findall(r'(\d+(?:\.\d+)?)\s*(千克|kg|克|g)',str(label[9]),re.I)]
    if len(weight)!=2:raise ValueError('OGL文字重量范围无法识别')
    other.update(min_g=weight[0],max_g=weight[1])
    money=str(label[8]);numbers=re.findall(r'\d+',money)
    if len(numbers)>=2:other.update(min_rub=numbers[0],max_rub=numbers[1])
    elif len(numbers)==1 and '不超' in money:other.update(min_rub='0',max_rub=numbers[0])
    else:raise ValueError('OGL文字货值范围无法识别')
    limits=re.findall(r'≤\s*(\d+(?:\.\d+)?)\s*cm',str(label[10]),re.I)
    if len(limits)!=2:raise ValueError('OGL文字三边或单边上限无法识别')
    other.update(max_side_cm=limits[0],sum_limit_cm=limits[1])
   rows.append(base);base['_labels']=other
  if not rows:raise ValueError('该OGL表没有所选运输方式')
  return {'workbook_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'filename':path.name,'service':service,'tiers':rows}
 finally:book.close()

def tiers(config,labels=False):
 return [OglTier(**(row['_labels'] if labels else {k:v for k,v in row.items() if k!='_labels'})) for row in config['tiers']]

def import_commissions(path):
 from openpyxl import load_workbook
 path=Path(path);book=load_workbook(path,data_only=True,read_only=True)
 try:
  sheet=book['Full ChinaHK'];header=next(sheet.iter_rows(min_row=2,max_row=2,values_only=True))
  if not ('1500' in str(header[10]) and '5000' in str(header[11]) and '5000' in str(header[12])):raise ValueError('佣金价格分档结构发生变化')
  if not all('RFBS' in str(header[i]).upper() for i in (10,11,12)):raise ValueError('佣金表不是已支持的中国跨境rFBS分档表')
  records=[]
  for n,row in enumerate(sheet.iter_rows(min_row=3,values_only=True),3):
   if not row[0]:continue
   rates=[D(x) for x in row[10:13]]
   if len(rates)!=3 or any(not 0<=x<1 for x in rates):raise ValueError('佣金数据缺失或比例异常')
   records.append({'type_ru':str(row[0]).strip(),'type_zh':str(row[1] or '').strip(),'category_ru':str(row[3] or '').strip(),'category_zh':str(row[4] or '').strip(),'market_ru':str(row[6] or '').strip(),'brand':str(row[9] or ''),'rates':[str(r) for r in rates],'source_row':n})
  return {'filename':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'effective_note':str(sheet['J1'].value or ''),'records':records,'source_url':OFFICIAL_COMMISSION_URL}
 finally:book.close()

def select_commission(config,type_name,record_index=None):
 records=config['records'];matched=[r for r in records if r['type_ru'].casefold()==type_name.strip().casefold() and r['brand'].casefold()=='all']
 if record_index is not None:
  matched=[r for r in matched if r['source_row']==int(record_index)]
 schedules={tuple(r['rates']) for r in matched}
 if len(schedules)!=1:raise ValueError('rFBS佣金无法唯一匹配，请核对商品类型并选择对应佣金行')
 rates=next(iter(schedules));source=config['filename']+' / Full ChinaHK rows '+','.join(str(r['source_row']) for r in matched)
 return [CommissionBand(a,b,r,source,'RFBS') for a,b,r in zip((0,1500,5000),(1500,5000,1000000000),rates)]
