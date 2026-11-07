import unittest,tempfile
from variants import article,valid_article,facts
from local_bridge import Store
class Tests(unittest.TestCase):
 def test_article_matches_offer_id(self):
  self.assertEqual(article('ITEM',1),'ITEM(1)');self.assertEqual(article('ITEM',12),'ITEM(12)');self.assertTrue(valid_article('ITEM(12)'));self.assertFalse(valid_article('../ITEM(1)'))
 def test_variant_task_roundtrip(self):
  with tempfile.TemporaryDirectory() as t:
   s=Store(t);s.create_set(article('ITEM',1),facts({'name':'test','quantity':'2','material':'plastic','margin':'25','stock':'1000'}));self.assertEqual(s.claim()['sku'],'ITEM(1)')
 def test_reject_bad_numeric(self):
  for value in ['NaN','Infinity','-2','100']:
   with self.assertRaises(ValueError):facts({'name':'test','margin':value})
 def test_no_invented_unknown(self):
  text=facts({'name':'test','material':'steel'});self.assertNotIn('净重',text);self.assertIn('品牌：无品牌',text)
 def test_column_bulk_fill(self):
  from variants import column_updates
  self.assertEqual(column_updates('中国',3),['中国']*3)
  self.assertEqual(column_updates('红\n蓝\n绿',3),['红','蓝','绿'])
  self.assertEqual(column_updates('',2),['',''])
  with self.assertRaises(ValueError):column_updates('红\n蓝',3)
  with self.assertRaises(ValueError):column_updates('红\t蓝',2)
if __name__=='__main__':unittest.main()
