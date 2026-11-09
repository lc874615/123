import copy,tempfile,unittest
from unittest.mock import patch
from local_bridge import Store
from image_retry import reserve,plan,configure
class RetryTests(unittest.TestCase):
 def test_configuration_disables_automatic_followup_even_for_legacy_tasks(self):
  t={'auto_image_retry':True,'sheet_layout':{'columns':3},'expected_images':7};configure(t);self.assertFalse(t['auto_image_retry']);self.assertFalse(plan(t)['auto_image_retry']);self.assertNotIn('sheet_layout',t)
 def test_retired_endpoint_cannot_create_requests_or_mutate_queue(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('A','椅子');task=store.tasks[0];task['state']='waiting';before=copy.deepcopy(task)
   with self.assertRaisesRegex(ValueError,'自动补图功能已移除'):reserve(store,task['id'],{'reply_finished':True,'no_collectable_result':True,'source_marker':'【OZON_TASK:'+task['id']+'】'})
   self.assertEqual(task,before)
 def test_already_sent_legacy_reply_can_still_be_collected_without_new_generation(self):
  task={'expected_images':7,'auto_image_retry':True,'image_retry_attempts':[{'request_id':'already-sent','count':5,'offset':2}]};value=plan(task)
  self.assertFalse(value['auto_image_retry']);self.assertEqual(value['recovery_marker'],'【OZON_TASK:already-sent】');self.assertEqual((value['collection_expected'],value['collection_offset']),(5,2));self.assertEqual(len(task['image_retry_attempts']),1)
 def test_independent_output_and_manual_restart_remain_available(self):
  from test_image_regeneration import ImageRegenerationTests
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=ImageRegenerationTests().setup(tmp);store.image_jobs.create('CHAIR(1)','shared_details',[],'保留人物');task=store.claim();self.assertFalse(task['auto_image_retry']);self.assertNotIn('sheet_layout',task);self.assertIn('独立成品交付',task['prompt'])
if __name__=='__main__':unittest.main()
