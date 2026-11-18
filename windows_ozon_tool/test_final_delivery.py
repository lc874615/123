import base64,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from local_bridge import Store
from product_group import configure
from image_prompts import generation_prompt,ROLES

def image(n,fmt='PNG'):
 output=io.BytesIO();Image.new('RGB',(600,800),(n,20,50)).save(output,fmt);return base64.b64encode(output.getvalue()).decode()

class Tests(unittest.TestCase):
 def test_copy_starts_after_images_without_waiting_for_video(self):
  with tempfile.TemporaryDirectory() as tmp,patch('threading.Thread'):
   store=Store(tmp);store.create_set('CHAIR(1)','椅子，灰色，单件');task=store.claim()
   for n in range(8):store.set_result(task['id'],n,image(n*20))
   self.assertNotIn('video',task)
   self.assertEqual(store.next_copy()['sku'],'CHAIR(1)')
   draft=json.loads((Path(tmp)/'products'/'CHAIR(1)'/'listing_bundle.json').read_text());self.assertFalse(draft['video']['exists'])
 def test_recover_completed_wrong_eight_requires_full_final_order_repair(self):
  with tempfile.TemporaryDirectory() as tmp,patch('threading.Thread'):
   store=Store(tmp);store.create_set('A','资料');task=store.claim()
   for n in range(8):store.set_result(task['id'],n,image(n*20))
   result=store.recover('A');self.assertTrue(result['orderRepairPending']);self.assertEqual(result['saved_count'],8)
   store.repair_order(task['id'])
   self.assertEqual(store.find(task['id'])['received_images'],[]);self.assertTrue(list((Path(tmp)/'products'/'A'/'auto_recovery').glob('*/images/01_main.png')))
 def test_repair_updates_followers_seven_details_without_replacing_their_main(self):
  with tempfile.TemporaryDirectory() as tmp,patch('threading.Thread'):
   store=Store(tmp)
   for n in (1,2):
    original=Path(tmp)/('original'+str(n)+'.png');original.write_bytes(base64.b64decode(image(240+n)));store.create_set(f'A({n})','资料',[original]);store.tasks[-1].update(base_article='A',variant_index=n)
   configure(store.tasks,'A');leader=store.claim()
   for n in range(8):store.set_result(leader['id'],n,image(n*20))
   follower=store.claim();store.set_result(follower['id'],0,image(190));own=follower['received_images'][0]['sha256']
   old_video=Path(tmp)/'products'/follower['sku']/'video'/'product_8s.mp4';old_video.parent.mkdir();old_video.write_bytes(b'old-video')
   store.recover(leader['sku']);store.repair_order(leader['id'])
   for n in range(8):store.set_result(leader['id'],n,image(n*20+5,'JPEG'))
   self.assertEqual(follower['received_images'][0]['sha256'],own)
   self.assertEqual([r['sha256'] for r in store.find(follower['id'])['received_images'][1:]],[r['sha256'] for r in store.find(leader['id'])['received_images'][1:]])
   self.assertTrue(list((Path(tmp)/'products'/follower['sku']/'shared_gallery_backups').glob('*/images/01_main.png')))
   self.assertEqual(len(list((Path(tmp)/'products'/follower['sku']/'images').iterdir())),8)
   self.assertFalse(old_video.exists());self.assertTrue(list(old_video.parent.parent.glob('shared_gallery_backups/*/video/product_8s.mp4')))
 def test_prompt_contract_uses_originals_only_and_preserves_scope(self):
  prompt=generation_prompt('MANUAL_FALSE_A','MANUAL_FALSE_B')
  self.assertIn('只能交付8张',prompt);self.assertNotIn('MANUAL_FALSE',prompt);self.assertIn('本次附件',prompt);self.assertIn('不提供ZIP',prompt)
  one=generation_prompt('MANUAL_FALSE',expected=1)
  self.assertIn('只能生成和交付1张',one);self.assertIn('01_main.jpg',one);self.assertNotIn('02_dimensions.jpg',one)
 def test_known_unsent_copy_can_continue_but_uncertain_copy_is_not_regenerated(self):
  with tempfile.TemporaryDirectory() as tmp,patch('threading.Thread'):
   store=Store(tmp);store.create_set('A','资料');task=store.claim()
   for n in range(8):store.set_result(task['id'],n,image(n*20))
   actual=store.find(task['id']);actual.update(copy_state='needs_attention',message='已发送但未提取到文案，结果不确定')
   self.assertIsNone(store.next_copy())
   actual['message']='未找到可用发送按钮'
   self.assertEqual(store.next_copy()['sku'],'A')
