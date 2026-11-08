import tempfile,threading,unittest
from pricing_service import read,write
from publication_service import PublicationService,Rejected
import test_group_publication as fixtures

READ='/v2/product/info/stocks-by-warehouse/fbs'
class CreationWaitTests(unittest.TestCase):
 def test_pending_import_never_queries_product_or_stock_index(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);api.import_pending=True;job=pub.begin(group,group.token());api.calls=[];result=pub.step(job['id'])
   self.assertEqual(result['state'],'importing');self.assertFalse(any(p in (READ,'/v3/product/info/list','/v2/products/stocks') for p,b in api.calls));self.assertIn('等待',next(iter(result['items'].values()))['status'])
 def test_stock_index_creation_delay_is_waited_without_rewriting_stock(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);original=pub.caller;delay=[True]
   def call(p,b):
    if p==READ and delay[0]:raise Rejected('HTTP 400: product creation incomplete')
    return original(p,b)
   pub.caller=call;job=pub.begin(group,group.token());result=pub.step(job['id']);self.assertEqual(result['state'],'waiting_creation');self.assertIn('等待',next(iter(result['items'].values()))['status'])
   delay[0]=False;self.assertEqual(pub.step(job['id'])['state'],'on_sale');self.assertEqual(sum(p=='/v2/products/stocks' for p,b in api.calls),1)
 def test_mixed_imports_only_query_ready_variant_and_continue_other_later(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp,True);offers=[b['sku'] for b in group.load()];original=pub.caller;pending=[True]
   def call(p,b):
    r=original(p,b)
    if p=='/v1/product/import/info' and pending[0]:
     for row in r['result']['items']:
      if row['offer_id']==offers[1]:row['status']='pending'
    if p==READ and pending[0]:self.assertEqual(b['offer_id'],[offers[0]])
    return r
   pub.caller=call;job=pub.begin(group,group.token());pub.step(job['id']);result=pub.step(job['id']);self.assertTrue(result['items'][offers[0]]['on_sale']);self.assertEqual(result['items'][offers[1]]['import_state'],'pending')
   pending[0]=False;pub.step(job['id']);self.assertEqual(pub.step(job['id'])['state'],'on_sale');counts=[row['offer_id'] for p,b in api.calls if p=='/v2/products/stocks' for row in b['stocks']];self.assertEqual(counts.count(offers[0]),1);self.assertEqual(counts.count(offers[1]),1)
 def test_one_unready_stock_index_does_not_hide_ready_variants(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp,True);offers=[b['sku'] for b in group.load()];original=pub.caller
   def call(p,b):
    if p==READ and offers[1] in b['offer_id']:raise Rejected('product creation incomplete')
    return original(p,b)
   pub.caller=call;job=pub.begin(group,group.token());pub.step(job['id']);result=pub.step(job['id']);self.assertTrue(result['items'][offers[0]]['on_sale']);self.assertFalse(result['items'][offers[1]]['on_sale']);self.assertEqual(result['state'],'waiting_creation')
 def test_other_stock_query_errors_are_not_masked(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);original=pub.caller
   def call(p,b):
    if p==READ:raise Rejected('HTTP 403 forbidden')
    return original(p,b)
   pub.caller=call;job=pub.begin(group,group.token())
   with self.assertRaisesRegex(Rejected,'403'):pub.step(job['id'])
   self.assertTrue(all(i['stock_state']=='done' for i in read(pub.root/(job['id']+'.json'))['items'].values()))
 def test_fixed_initial_thousand_does_not_reset_stock_after_sales(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,old=fixtures.GroupTests().setup_group(tmp);pub=PublicationService(old.data,threading.Lock(),api,lambda:'test-shop',initial_stock=1000);group.ensure_initial_stock(1000);token=group.token();self.assertFalse(group.ensure_initial_stock(1000));self.assertEqual(token,group.token());offer=group.load()[0]['sku']
   job=pub.begin(group,group.token());pub.step(job['id']);self.assertEqual(api.stocks[(offer,77)],1000)
   api.stocks[(offer,77)]=999;group.set_parameters([0],'cost',['30'],group.token());new=pub.begin(group,group.token());pub.step(new['id']);self.assertEqual(api.stocks[(offer,77)],999);self.assertEqual(sum(p=='/v2/products/stocks' for p,b in api.calls),1)
