import hashlib,tempfile,unittest
from pathlib import Path
from local_bridge import Store
from pricing_service import read
from composer_cleanup import backup
class CleanupTests(unittest.TestCase):
 def test_owned_automation_draft_is_backed_up_before_clear(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('A','椅子');task=store.tasks[0];text='任务提示词\n【OZON_TASK:'+task['id']+'】';result=backup(store,task['id'],text,['own.png']);saved=read(result['backup']);self.assertEqual(saved['text'],text);self.assertEqual(saved['attachment_labels'],['own.png']);self.assertEqual(task['state'],'queued')
 def test_handwritten_or_other_variant_draft_is_never_authorized_for_clear(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('A','椅子');store.create_set('B','桌子');a,b=store.tasks
   for text in ('我的手写内容','【OZON_TASK:'+b['id']+'】'):
    with self.assertRaises(ValueError):backup(store,a['id'],text,[])
 def test_known_unsent_copy_prompt_from_previous_prepare_can_be_backed_up(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('A','椅子');task=store.tasks[0];text='【OZON_COPY:old】旧文案指令';task['previous_unsent_copy_prompt_hash']=hashlib.sha256(text.encode()).hexdigest();result=backup(store,'copy:A',text,[]);self.assertEqual(read(result['backup'])['text'],text)
 def test_only_explicit_unsent_errors_are_restored_without_restarting_sent_requests(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('A','椅子');store.create_set('B','桌子');a,b=store.tasks;a.update(state='needs_attention',message='未识别到唯一可用发送按钮；提示词已保留，请人工检查。未自动发送');b.update(state='needs_attention',message='发送结果不确定');store.set_paused(False)
   self.assertEqual(store.resume_unsent_upload()['resumed'],1);self.assertEqual(a['state'],'queued');self.assertEqual(b['state'],'needs_attention')
 def test_changed_page_unsent_image_job_requeues_twice_without_touching_uncertain_send(self):
  import test_image_regeneration as fixture
  with tempfile.TemporaryDirectory() as tmp:
   store=fixture.ImageRegenerationTests().setup(tmp);store.image_jobs.create('CHAIR(1)','variant_main',['CHAIR(1)'],'')
   job=store.image_jobs.jobs[0]
   for i in range(3):
    job.update(state='needs_attention',message='输入框内容或页面状态已变化，未发送任务')
    self.assertEqual(store.resume_unsent_upload()['resumed'],1 if i<2 else 0)
   self.assertEqual(job['automatic_unsent_retries'],2)
 def test_finished_previous_variant_in_same_group_does_not_block_next_variant(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('A','椅子');store.create_set('B','椅子');a,b=store.tasks;a.update(copy_leader='A',state='saved');b.update(copy_leader='A',state='claimed')
   result=backup(store,b['id'],'旧同组任务【OZON_TASK:'+a['id']+'】',[]);self.assertTrue(result['ok'])
 def test_exact_markerless_current_prompt_can_be_backed_up(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('A','椅子');t=store.tasks[0];result=backup(store,t['id'],t['prompt'],[]);self.assertTrue(result['ok'])
if __name__=='__main__':unittest.main()
