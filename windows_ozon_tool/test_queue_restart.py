import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from local_bridge import Store
from queue_restart import restart,choose,ready
from pricing_service import read

class RestartTests(unittest.TestCase):
 def test_failed_task_gets_fresh_identity_backup_and_automatic_queue(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('A','椅子');store.create_set('B','桌子');a,b=store.tasks;a.update(state='needs_attention',resume_mode='inspect_only',sheet_layout={'columns':3},image_retry_attempts=[{'request_id':'stale'}]);before=copy.deepcopy(b)
   folder=store.folder/'products'/'A';(folder/'images').mkdir(parents=True);(folder/'images'/'old.txt').write_text('old');old=a['id'];store.set_paused(True)
   result=restart(store,old);fresh=store.find(result['id']);self.assertNotEqual(fresh['id'],old);self.assertEqual(fresh['state'],'queued');self.assertTrue(fresh['auto_batch']);self.assertFalse(store.control['paused']);self.assertNotIn('image_retry_attempts',fresh);self.assertNotIn('sheet_layout',fresh)
   self.assertEqual((Path(result['backup'])/'A'/'images'/'old.txt').read_text(),'old');self.assertFalse((folder/'images').exists());self.assertEqual(store.tasks[1],before);self.assertTrue(store.poll_state()['ready'])
   with self.assertRaises(ValueError):store.find(old)
 def test_live_task_must_ack_pause_before_any_reset(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('A','椅子');task=store.tasks[0];task['state']='waiting';store.set_paused(True);old=task['id']
   self.assertFalse(ready(store,task))
   with self.assertRaises(ValueError):restart(store,old)
   self.assertEqual(task['id'],old);self.assertFalse((store.folder/'queue_restarts').exists())
   task['pause_ack']=True;self.assertTrue(ready(store,task));self.assertEqual(restart(store,old)['old_id'],old)
 def test_backup_failure_leaves_live_queue_and_files_untouched(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('A','椅子');task=store.tasks[0];task['state']='needs_attention';store.set_paused(True);before=copy.deepcopy(task)
   folder=store.folder/'products'/'A';(folder/'images').mkdir(parents=True);(folder/'images'/'old').write_text('keep')
   with patch('queue_restart.shutil.copytree',side_effect=OSError('disk full')),self.assertRaises(OSError):restart(store,task['id'])
   self.assertEqual(task,before);self.assertEqual((folder/'images'/'old').read_text(),'keep')
 def test_failed_shared_job_restarts_original_scope_and_preserves_live_materials(self):
  from test_image_regeneration import ImageRegenerationTests
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=ImageRegenerationTests().setup(tmp);ids=store.image_jobs.create('CHAIR(1)','shared_details',[],'保留人物');job=store.image_jobs.get(ids[0]);job.update(state='needs_attention',image_retry_attempts=[{'request_id':'old'}]);store.set_paused(True)
   rows=[copy.deepcopy(t['received_images']) for t in store.tasks];result=restart(store,store.tasks[0]['id']);fresh=store.image_jobs.get(result['id'])
   self.assertEqual(job['state'],'cancelled');self.assertEqual(fresh['expected_images'],7);self.assertEqual(fresh['targets'],job['targets']);self.assertEqual(fresh['received_images'],[]);self.assertNotIn('image_retry_attempts',fresh);self.assertIn('保留人物',fresh['prompt']);self.assertIn('独立成品交付',fresh['prompt']);self.assertEqual([t['received_images'] for t in store.tasks],rows)
   self.assertTrue(store.poll_state()['ready']);claimed=store.claim();self.assertEqual(claimed['id'],result['id'])
   for sku in result['target_skus']:
    b=read(store.folder/'products'/sku/'listing_bundle.json');self.assertIn(result['id'],b['image_regeneration_jobs']);self.assertNotIn(ids[0],b['image_regeneration_jobs'])
 def test_shared_restart_completes_then_next_queued_variant_is_ready(self):
  from test_image_regeneration import ImageRegenerationTests
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   fixture=ImageRegenerationTests();store=fixture.setup(tmp);store.image_jobs.create('CHAIR(1)','shared_details',[],'');store.set_paused(True);result=restart(store,store.tasks[0]['id']);job=store.claim();fixture.send(store,job,40)
   self.assertEqual(store.image_jobs.get(result['id'])['state'],'saved');store.create_set('NEXT','椅子，金属');self.assertFalse(store.control['paused'])
   action=store.poll_state();self.assertTrue(action['ready'] or action['copy_sku'])
   # Copy has priority when it needs refresh; after that stage the image queue stays enabled.
   with patch.object(store,'next_copy',return_value=None):
    self.assertTrue(store.poll_state()['ready']);self.assertEqual(store.claim()['sku'],'NEXT')
 def test_restart_command_persists_fresh_identity_and_waits_for_plugin_receipt(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('A','椅子');task=store.tasks[0];task['state']='needs_attention';store.set_paused(True);old=task['id'];result=restart(store,old)
   command=store.control['queue_restart'];self.assertEqual(command['task_id'],result['id']);self.assertEqual(command['old_id'],old);self.assertIn('等待插件接收重启请求',store.queue_reason());self.assertEqual(read(store.control_path)['queue_restart'],command)
   store.control['queue_restart_ack']={'token':command['token']};self.assertNotIn('等待插件接收重启请求',store.queue_reason())
if __name__=='__main__':unittest.main()
