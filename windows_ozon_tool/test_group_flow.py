import base64,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from local_bridge import Store
from product_group import configure
class Tests(unittest.TestCase):
 def test_secondary_one_image_produces_eight_and_completes(self):
  with tempfile.TemporaryDirectory() as temp:
   store=Store(temp)
   for i in (1,2):
    store.create_set(f'ITEM({i})','generic product');t=store.tasks[-1];t.update(base_article='ITEM',variant_index=i)
   configure(store.tasks,'ITEM');first=store.claim()
   with patch('threading.Thread'):
    for i in range(8):
     out=io.BytesIO();Image.new('RGB',(600,800),(i*25,10,10)).save(out,format='PNG');store.set_result(first['id'],i,base64.b64encode(out.getvalue()).decode())
    second=store.claim();self.assertEqual(second['expected_images'],1)
    out=io.BytesIO();Image.new('RGB',(600,800),'blue').save(out,format='PNG');result=store.set_result(second['id'],0,base64.b64encode(out.getvalue()).decode())
   self.assertTrue(result['complete']);self.assertEqual(result['saved_count'],8)
   a=store.tasks[0]['received_images'];b=store.tasks[1]['received_images'];self.assertNotEqual(a[0]['sha256'],b[0]['sha256']);self.assertEqual([r['sha256'] for r in a[1:]],[r['sha256'] for r in b[1:]])
if __name__=='__main__':unittest.main()
