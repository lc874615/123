import copy,tempfile,unittest
from unittest.mock import Mock,patch
from local_bridge import Store
from failed_generation import request
from task_alerts import AlertPopup,issue
MESSAGE='本次Ozon主图生成失败，图片生成工具返回错误。因此未能交付01_main.jpg，也没有可用的最终成品下载链接。'
class FailureRestartTests(unittest.TestCase):
 def setup(self,tmp):
  store=Store(tmp);store.create_set('A','灰色椅子');store.set_paused(False);t=store.tasks[0];t['state']='waiting';return store,t
 def body(self,t):return {'marker':'【OZON_TASK:'+t['id']+'】','message':MESSAGE,'reply_finished':True,'no_images':True,'collector_stopped':True}
 def test_definite_failure_restarts_and_persists_command_once(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,t=self.setup(tmp);body=self.body(t);r=request(store,t['id'],body);self.assertFalse(r['pending']);self.assertEqual(r['restart_count'],1);self.assertFalse(store.control['paused']);self.assertEqual(store.control['queue_restart']['task_id'],r['id']);self.assertEqual(store.find(r['id'])['state'],'queued');self.assertEqual(request(store,t['id'],body)['id'],r['id'])
 def test_full_set_failure_wording_resends_as_a_new_queued_instruction(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,t=self.setup(tmp);body=self.body(t)
   body['message']='本次图片生成失败，未能完成要求的8张独立高清Ozon商品图。因此，暂时无法提供01_main.jpg至08_contents.jpg的真实成品下载链接。没有使用简化模板、占位图或原始图片冒充最终成品。图像生成失败'
   result=request(store,t['id'],body);fresh=store.find(result['id'])
   self.assertNotEqual(fresh['id'],t['id']);self.assertEqual(fresh['state'],'queued');self.assertFalse(store.control['paused']);self.assertEqual(store.control['queue_restart']['task_id'],fresh['id'])
 def test_exact_screenshot_failure_restarts_partial_regeneration_job(self):
  import test_image_regeneration as fixture
  with tempfile.TemporaryDirectory() as tmp:
   store=fixture.ImageRegenerationTests().setup(tmp)
   store.image_jobs.create(store.tasks[0]['sku'],'variant_main',[store.tasks[0]['sku']],'')
   task=store.claim();job=store.find(task['id']);body=self.body(job)
   body['message']='本次Ozon主图生成失败，图片生成工具返回错误。因此，暂时无法交付符合要求的01_main.jpg。本次没有生成有效成品文件，因此不提供虚假下载链接。'
   result=request(store,job['id'],body);fresh=store.find(result['id'])
   self.assertEqual(fresh['kind'],'variant_main');self.assertEqual(fresh['state'],'queued');self.assertFalse(store.control['paused']);self.assertEqual(fresh['targets'],job['targets']);self.assertEqual(len(store.tasks[0]['received_images']),8)
 def test_automatic_recollection_failure_restarts_the_matching_source_queue(self):
  import test_image_regeneration as fixture
  with tempfile.TemporaryDirectory() as tmp:
   store=fixture.ImageRegenerationTests().setup(tmp)
   store.image_jobs.create(store.tasks[0]['sku'],'shared_details',[],'保持大特写')
   job=store.image_jobs.jobs[0];job.update(kind='asset_recollection',source_request_id='failed-source',state='waiting')
   body=self.body(job);body['marker']='【OZON_TASK:failed-source】'
   result=request(store,job['id'],body);fresh=store.find(result['id'])
   self.assertEqual(fresh['kind'],'shared_details');self.assertEqual(fresh['expected_images'],7);self.assertEqual(fresh['targets'],job['targets']);self.assertNotIn('source_request_id',fresh)
   self.assertEqual(store.claim()['id'],fresh['id'])
 def test_restart_limit_survives_new_request_ids(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,t=self.setup(tmp)
   for n in range(2):
    result=request(store,t['id'],self.body(t));t=store.find(result['id']);t['state']='waiting'
   with self.assertRaisesRegex(ValueError,'2次'):request(store,t['id'],self.body(t))
   self.assertEqual(t['state'],'waiting')
 def test_unknown_generating_quota_and_wrong_marker_are_not_restart_proof(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,t=self.setup(tmp)
   for key,value in [('message','暂无图片，继续等待'),('message',MESSAGE+'额度不足'),('marker','wrong'),('reply_finished',False),('collector_stopped',False)]:
    b=self.body(t);b[key]=value
    with self.assertRaises(ValueError):request(store,t['id'],b)
   self.assertEqual(t['state'],'waiting');self.assertFalse(store.control['paused'])
 def test_existing_result_and_user_pause_are_preserved(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,t=self.setup(tmp);t['received_images']=[{'sha256':'existing'}]
   with self.assertRaises(ValueError):request(store,t['id'],self.body(t))
   t['received_images']=[];store.set_paused(True)
   with self.assertRaises(ValueError):request(store,t['id'],self.body(t))
 def test_alert_stays_visible_without_grabbing_all_main_window_controls(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Mock();root.winfo_screenwidth.return_value=1600;root.winfo_screenheight.return_value=1000;window=Mock()
   with patch('tkinter.Toplevel',return_value=window),patch('tkinter.ttk.Label'),patch('tkinter.ttk.Frame'),patch('tkinter.ttk.Button'),patch('tkinter.scrolledtext.ScrolledText'):
    popup=AlertPopup(root,tmp+'/alerts.json',Mock());popup.update([issue('A','作图','真实作图异常')]);window.grab_set.assert_not_called();root.grab_current.assert_not_called();window.lift.assert_called()
if __name__=='__main__':unittest.main()
