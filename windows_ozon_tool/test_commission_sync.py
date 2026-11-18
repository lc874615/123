import copy,tempfile,time,unittest,datetime as dt
from pathlib import Path
from unittest.mock import patch
from commission_sync import collect,compare,bands_for,export_table,location,MAX_AGE
from pricing_sources import select_commission
from pricing_core import D
from pricing_service import PricingService,write,read
NAME='Держатель для костылей, трости'
def config():return {'filename':'base.xlsx','sha256':'fixture','effective_note':'2025-12-01','records':[{'type_ru':n,'brand':'All','rates':['.12','.14','.17'],'source_row':i} for i,n in enumerate(('Держатель для костылей','Держатель для трости'),1)]}
def caller(items):
 def call(p,b):
  if 'prices' in p:return {'items':items,'cursor':''}
  if 'info/list' in p:return {'items':[{'id':r['product_id'],'type_id':20,'description_category_id':10} for r in items]}
  return {'result':[{'description_category_id':10,'category_name':'康复','children':[{'type_id':20,'type_name':NAME,'children':[]}]}]}
 return call
def item(n,rate=20,price='2000',currency='RUB'):return {'product_id':n,'price':{'price':price,'currency_code':currency},'commissions':{'sales_percent_rfbs':rate}}
class CommissionSyncTests(unittest.TestCase):
 def test_merged_category_only_adopts_identical_schedules(self):
  c=config();bands=select_commission(c,NAME);self.assertEqual([b.rate for b in bands],[D('.12'),D('.14'),D('.17')]);self.assertIn('1,2',bands[0].source)
  c['records'][1]['rates'][1]='.22'
  with self.assertRaisesRegex(ValueError,'多条不同'):select_commission(c,NAME)
  with self.assertRaisesRegex(ValueError,'未找到'):select_commission(config(),'unknown')
 def test_only_observed_band_changes_and_source_is_retained(self):
  c=config();before=copy.deepcopy(c);s=compare(collect(caller([item(1)]),'shop',None),c);self.assertTrue(s['cells'][0]['changed']);self.assertEqual(s['cells'][0]['imported_rate'],'0.14')
  bands=bands_for(s,{'type_id':20,'description_category_id':10},select_commission(c,NAME));self.assertEqual([b.rate for b in bands],[D('.12'),D('.2'),D('.17')]);self.assertIn('products 1',bands[1].source);self.assertEqual(c,before)
  self.assertEqual(bands_for(s,{'type_id':30},select_commission(c,NAME))[1].rate,D('.14'))
  s['fetched_at']=time.time()-MAX_AGE-1;self.assertEqual(bands_for(s,{'type_id':20,'description_category_id':10},select_commission(c,NAME))[1].rate,D('.14'))
 def test_conflicts_missing_rate_currency_and_boundary_are_not_guessed(self):
  bad=item(4);bad['commissions']={}
  fx={'rub_per_cny':'10','date':dt.date.today().isoformat()}
  s=collect(caller([item(1,20),item(2,21),item(3,20,currency='USD'),bad,item(5,20,'150','CNY')]),'shop',fx)
  self.assertEqual(s['cells'],[]);self.assertEqual(len(s['conflicts']),1);self.assertEqual(s['skipped'],3)
 def test_rub_band_boundaries_and_percent_zero(self):
  s=collect(caller([item(1,0,'1500'),item(2,14,'5000'),item(3,17,'5001')]),'shop',None)
  self.assertEqual([(c['band'],D(c['rate'])) for c in s['cells']],[(0,D(0)),(1,D('.14')),(2,D('.17'))])
 def test_repeated_pagination_does_not_publish_partial_data(self):
  with self.assertRaisesRegex(ValueError,'游标重复'):collect(lambda p,b:{'items':[item(1)],'cursor':'repeat'},'shop',None)
 def test_service_shop_scope_retry_and_export(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict('os.environ',{'OZON_CLIENT_ID':'shop','OZON_API_KEY':'synthetic-only'}):
   service=PricingService(tmp);write(service.root/'commissions.json',config());service.sync_commissions(True,caller([item(1)]));dest=Path(tmp)/'report.xlsx';service.export_commissions(dest)
   from openpyxl import load_workbook
   b=load_workbook(dest);self.assertIn('有效佣金表',b.sheetnames);self.assertEqual(b['有效佣金表']['E2'].value,.2);b.close()
   path=location(service.root,'shop');before=path.read_bytes()
   with self.assertRaises(ValueError):service.sync_commissions(True,lambda p,b:(_ for _ in ()).throw(ValueError('offline')))
   self.assertEqual(path.read_bytes(),before)
   service.sync_commissions(False,lambda p,b:(_ for _ in ()).throw(AssertionError('not due')))
   self.assertFalse(location(service.root,'other').exists())
 def test_quote_uses_shop_correction_preserves_other_shop_and_blocks_expiry(self):
  from test_pricing import PricingTests
  with tempfile.TemporaryDirectory() as tmp,patch.dict('os.environ',{'OZON_CLIENT_ID':'shop'}):
   service=PricingService(tmp);cfg=PricingTests().configs();cfg['commissions']=config();b=PricingTests().bundle();b['category']={'type_id':20,'description_category_id':10,'name':NAME,'confirmed':True}
   snapshot=compare(collect(caller([item(1,20,'1000')]),'shop',None),config());cfg['shop_commissions']=snapshot
   result=service.quote(b,cfg,{});self.assertEqual(D(result['commission_rate']),D('.2'));self.assertGreaterEqual(D(result['net_margin']),D('.25'));self.assertIn('店铺API校准',result['commission_source'])
   snapshot['account_id']='other';self.assertEqual(D(service.quote(b,cfg,{})['commission_rate']),D('.12'))
   snapshot['account_id']='shop';snapshot['fetched_at']=time.time()-MAX_AGE-1
   for cell in snapshot['cells']:cell['fetched_at']=snapshot['fetched_at']
   with self.assertRaisesRegex(ValueError,'24小时'):service.quote(b,cfg,{})
   cfg['shop_commissions']=collect(caller([item(1,20),item(2,21)]),'shop',None)
   with self.assertRaisesRegex(ValueError,'不同rFBS'):service.quote(b,cfg,{})
 def test_partial_coverage_keeps_previous_expiry_and_conflicts_remove_old_cell(self):
  from commission_sync import preserve_uncovered
  old=collect(caller([item(1,20,'1000')]),'shop',None);stamp=old['cells'][0]['fetched_at']
  fresh=preserve_uncovered(collect(caller([item(2,22,'2000')]),'shop',None),old)
  self.assertEqual(len(fresh['cells']),2);self.assertEqual(next(c for c in fresh['cells'] if c['band']==0)['fetched_at'],stamp)
  conflict=preserve_uncovered(collect(caller([item(1,20,'1000'),item(2,21,'1000')]),'shop',None),old)
  self.assertFalse(conflict['cells'])
 def test_shop_change_discards_response(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict('os.environ',{'OZON_CLIENT_ID':'shop','OZON_API_KEY':'synthetic-only'}):
   service=PricingService(tmp);write(service.root/'commissions.json',config());real=caller([item(1)])
   def changed(p,b):
    value=real(p,b)
    if 'tree' in p:__import__('os').environ['OZON_CLIENT_ID']='other'
    return value
   with self.assertRaisesRegex(ValueError,'切换'):service.sync_commissions(True,changed)
   self.assertFalse(location(service.root,'shop').exists())
