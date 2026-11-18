"""Source coverage and immutable evidence snapshots across initial/remake requests."""
import copy,hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from group_references import compile_references,verify_sources,pack_sources
from test_image_regeneration import ImageRegenerationTests,picture
class OriginalSourceTests(unittest.TestCase):
 def extras(self,store):
  leader=store.tasks[0]
  for t in store.tasks:
   folder=store.folder/'products'/t['sku']/'references'
   for n in (2,3):
    path=folder/f'extra{n}.png';path.write_bytes(picture(t['variant_index']*100+n));t['main_references'].append({'path':str(path),'name':path.name,'mime':'image/png'})
  folder=store.folder/'products'/leader['sku']/'shared_references';folder.mkdir(exist_ok=True);path=folder/'detail.png';path.write_bytes(picture(77));leader['detail_references']=[{'path':str(path),'name':path.name,'mime':'image/png','purpose':'shared_gallery'}]
 def flatten(self,refs):
  return [c for ref in refs for c in (ref.get('cells') or [{'path':ref['path'],'sku':ref.get('sku'),'purpose':ref.get('purpose'),'sha256':ref.get('reference_sha256')}])]
 def test_initial_and_shared_remake_keep_every_original_not_only_first_hero(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=ImageRegenerationTests().setup(tmp);self.extras(store)
   expected={str(Path(r['path']).resolve()) for t in store.tasks for r in t['main_references']+t.get('detail_references',[])}
   for scope in ('full','shared'):
    refs=compile_references(store,store.tasks[0],scope);self.assertLessEqual(len(refs),8);self.assertEqual({r['path'] for r in self.flatten(refs)},expected);self.assertTrue(all(len(r.get('cells') or [])<=4 for r in refs));verify_sources(refs)
 def test_main_remake_only_own_appearance_and_original_shared_details(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=ImageRegenerationTests().setup(tmp);self.extras(store);task=store.tasks[1]
   task['references']=compile_references(store,store.tasks[0],'full')
   refs=compile_references(store,task,'main');self.assertTrue(all(r.get('sku')==task['sku'] for r in refs if r.get('purpose')=='variant_main'));self.assertEqual(len([r for r in refs if r.get('purpose')=='variant_main']),3);self.assertTrue(any(r.get('purpose')=='shared_information' for r in refs));self.assertFalse(any('images' in Path(r['path']).parts for r in self.flatten(refs)))
 def test_sheet_source_changes_are_detected_even_when_sheet_bytes_unchanged(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=ImageRegenerationTests().setup(tmp);self.extras(store);refs=compile_references(store,store.tasks[0],'shared');sheet=next(r for r in refs if r.get('cells'));old=Path(sheet['path']).read_bytes();path=Path(sheet['cells'][1]['path']);path.write_bytes(picture(221));self.assertEqual(Path(sheet['path']).read_bytes(),old)
   with self.assertRaisesRegex(ValueError,'原始参考图已变化'):verify_sources(refs)
 def test_generated_image_paths_cannot_be_relabelled_as_originals(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=ImageRegenerationTests().setup(tmp);t=store.tasks[0];ref={'path':t['received_images'][0]['file'],'purpose':'variant_main','sku':t['sku']}
   with self.assertRaisesRegex(ValueError,'只允许主图'):pack_sources(store,t,[ref])
 def test_output_cannot_copy_an_original_hidden_inside_an_input_sheet(self):
  from asset_guard import reject_reference
  with tempfile.TemporaryDirectory() as tmp:
   store=ImageRegenerationTests().setup(tmp);self.extras(store);refs=compile_references(store,store.tasks[0],'shared');sheet=next(r for r in refs if r.get('cells'));raw=Path(sheet['cells'][0]['path']).read_bytes()
   with self.assertRaisesRegex(ValueError,'参考图'):reject_reference(raw,refs)
 def test_oversized_evidence_set_fails_without_silent_omission(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=ImageRegenerationTests().setup(tmp);t=store.tasks[0];original=t['main_references'][0];refs=[{**original,'sku':'VAR'+str(n),'purpose':'shared_variant'} for n in range(33)]
   with self.assertRaisesRegex(ValueError,'不会压成小缩略图或遗漏'):pack_sources(store,t,refs)
 def test_changed_original_rejects_claimed_remake_before_overwriting_live_images(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=ImageRegenerationTests().setup(tmp);self.extras(store);before=copy.deepcopy(store.tasks[0]['received_images']);store.image_jobs.create(store.tasks[0]['sku'],'shared_details',[],'');job=store.claim();saved=store.image_jobs.get(job['id']);rows=self.flatten(saved['references']);Path(rows[-1]['path']).write_bytes(picture(222))
   with self.assertRaisesRegex(ValueError,'原始参考图已变化'):store.image_jobs.commit(saved)
   self.assertEqual(store.tasks[0]['received_images'],before)
 def test_queued_request_refreshes_old_prompt_but_dispatched_snapshot_stays_frozen(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=ImageRegenerationTests().setup(tmp);ids=store.image_jobs.create(store.tasks[0]['sku'],'variant_main',[store.tasks[0]['sku']],'深色背景');job=store.image_jobs.get(ids[0]);job['prompt']='LEGACY_FALSE_MATERIAL';job['visual_plan']={'version':1};request=store.claim();self.assertNotIn('LEGACY_FALSE_MATERIAL',request['prompt']);self.assertIn('深色背景',request['prompt']);snapshot=copy.deepcopy(job['prompt']);store.image_jobs.recover(job['id']);self.assertEqual(job['prompt'],snapshot)
if __name__=='__main__':unittest.main()
