import copy,tempfile,unittest
from unittest.mock import patch
import test_image_regeneration as fixtures
from copy_pipeline import prepare,save
from asset_reconcile import copy_basis,group_bundles
from pricing_service import read,write
class CopyPipelineTests(unittest.TestCase):
 def test_explicit_regeneration_preserves_copy_then_saves_to_whole_group(self):
  from copy_pipeline import regenerate
  with tempfile.TemporaryDirectory() as tmp:
   store=fixtures.ImageRegenerationTests().setup(tmp);path=store.folder/'products'/'CHAIR(1)'/'listing_bundle.json';before=read(path)
   result=regenerate(store,'CHAIR(2)');self.assertEqual(result['leader'],'CHAIR(1)');self.assertEqual(read(path)['copy'],before['copy']);self.assertEqual(store.next_copy()['copy_mode'],'copy_refresh')
   inspection=prepare(store,{'sku':'CHAIR(1)','prepare_only':True});self.assertTrue(inspection['force_new'])
   with self.assertRaisesRegex(ValueError,'不能沿用旧回复'):save(store,{'sku':'CHAIR(1)','copy':{**before['copy'],'facts_fingerprint':inspection['fingerprint']},'existing':True})
   task=prepare(store,{'sku':'CHAIR(1)'});value={**before['copy'],'title_ru':'Новое название','sku':'CHAIR(1)','facts_fingerprint':task['fingerprint']};save(store,{'sku':'CHAIR(1)','copy':value})
   for row in group_bundles(store,'CHAIR(1)'):self.assertNotIn('copy_regeneration_requested',row);self.assertEqual(row['copy']['title_ru'],'Новое название')
 def test_preview_file_cache_reloads_changes_and_does_not_share_mutable_values(self):
  import test_group_publication as groups
  import group_service
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=groups.GroupTests().setup_group(tmp);group.__dict__.pop('_preview_stamp',None)
   with patch('group_service.read',wraps=group_service.read) as reader:
    first=group.try_load();first[0]['sku']='tampered';again=group.try_load();self.assertNotEqual(again[0]['sku'],'tampered');self.assertEqual(reader.call_count,len(group.paths))
    b=read(group.paths[0]);b['pricing_status']='changed';write(group.paths[0],b);self.assertEqual(group.try_load()[0]['pricing_status'],'changed');self.assertEqual(reader.call_count,len(group.paths)*2)
 def test_regeneration_does_not_duplicate_a_dispatched_request(self):
  from copy_pipeline import regenerate
  with tempfile.TemporaryDirectory() as tmp:
   store=fixtures.ImageRegenerationTests().setup(tmp);store.tasks[0].update(copy_state='running',copy_phase='generating')
   with self.assertRaisesRegex(ValueError,'已有文案请求'):regenerate(store,'CHAIR(2)')
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
 def test_unsent_draft_is_returned_only_when_owned_by_the_previous_marker(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=fixtures.ImageRegenerationTests().setup(tmp);owner=store.tasks[0];folder=store.folder/'products'/owner['sku'];b=read(folder/'listing_bundle.json');b['copy']={};write(folder/'listing_bundle.json',b);owner.update(copy_phase='inspecting',copy_request_marker='【OZON_COPY:old】');old='【OZON_COPY:old】\nprevious request';(folder/'copy_prompt.txt').write_text(old,encoding='utf-8');result=prepare(store,{'sku':owner['sku']});self.assertEqual(result['replace_unsent_prompt'],old)
if __name__=='__main__':unittest.main()
