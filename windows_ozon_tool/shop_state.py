"""Shop-specific listing settings over shared local images and copy."""
import copy,hashlib
from pathlib import Path
from pricing_service import read,write
FIELDS=('category','category_match_status','attribute_draft','attribute_history','attribute_archives','export_settings','fulfillment','price_cny','manual_price','auto_pricing','manual_pricing','pricing_fingerprint','pricing_confirmed_fingerprint','pricing_confirmed_price','pricing_status','stock_revision')
def switch(data,old,new):
 if old==new:
  write(Path(data)/'active_shop.json',{'account_id':new});return
 root=Path(data);paths=list((root/'products').glob('*/listing_bundle.json'))
 def location(account):return root/'shops'/hashlib.sha256(account.encode()).hexdigest()/'draft_settings.json'
 if old:
  settings={}
  for path in paths:
   try:b=read(path);settings[path.parent.name]={k:copy.deepcopy(b[k]) for k in FIELDS if k in b}
   except (ValueError,OSError):continue
  write(location(old),settings)
 saved=read(location(new)) if location(new).exists() else {}
 for path in paths:
  try:b=read(path)
  except (ValueError,OSError):continue
  if path.parent.name in saved:
   for key in FIELDS:b.pop(key,None)
   b.update(copy.deepcopy(saved[path.parent.name]))
  else:
   b.pop('fulfillment',None);b['export_settings']={'currency_code':'CNY','currency_confirmed':False};b['price_cny']=None
   for key in ('pricing_fingerprint','pricing_confirmed_fingerprint','manual_price','manual_pricing','attribute_draft'):b.pop(key,None)
   if b.get('category'):b['category']={**b['category'],'confirmed':False,'attributes_revalidation_required':True}
   b['pricing_status']='新店铺：请核对类目、税率、币种和仓库'
  write(path,b)
 write(root/'active_shop.json',{'account_id':new})

def activate(data,current):
 if not current:return
 root=Path(data);path=root/'active_shop.json'
 old=(read(path).get('account_id','') if path.exists() else '')
 if not path.exists():
  owners=set()
  for bundle in (root/'products').glob('*/listing_bundle.json'):
   try:
    account=(read(bundle).get('fulfillment') or {}).get('account_id')
    if account:owners.add(account)
   except (ValueError,OSError):pass
  old=next(iter(owners)) if len(owners)==1 else current
 if old!=current:switch(root,old,current)
 write(path,{'account_id':current})
