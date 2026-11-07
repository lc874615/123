import base64,hashlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from local_bridge import Store,ImageOrderConflict
from listing_bundle import copy_hash
COPY={'sku':'GROUP(1)','title_ru':'Корзины для хранения','description_ru':'Два цвета на выбор.','tags_ru':['#корзины'],'missing_facts':[]}
def encoded(n):
 b=io.BytesIO();Image.new('RGB',(600,800),(n,35,80)).save(b,format='PNG');return base64.b64encode(b.getvalue()).decode()
class Tests(unittest.TestCase):
 def seed(self,root):
  store=Store(root)
  for i in (1,2):
   sku=f'GROUP({i})';store.create_set(sku,'generic');task=store.tasks[-1];task.update(state='saved',copy_leader='GROUP(1)',copy_state='done',video='video',received_images=[{}]*8)
   folder=Path(root)/'products'/sku;folder.mkdir(parents=True)
   (folder/'listing_bundle.json').write_text(json.dumps({'sku':sku,'copy':COPY if i==1 else {'title_ru':None},'blockers':[]}),encoding='utf-8')
  store.save();return store
 def test_startup_repairs_missing_follower_copy_and_message(self):
  with tempfile.TemporaryDirectory() as tmp:
   self.seed(tmp);store=Store(tmp);rows=store.listing_status()
   self.assertTrue(all(r['copy_complete'] and r['shared_copy_matches'] for r in rows));self.assertEqual(rows[0]['copy_hash'],rows[1]['copy_hash'])
   follower=json.loads((Path(tmp)/'products'/'GROUP(2)'/'listing_bundle.json').read_text(encoding='utf-8'))
   self.assertEqual(follower['copy']['sku'],'GROUP(2)');self.assertIn('文案来源：GROUP(1)',store.tasks[1]['message'])
 def test_different_follower_copy_is_backed_up_before_unifying(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=self.seed(tmp);folder=Path(tmp)/'products'/'GROUP(2)';p=folder/'listing_bundle.json';bundle=json.loads(p.read_text());bundle['copy']={**COPY,'sku':'GROUP(2)','title_ru':'Old title'};p.write_text(json.dumps(bundle));store.sync_shared_copies()
   self.assertEqual(len(list(folder.glob('copy_before_shared_sync_*.json'))),1)
   self.assertEqual(json.loads(p.read_text())['copy']['title_ru'],COPY['title_ru'])
 def test_order_repair_backs_up_prefix_preserves_copy_and_accepts_final_eight(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('GROUP(1)','generic');task=store.claim();folder=Path(tmp)/'products'/'GROUP(1)'
   for i in range(3):store.set_result(task['id'],i,encoded(i*20))
   bundle={'sku':'GROUP(1)','copy':COPY,'images':[],'video':{},'blockers':[]};(folder/'listing_bundle.json').write_text(json.dumps(bundle))
   with self.assertRaises(ImageOrderConflict):store.set_result(task['id'],0,encoded(180))
   store.repair_order(task['id']);self.assertEqual(len(list((folder/'auto_recovery').glob('*/images/01_main.png'))),1)
   self.assertEqual(json.loads((folder/'listing_bundle.json').read_text())['copy'],COPY)
   with patch('threading.Thread'):
    for i in range(8):store.set_result(task['id'],i,encoded(100+i*15))
   current=json.loads((folder/'listing_bundle.json').read_text());self.assertEqual(len(current['images']),8);self.assertNotIn('recollection_pending',current);self.assertEqual(current['copy'],COPY)
   self.assertEqual(store.tasks[0]['state'],'saved')
if __name__=='__main__':unittest.main()
