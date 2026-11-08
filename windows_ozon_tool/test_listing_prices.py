import tempfile,unittest
from listing_prices import listing_prices
import test_group_publication as fixtures

class Tests(unittest.TestCase):
 def test_price_multipliers_and_supplied_cost(self):
  result=listing_prices({'sku':'A','price_cny':'173.31','variant_parameters':{'cost':'50.8'}})
  self.assertEqual(result,{'offer_id':'A','currency_code':'CNY','price':'346.62','old_price':'693.24','min_price':'173.31','net_price':'50.80'})
 def test_invalid_cost_rejected(self):
  for value in (None,'NaN','-1'):
   with self.assertRaises(Exception):listing_prices({'sku':'A','price_cny':'10','variant_parameters':{'cost':value}})
 def test_all_variants_price_sync_before_stock_and_no_repeated_write(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp,True)
   expected=[listing_prices(b) for b in group.load()]
   job=pub.begin(group,group.token());job=pub.step(job['id'])
   calls=[body for path,body in api.calls if path=='/v1/product/import/prices']
   self.assertEqual(calls,[{'prices':expected}]);self.assertTrue(all(i['price_state']=='done' for i in job['items'].values()))
   paths=[p for p,_ in api.calls];self.assertLess(paths.index('/v1/product/import/prices'),paths.index('/v2/products/stocks'))
   pub.step(job['id'],refresh=True)
   self.assertEqual(sum(p=='/v1/product/import/prices' for p,_ in api.calls),1)
 def test_price_failure_does_not_report_listing_complete_or_write_stock(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp)
   def caller(path,body):
    if path=='/v1/product/import/prices':return {'result':[{'offer_id':r['offer_id'],'updated':False,'errors':[{'code':'INVALID_PRICE'}]} for r in body['prices']]}
    return api(path,body)
   pub.caller=caller;job=pub.begin(group,group.token());job=pub.step(job['id'])
   self.assertEqual(job['state'],'waiting_platform');self.assertFalse(any(p=='/v2/products/stocks' for p,_ in api.calls))
   self.assertEqual(next(iter(job['items'].values()))['price_errors'][0]['code'],'INVALID_PRICE')
   self.assertGreater(next(iter(job['items'].values()))['price_retry_at'],0)
