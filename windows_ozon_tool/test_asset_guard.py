import base64,io,json,tempfile,unittest
from pathlib import Path
from PIL import Image
from asset_guard import reject_reference
from local_bridge import Store

def png(color,size=(600,800)):
 out=io.BytesIO();Image.new('RGB',size,color).save(out,format='PNG');return out.getvalue()
class Tests(unittest.TestCase):
 def test_reference_rejected_even_if_resized(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'reference.png';path.write_bytes(png('red'));refs=[{'path':str(path)}]
   for data in (path.read_bytes(),png('red',(768,1024))):
    with self.assertRaisesRegex(ValueError,'参考图'):reject_reference(data,refs)
   reject_reference(png('blue'),refs)
 def test_bridge_rejects_reference_without_changing_manifest(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);source=p/'reference.png';source.write_bytes(png('red'));store=Store(p/'data');store.create_set('ITEM','generic',[source]);task=store.claim()
   with self.assertRaisesRegex(ValueError,'参考图'):store.set_result(task['id'],0,base64.b64encode(source.read_bytes()).decode())
   self.assertEqual(store.find(task['id'])['received_images'],[])
 def test_recollection_backs_up_entire_group_and_never_queues_generation(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp)
   for i in (1,2):
    sku=f'GROUP({i})';store.create_set(sku,'generic');task=store.tasks[-1];task.update(state='saved',copy_leader='GROUP(1)',copy_state='done',video='video.mp4',received_images=[{'file':'old'}])
    folder=Path(tmp)/'products'/sku;(folder/'images').mkdir(parents=True);(folder/'images'/'old.png').write_bytes(png('red'));(folder/'listing_bundle.json').write_text('{"copy":{"title_ru":"saved"}}')
   stamp=store.recollect(store.tasks[0]['id'])
   for task in store.tasks:
    folder=Path(tmp)/'products'/task['sku'];self.assertTrue((folder/'recovery_backups'/stamp/'images'/'old.png').exists());self.assertFalse((folder/'images').exists());self.assertEqual(task['state'],'needs_attention');self.assertEqual(task['received_images'],[]);self.assertEqual(task['resume_mode'],'inspect_only');self.assertTrue(task['recollection_requested']);self.assertTrue((folder/'listing_bundle.json').exists());self.assertFalse(store.control['paused'])
 def test_recollection_preserves_ungenerated_variant_queue(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp)
   for i in (1,2):
    store.create_set(f'GROUP({i})','generic');store.tasks[-1]['copy_leader']='GROUP(1)'
   store.tasks[0].update(state='saved',received_images=[{'file':'old'}])
   store.recollect(store.tasks[0]['id'])
   self.assertEqual(store.tasks[0]['state'],'needs_attention');self.assertEqual(store.tasks[1]['state'],'queued')
 def test_recollection_requires_paused_copy(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('ITEM','generic');task=store.tasks[0];task.update(state='saved',copy_state='running')
   with self.assertRaisesRegex(ValueError,'停止'):store.recollect(task['id'])
if __name__=='__main__':unittest.main()
