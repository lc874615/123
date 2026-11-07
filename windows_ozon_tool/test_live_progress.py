import base64,io,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from local_bridge import Store,task_view
class Tests(unittest.TestCase):
 def test_each_received_image_is_on_disk_and_visible_before_batch_completion(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('LIVE(1)','generic');task=store.claim()
   with patch('threading.Thread'):
    for index in range(8):
     output=io.BytesIO();Image.new('RGB',(600,800),(index*25,50,60)).save(output,format='PNG')
     store.set_result(task['id'],index,base64.b64encode(output.getvalue()).decode())
     current=store.find(task['id']);values=task_view(current)
     self.assertIn(f'{index+1}/8',values[1]);self.assertIn(f'{index+1}/8',values[2]);self.assertEqual(len(list((Path(tmp)/'products'/'LIVE(1)'/'images').iterdir())),index+1)
     self.assertEqual(current['state'],'saved' if index==7 else 'waiting')
 def test_upload_and_read_stage_messages_are_visible(self):
  task={'sku':'LIVE','set_mode':True,'state':'waiting','received_images':[],'message':'正在读取原图 2/8'}
  self.assertIn('正在读取原图 2/8',task_view(task)[2])
  task['message']='正在自动上传 01.jpg';self.assertIn('自动上传',task_view(task)[2])
if __name__=='__main__':unittest.main()
