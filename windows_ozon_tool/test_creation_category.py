import tempfile,unittest
from unittest.mock import patch
from creation_category import selection,apply_task,category_for_task
class CreationCategoryTests(unittest.TestCase):
 def test_validated_shop_scoped_selection(self):
  c={'description_category_id':10,'type_id':20,'name':'Стул','zh_path':'家具 / 椅子'}
  chosen=selection(c,'shop');a={};b={};apply_task(a,chosen,'shop');apply_task(b,chosen,'shop')
  a['category_selection']['category']['name']='changed'
  self.assertEqual(category_for_task(b,'shop')['name'],'Стул');self.assertTrue(category_for_task(b,'shop')['confirmed'])
  self.assertFalse(category_for_task(b,'other')['confirmed'])
  with self.assertRaises(ValueError):apply_task({},chosen,'other')
  for bad in (True,'10',0):
   with self.assertRaises(ValueError):selection({**c,'type_id':bad},'shop')
 def test_selection_reaches_listing_without_reconfirmation(self):
  from test_image_regeneration import ImageRegenerationTests
  from listing_bundle import prepare
  from category_catalog import setup_errors
  from category_match import suggest
  with tempfile.TemporaryDirectory() as tmp,patch.dict('os.environ',{'OZON_CLIENT_ID':'shop'}):
   store=ImageRegenerationTests().setup(tmp);task=store.tasks[0];folder=store.folder/'products'/task['sku']
   apply_task(task,selection({'description_category_id':10,'type_id':20,'name':'Стул'},'shop'),'shop');store.save();(folder/'listing_bundle.json').unlink()
   from pricing_service import read
   bundle=read(prepare(folder,task))
   with patch('urllib.request.urlopen',side_effect=AssertionError('must not rematch')):suggest(folder)
   self.assertTrue(bundle['category']['confirmed']);self.assertEqual(bundle['category']['type_id'],20)
   self.assertFalse(any('类目未确认' in e for e in setup_errors([bundle],'shop')))
