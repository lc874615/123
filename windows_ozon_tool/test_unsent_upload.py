import tempfile,unittest
from local_bridge import Store
class Tests(unittest.TestCase):
 def test_resume_only_exact_unsent_missing_input_failure(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp)
   for sku,message in [('SAFE','未找到图片上传控件，已暂停，未发送任务'),('UNKNOWN','等待回复超时'),('PARTIAL','未找到图片上传控件，已暂停，未发送任务')]:
    store.create_set(sku,'generic');store.tasks[-1].update(state='needs_attention',message=message)
   store.tasks[-1]['received_images']=[{'file':'saved'}]
   result=store.resume_unsent_upload();self.assertEqual(result['resumed'],1);self.assertEqual(store.tasks[0]['state'],'queued');self.assertEqual(store.tasks[1]['state'],'needs_attention');self.assertEqual(store.tasks[2]['state'],'needs_attention')
if __name__=='__main__':unittest.main()
