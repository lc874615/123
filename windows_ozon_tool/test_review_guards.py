import base64,io,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from category_match import commit
from local_bridge import Store
from product_group import configure
class Tests(unittest.TestCase):
 def test_confirmed_category_cannot_be_overwritten_by_late_suggestion(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'listing_bundle.json';value={'copy':{'title_ru':'Корзины'},'category':{'description_category_id':9,'type_id':10,'confirmed':True}}
   path.write_text(json.dumps(value),encoding='utf-8');self.assertFalse(commit(path,'корзины',{'category':{'confirmed':False}},threading.Lock()));self.assertEqual(json.loads(path.read_text()),value)
 def test_stale_title_result_is_ignored(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'listing_bundle.json';value={'copy':{'title_ru':'Другой товар'}};path.write_text(json.dumps(value),encoding='utf-8');self.assertFalse(commit(path,'корзины',{'category':{}},threading.Lock()));self.assertEqual(json.loads(path.read_text()),value)
 def test_category_merge_preserves_current_copy_and_edits(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'listing_bundle.json';value={'copy':{'title_ru':'Корзины','description_ru':'Latest copy'},'price_cny':200};path.write_text(json.dumps(value),encoding='utf-8');self.assertTrue(commit(path,'корзины',{'category':{'confirmed':False,'type_id':10}},threading.Lock()));data=json.loads(path.read_text());self.assertEqual(data['copy'],value['copy']);self.assertEqual(data['price_cny'],200)
 def test_real_asset_audit_and_shared_detail_match(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp)
   for i in (1,2):
    store.create_set(f'AUDIT({i})','generic');store.tasks[-1].update(base_article='AUDIT',variant_index=i)
   configure(store.tasks,'AUDIT')
   def encoded(color):
    b=io.BytesIO();Image.new('RGB',(600,800),color).save(b,format='PNG');return base64.b64encode(b.getvalue()).decode()
   with patch('threading.Thread'):
    first=store.claim()
    for i in range(8):store.set_result(first['id'],i,encoded((i*25,20,80)))
    second=store.claim();store.set_result(second['id'],0,encoded('blue'))
   rows=store.listing_status();self.assertTrue(all(row['image_files_verified'] and row['shared_gallery_matches'] for row in rows));self.assertNotEqual(rows[0]['primary_hash'],rows[1]['primary_hash'])
   (Path(tmp)/'products'/'AUDIT(2)'/'images'/'02_dimensions.png').write_bytes(b'changed')
   rows=store.listing_status();self.assertTrue(rows[0]['image_files_verified']);self.assertFalse(rows[1]['image_files_verified'])
 def test_shared_details_retry_does_not_leave_partial_gallery(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp)
   for i in (1,2):
    store.create_set(f'RETRY({i})','generic');store.tasks[-1].update(base_article='RETRY',variant_index=i)
   configure(store.tasks,'RETRY')
   def encoded(n):
    b=io.BytesIO();Image.new('RGB',(600,800),(n,50,80)).save(b,format='PNG');return base64.b64encode(b.getvalue()).decode()
   with patch('threading.Thread'):
    first=store.claim()
    for i in range(8):store.set_result(first['id'],i,encoded(i*25))
    path=Path(tmp)/'products'/'RETRY(1)'/'images'/'06_structure.png';original=path.read_bytes();path.write_bytes(b'changed')
    second=store.claim()
    with self.assertRaisesRegex(ValueError,'共用详情'):store.set_result(second['id'],0,encoded(240))
    self.assertEqual(len(store.find(second['id'])['received_images']),1)
    path.write_bytes(original);result=store.set_result(second['id'],0,encoded(240));self.assertTrue(result['complete']);self.assertEqual(result['saved_count'],8)
if __name__=='__main__':unittest.main()
