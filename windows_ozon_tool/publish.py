"""Explicit local CLI. Preview by default; writes only with --submit.
Public HTTPS image URLs are required. No secret is written into the package.
"""
import argparse,json,os,urllib.request,urllib.parse
from pathlib import Path

def validate(payload):
 from decimal import Decimal,InvalidOperation
 items=payload.get('items',[])
 if not isinstance(items,list) or not 1<=len(items)<=100:raise ValueError('每批须包含1至100个商品')
 seen=set()
 for x in items:
  for k in ['offer_id','name','description_category_id','type_id','price','currency_code','weight','height','width','depth']:
   if not x.get(k):raise ValueError('缺少字段 '+k)
  if x['offer_id'] in seen:raise ValueError('重复的上架货号')
  seen.add(x['offer_id'])
  if len(str(x['offer_id']))>50 or len(str(x['name']))>500:raise ValueError('货号或标题超出长度限制')
  try:
   price=Decimal(str(x['price']))
   if not price.is_finite() or price<=0:raise ValueError('售价必须为有效正数')
  except InvalidOperation:raise ValueError('售价无效') from None
  if x['currency_code'] not in ('CNY','RUB','USD','EUR','KZT','BYN'):raise ValueError('币种无效')
  if str(x.get('vat')) not in ('0','0.05','0.07','0.1','0.2','0.22'):raise ValueError('缺少有效税率')
  for k in ('weight','height','width','depth','description_category_id','type_id'):
   if type(x[k]) is not int or not 0<x[k]<2147483648:raise ValueError('字段须为正整数 '+k)
  if x.get('dimension_unit') not in ('mm','cm','in') or x.get('weight_unit') not in ('g','kg','lb'):raise ValueError('缺少尺寸或重量单位')
  if Decimal(x['weight'])*{'g':Decimal(1),'kg':Decimal(1000),'lb':Decimal('453.59237')}[x['weight_unit']]>1000000:raise ValueError('包装重量超过平台1000kg上限')
  images=list(x.get('images') or [])
  if x.get('primary_image'):images=[x['primary_image']]+images
  if len(images)!=8:raise ValueError('必须提供8张图片（含主图）')
  for u in images:
   p=urllib.parse.urlsplit(u)
   if p.scheme!='https' or not p.hostname or p.username or p.password:raise ValueError('图片必须为可公开读取的HTTPS地址')
  attributes=list(x.get('attributes') or [])
  for group in x.get('complex_attributes') or []:attributes.extend(group.get('attributes') or [])
  for attribute in attributes:
   if type(attribute.get('id')) is not int or attribute['id']<=0 or not attribute.get('values'):raise ValueError('属性ID或值无效')
   for value in attribute['values']:
    if not value.get('dictionary_value_id') and not str(value.get('value') or '').strip():raise ValueError('存在空属性值')
 # type_id replaces the obsolete requirement to always send attribute 8229.
 # Required attribute IDs come from each live category schema, not a fixed global list.
 return items[0] if len(items)==1 else items

def call(path,body):
 h={'Client-Id':os.environ['OZON_CLIENT_ID'],'Api-Key':os.environ['OZON_API_KEY'],'Content-Type':'application/json'}
 req=urllib.request.Request('https://api-seller.ozon.ru'+path,data=json.dumps(body).encode(),headers=h)
 with urllib.request.urlopen(req,timeout=45) as r:return json.load(r)

def main():
 p=argparse.ArgumentParser();p.add_argument('payload',type=Path);p.add_argument('--submit',action='store_true');a=p.parse_args()
 body=json.loads(a.payload.read_text(encoding='utf-8'));validate(body)
 print(json.dumps({'items':[{'offer_id':item['offer_id'],'price':item['price'],'currency':item['currency_code'],'image_count':8} for item in body['items']]},ensure_ascii=False))
 if not a.submit:print('本地结构检查通过；未提交。请先完成官方必填属性及资料核对；显式 --submit 才会调用商品写入接口。');return
 if a.payload.name=='ozon_import_preview.json':
  from listing_preview import validate_saved_preview
  validate_saved_preview(a.payload,body)
 receipt=a.payload.with_suffix('.receipt.json')
 if receipt.exists():raise ValueError('已有提交记录，请先查询任务状态，避免重复提交')
 pending=a.payload.with_suffix('.submitting')
 with pending.open('x',encoding='utf-8') as f:f.write('Submission started; uncertain failures must be reconciled before retry.')
 result=call('/v3/product/import',body)
 receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 pending.unlink()
 print('已保存API响应：'+str(receipt))
 print('需查询 /v1/product/import/info 确认导入结果，再检查审核状态。库存不在此步修改。')
if __name__=='__main__':main()
