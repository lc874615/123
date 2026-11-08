import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import test_image_regeneration as fixtures
from asset_reconcile import reconcile,copy_basis
from asset_state import pending
from pipeline_status import stage
from pricing_service import read,write
class AssetReconcileTests(unittest.TestCase):
 def seed(self,tmp):
  store=fixtures.ImageRegenerationTests().setup(tmp)
  for t in store.tasks:
   path=store.folder/'products'/t['sku']/'listing_bundle.json';b=read(path);b.update(asset_basis=copy.deepcopy(b['variant_parameters']),gallery_basis=copy.deepcopy(t['group_variants']),asset_review={'main':True,'gallery':True,'copy':True,'fields':['color']});write(path,b)
  return store
 def test_checked_matching_images_clear_stale_photo_flags_and_copy_continues(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=self.seed(tmp);reconcile(store)
   for t in store.tasks:
    b=read(store.folder/'products'/t['sku']/'listing_bundle.json');self.assertFalse(b['asset_review']['main']);self.assertFalse(b['asset_review']['gallery']);self.assertTrue(b['asset_review']['copy']);self.assertEqual(stage(t,b,[]),'整组文案待自动采集/更新')
   self.assertEqual(store.next_copy()['copy_mode'],'copy_refresh')
 def test_real_changes_remain_visible_and_one_group_acceptance_persists_for_same_images(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=self.seed(tmp);path=store.folder/'products'/'CHAIR(1)'/'listing_bundle.json';b=read(path);old=copy.deepcopy(b['asset_basis']);b['variant_parameters']['length']='45';write(path,b);reconcile(store);b=read(path);self.assertIn('商品长',b['asset_validation']['main_changes']);self.assertTrue(b['asset_review']['main'])
   reconcile(store,accept_group='CHAIR(1)');b=read(path);self.assertFalse(b['asset_review']['main']);self.assertTrue(b['asset_validation']['accepted_by_user']);b['asset_basis']=old;write(path,b);reconcile(store);self.assertFalse(read(path)['asset_review']['main'])
 def test_copy_basis_clears_only_copy_flag_and_invalid_files_cannot_be_accepted(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=self.seed(tmp);bundles=[read(store.folder/'products'/t['sku']/'listing_bundle.json') for t in store.tasks];fingerprint=copy_basis(bundles)
   for b in bundles:b['copy_basis']=fingerprint;write(store.folder/'products'/b['sku']/'listing_bundle.json',b)
   reconcile(store);self.assertTrue(all(not pending(read(store.folder/'products'/t['sku']/'listing_bundle.json')) for t in store.tasks));Path(store.tasks[0]['received_images'][0]['file']).write_bytes(b'corrupt')
   with self.assertRaises(ValueError):reconcile(store,accept_group='CHAIR(1)')
if __name__=='__main__':unittest.main()
