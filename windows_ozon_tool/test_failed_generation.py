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
