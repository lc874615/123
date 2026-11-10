import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from group_references import collect,INFO
from pricing_service import read,write
import test_image_regeneration as fixtures
class AllVariantReferencesTests(unittest.TestCase):
 def test_initial_and_regeneration_include_every_variant(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=fixtures.ImageRegenerationTests().setup(tmp)
   for task in store.tasks:task['state']='queued'
   task=store.claim();self.assertEqual({r['sku'] for r in store.tasks},{r['sku'] for r in store.tasks if r['sku'] in task['prompt']})
   self.assertTrue(all(any(r['sku'] in ref['name'] for ref in task['references']) for r in store.tasks));self.assertIn(INFO,task['prompt']);self.assertLessEqual(len(task['references']),8)
   for row in store.tasks:row['state']='saved'
   refs=store.image_jobs.refs(store.tasks,'shared_details');self.assertEqual({r['sku'] for r in refs},{t['sku'] for t in store.tasks})
   self.assertIn(INFO,store.image_jobs.prompt(store.tasks[0]['sku'],'shared_details'))
 def test_large_group_keeps_all_skus_in_reference_sheet_mapping(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=fixtures.ImageRegenerationTests().setup(tmp);leader=store.tasks[0]['sku']
   for i in range(4,18):
    row=copy.deepcopy(store.tasks[0]);row.update(sku='CHAIR('+str(i)+')',id='fixture-'+str(i),copy_leader=leader);store.tasks.append(row)
   refs,variants=collect(store,store.tasks[0],limit=7)
   self.assertLessEqual(len(refs),7);self.assertEqual(len(variants),17)
   self.assertEqual({r['sku'] for r in variants},{cell['sku'] for ref in refs for cell in ref['cells']})
   self.assertTrue(all(Path(r['path']).is_file() for r in refs));self.assertTrue(all(r['purpose']=='shared_reference_sheet' for r in refs))
 def test_uses_latest_parameters_and_rejects_missing_original(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=fixtures.ImageRegenerationTests().setup(tmp);path=store.folder/'products'/store.tasks[1]['sku']/'listing_bundle.json';bundle=read(path);bundle['variant_parameters']['color']='最新颜色';write(path,bundle)
   self.assertEqual(collect(store,store.tasks[0])[1][1]['variant_parameters']['color'],'最新颜色')
   store.tasks[1]['main_references']=[];store.tasks[1]['references']=[]
   with self.assertRaisesRegex(ValueError,'缺少变体主图原始参考'):collect(store,store.tasks[0])
if __name__=='__main__':unittest.main()
