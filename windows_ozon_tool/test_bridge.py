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
if __name__=='__main__':unittest.main()
