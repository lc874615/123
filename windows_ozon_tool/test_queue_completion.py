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
