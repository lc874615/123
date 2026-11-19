import copy,unittest
from unittest.mock import Mock,patch
from variants import cell_values,pack_display,compact_paste_keys,PACK_KEYS,COMPACT_COLUMNS,FIELDS,VariantGrid
class CompactVariantTests(unittest.TestCase):
 def test_dimensions_map_to_three_original_fields_without_changing_product_size(self):
  before={'length':'12','width':'4','height':'5','material':'metal','competitor_url':'original'}
  for text in ['35 × 25 × 7','35x25x7','35 25 7',('35','25','7')]:
   result=cell_values(before,'pack_dimensions',text);self.assertEqual([result[k] for k in PACK_KEYS],['35','25','7']);self.assertEqual(result['length'],'12');self.assertEqual(before.get('pack_length'),None);self.assertEqual(result['competitor_url'],'original')
  self.assertEqual(pack_display(result),'35 × 25 × 7');self.assertEqual(pack_display({}),'');self.assertEqual(cell_values(result,'pack_dimensions','')['pack_length'],'')
 def test_invalid_size_never_partially_updates_values(self):
  before={'pack_length':'1','pack_width':'2','pack_height':'3'}
  for text in ['35x25','35x25x7x8','0x1x2','NaNx1x2','-1x2x3','abc']:
   with self.subTest(text=text),self.assertRaises(ValueError):cell_values(before,'pack_dimensions',text)
   self.assertEqual(before,{'pack_length':'1','pack_width':'2','pack_height':'3'})
 def test_new_paste_order_and_legacy_full_schema(self):
  self.assertEqual(compact_paste_keys('name',6),COMPACT_COLUMNS[:6]);self.assertEqual(compact_paste_keys('pack_dimensions',4),COMPACT_COLUMNS[2:6]);self.assertEqual(compact_paste_keys('name',len(FIELDS)),tuple(k for k,_,_ in FIELDS))
 def test_copy_dimension_group_preserves_individual_fields_and_other_values(self):
  g=VariantGrid.__new__(VariantGrid);g.rows=[{'index':1,'values':{'pack_length':'35','pack_width':'25','pack_height':'7'}},{'index':3,'values':{'pack_length':'1','pack_width':'2','pack_height':'3','color':'blue'}}];g.commit=Mock();g.refresh=Mock();g.hint=Mock();g.bulk_column('pack_dimensions');self.assertEqual(g.rows[1]['values'],{'pack_length':'35','pack_width':'25','pack_height':'7','color':'blue'});self.assertEqual(g.focus_key,'pack_dimensions')
 def test_malformed_later_excel_row_does_not_modify_any_variant(self):
  g=VariantGrid.__new__(VariantGrid);g.rows=[{'index':1,'values':{'name':'original'}}];g.focus=(1,0);g.focus_key='name';g.commit=Mock();g.frame=Mock();g.frame.clipboard_get.return_value='New\tBlack\t35x25x7\t1000\t29\t1\nWrong\tBlack\t35x25\t1000\t29\t1';g.refresh=Mock();g.add=Mock();before=copy.deepcopy(g.rows)
  with patch('tkinter.messagebox.showerror') as error:g.paste()
  self.assertEqual(g.rows,before);g.add.assert_not_called();error.assert_called_once()
if __name__=='__main__':unittest.main()
