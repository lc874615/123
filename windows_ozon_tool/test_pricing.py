import copy,datetime as dt,json,tempfile,unittest
from pathlib import Path
from pricing_core import D,Package,CommissionBand,OglTier,solve,confirmed_fee_breakdown
from pricing_service import parse_fx,PricingService,write,read,FX_URL

class PricingTests(unittest.TestCase):
 def band(self):return [CommissionBand(0,1000000,'.1','official fixture','RFBS')]
 def tier(self,profile='uploaded_labels'):
  return OglTier('test',3,'.01',1,30000,0,1000000,100,200,False,'synthetic fixture',profile)
 def test_target_and_conservative_rounding(self):
  result=solve(20,'.25',12,Package(500,10,20,30),self.band(),[self.tier()])[0]
  self.assertGreaterEqual(result['net_margin'],D('.25'))
  previous=confirmed_fee_breakdown(result['price_cny']-D('.01'),20,8,D('.1'))
  self.assertLess(previous['net_margin'],D('.25'))
  self.assertEqual(result['fees_cny']['label'],1)
  self.assertEqual(result['fees_cny']['product_cost'],20)
  self.assertEqual(set(result['fees_cny']),{'label','commission','product_cost','ogl_transport','last_mile','withdrawal','acquiring'})
 def test_band_discontinuities(self):
  bands=[CommissionBand(0,1500,'.5','first','RFBS'),CommissionBand(1500,1000000,'.1','second','RFBS')]
  result=solve(20,'.25',12,Package(500,10,20,30),bands,[self.tier()])[0]
  self.assertGreater(result['price_rub_reference'],1500)
  self.assertEqual(result['commission_source'],'second')
 def test_boundaries_are_inclusive_only_when_confirmed(self):
  package=Package(500,80,70,50)
  self.assertIsNotNone(self.tier().shipping(package))
  self.assertIsNone(self.tier('uploaded_formula').shipping(package))
 def test_bad_inputs(self):
  for value in ('NaN','Infinity','-1','0'):
   with self.assertRaises(ValueError):Package(value,1,1,1)
  with self.assertRaises(ValueError):CommissionBand(0,100,'.1','fixture','FBS')
 def test_fx_nominal_source_date_and_age(self):
  raw=b'<ValCurs Date="07.11.2026"><Valute><CharCode>CNY</CharCode><Nominal>10</Nominal><Value>115,0000</Value></Valute></ValCurs>'
  result=parse_fx(raw,dt.date(2026,11,8));self.assertEqual(result['rub_per_cny'],'11.5000');self.assertEqual(result['url'],FX_URL);self.assertEqual(result['date'],'2026-11-07')
  with self.assertRaises(ValueError):parse_fx(raw,dt.date(2026,11,15))
  with self.assertRaises(ValueError):parse_fx(raw,dt.date(2026,11,6))
 def configs(self):
  tier=self.tier();row={k:str(v) if k not in ('volumetric',) else v for k,v in tier.__dict__.items()};row['_labels']=dict(row)
  return {'ogl':{'tiers':[row],'boundary_policy':'uploaded_labels','workbook_sha256':'test'},'commissions':{'records':[{'type_ru':'test','brand':'All','rates':['.1','.1','.1'],'source_row':3}],'filename':'synthetic.xlsx','sha256':'test','effective_note':'synthetic'},'fx':{'rub_per_cny':'12','date':dt.datetime.now(dt.timezone.utc).date().isoformat(),'source':'fixture'}}
 def bundle(self):
  return {'variant_parameters':{'cost':'20','margin':'25','quantity':'8','pack_weight':'500','pack_length':'10','pack_width':'20','pack_height':'30'},'category':{'type_id':123,'name':'test','confirmed':False},'price_cny':None,'blockers':['实际定价待核验']}
 def test_quote_per_set_shared_copy_not_required(self):
  with tempfile.TemporaryDirectory() as tmp:
   service=PricingService(tmp);result=service.quote(self.bundle(),self.configs(),{})
   self.assertEqual(result['fees_cny']['product_cost'],'20');self.assertFalse(result['category_confirmed'])
 def test_auto_update_invalidation_and_manual_preservation(self):
  with tempfile.TemporaryDirectory() as tmp:
   service=PricingService(tmp);config=self.configs()
   for name,value in config.items():write(service.root/(name+'.json'),value)
   path=Path(tmp)/'products'/'TEST'/'listing_bundle.json';write(path,self.bundle())
   service.calculate_all();first=read(path);self.assertIsNotNone(first['price_cny'])
   first['variant_parameters']['cost']='30';write(path,first);service.calculate_all();second=read(path)
   self.assertGreater(D(second['price_cny']),D(first['price_cny']))
   second['price_cny']='999';second['variant_parameters']['cost']='40';write(path,second);service.calculate_all()
   self.assertEqual(read(path)['price_cny'],'999')
 def test_source_missing_removes_previous_auto_estimate(self):
  with tempfile.TemporaryDirectory() as tmp:
   service=PricingService(tmp)
   for name,value in self.configs().items():write(service.root/(name+'.json'),value)
   path=Path(tmp)/'products'/'TEST'/'listing_bundle.json';write(path,self.bundle());service.calculate_all()
   (service.root/'fx.json').unlink();service.calculate_all()
   self.assertIsNone(read(path)['price_cny']);self.assertIn('自动定价未完成',read(path)['blockers'])
 def test_missing_sources_then_import_recovers_null_estimate(self):
  with tempfile.TemporaryDirectory() as tmp:
   service=PricingService(tmp)
   for name in ('FIRST','SECOND'):
    path=Path(tmp)/'products'/name/'listing_bundle.json';write(path,self.bundle())
   service.calculate_all()
   self.assertIsNone(read(path)['auto_pricing'])
   for name,value in self.configs().items():write(service.root/(name+'.json'),value)
   service.calculate_all()
   for name in ('FIRST','SECOND'):
    saved=read(Path(tmp)/'products'/name/'listing_bundle.json')
    self.assertIsNotNone(saved['price_cny']);self.assertIsNotNone(saved['auto_pricing'])
 def test_null_category_and_parameters_stay_pending(self):
  with tempfile.TemporaryDirectory() as tmp:
   service=PricingService(tmp)
   for name,value in self.configs().items():write(service.root/(name+'.json'),value)
   path=Path(tmp)/'products'/'OLD'/'listing_bundle.json'
   value=self.bundle();value.update(category=None,variant_parameters=None,auto_pricing=None,blockers=None);write(path,value)
   service.calculate_all();self.assertIn('尚未匹配',read(path)['pricing_status'])
   good=Path(tmp)/'products'/'NEW'/'listing_bundle.json';write(good,self.bundle());service.calculate_all()
   self.assertIsNotNone(read(good)['price_cny'])
 def test_one_bad_legacy_estimate_does_not_block_other_variants(self):
  with tempfile.TemporaryDirectory() as tmp:
   service=PricingService(tmp)
   for name,value in self.configs().items():write(service.root/(name+'.json'),value)
   bad=Path(tmp)/'products'/'BAD'/'listing_bundle.json'
   value=self.bundle();value['auto_pricing']=[];write(bad,value)
   good=Path(tmp)/'products'/'GOOD'/'listing_bundle.json';write(good,self.bundle())
   service.calculate_all()
   self.assertIsNotNone(read(good)['price_cny']);self.assertIn('BAD',service.status)
   self.assertEqual(read(bad)['auto_pricing'],[])
 def test_manual_price_with_null_estimate_preserved_on_recovery(self):
  with tempfile.TemporaryDirectory() as tmp:
   service=PricingService(tmp)
   for name,value in self.configs().items():write(service.root/(name+'.json'),value)
   path=Path(tmp)/'products'/'MANUAL'/'listing_bundle.json'
   value=self.bundle();value.update(auto_pricing=None,price_cny='999');write(path,value)
   service.calculate_all();saved=read(path)
   self.assertEqual(saved['price_cny'],'999');self.assertIsNotNone(saved['auto_pricing'])
 def test_selected_commission_row_disambiguates_same_type(self):
  with tempfile.TemporaryDirectory() as tmp:
   service=PricingService(tmp);config=self.configs()
   config['commissions']['records'].append({'type_ru':'test','brand':'All','rates':['.2','.2','.2'],'source_row':4})
   mapping={'123':{'type_name':'test','source_row':4,'commission_sha256':'test'}}
   result=service.quote(self.bundle(),config,mapping)
   self.assertEqual(result['commission_rate'],'0.2');self.assertIn('4',result['commission_source'])
 def test_changed_commission_workbook_invalidates_selected_row(self):
  with tempfile.TemporaryDirectory() as tmp:
   mapping={'123':{'type_name':'test','source_row':3,'commission_sha256':'old'}}
   with self.assertRaisesRegex(ValueError,'佣金表已更新'):PricingService(tmp).quote(self.bundle(),self.configs(),mapping)
 def test_attribute_review_flag_does_not_reset_confirmed_price(self):
  with tempfile.TemporaryDirectory() as tmp:
   service=PricingService(tmp)
   for name,value in self.configs().items():write(service.root/(name+'.json'),value)
   path=Path(tmp)/'products'/'ITEM'/'listing_bundle.json';write(path,self.bundle());service.calculate_all();data=read(path)
   data['pricing_confirmed_fingerprint']=data['pricing_fingerprint'];data['category']['attributes_revalidation_required']=False;write(path,data);service.calculate_all()
   self.assertEqual(read(path)['pricing_confirmed_fingerprint'],data['pricing_fingerprint'])
 def test_no_unverified_commission_fallback(self):
  with tempfile.TemporaryDirectory() as tmp:
   bundle=self.bundle();bundle['category']['name']='unknown'
   with self.assertRaises(ValueError):PricingService(tmp).quote(bundle,self.configs(),{})


