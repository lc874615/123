import copy,tempfile,unittest
from group_service import edit_guard,EditConflict
from pricing_service import read,write
import test_group_publication as fixtures
class EditGuardTests(unittest.TestCase):
 def test_background_price_media_and_other_parameter_updates_do_not_block_save(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp,True);before=group.load();guard=edit_guard(before,[0],'p','color')
   b=read(group.paths[0]);b['price_cny']='999';b['video']={'https_url':'https://example.com/new.mp4'};b['variant_parameters']['size']='新规格';write(group.paths[0],b)
   group.set_parameters([0],'color',['白色；黑色'],guard)
   current=group.load()[0];self.assertEqual(current['variant_parameters']['color'],'白色；黑色');self.assertEqual(current['variant_parameters']['size'],'新规格');self.assertEqual(current['video']['https_url'],'https://example.com/new.mp4')
 def test_background_auto_price_does_not_block_setting_manual_price(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp,True);rows=group.load();guard=edit_guard(rows,[0],'s','price')
   b=read(group.paths[0]);b['price_cny']='999';write(group.paths[0],b);group.set_prices([0],['123.45'],guard)
   self.assertEqual(str(read(group.paths[0])['price_cny']),'123.45')
 def test_same_parameter_conflict_does_not_overwrite_newer_value(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp,True);guard=edit_guard(group.load(),[0],'p','color');b=read(group.paths[0]);b['variant_parameters']['color']='新颜色';write(group.paths[0],b)
   with self.assertRaises(EditConflict):group.set_parameters([0],'color',['旧编辑值'],guard)
   self.assertEqual(read(group.paths[0])['variant_parameters']['color'],'新颜色')
 def test_attribute_guard_ignores_other_fields_but_rejects_category_and_own_changes(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp,True);rows=group.load();field=rows[0]['attribute_draft']['fields'][0]
   from attribute_service import field_key
   key=field_key(field);guard=edit_guard(rows,[0],'a',key);other=copy.deepcopy(rows);other[0]['attribute_draft']['values']['0:unrelated']=[{'value':'updated'}];group._check(other,guard)
   own=copy.deepcopy(rows);own[0]['attribute_draft']['values'][key]=[{'value':'changed'}]
   with self.assertRaises(EditConflict):group._check(own,guard)
   category=copy.deepcopy(rows);category[0]['category']['type_id']=999
   with self.assertRaises(EditConflict):group._check(category,guard)
if __name__=='__main__':unittest.main()
