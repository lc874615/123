import tempfile,unittest
from unittest.mock import patch
from local_bridge import Store
from image_retry import reserve,plan,configure
class RetryTests(unittest.TestCase):
 def setup(self,tmp):
  store=Store(tmp);store.create_set('A','灰色椅子，金属');store.set_paused(False);task=store.tasks[0];task.update(state='waiting');return store,task
 def body(self,task):return {'source_marker':plan(task)['recovery_marker'] or '【OZON_TASK:'+task['id']+'】','reply_finished':True,'no_collectable_result':True}
 def test_retry_is_persisted_and_duplicate_reservation_is_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,t=self.setup(tmp);body=self.body(t);r=reserve(store,t['id'],body);self.assertEqual(r['count'],8);self.assertIn('对应图片内容',r['prompt'])
   with self.assertRaises(ValueError):reserve(store,t['id'],body)
   restored=Store(tmp);self.assertEqual(plan(restored.find(t['id']))['recovery_marker'],r['marker'])
 def test_only_missing_positions_and_at_most_two_followups(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,t=self.setup(tmp);t['received_images']=[{},{}];first=reserve(store,t['id'],self.body(t));self.assertEqual((first['offset'],first['count']),(2,6));self.assertNotIn('主图：',first['prompt'])
   second=reserve(store,t['id'],self.body(t));self.assertEqual(second['attempt'],2)
   with self.assertRaises(ValueError):reserve(store,t['id'],self.body(t))
 def test_pause_unknown_result_and_unfinished_reply_do_not_regenerate(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,t=self.setup(tmp);store.set_paused(True)
   with self.assertRaises(ValueError):reserve(store,t['id'],self.body(t))
   store.set_paused(False);t['state']='waiting'
   for key,value in (('source_marker','wrong'),('reply_finished',False),('no_collectable_result',False)):
    body=self.body(t);body[key]=value
    with self.assertRaises(ValueError):reserve(store,t['id'],body)
   self.assertEqual(t.get('image_retry_attempts',[]),[])
 def test_new_full_claim_and_shared_job_request_independent_outputs(self):
  from test_image_regeneration import ImageRegenerationTests
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('A','椅子');store.set_paused(False);task=store.claim();self.assertNotIn('sheet_layout',task);self.assertIn('独立成品交付',task['prompt']);self.assertNotIn('高分辨率3×3',task['prompt'])
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=ImageRegenerationTests().setup(tmp);store.image_jobs.create('CHAIR(1)','shared_details',[],'保留人物');task=store.claim();self.assertNotIn('sheet_layout',task);self.assertEqual(task['delivery_policy'],'independent_images');self.assertIn('保留人物',task['prompt'])
if __name__=='__main__':unittest.main()
