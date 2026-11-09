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
 def test_same_first_copies_only_one_parameter_to_all_other_rows(self):
  from variants import same_first
  rows=[{'index':4,'refs':['a'],'values':{'color':'红色','cost':'10'}},{'index':5,'refs':['b'],'values':{'color':'蓝色','cost':'20'}}];self.assertEqual(same_first(rows,'cost'),1);self.assertEqual(rows[1]['values'],{'color':'蓝色','cost':'10'});self.assertEqual(rows[1]['refs'],['b']);self.assertEqual(rows[1]['index'],5)
 def test_same_first_empty_does_not_erase_and_fixed_columns_are_rejected(self):
  from variants import same_first
  rows=[{'values':{'color':''}},{'values':{'color':'蓝色'}}];self.assertEqual(same_first(rows,'color'),0);self.assertEqual(rows[1]['values']['color'],'蓝色')
  for key in ('refs','article','index','stock'):
   with self.assertRaises(ValueError):same_first(rows,key)
 def test_same_first_button_commits_current_editor_and_uses_first_remaining_row(self):
  from variants import VariantGrid
  from unittest.mock import Mock
  grid=VariantGrid.__new__(VariantGrid);grid.rows=[{'index':2,'values':{'quantity':'1'}},{'index':5,'values':{'quantity':'3'}}];grid.focus=(5,3);grid.refresh=Mock();grid.hint=Mock()
  def commit():grid.rows[0]['values']['quantity']='2'
  grid.commit=commit;grid.fill_row();self.assertEqual([r['values']['quantity'] for r in grid.rows],['2','2']);grid.refresh.assert_called_once();self.assertEqual(grid.focus,(2,3))
if __name__=='__main__':unittest.main()
