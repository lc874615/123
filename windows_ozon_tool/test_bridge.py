import base64,io,tempfile,unittest
from pathlib import Path
from PIL import Image
from local_bridge import Store
class Tests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name));self.s.create('TEST','generic product test')
 def tearDown(self):self.tmp.cleanup()
 def test_claim_blocks_duplicate(self):
  self.s.claim()
  with self.assertRaises(ValueError):self.s.claim()
 def test_restart_requires_attention(self):
  self.s.claim();s=Store(self.tmp.name);self.assertEqual(s.tasks[0]['state'],'needs_attention')
 def test_image_review_before_next(self):
  t=self.s.claim();b=io.BytesIO();Image.new('RGB',(768,1024)).save(b,format='PNG');r=self.s.result(t['id'],base64.b64encode(b.getvalue()).decode());self.assertTrue(Path(r['saved']).exists())
  with self.assertRaises(ValueError):self.s.claim()
  self.s.tasks[0]['state']='approved';self.assertNotEqual(self.s.claim()['id'],t['id'])
 def test_invalid_image_and_path(self):
  t=self.s.claim()
  with self.assertRaises(Exception):self.s.result(t['id'],base64.b64encode(b'<html>bad</html>').decode())
  with self.assertRaises(ValueError):self.s.create('../x','x')
 def test_reference_copy_and_transfer(self):
  b=io.BytesIO();Image.new('RGB',(600,700)).save(b,format='PNG');ref=Path(self.tmp.name)/'source.png';ref.write_bytes(b.getvalue())
  other=Store(Path(self.tmp.name)/'new');other.create('REF','generic',[ref]);ref.unlink();task=other.claim()
  self.assertEqual(base64.b64decode(task['references'][0]['base64']),b.getvalue())
 def test_invalid_reference_creates_no_tasks(self):
  other=Store(Path(self.tmp.name)/'bad');ref=Path(self.tmp.name)/'bad.png';ref.write_bytes(b'not an image')
  with self.assertRaises(Exception):other.create('BAD','generic',[ref])
  self.assertEqual(other.tasks,[])
 def test_utf8_restart_under_windows_gbk_default(self):
  from unittest.mock import patch
  original=Path.read_text
  def windows_read(path,encoding=None,errors=None,**kwargs):
   return original(path,encoding=encoding or 'gbk',errors=errors,**kwargs)
  self.s.tasks[0]['message']='中文任务：黑色椅子，等待处理'
  self.s.save()
  with patch.object(Path,'read_text',windows_read):
   restored=Store(self.tmp.name)
  self.assertEqual(restored.tasks[0]['message'],'中文任务：黑色椅子，等待处理')
 def test_utf8_bom_task_file(self):
  self.s.path.write_text(self.s.path.read_text(encoding='utf-8'),encoding='utf-8-sig')
  restored=Store(self.tmp.name)
  self.assertEqual(len(restored.tasks),8)
 def test_retry_requires_exception_state(self):
  t=self.s.claim()
  with self.assertRaises(ValueError):self.s.retry(t['id'])
  self.s.find(t['id'])['state']='needs_attention';self.s.retry(t['id']);self.assertEqual(self.s.claim()['id'],t['id'])
 def test_cancel_old_product_unblocks_new_product(self):
  self.s.tasks[0]['state']='needs_attention';self.s.create('NEW','generic')
  self.s.cancel_product('TEST')
  self.assertEqual(self.s.claim()['sku'],'NEW')
 def test_cancel_rejects_running_task(self):
  self.s.claim()
  with self.assertRaises(ValueError):self.s.cancel_product('TEST')
 def test_set_mode_orders_primary_and_video(self):
  from unittest.mock import patch
  other=Store(Path(self.tmp.name)/'set');other.create_set('SET','generic product');task=other.claim();self.assertTrue(task['set_mode']);self.assertEqual(len(other.tasks),1)
  with patch('threading.Thread') as thread:
   for i in range(8):
    b=io.BytesIO();Image.new('RGB',(600,800),(i*20,0,0)).save(b,format='PNG');other.set_result(task['id'],i,base64.b64encode(b.getvalue()).decode())
   thread.assert_called_once()
  t=other.find(task['id']);self.assertEqual(t['state'],'saved');self.assertEqual(t['received_images'][0]['role'],'primary');self.assertEqual(len(t['received_images']),8)
 def test_set_rejects_wrong_index(self):
  other=Store(Path(self.tmp.name)/'set');other.create_set('SET','generic');task=other.claim()
  with self.assertRaises(ValueError):other.set_result(task['id'],1,'')
 def test_delete_preserves_files_and_blocks_active(self):
  task=self.s.claim()
  with self.assertRaises(ValueError):self.s.delete_task(task['id'])
  self.s.find(task['id'])['state']='cancelled';self.s.delete_task(task['id']);self.assertEqual(len(self.s.tasks),7)
if __name__=='__main__':unittest.main()
