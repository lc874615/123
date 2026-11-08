"""Merchant's four price fields, in the store's CNY currency."""
from decimal import Decimal,ROUND_HALF_UP

def listing_prices(bundle):
 def money(value,positive=False):
  amount=Decimal(str(value))
  if not amount.is_finite() or amount<0 or (positive and amount<=0):raise ValueError('售价或成本无效')
  return amount.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
 base=money(bundle.get('price_cny'),True)
 cost=money((bundle.get('variant_parameters') or {}).get('cost'))
 return {'offer_id':bundle.get('offer_id') or bundle['sku'],'currency_code':'CNY','price':str(base*2),'old_price':str(base*4),'min_price':str(base),'net_price':str(cost)}
