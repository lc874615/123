import copy,tempfile,unittest
from unittest.mock import patch
import test_image_regeneration as fixtures
from pricing_service import read,write
from copy_pipeline import prepare,save
class CopySchedulingTests(unittest.TestCase):
 def setup(self,tmp):
  store=fixtures.ImageRegenerationTests().setup(tmp);leader=store.tasks[0];leader.pop('copy_state',None);path=store.folder/'products'/leader['sku']/'listing_bundle.json';b=read(path);b['copy']={'title_ru':None,'description_ru':None,'tags_ru':[]};write(path,b)
  for task in store.tasks[1:]:
   task.update(state='queued',received_images=[]);task.pop('copy_state',None);task.pop('video',None);(store.folder/'products'/task['sku']/'listing_bundle.json').unlink()
  store.save();return store,leader
 def test_first_variant_images_schedule_copy_before_remaining_variants_and_video(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store,leader=self.setup(tmp);leader.pop('video',None);store.video_running.add(leader['sku']);q=store.poll_state();self.assertEqual(q['copy_sku'],leader['sku']);self.assertFalse(q['ready']);self.assertEqual([t['state'] for t in store.tasks],['saved','queued','queued'])
 def test_shared_copy_saves_to_pending_variants_then_queue_continues(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store,leader=self.setup(tmp);self.assertEqual(store.poll_state()['copy_sku'],leader['sku']);task=prepare(store,{'sku':leader['sku']});value={'sku':leader['sku'],'facts_fingerprint':task['fingerprint'],'title_ru':'Стул','description_ru':'Металлический стул','tags_ru':['#стул'],'missing_facts':[]};save(store,{'sku':leader['sku'],'copy':value})
   for follower in store.tasks[1:]:self.assertEqual(read(store.folder/'products'/follower['sku']/'shared_copy.json')['copy']['title_ru'],'Стул')
   q=store.poll_state();self.assertIsNone(q['copy_sku']);self.assertTrue(q['ready']);self.assertEqual(store.claim()['sku'],store.tasks[1]['sku'])
 def test_known_unsent_copy_is_repaired_before_blocker_check(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store,leader=self.setup(tmp);leader.update(copy_state='needs_attention',copy_phase='inspecting',message='图片回复尚未结束，文案等待下一次自动继续',resume_mode='copy_inspect_only');q=store.poll_state();self.assertEqual(q['copy_sku'],leader['sku']);self.assertIsNone(leader.get('copy_state'));self.assertNotIn('resume_mode',leader)
 def test_uncertain_sent_copy_and_user_pause_never_regenerate(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store,leader=self.setup(tmp);leader.update(copy_state='needs_attention',copy_phase='generating',message='文案请求结果未知',resume_mode='copy_inspect_only');self.assertIsNone(store.poll_state()['copy_sku']);self.assertEqual(leader['copy_phase'],'generating');leader.pop('copy_state');store.set_paused(True);q=store.poll_state();self.assertIsNone(q['copy_sku']);self.assertFalse(q['ready'])
 def test_missing_new_group_copy_precedes_old_group_optional_attribute_read(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=fixtures.ImageRegenerationTests().setup(tmp);new=store.tasks[1];new['copy_leader']=new['sku'];new['base_article']='SECOND';new.pop('copy_state',None);path=store.folder/'products'/new['sku']/'listing_bundle.json';b=read(path);b['copy']={};write(path,b);self.assertEqual(store.next_copy()['sku'],new['sku']);self.assertEqual(new['copy_mode'],'copy')
if __name__=='__main__':unittest.main()
