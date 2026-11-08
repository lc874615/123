import copy,tempfile,unittest,time
from unittest.mock import patch
from pricing_service import read,write
from publication_service import PublicationService,Rejected
from barcode_service import sync
import test_group_publication as fixtures
GEN='/v1/barcode/generate';INFO='/v3/product/info/list';STOCK='/v2/products/stocks'
class BarcodeTests(unittest.TestCase):
 def test_missing_barcodes_generated_after_creation_and_confirmed_for_every_variant(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp,True);job=pub.begin(group,group.token());api.calls=[];job=pub.step(job['id'])
   self.assertEqual([body for path,body in api.calls if path==GEN],[{'product_ids':[100,101]}]);self.assertTrue(all(i['barcode_state']=='done' and i['barcodes'] for i in job['items'].values()));paths=[p for p,b in api.calls];self.assertLess(paths.index(INFO),paths.index(GEN));self.assertLess(paths.index(GEN),paths.index(STOCK));pub.step(job['id']);self.assertEqual(sum(p==GEN for p,b in api.calls),1)
 def test_existing_barcodes_are_kept_without_generation(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);job=pub.begin(group,group.token());offer=group.load()[0]['sku'];api.items[offer]['barcodes']=['EAN-existing'];pub.step(job['id']);self.assertFalse(any(p==GEN for p,b in api.calls));self.assertEqual(read(pub.root/(job['id']+'.json'))['items'][offer]['barcodes'],['EAN-existing'])
 def test_pending_import_does_not_generate(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);api.import_pending=True;job=pub.begin(group,group.token());pub.step(job['id']);self.assertFalse(any(p==GEN for p,b in api.calls))
 def test_accepted_generation_waits_for_value_without_resending_after_restart(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);calls=[];original=pub.caller
   def delayed(path,body):
    if path==GEN:calls.append(body);return {'errors':[]}
    return original(path,body)
   pub.caller=delayed;job=pub.begin(group,group.token());job=pub.step(job['id']);self.assertEqual(next(iter(job['items'].values()))['barcode_state'],'accepted');self.assertFalse(job['writes_complete']);self.assertFalse(any(p==STOCK for p,b in api.calls))
   pub=PublicationService(tmp,group.lock,caller=delayed,account_getter=lambda:'test-shop');pub.step(job['id']);self.assertEqual(len(calls),1)
   for item in api.items.values():item['barcodes']=['OZN-confirmed']
   pub.step(job['id']);self.assertEqual(pub.step(job['id'])['state'],'on_sale');self.assertEqual(len(calls),1)
 def test_uncertain_generation_only_queries_until_actual_barcode_visible(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);calls=[];original=pub.caller
   def uncertain(path,body):
    if path==GEN:calls.append(body);raise TimeoutError('lost reply')
    return original(path,body)
   pub.caller=uncertain;job=pub.begin(group,group.token());job=pub.step(job['id']);self.assertEqual(next(iter(job['items'].values()))['barcode_state'],'uncertain')
   pub=PublicationService(tmp,group.lock,caller=uncertain,account_getter=lambda:'test-shop');pub.step(job['id']);self.assertEqual(len(calls),1)
   pub.clear_group(list(job['items']));new=pub.begin(group,group.token());pub.step(new['id']);self.assertEqual(len(calls),1);job=new
   for item in api.items.values():item['barcodes']=['OZN-recovered']
   pub.step(job['id']);self.assertEqual(pub.step(job['id'])['state'],'on_sale')
 def test_partial_rejection_does_not_block_other_variant(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp,True);original=pub.caller;offers=[b['sku'] for b in group.load()]
   def partial(path,body):
    if path==GEN:
     api.items[offers[0]]['barcodes']=['OZN-first'];return {'errors':[{'product_id':101,'code':'NOT_READY','error':'Wait'}]}
    return original(path,body)
   pub.caller=partial;job=pub.begin(group,group.token());pub.step(job['id']);job=pub.step(job['id']);self.assertTrue(job['items'][offers[0]]['on_sale']);self.assertFalse(job['items'][offers[1]]['on_sale']);self.assertEqual(job['items'][offers[1]]['barcode_errors'][0]['code'],'NOT_READY');self.assertNotIn((offers[1],77),api.stocks)
 def test_legacy_completed_job_backfills_without_import_or_stock_reset(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);job=pub.begin(group,group.token());pub.step(job['id']);job=pub.step(job['id']);self.assertEqual(job['state'],'on_sale')
   for item in job['items'].values():
    for key in list(item):
     if key.startswith('barcode') or key=='barcodes':item.pop(key)
   for item in api.items.values():item.pop('barcodes',None)
   job['barcode_attempt_at']=0;write(pub.root/(job['id']+'.json'),job);api.calls=[];api.stocks[(group.load()[0]['sku'],77)]=3
   pub=PublicationService(tmp,group.lock,caller=api,account_getter=lambda:'test-shop');self.assertEqual(pub.jobs()[0]['state'],'waiting_platform');job=pub.step(job['id']);self.assertEqual(job['state'],'on_sale');self.assertEqual(sum(p==GEN for p,b in api.calls),1);self.assertFalse(any(p in ('/v3/product/import',STOCK) for p,b in api.calls));self.assertEqual(list(api.stocks.values()),[3])
 def test_intent_is_not_lost_when_product_temporarily_missing(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);job=pub.begin(group,group.token());offer=next(iter(job['items']));item=job['items'][offer];item.update(import_state='imported',product_id=100,barcode_product_id=100,barcode_state='intent');sync(pub,job,{});self.assertEqual(item['barcode_state'],'intent')
   sync(pub,job,{offer:{'id':100,'statuses':{'is_created':True},'barcodes':[]}});self.assertEqual(item['barcode_state'],'uncertain');self.assertFalse(any(p==GEN for p,b in api.calls))
 def test_wrong_account_and_local_changes_cannot_generate(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);job=pub.begin(group,group.token());pub.account_getter=lambda:'another-shop'
   with self.assertRaises(ValueError):pub.step(job['id'])
   pub.account_getter=lambda:'test-shop';b=read(group.paths[0]);b['price_cny']='9999';write(group.paths[0],b);self.assertEqual(pub.step(job['id'])['state'],'local_changed');self.assertFalse(any(p==GEN for p,b in api.calls))
 def test_permission_rejection_is_visible_and_not_retried_immediately(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);original=pub.caller;calls=[]
   def caller(path,body):
    if path==GEN:calls.append(body);raise Rejected('Ozon拒绝请求（HTTP 403）')
    return original(path,body)
   pub.caller=caller;job=pub.begin(group,group.token());job=pub.step(job['id']);item=next(iter(job['items'].values()));self.assertIn('Barcode权限',item['status']);self.assertEqual(item['barcode_state'],'rejected');self.assertFalse(job['writes_complete']);pub.step(job['id']);self.assertEqual(len(calls),1);self.assertFalse(any(p==STOCK for p,b in api.calls))
 def test_malformed_generation_response_does_not_count_as_success_or_retry(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);original=pub.caller;calls=[]
   def caller(path,body):
    if path==GEN:calls.append(body);return {}
    return original(path,body)
   pub.caller=caller;job=pub.begin(group,group.token());job=pub.step(job['id']);self.assertEqual(next(iter(job['items'].values()))['barcode_state'],'uncertain');pub.step(job['id']);self.assertEqual(len(calls),1);self.assertFalse(any(p==STOCK for p,b in api.calls))
 def test_batch_limit_and_persisted_rate_limit(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);job=pub.begin(group,group.token());job['items']={str(i):{'import_state':'imported','product_id':i+1} for i in range(101)};products={str(i):{'id':i+1,'statuses':{'is_created':True}} for i in range(101)};calls=[]
   def caller(path,body):
    calls.append((path,body));return {'errors':[]} if path==GEN else {'items':[]}
   pub.caller=caller;sync(pub,job,products);self.assertEqual(len(next(b['product_ids'] for p,b in calls if p==GEN)),100);sync(pub,job,products);self.assertEqual(sum(p==GEN for p,b in calls),1)
if __name__=='__main__':unittest.main()
