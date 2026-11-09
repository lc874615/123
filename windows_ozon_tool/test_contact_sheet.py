import base64,io,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from contact_sheet import split,accept,LAYOUT
from image_prompts import sheet_prompt

def sheet(w=2250,h=3000):
 image=Image.new('RGB',(w,h));tw=w//3;th=h//3
 for i in range(9):image.paste((i*23+3,i*17+1,i*11+2),(i%3*tw,i//3*th,(i%3+1)*tw,(i//3+1)*th))
 out=io.BytesIO();image.save(out,'PNG');return out.getvalue(),image
class SheetTests(unittest.TestCase):
 def test_crop_preserves_original_pixels_dimensions_and_order(self):
  raw,image=sheet();values,info=split(raw,7);self.assertEqual(len(values),7);self.assertFalse(info['resized'])
  for i,value in enumerate(values):
   with Image.open(io.BytesIO(value)) as tile:
    self.assertEqual(tile.size,(750,1000));self.assertEqual(tile.tobytes(),image.crop((i%3*750,i//3*1000,(i%3+1)*750,(i//3+1)*1000)).tobytes())
 def test_low_resolution_wrong_grid_and_duplicates_rejected(self):
  for w,h in ((900,1200),(2251,3000),(3000,3000)):
   with self.subTest(size=(w,h)),self.assertRaises(ValueError):split(sheet(w,h)[0],7)
  image=Image.new('RGB',(2250,3000),'white');out=io.BytesIO();image.save(out,'PNG')
  with self.assertRaises(ValueError):split(out.getvalue(),7)
 def test_sheet_contract_does_not_request_independent_files_or_sequential_requests(self):
  for prompt in (sheet_prompt('本品','全组',8),sheet_prompt('本品','全组',7,True)):
   self.assertIn('只生成一张高分辨率3×3整套拼图',prompt);self.assertIn('2250×3000',prompt)
   self.assertNotIn('逐张制作',prompt);self.assertNotIn('逐张下载入口',prompt);self.assertNotIn('不能整套拼成一张',prompt)
 def test_low_resolution_does_not_mutate_existing_images(self):
  from local_bridge import Store
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('A','椅子');task=store.tasks[0];task.update(state='waiting',sheet_layout=LAYOUT);store.set_paused(False)
   with patch.object(store,'set_result') as save,self.assertRaises(ValueError):accept(store,task['id'],base64.b64encode(sheet(900,1200)[0]).decode())
   save.assert_not_called();self.assertEqual(task['received_images'],[])
 def test_adopt_rejects_mixing_partially_saved_legacy_images(self):
  from local_bridge import Store
  from contact_sheet import adopt
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('A','椅子');task=store.tasks[0];task.update(state='waiting',received_images=[{'sha256':'old'}])
   with self.assertRaises(ValueError):adopt(store,task['id'])
   self.assertNotIn('sheet_layout',task)
if __name__=='__main__':unittest.main()
