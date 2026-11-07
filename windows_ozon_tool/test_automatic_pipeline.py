import datetime as dt,io,json,os,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from pricing_service import PricingService,write,read

class OneCycle:
 def is_set(self):return False
 def wait(self,seconds):return True

class AutomaticPipelineTests(unittest.TestCase):
 def test_background_matches_one_group_and_prices_three_variants_without_manual_actions(self):
  with tempfile.TemporaryDirectory() as tmp:
   service=PricingService(tmp,threading.Lock());today=dt.datetime.now(dt.timezone.utc).date().isoformat()
   tier={'name':'synthetic','fixed_cny':'3','per_gram_cny':'.01','min_g':'1','max_g':'30000','min_rub':'0','max_rub':'1000000','max_side_cm':'100','sum_limit_cm':'200','volumetric':False,'source':'synthetic fixture','profile':'uploaded_labels'}
   tier['_labels']=dict(tier)
   sources={'ogl':{'tiers':[tier],'boundary_policy':'uploaded_labels','workbook_sha256':'synthetic'},'commissions':{'records':[{'type_ru':'Корзина','brand':'All','rates':['.1','.1','.1'],'source_row':3}],'filename':'synthetic.xlsx','sha256':'synthetic','effective_note':'synthetic'},'fx':{'rub_per_cny':'12','date':today,'fetched_at':today,'source':'synthetic'}}
   for name,value in sources.items():write(service.root/(name+'.json'),value)
   paths=[]
   for n in (1,2,3):
    path=Path(tmp)/'products'/f'GROUP({n})'/'listing_bundle.json';paths.append(path)
    write(path,{'sku':f'GROUP({n})','base_article':'GROUP','variant_index':n,'copy':{'title_ru':'Корзины для хранения'},'category':None,'variant_parameters':{'cost':str(n*10),'margin':'25','pack_weight':'500','pack_length':'10','pack_width':'20','pack_height':'30'},'price_cny':None,'blockers':['实际定价待核验']})
   tree={'result':[{'description_category_id':10,'category_name':'Дом','children':[{'type_id':20,'type_name':'Корзина','children':[]}]}]}
   with patch.dict(os.environ,{'OZON_CLIENT_ID':'test','OZON_API_KEY':'test'}),patch('category_match.urllib.request.urlopen',side_effect=lambda *a,**k:io.BytesIO(json.dumps(tree).encode())) as request:
    service.worker(OneCycle())
   self.assertEqual(request.call_count,1)
   bundles=[read(path) for path in paths]
   self.assertTrue(all(b['category']['type_id']==20 for b in bundles))
   self.assertTrue(all(b['price_cny'] is not None for b in bundles))
   self.assertEqual(len({b['price_cny'] for b in bundles}),3)
   self.assertTrue(all(not b['category']['confirmed'] for b in bundles))

if __name__=='__main__':unittest.main()
