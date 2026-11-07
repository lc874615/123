import copy,io,json,os,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from category_match import sync_group,confirm_group,repair_groups,suggest
from category_search import commission_options
from pricing_service import write,read

class CategoryFlowTests(unittest.TestCase):
 def draft(self,sku,index=1,base='GROUP'):
  return {'sku':sku,'base_article':base,'variant_index':index,'copy':{'title_ru':'Корзины для хранения'},'category':{},'copy_source':'FIRST','price_cny':None}
 def seed(self,root,sku,index=1,base='GROUP'):
  path=Path(root)/sku/'listing_bundle.json';write(path,self.draft(sku,index,base));return path
 def cat(self):return {'description_category_id':10,'type_id':20,'name':'Корзины','path':'Дом / Корзины','confirmed':False}
 def test_suggestion_reaches_later_variants_and_preserves_confirmed_edits(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=self.seed(tmp,'FIRST');b=self.seed(tmp,'SECOND',2);c=self.seed(tmp,'THIRD',3);other=self.seed(tmp,'OTHER',1,'OTHER')
   data=read(a);data['category']=self.cat();write(a,data)
   protected=read(c);protected['category']={**self.cat(),'type_id':999,'confirmed':True};write(c,protected)
   sync_group(a.parent,threading.Lock())
   self.assertEqual(read(b)['category']['type_id'],20);self.assertFalse(read(b)['category']['confirmed'])
   self.assertEqual(read(c)['category']['type_id'],999);self.assertEqual(read(other)['category'],{})
 def test_confirm_group_retains_type_names_manual_price_and_future_variants(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=self.seed(tmp,'FIRST');b=self.seed(tmp,'SECOND',2)
   data=read(b);data.update(price_cny='999',auto_pricing={'price_cny':'50'});write(b,data)
   self.assertEqual(confirm_group(a.parent,self.cat(),True,threading.Lock()),2)
   self.assertEqual(read(b)['price_cny'],'999');self.assertTrue(read(b)['category']['confirmed']);self.assertEqual(read(b)['category']['name'],'Корзины')
   c=self.seed(tmp,'THIRD',3);sync_group(a.parent)
   self.assertTrue(read(c)['category']['confirmed'])
 def test_restart_repairs_group_without_network(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=self.seed(tmp,'FIRST');b=self.seed(tmp,'SECOND',2)
   data=read(a);data['category']=self.cat();write(a,data)
   with patch('category_match.suggest') as request:repair_groups(tmp,threading.Lock());request.assert_not_called()
   self.assertEqual(read(b)['category']['type_id'],20)
 def test_unmatched_group_requests_once(self):
  with tempfile.TemporaryDirectory() as tmp:
   self.seed(tmp,'FIRST');self.seed(tmp,'SECOND',2)
   with patch('category_match.suggest') as request:repair_groups(tmp);self.assertEqual(request.call_count,1)
 def test_live_tree_response_populates_all_variants(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=self.seed(tmp,'FIRST');b=self.seed(tmp,'SECOND',2)
   response={'result':[{'description_category_id':10,'category_name':'Дом','children':[{'type_id':20,'type_name':'Корзина','children':[]}]}]}
   with patch.dict(os.environ,{'OZON_CLIENT_ID':'test-client','OZON_API_KEY':'test-key'}),patch('category_match.urllib.request.urlopen',side_effect=lambda *a,**k:io.BytesIO(json.dumps(response).encode())):
    suggest(a.parent,threading.Lock())
   self.assertEqual(read(a)['category']['type_id'],20);self.assertEqual(read(b)['category']['type_id'],20)
   self.assertFalse(read(b)['category']['confirmed'])
 def test_missing_connection_has_actionable_reason_and_does_not_leak_key(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=self.seed(tmp,'FIRST')
   with patch.dict(os.environ,{},clear=True),patch('category_match.urllib.request.urlopen') as request:suggest(a.parent);request.assert_not_called()
   self.assertIn('连接Ozon API',read(a)['category_match_status'])
 def test_chinese_and_russian_keyword_search_keeps_distinct_rate_rows(self):
  rows=[{'type_ru':'Корзина','type_zh':'收纳篮','category_zh':'家居收纳','category_ru':'Дом','brand':'All','rates':['.1','.2','.3'],'source_row':3},{'type_ru':'Корзина','type_zh':'收纳篮','category_zh':'家居收纳','category_ru':'Дом','brand':'All','rates':['.2','.2','.3'],'source_row':4},{'type_ru':'Лампа','type_zh':'灯具','category_zh':'照明','category_ru':'Свет','brand':'All','rates':['.1','.1','.1'],'source_row':5}]
  self.assertEqual(len(commission_options({'records':rows},'收纳')),2)
  self.assertEqual(len(commission_options({'records':rows},'корз')),2)
  self.assertEqual(len(commission_options({'records':rows},'收纳 家居')),2)
  self.assertEqual(commission_options({'records':rows},'不存在'),[])

if __name__=='__main__':unittest.main()