class SourceImportTests(unittest.TestCase):
 def test_generic_ogl_text_boundaries(self):
  from openpyxl import Workbook
  from openpyxl.worksheet.formula import ArrayFormula
  from pricing_sources import import_ogl,tiers
  with tempfile.TemporaryDirectory() as tmp:
   book=Workbook();s=book.active;s.title='1111';s.append(['type','service','channel','mode','price','kg rate','fixed','formula'])
   s.append(['Budget','Economy',None,None,None,10,3,'=IF($Q$2<0.51,"weight",IF($K$2>1000,"value",IF($T$1="limit","limit",IF($W$1="limit","limit",ROUNDUP(F2*$Q$2+G2,2)))))'])
   s['T1']='=IF($P$2>=100,"limit","ok")';s['W1']=ArrayFormula(ref='W1',text='=IF(OR($L$2:$N$2>50),"limit","ok")')
   labels=book.create_sheet('OGL渠道计算');labels.append([None,'Budget','Economy',None,None,None,None,None,'不超1000卢布','501克→30千克','单边≤50cm；三边和≤100cm'])
   path=Path(tmp)/'synthetic.xlsx';book.save(path);result=import_ogl(path)
   self.assertEqual(result['tiers'][0]['min_g'],'510.00');self.assertEqual(result['tiers'][0]['_labels']['min_g'],'501')
   self.assertEqual(result['tiers'][0]['_labels']['max_g'],'30000')
   package=Package(501,40,40,20)
   self.assertIsNone(tiers(result)[0].shipping(package));self.assertIsNotNone(tiers(result,True)[0].shipping(package))
 def test_unknown_workbook_rejected(self):
  from openpyxl import Workbook
  from pricing_sources import import_ogl
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'unknown.xlsx';Workbook().save(path)
   with self.assertRaises(ValueError):import_ogl(path)
 def test_official_commission_schema(self):
  from openpyxl import Workbook
  from pricing_sources import import_commissions,select_commission
  with tempfile.TemporaryDirectory() as tmp:
   book=Workbook();s=book.active;s.title='Full ChinaHK';s['J1']='synthetic version'
   s.append([None]*10+['RFBS 0 - 1500','RFBS 1500.01 - 5000','RFBS 5000.01+'])
   s.append(['test','测试',None,'category','类目',None,'market',None,None,'All',.1,.15,.2])
   path=Path(tmp)/'synthetic.xlsx';book.save(path);result=import_commissions(path)
   self.assertEqual([x.rate for x in select_commission(result,'test')],[D('.1'),D('.15'),D('.2')])

if __name__=='__main__':unittest.main()
