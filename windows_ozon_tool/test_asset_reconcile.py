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
 def test_multimaterial_translation_order_and_legacy_copy_hash_do_not_require_new_assets(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=self.seed(tmp)
   for t in store.tasks:
    path=store.folder/'products'/t['sku']/'listing_bundle.json';b=read(path);b['asset_basis']['material']='金属；塑料';b['variant_parameters']['material']='Пластик；Металл；Металл';b['gallery_basis']=[{'sku':x['sku'],'variant_parameters':dict(x['variant_parameters'],material='金属；塑料')} for x in store.tasks];write(path,b)
   bundles=[read(store.folder/'products'/t['sku']/'listing_bundle.json') for t in store.tasks];legacy=copy_basis([{'sku':b['sku'],'variant_parameters':b['asset_basis']} for b in bundles],legacy=True)
   for b in bundles:b['copy_basis']=legacy;write(store.folder/'products'/b['sku']/'listing_bundle.json',b)
   reconcile(store)
   for t in store.tasks:
    b=read(store.folder/'products'/t['sku']/'listing_bundle.json');self.assertFalse(b['asset_review']['main']);self.assertFalse(b['asset_review']['gallery']);self.assertEqual(b['copy_basis'],copy_basis(bundles))
 def test_real_material_change_stays_pending_until_checked_group_acceptance(self):
  from asset_state import blocking_reason
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=self.seed(tmp);path=store.folder/'products'/'CHAIR(1)'/'listing_bundle.json';b=read(path);b['variant_parameters']['material']='Сталь';write(path,b);reconcile(store);b=read(path);self.assertTrue(b['asset_review']['main']);self.assertIn('主体材质',blocking_reason(b));self.assertIn('沿用本组',blocking_reason(b));reconcile(store,accept_group='CHAIR(1)');b=read(path);self.assertFalse(b['asset_review']['main']);self.assertFalse(b['asset_review']['gallery'])
 def test_copy_only_blocker_never_requires_regenerating_images(self):
  from asset_state import blocking_reason
  reason=blocking_reason({'asset_review':{'copy':True}});self.assertIn('文案',reason);self.assertIn('无需重新作图',reason);self.assertNotIn('手动重做',reason)
if __name__=='__main__':unittest.main()
