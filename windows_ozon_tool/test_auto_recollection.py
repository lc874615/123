import base64,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from local_bridge import Store
from product_group import configure
from pricing_service import read,write

def picture(index):
 stream=io.BytesIO();Image.new('RGB',(600,800),(index*20,80,100)).save(stream,format='PNG');return base64.b64encode(stream.getvalue()).decode()
COPY={'title_ru':'Стул','description_ru':'Металлический стул','tags_ru':['#стул'],'missing_facts':[]}
class AutoRecollectionTests(unittest.TestCase):
 def make_group(self,tmp):
  store=Store(tmp)
  for i in range(1,4):
   store.create_set('GROUP('+str(i)+')','椅子');task=store.tasks[-1];task.update(base_article='GROUP',variant_index=i,variant_parameters={'name':'椅子','material':'金属'},state='saved',copy_state='done')
  configure(store.tasks,'GROUP')
  for task in store.tasks:
   folder=Path(tmp)/'products'/task['sku'];(folder/'images').mkdir(parents=True);(folder/'images'/'old.png').write_bytes(base64.b64decode(picture(1)));task['received_images']=[{'file':str(folder/'images'/'old.png')}]
   write(folder/'listing_bundle.json',{'sku':task['sku'],'copy':{**COPY,'sku':task['sku']},'copy_source':'GROUP(1)','variant_parameters':task['variant_parameters'],'category':{'confirmed':True,'type_id':10},'price_cny':'200','images':[],'blockers':[]})
  return store
 def test_whole_group_recovers_without_claiming_generation_and_preserves_edits(self):
  with tempfile.TemporaryDirectory() as tmp,patch('local_bridge.threading.Thread'):
   store=self.make_group(tmp);stamp=store.recollect(store.tasks[2]['id'])
   self.assertFalse(store.control['paused']);self.assertEqual([t['resume_mode'] for t in store.tasks],['inspect_only']*3)
   store.sync_shared_copies();self.assertEqual([t['resume_mode'] for t in store.tasks],['inspect_only']*3)
   for task in store.tasks:
    recovered=store.recover(task['sku']);self.assertTrue(recovered['automaticRecovery'])
    for i in range(recovered['expected_images']):store.set_result(task['id'],i,picture(i+1 if task is store.tasks[0] else 9+task['variant_index']))
   self.assertTrue(all(t['state']=='saved' and len(t['received_images'])==8 for t in store.tasks));self.assertFalse(any(t.get('recollection_requested') for t in store.tasks))
   shared=[r['sha256'] for r in store.tasks[0]['received_images'][1:]]
   for task in store.tasks:
    folder=Path(tmp)/'products'/task['sku'];bundle=read(folder/'listing_bundle.json');self.assertEqual(bundle['copy'],{**COPY,'sku':task['sku']});self.assertEqual(bundle['price_cny'],'200');self.assertTrue(bundle['category']['confirmed']);self.assertEqual(len(bundle['images']),8);self.assertTrue((folder/'recovery_backups'/stamp/'images'/'old.png').is_file());self.assertEqual([r['sha256'] for r in task['received_images'][1:]],shared)
 def test_legacy_stuck_backup_is_migrated_without_losing_saved_copy(self):
  with tempfile.TemporaryDirectory() as tmp,patch('local_bridge.threading.Thread'):
   store=self.make_group(tmp);stamp=store.recollect(store.tasks[0]['id'])
   for task in store.tasks:
    task.update(message='已备份旧素材；等待从网页重新采集生成图，不重新发送作图');task.pop('resume_mode',None);(Path(tmp)/'products'/task['sku']/'listing_bundle.json').unlink()
   store.save();restored=Store(tmp)
   for task in restored.tasks:
    self.assertEqual(task['resume_mode'],'inspect_only');self.assertTrue(task['recollection_requested']);bundle=read(Path(tmp)/'products'/task['sku']/'listing_bundle.json');self.assertEqual(bundle['copy']['title_ru'],'Стул');self.assertEqual(bundle['images'],[])
 def test_missing_leader_outputs_are_still_queued_and_automatic_is_explicit(self):
  import shutil
  with tempfile.TemporaryDirectory() as tmp,patch('local_bridge.threading.Thread'):
   store=self.make_group(tmp);leader=store.tasks[0];folder=Path(tmp)/'products'/leader['sku'];shutil.rmtree(folder/'images');(folder/'listing_bundle.json').unlink();leader['received_images']=[]
   store.recollect(store.tasks[2]['id']);self.assertTrue(leader['recollection_requested']);self.assertEqual(store.next_recollection()['sku'],leader['sku'])
   leader.pop('recollection_requested');self.assertTrue(store.recover(leader['sku'],automatic=True)['automaticRecovery'])
 def test_restart_repairs_leader_flag_and_restores_its_previous_draft(self):
  import shutil
  with tempfile.TemporaryDirectory() as tmp,patch('local_bridge.threading.Thread'):
   store=self.make_group(tmp);stamp=store.recollect(store.tasks[0]['id']);leader=store.tasks[0];leader.pop('recollection_requested');leader.update(state='waiting',message='回复已结束，正在核对最终图片交付与编号');(Path(tmp)/'products'/leader['sku']/'listing_bundle.json').unlink();store.save()
   restored=Store(tmp);self.assertEqual(restored.next_recollection()['sku'],leader['sku']);self.assertTrue(restored.tasks[0]['recollection_requested']);self.assertEqual(read(Path(tmp)/'products'/leader['sku']/'listing_bundle.json')['price_cny'],'200')
 def test_unacknowledged_stop_and_running_video_keep_all_original_files(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=self.make_group(tmp);task=store.tasks[0];task.update(pause_requested=True,pause_ack=False)
   with self.assertRaisesRegex(ValueError,'回执'):store.recollect(task['id'])
   task['pause_ack']=True;store.video_running.add(task['sku'])
   with self.assertRaisesRegex(ValueError,'视频'):store.recollect(task['id'])
   self.assertTrue((Path(tmp)/'products'/task['sku']/'images'/'old.png').is_file())
if __name__=='__main__':unittest.main()
