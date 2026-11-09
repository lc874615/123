import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from task_alerts import collect,issue,render,AlertState,ProgressWatch,save_plugin_status,solution
from local_bridge import Store
class AlertTests(unittest.TestCase):
 def test_image_exception_has_chinese_task_and_recovery_steps(self):
  rows=collect([{'id':'T','sku':'SKU(1)','state':'needs_attention','message':'未找到原始作图标记'}],[],[]);text=render(rows);self.assertIn('SKU(1)',text);self.assertIn('中文说明',text);self.assertIn('定位 / 更换作图页',text);self.assertIn('不重新作图',text)
 def test_normal_queue_generation_pause_restart_and_recovery_do_not_popup(self):
  tasks=[{'id':'1','sku':'A','state':'queued'},{'id':'2','sku':'B','state':'waiting','message':'正在生成图片'},{'id':'3','sku':'C','state':'needs_attention','pause_requested':True,'message':'已请求暂停'},{'id':'4','sku':'D','state':'needs_attention','message':'服务已重启，等待自动读取现有网页结果；不重新发送'}];self.assertEqual(collect(tasks,[],[]),[])
 def test_same_exception_is_acknowledged_across_polls_and_restart(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'alerts.json';a=AlertState(path);rows=[issue('A','采图','等待10秒，未找到原图')];self.assertEqual(len(a.update(rows)),1);a.acknowledge([r['key'] for r in rows]);self.assertEqual(a.update(rows),[]);self.assertEqual(AlertState(path).update(rows),[])
 def test_resolved_then_recurred_exception_alerts_again(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=AlertState(Path(tmp)/'a.json');rows=[issue('A','文案','文案读取失败')];a.update(rows);a.acknowledge([rows[0]['key']]);a.update([]);self.assertEqual(len(a.update(rows)),1)
 def test_changed_exception_and_affected_variant_each_remain_visible(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=AlertState(Path(tmp)/'a.json');first=issue('A','文案','文案读取失败');a.update([first]);a.acknowledge([first['key']]);second=issue('B','文案','文案读取失败');self.assertEqual(a.update([first,second]),[second])
 def test_unknown_import_does_not_advise_blind_retry(self):
  rows=collect([],[],[{'state':'import_uncertain','message':'response lost','items':{'A':{'status':'timeout'}}}]);text=render(rows);self.assertIn('请求结果尚未确认',text);self.assertIn('不要重新创建',text);self.assertIn('明确确认未受理',text)
 def test_barcode_stock_and_warehouse_errors_have_relevant_solutions(self):
  self.assertIn('Barcode',render([issue('A','上架','条形码 HTTP 403')]));self.assertIn('仓库',solution('WAREHOUSE_BLOCKED')[0]);self.assertIn('不重置库存',render([issue('A','库存','库存写入失败')]))
 def test_hosting_pending_failure_is_reported_but_waiting_is_normal(self):
  b={'sku':'A','hosting':{'state':'pending','message':'COS AccessDenied'}};self.assertEqual(len(collect([],[b],[])),1);b['hosting']={'state':'waiting','message':'等待8张图片'};self.assertEqual(collect([],[b],[]),[])
 def test_platform_warning_and_normal_creation_wait_are_not_failures(self):
  job={'state':'waiting_creation','items':{'A':{'import_state':'imported','platform_errors':[{'level':'WARNING','message':'quality warning'}]}}};self.assertEqual(collect([],[],[job]),[])
 def test_plugin_error_forwarding_is_persisted_sanitized_and_clearable(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'OZON_API_KEY':'private-test-key'}):
   store=Store(tmp);save_plugin_status(store,{'error':True,'message':'未找到输入框 private-test-key https://example.test/a?token=secret','sku':'A'});text=render(collect([],[],[],plugin=store.plugin_status));self.assertNotIn('private-test-key',text);self.assertNotIn('token=secret',text);self.assertIn('A',text);save_plugin_status(store,{'error':False,'message':'任务已恢复'});self.assertEqual(collect([],[],[],plugin=store.plugin_status),[])
 def test_progress_watch_only_alerts_long_stall_and_offline_active_work(self):
  watch=ProgressWatch();tasks=[{'id':'1','sku':'A','state':'waiting','received_images':[]}];self.assertEqual(watch.update(tasks,{'last_seen':1000},False,1000),[]);rows=watch.update(tasks,{'last_seen':2200},False,2200);self.assertTrue(any(r['stage']=='进度停滞' for r in rows));tasks[0]['received_images']=[{}];self.assertEqual(watch.update(tasks,{'last_seen':2201},False,2201),[]);self.assertEqual(watch.update(tasks,{},True,4000),[])
 def test_queued_work_without_plugin_has_grace_period_and_no_idle_alert(self):
  watch=ProgressWatch();tasks=[{'id':'Q','sku':'A','state':'queued','auto_batch':True}];self.assertEqual(watch.update(tasks,{},False,1000),[]);self.assertTrue(watch.update(tasks,{},False,1091));self.assertEqual(watch.update([],{},False,1200),[])
 def test_bad_alert_state_file_does_not_crash_startup(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'a.json';path.write_text('[]');self.assertEqual(AlertState(path).acked,set());(Path(tmp)/'plugin_status.json').write_text('[]');self.assertEqual(Store(tmp).plugin_status,{})
 def test_new_task_with_same_sku_and_error_is_a_new_incident(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=AlertState(Path(tmp)/'a.json');task={'id':'OLD','sku':'A','state':'needs_attention','message':'未找到原图'};first=collect([task],[],[]);a.update(first);a.acknowledge([first[0]['key']]);task['id']='NEW';self.assertTrue(a.update(collect([task],[],[])))
 def test_rejected_group_displays_actual_api_error_instead_of_waiting_status(self):
  rows=collect([],[],[{'id':'J','state':'rejected','message':'HTTP 403 forbidden','items':{'A':{'status':'等待提交'}}}]);text=render(rows);self.assertIn('403',text);self.assertIn('访问权限',text)
  query={'id':'J','state':'importing','retry_count':1,'message':'安全查询待重试：network timeout','items':{'A':{'status':'等待创建'}}};self.assertIn('network timeout',render(collect([],[],[query])))
 def test_invalid_manual_price_alerts_but_valid_low_margin_warning_does_not(self):
  b={'sku':'A','manual_price':True,'manual_pricing':{'valid':False,'message':'包装尺寸超出物流上限'}};self.assertTrue(collect([],[b],[]));b['manual_pricing']={'valid':True,'warning':'低于目标净利润率'};self.assertEqual(collect([],[b],[]),[])
 def test_old_failed_receipt_is_not_alerted_after_newer_success_or_stop(self):
  old={'id':'OLD','created_at':1,'state':'failed','message':'old failure','items':{'A':{'import_state':'failed'}}};new={'id':'NEW','created_at':2,'state':'on_sale','items':{'A':{'import_state':'imported','on_sale':True}}};self.assertEqual(collect([],[],[old,new]),[]);new['state']='cancelled_followup';self.assertEqual(collect([],[],[old,new]),[])
 def test_certificate_and_creation_messages_are_explained_in_chinese(self):
  self.assertIn('证书',solution('SSL CERTIFICATE_VERIFY_FAILED')[0]);self.assertIn('平台商品创建尚未完成',solution('product creation incomplete')[0])
if __name__=='__main__':unittest.main()
