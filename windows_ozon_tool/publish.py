"""Explicit local CLI. Preview by default; writes only with --submit.
Public HTTPS image URLs are required. No secret is written into the package.
"""
import argparse,json,os,urllib.request,urllib.parse
from pathlib import Path

def validate(payload):
 items=payload.get('items',[])
 if len(items)!=1:raise ValueError('首版一次只发布一个商品')
 x=items[0]
 for k in ['offer_id','name','description_category_id','type_id','price','currency_code','attributes','weight','height','width','depth']:
  if not x.get(k):raise ValueError('缺少字段 '+k)
 if float(x['price'])<=0:raise ValueError('售价必须为正')
 images=x.get('images',[])
 if len(images)!=8:raise ValueError('必须提供8张图片')
 for u in images:
  p=urllib.parse.urlsplit(u)
  if p.scheme!='https' or not p.hostname or p.username or p.password:raise ValueError('图片必须为可公开读取的HTTPS地址')
 ids={v['id'] for v in x['attributes']}
 if not {85,8229,9048}.issubset(ids):raise ValueError('缺少品牌、类型或型号')
 return x

def call(path,body):
 h={'Client-Id':os.environ['OZON_CLIENT_ID'],'Api-Key':os.environ['OZON_API_KEY'],'Content-Type':'application/json'}
 req=urllib.request.Request('https://api-seller.ozon.ru'+path,data=json.dumps(body).encode(),headers=h)
 with urllib.request.urlopen(req,timeout=45) as r:return json.load(r)

def main():
 p=argparse.ArgumentParser();p.add_argument('payload',type=Path);p.add_argument('--submit',action='store_true');a=p.parse_args()
 body=json.loads(a.payload.read_text(encoding='utf-8'));item=validate(body)
 print(json.dumps({'offer_id':item['offer_id'],'price':item['price'],'currency':item['currency_code'],'image_count':8},ensure_ascii=False))
 if not a.submit:print('预览通过；未提交。确认资料及实际定价后使用 --submit。');return
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
