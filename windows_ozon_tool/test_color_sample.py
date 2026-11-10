import copy,tempfile,unittest
from pricing_service import read,write
import test_group_publication as fixtures
from publish import validate
class ColorSampleTests(unittest.TestCase):
 def test_each_variant_import_uses_own_main_as_color_sample(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp,True);other=read(group.paths[1]);other['images'][0]['https_url']='https://cdn.example.test/variant-two-main.jpg';write(group.paths[1],other);job=pub.begin(group,group.token());items=job['payload']['items']
   for item,bundle in zip(items,group.load()):
    self.assertEqual(item['color_image'],bundle['images'][0]['https_url']);self.assertEqual(item['color_image'],item['images'][0]);self.assertEqual(len(item['images']),8)
   self.assertNotEqual(items[0]['color_image'],items[1]['color_image'])
 def test_changed_main_refreshes_color_sample_on_product_update(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);first=pub.begin(group,group.token());pub.step(first['id']);pub.step(first['id'])
   path=group.paths[0];bundle=read(path);bundle['images'][0]['https_url']='https://cdn.example.test/replacement-main.jpg';write(path,bundle)
   next_job=pub.begin(group,group.token());self.assertNotEqual(first['id'],next_job['id']);self.assertEqual(next_job['payload']['items'][0]['color_image'],'https://cdn.example.test/replacement-main.jpg')
   calls=[body for route,body in api.calls if route=='/v3/product/import'];self.assertEqual(calls[-1]['items'][0]['color_image'],'https://cdn.example.test/replacement-main.jpg')
 def test_legacy_cli_payload_missing_sample_is_filled_from_its_own_main(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);item=copy.deepcopy(pub.begin(group,group.token())['payload']['items'][0]);item.pop('color_image');validate({'items':[item]});self.assertEqual(item['color_image'],item['images'][0])
 def test_cli_rejects_color_sample_pointing_to_another_image(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);item=copy.deepcopy(pub.begin(group,group.token())['payload']['items'][0]);item['color_image']=item['images'][1]
   with self.assertRaisesRegex(ValueError,'颜色样本'):validate({'items':[item]})
if __name__=='__main__':unittest.main()
