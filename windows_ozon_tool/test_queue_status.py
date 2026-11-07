import tempfile,time,unittest
from local_bridge import Store
class Tests(unittest.TestCase):
 def test_new_task_has_waiting_message(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('NEW','generic')
   self.assertEqual(store.tasks[0]['state'],'queued');self.assertEqual(store.tasks[0]['message'],'等待扩展领取任务')
 def test_connection_and_auto_mode_are_explained(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);self.assertIn('等待扩展连接',store.queue_reason())
   store.client={'last_seen':time.time(),'auto_enabled':False};self.assertIn('未启用',store.queue_reason())
   store.client['auto_enabled']=True;self.assertIn('等待下一次轮询',store.queue_reason())
 def test_old_uncertain_task_is_identified_and_never_silently_removed(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('OLD','generic');old=store.claim();store.find(old['id']).update(state='needs_attention',message='尚未保存生成图');store.create_set('NEW','generic')
   self.assertIn('OLD',store.queue_reason());self.assertIn('尚未保存生成图',store.queue_reason());self.assertEqual(store.blockers()[0]['id'],old['id']);self.assertEqual(len(store.tasks),2)
   self.assertFalse(store.task_status('deleted-id')['found']);self.assertEqual(store.task_status(old['id'])['state'],'needs_attention')
if __name__=='__main__':unittest.main()
