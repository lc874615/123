import copy,tempfile,unittest
from unittest.mock import patch
import test_image_regeneration as fixtures
from copy_pipeline import prepare,save
from asset_reconcile import copy_basis,group_bundles
from pricing_service import read,write
class CopyPipelineTests(unittest.TestCase):
 def test_prepare_only_is_read_only_and_local_copy_shares(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=fixtures.ImageRegenerationTests().setup(tmp)
   result=prepare(store,{'sku':'CHAIR(2)','prepare_only':True})
   self.assertTrue(result['local_ready']);self.assertEqual(result['sku'],'CHAIR(1)')
   self.assertNotEqual(store.tasks[0].get('copy_phase'),'generating')
 def test_stale_copy_rejects_old_text_then_saves_current_copy_to_every_variant(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=fixtures.ImageRegenerationTests().setup(tmp);path=store.folder/'products'/'CHAIR(1)'/'listing_bundle.json';b=read(path);b['asset_review']={'copy':True};write(path,b)
   task=prepare(store,{'sku':'CHAIR(1)','prepare_only':True});self.assertTrue(task['needsRefresh']);value=copy.deepcopy(b['copy']);value['sku']='CHAIR(1)'
   with self.assertRaises(ValueError):save(store,{'sku':'CHAIR(1)','copy':value,'existing':True})
   value['facts_fingerprint']=task['fingerprint'];save(store,{'sku':'CHAIR(1)','copy':value,'existing':True})
   for t in store.tasks:
    result=read(store.folder/'products'/t['sku']/'listing_bundle.json');self.assertEqual(result['copy_basis'],task['fingerprint']);self.assertFalse((result.get('asset_review') or {}).get('copy'))
 def test_dispatched_request_cannot_be_sent_twice_and_changed_context_is_rejected(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=fixtures.ImageRegenerationTests().setup(tmp);owner=store.tasks[0];owner.update(copy_phase='generating',copy_state='running',copy_context_basis=copy_basis(group_bundles(store,'CHAIR(1)')))
   self.assertTrue(prepare(store,{'sku':'CHAIR(1)','prepare_only':True})['dispatched'])
   with self.assertRaises(ValueError):prepare(store,{'sku':'CHAIR(1)'})
   path=store.folder/'products'/'CHAIR(1)'/'listing_bundle.json';b=read(path);b['variant_parameters']['length']='99';write(path,b)
   with self.assertRaises(ValueError):save(store,{'sku':'CHAIR(1)','copy':b['copy']})
 def test_saved_local_copy_is_not_overwritten_by_an_older_automatic_result(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=fixtures.ImageRegenerationTests().setup(tmp);path=store.folder/'products'/'CHAIR(1)'/'listing_bundle.json';b=read(path);b['copy_user_revision']='new-local-revision';write(path,b);before=read(path);owner=store.tasks[0];owner.update(copy_mode='copy_refresh',copy_phase='generating',copy_source_revision=None)
   with self.assertRaisesRegex(ValueError,'未覆盖'):save(store,{'sku':'CHAIR(1)','copy':dict(b['copy'],title_ru='Old generated title')})
   self.assertEqual(read(path),before)
if __name__=='__main__':unittest.main()
