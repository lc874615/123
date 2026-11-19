import tempfile,unittest
from pathlib import Path
from PIL import Image,ImageOps
from group_references import compile_references,verify_sources
import test_image_regeneration as fixtures
class ReferenceReadabilityTests(unittest.TestCase):
 def setup_long(self,tmp):
  store=fixtures.ImageRegenerationTests().setup(tmp);t=store.tasks[0];folder=store.folder/'products'/t['sku']/'shared_references';folder.mkdir();path=folder/'long.png'
  image=Image.new('RGB',(600,1900),'white');image.paste('red',(0,0,600,900));image.paste('blue',(0,1000,600,1900));image.save(path)
  t['detail_references']=[{'path':str(path),'name':'long.png','mime':'image/png','purpose':'shared_gallery'}];return store,path
 def test_regions_are_exact_original_pixels_with_parent_provenance_and_full_original_kept(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,path=self.setup_long(tmp);refs=compile_references(store,store.tasks[0],'main');self.assertLessEqual(len(refs),8);self.assertTrue(any(r['path']==str(path) for r in refs));regions=[r for r in refs if r.get('source_path')]
   self.assertGreater(len(regions),0)
   for ref in regions:
    with Image.open(path) as source,Image.open(ref['path']) as crop:self.assertEqual(crop.tobytes(),ImageOps.exif_transpose(source).crop(tuple(ref['crop_box'])).tobytes())
    self.assertEqual(ref['purpose'],'shared_information');self.assertEqual(ref['source_path'],str(path));self.assertIn('区域',ref['region'])
   verify_sources(refs)
 def test_parent_change_invalidates_regions_and_source_index_together(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,path=self.setup_long(tmp);refs=compile_references(store,store.tasks[0],'main');Image.new('RGB',(600,1900),'green').save(path)
   with self.assertRaisesRegex(ValueError,'原始参考图已变化'):verify_sources(refs)
 def test_crop_coordinates_and_private_paths_never_become_product_dimensions_in_prompt(self):
  from image_prompts import reference_contract
  with tempfile.TemporaryDirectory() as tmp:
   store,path=self.setup_long(tmp);t=store.tasks[0];refs=compile_references(store,t,'main');text=reference_contract({'sku':t['sku'],'references':refs,'expected_images':1})
   self.assertNotIn(str(path),text);self.assertNotIn('crop_box',text);self.assertIn('区域编号不代表商品尺寸',text);self.assertIn('同一原始详情',text)

class RebasedRegionTests(unittest.TestCase):
 def test_queued_region_and_parent_hashes_survive_installation_directory_move(self):
  import shutil
  from unittest.mock import patch
  from local_bridge import Store
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   old=Path(tmp)/'old';new=Path(tmp)/'new';store,path=ReferenceReadabilityTests().setup_long(old);sku=store.tasks[0]['sku'];store.image_jobs.create(sku,'variant_main',[sku],'');shutil.copytree(old,new);shutil.rmtree(old);restored=Store(new);request=restored.image_jobs.claim();self.assertEqual(request['expected_images'],1);self.assertTrue(any(r.get('source_path') for r in restored.image_jobs.get(request['id'])['references']));verify_sources(restored.image_jobs.get(request['id'])['references'])

if __name__=='__main__':unittest.main()
