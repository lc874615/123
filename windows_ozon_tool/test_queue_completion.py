import tempfile,unittest,os
from unittest.mock import patch
import test_image_regeneration as fixtures
from pricing_service import read,write
class Tests(unittest.TestCase):
 def setup(self,tmp):
  store=fixtures.ImageRegenerationTests().setup(tmp);task=store.tasks[0]
  task.update(state='needs_attention',copy_state='done',message='8图、视频、共用俄语文案及草稿已完成；待上架审核')
  write(store.folder/'publications'/'receipt.json',{'id':'receipt','account_id':'mock-shop','created_at':1,'items':{t['sku']:{'on_sale':True} for t in store.tasks}})
  return store,task
 def test_published_historical_blocker_does_not_stop_new_task(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'OZON_CLIENT_ID':'mock-shop'}),patch('image_regeneration.threading.Thread'):
   store,task=self.setup(tmp);store.create_set('NEW','new product');before=dict(task)
   self.assertFalse(store.blockers());self.assertTrue(store.poll_state()['ready']);self.assertEqual(store.claim()['sku'],'NEW');self.assertEqual(task['state'],before['state'])
 def test_published_group_does_not_schedule_optional_attribute_work(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'OZON_CLIENT_ID':'mock-shop'}),patch('image_regeneration.threading.Thread'):
   store,task=self.setup(tmp);task['state']='saved'
   with patch('reference_prefill.needed',return_value=True):self.assertIsNone(store.next_copy())
 def test_new_explicit_work_and_other_account_remain_blocking(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'OZON_CLIENT_ID':'mock-shop'}),patch('image_regeneration.threading.Thread'):
   store,task=self.setup(tmp)
   for fields in ({'recollection_requested':True},{'copy_state':'running'},{'copy_state':'needs_attention','copy_phase':'generating'}):
    old=dict(task);task.update(fields);self.assertTrue(store.blockers());task.clear();task.update(old)
   store.image_jobs.create(task['sku'],'variant_main',[task['sku']],'test');self.assertTrue(store.blockers())
   store.image_jobs.jobs.clear()
   with patch.dict(os.environ,{'OZON_CLIENT_ID':'other-shop'}):self.assertTrue(store.blockers())
 def test_changed_assets_or_newer_receipt_prevent_retirement(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'OZON_CLIENT_ID':'mock-shop'}),patch('image_regeneration.threading.Thread'):
   store,task=self.setup(tmp);path=store.folder/'products'/task['sku']/'listing_bundle.json';b=read(path);b['asset_review']={'copy':True};write(path,b);self.assertTrue(store.blockers())
   b.pop('asset_review');write(path,b);write(store.folder/'publications'/'new.json',{'id':'new','account_id':'mock-shop','created_at':2,'items':{task['sku']:{'on_sale':False}}});self.assertTrue(store.blockers())
 def test_published_saved_optional_error_is_historical_but_not_deleted(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'OZON_CLIENT_ID':'mock-shop'}),patch('image_regeneration.threading.Thread'):
   store,task=self.setup(tmp);task.update(state='saved',copy_mode='attributes',copy_state='needs_attention',copy_phase='inspecting',message='旧属性读取异常')
   before=dict(task);self.assertFalse(store.blockers());self.assertEqual(task,before)
 def test_missing_or_unconfirmed_receipt_never_retires_a_task(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'OZON_CLIENT_ID':'mock-shop'}),patch('image_regeneration.threading.Thread'):
   store,task=self.setup(tmp);p=store.folder/'publications'/'receipt.json';p.write_text('invalid')
   self.assertTrue(store.blockers());p.unlink();self.assertTrue(store.blockers())
 def test_saved_optional_failure_does_not_require_publication_receipt(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store,task=self.setup(tmp);(store.folder/'publications'/'receipt.json').unlink()
   task.update(state='saved',copy_state='needs_attention',copy_mode='attributes',copy_phase='generating',message='旧属性任务异常')
   store.create_set('NEW','new product');before=dict(task)
   self.assertFalse(store.blockers());self.assertTrue(store.poll_state()['ready']);self.assertEqual(task['copy_state'],before['copy_state']);self.assertEqual(task['message'],before['message']);self.assertEqual(task['copy_phase'],before['copy_phase'])
 def test_idle_extension_defers_orphan_optional_request_without_resending(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store,task=self.setup(tmp);task.update(state='saved',copy_state='running',copy_mode='attributes',copy_phase='generating')
   store.create_set('NEW','new product');self.assertTrue(store.blockers())
   self.assertFalse(store.poll_state()['ready']);self.assertEqual(task['copy_state'],'running')
   self.assertTrue(store.poll_state(extension_idle=True)['ready']);self.assertEqual(task['copy_state'],'needs_attention');self.assertEqual(task['copy_phase'],'generating')
   self.assertEqual(store.claim()['sku'],'NEW')
 def test_optional_failure_with_missing_or_stale_copy_still_blocks(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store,task=self.setup(tmp);(store.folder/'publications'/'receipt.json').unlink();task.update(state='saved',copy_state='needs_attention',copy_mode='attributes')
   path=store.folder/'products'/task['sku']/'listing_bundle.json';b=read(path);b['copy']={};write(path,b);self.assertTrue(store.blockers())
   task['copy_mode']='copy';self.assertTrue(store.blockers())
 def test_uncertain_image_remake_recovers_without_requeueing_or_generating(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store,task=self.setup(tmp);store.image_jobs.create(task['sku'],'shared_details',[],'synthetic remake')
   job=store.image_jobs.jobs[0];job.update(state='needs_attention',message='发送结果尚未确认，已保留当前任务；请核对页面回执，不会启动下一任务或重复生成')
   store.poll_state();self.assertEqual(job['resume_mode'],'inspect_only');self.assertEqual(job['state'],'needs_attention');self.assertIsNone(store.image_jobs.next())
   store.set_paused(True);job.pop('resume_mode');store.poll_state();self.assertNotIn('resume_mode',job)

 def test_legacy_optional_bug_retires_while_paused_after_real_asset_audit(self):
  from queue_completion import retire_legacy_attribute_save_error
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store,t=self.setup(tmp);t.update(state='saved',copy_mode='attributes',copy_state='needs_attention',copy_phase='generating',message="'list' object has no attribute 'get'",copy_request_marker='OLD')
   store.set_paused(True);before=read(store.folder/'products'/t['sku']/'listing_bundle.json')
   self.assertTrue(retire_legacy_attribute_save_error(store));self.assertTrue(store.control['paused']);self.assertEqual(t['copy_state'],'done');self.assertEqual(t['attribute_extract_state'],'deferred');self.assertFalse(store.blockers())
   self.assertEqual(read(store.folder/'products'/t['sku']/'listing_bundle.json'),before);self.assertTrue((store.folder/'products'/t['sku']/'attribute_failure_history.json').exists());self.assertFalse(retire_legacy_attribute_save_error(store))
 def test_legacy_error_is_not_retired_when_required_copy_or_image_is_missing(self):
  from queue_completion import retire_legacy_attribute_save_error
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store,t=self.setup(tmp);t.update(state='saved',copy_mode='attributes',copy_state='needs_attention',message="'list' object has no attribute 'get'")
   path=store.folder/'products'/t['sku']/'listing_bundle.json';b=read(path);b['copy']={};write(path,b);self.assertFalse(retire_legacy_attribute_save_error(store));self.assertEqual(t['copy_state'],'needs_attention')

 def test_download_timeout_recovers_existing_request_without_reset_or_generation(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store,t=self.setup(tmp);t.update(state='needs_attention',copy_state=None,message='文件链接读取失败：等待浏览器下载超时；直接读取：文件由网页按钮提供',received_images=[])
   store.set_paused(True);store.repair_uncertain_send_collection();self.assertNotEqual(t.get('resume_mode'),'inspect_only')
   store.set_paused(False);old=t['id'];store.repair_uncertain_send_collection();self.assertEqual(t['id'],old);self.assertEqual(t['state'],'needs_attention');self.assertEqual(t['resume_mode'],'inspect_only');self.assertEqual(t['download_recovery_attempts'],1)
   store.repair_uncertain_send_collection();self.assertEqual(t['download_recovery_attempts'],1)
