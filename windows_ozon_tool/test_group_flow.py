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

 def test_three_variant_primary_images_stay_distinct_and_seven_details_are_shared(self):
  with tempfile.TemporaryDirectory() as temp:
   store=Store(temp)
   for i in (1,2,3):
    store.create_set(f'GROUP({i})','generic');store.tasks[-1].update(base_article='GROUP',variant_index=i)
   configure(store.tasks,'GROUP')
   with patch('threading.Thread'):
    first=store.claim()
    for i in range(8):
     b=io.BytesIO();Image.new('RGB',(600,800),(i*25,40,80)).save(b,format='PNG');store.set_result(first['id'],i,base64.b64encode(b.getvalue()).decode())
    for color in ('blue','green'):
     task=store.claim();self.assertEqual(task['expected_images'],1)
     b=io.BytesIO();Image.new('RGB',(600,800),color).save(b,format='PNG');store.set_result(task['id'],0,base64.b64encode(b.getvalue()).decode())
   manifests=[json.loads((Path(temp)/'products'/f'GROUP({i})'/'image_manifest.json').read_text(encoding='utf-8')) for i in (1,2,3)]
   self.assertEqual(len({rows[0]['sha256'] for rows in manifests}),3)
   for rows in manifests:
    self.assertEqual(rows[0]['role'],'primary');self.assertEqual(rows[0]['order'],1)
    self.assertEqual([row['sha256'] for row in rows[1:]],[row['sha256'] for row in manifests[0][1:]])

if __name__=='__main__':unittest.main()
