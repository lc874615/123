import base64,copy,hashlib,io,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from local_bridge import Store
from product_group import configure
from pricing_service import read,write

def picture(n,fmt='PNG'):
 s=io.BytesIO();Image.new('RGB',(600,800),(n*9%255,40+n%50,80)).save(s,format=fmt);return s.getvalue()
class ImageRegenerationTests(unittest.TestCase):
 def test_main_prompt_uses_only_this_variant_and_locks_original_structure(self):
  from image_prompts import generation_prompt,shared_prompt
  prompt=generation_prompt('灰色椅子，数量1','OTHER_RED_VARIANT',1)
  self.assertNotIn('OTHER_RED_VARIANT',prompt);self.assertIn('灰色椅子',prompt);self.assertIn('抠图合成',prompt);self.assertIn('扶手有无',prompt);self.assertIn('2—4',prompt);self.assertIn('01—07',shared_prompt('真实全组参数'))
 def setup(self,tmp):
  store=Store(tmp)
  for i in range(1,4):
   original=Path(tmp)/('ref'+str(i)+'.png');original.write_bytes(picture(100+i));store.create_set('CHAIR('+str(i)+')','椅子，金属，数量1',[original]);t=store.tasks[-1];t.update(base_article='CHAIR',variant_index=i,state='saved',copy_state='done',variant_parameters={'name':'椅子','material':'金属','quantity':'1','color':['灰色','红色','米色'][i-1]});t['main_references']=copy.deepcopy(t['references'])
  configure(store.tasks,'CHAIR')
  for i,t in enumerate(store.tasks):
   folder=store.folder/'products'/t['sku'];(folder/'images').mkdir();rows=[]
   for k in range(8):
    raw=picture(1+i*10 if k==0 else k+1);path=folder/'images'/('%02d_old.png'%(k+1));path.write_bytes(raw);rows.append({'file':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'order':k+1,'role':'primary' if k==0 else 'gallery'})
   t['received_images']=rows;t['video']=str(folder/'video'/'product_8s.mp4');(folder/'video').mkdir();(folder/'video'/'product_8s.mp4').write_bytes(b'old-video');write(folder/'image_manifest.json',rows)
   write(folder/'listing_bundle.json',{'sku':t['sku'],'variant_parameters':t['variant_parameters'],'facts':t['facts'],'images':[{'order':r['order'],'role':r['role'],'local_file':'images/'+Path(r['file']).name,'sha256':r['sha256'],'https_url':'https://example.com/'+str(r['order'])+'.png'} for r in rows],'copy':{'sku':t['sku'],'title_ru':'Стул','description_ru':'Описание','tags_ru':['#стул'],'missing_facts':[]},'copy_source':'CHAIR(1)','price_cny':'123','category':{'confirmed':True},'blockers':[],'hosting':{'state':'done'}})
  store.save();return store
 def send(self,store,job,start=30):
  for k in range(job['expected_images']):result=store.set_result(job['id'],k,base64.b64encode(picture(start+k)).decode())
  return result
 def test_shared_seven_replace_all_details_and_preserve_every_main_and_copy(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=self.setup(tmp);before=[copy.deepcopy(t['received_images']) for t in store.tasks];ids=store.image_jobs.create('CHAIR(2)','shared_details',[],'详情场景增加人物使用');self.assertEqual(len(ids),1)
   self.assertTrue(all(t['received_images']==b for t,b in zip(store.tasks,before)));job=store.claim();self.assertEqual(job['expected_images'],7);self.assertIn('详情场景增加人物使用',job['prompt']);self.assertTrue(job['image_job'])
   self.assertTrue(self.send(store,job)['complete'])
   for n,t in enumerate(store.tasks):
    self.assertEqual(t['received_images'][0],before[n][0] if before[n][0].get('generation_task_id') else {**before[n][0],'generation_task_id':t['id'],'source_index':0,'source_expected':8 if n==0 else 1})
    self.assertFalse((store.folder/'products'/t['sku']/'images'/'02_old.png').exists());b=read(store.folder/'products'/t['sku']/'listing_bundle.json');self.assertEqual(b['copy']['title_ru'],'Стул');self.assertEqual(b['price_cny'],'123');self.assertFalse(b['image_regeneration_jobs']);self.assertEqual(b['hosting']['state'],'pending')
   self.assertEqual(len({tuple(r['sha256'] for r in t['received_images'][1:]) for t in store.tasks}),1)
 def test_selected_mains_only_use_own_references_and_other_assets_remain(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=self.setup(tmp);before=copy.deepcopy(store.tasks);ids=store.image_jobs.create('CHAIR(1)','variant_main',['CHAIR(1)','CHAIR(3)'],'大标题并保留原椅腿造型');self.assertEqual(len(ids),2)
   for n in range(2):
    job=store.claim();self.assertEqual(job['expected_images'],1);self.assertTrue(all(r['name'].startswith(job['sku']) for r in job['references']));self.assertIn('大标题并保留原椅腿造型',job['prompt']);self.send(store,job,40+n)
   self.assertEqual(store.tasks[1]['received_images'],before[1]['received_images'])
   for n in (0,2):
    self.assertNotEqual(store.tasks[n]['received_images'][0]['sha256'],before[n]['received_images'][0]['sha256']);self.assertEqual([r['sha256'] for r in store.tasks[n]['received_images'][1:]],[r['sha256'] for r in before[n]['received_images'][1:]])
 def test_interruption_never_resends_and_originals_survive_until_all_seven(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=self.setup(tmp);old=copy.deepcopy(store.tasks[0]['received_images']);store.image_jobs.create('CHAIR(1)','shared_details',[],'');job=store.claim();store.set_result(job['id'],0,base64.b64encode(picture(30)).decode());restored=Store(tmp)
   self.assertEqual(restored.image_jobs.get(job['id'])['resume_mode'],'inspect_only');self.assertIsNone(restored.image_jobs.next());self.assertEqual(restored.tasks[0]['received_images'],old);result=restored.image_jobs.recover(job['id']);self.assertEqual(result['expected_images'],7);self.assertTrue(result['image_job']);self.assertTrue(self.send(restored,job)['complete'])
 def test_changed_parameters_block_replacement_and_duplicate_scope_is_rejected(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=self.setup(tmp);store.image_jobs.create('CHAIR(1)','variant_main',['CHAIR(2)'],'')
   with self.assertRaises(ValueError):store.image_jobs.create('CHAIR(1)','variant_main',['CHAIR(2)'],'again')
   job=store.claim();path=store.folder/'products'/'CHAIR(2)'/'listing_bundle.json';b=read(path);b['variant_parameters']['color']='蓝色';write(path,b);old=copy.deepcopy(store.tasks[1]['received_images']);result=self.send(store,job);self.assertFalse(result['complete']);self.assertEqual(store.tasks[1]['received_images'],old);self.assertEqual(store.image_jobs.get(job['id'])['state'],'needs_attention')
 def test_write_failure_rolls_forward_without_another_generation_request(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=self.setup(tmp);store.image_jobs.create('CHAIR(1)','shared_details',[],'');job=store.claim();original_write=write;failed=[False]
   def disk_failure(path,value):
    if Path(path).name=='image_manifest.json' and 'CHAIR(2)' in str(path) and not failed[0]:failed[0]=True;raise OSError('synthetic interrupted write')
    return original_write(path,value)
   with patch('image_regeneration.write',side_effect=disk_failure):result=self.send(store,job)
   self.assertFalse(result['complete']);self.assertEqual(store.image_jobs.get(job['id'])['state'],'committing');self.assertIsNone(store.image_jobs.next());store.image_jobs.tick();self.assertEqual(store.image_jobs.get(job['id'])['state'],'saved');self.assertEqual(len({tuple(r['sha256'] for r in t['received_images'][1:]) for t in store.tasks}),1)
 def test_cancel_before_commit_keeps_original_images_and_copy(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=self.setup(tmp);before=copy.deepcopy(store.tasks[0]['received_images']);store.image_jobs.create('CHAIR(1)','shared_details',[],'');self.assertEqual(store.image_jobs.cancel(['CHAIR(1)']),1);self.assertEqual(store.tasks[0]['received_images'],before);self.assertFalse(read(store.folder/'products'/'CHAIR(1)'/'listing_bundle.json')['image_regeneration_jobs'])
 def test_partial_provenance_recollection_uses_original_requests_without_regenerating(self):
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=self.setup(tmp);store.image_jobs.create('CHAIR(1)','shared_details',[],'');detail=store.claim();self.send(store,detail,30);store.image_jobs.create('CHAIR(1)','variant_main',['CHAIR(1)'],'');main=store.claim();self.send(store,main,50)
   expected=[[r['sha256'] for r in t['received_images']] for t in store.tasks];store.recollect(store.tasks[0]['id']);self.assertIsNone(store.image_jobs.next());jobs=store.image_jobs.active([t['sku'] for t in store.tasks]);self.assertTrue(all(j['kind']=='asset_recollection' for j in jobs))
   sources={detail['id']:[picture(30+i) for i in range(7)],main['id']:[picture(50)],store.tasks[1]['id']:[picture(11)],store.tasks[2]['id']:[picture(21)]}
   for job in jobs:
    recovered=store.image_jobs.recover(job['id']);self.assertIn(job['source_request_id'],recovered['source_marker'])
    for i,raw in enumerate(sources[job['source_request_id']]):store.set_result(job['id'],i,base64.b64encode(raw).decode())
   self.assertEqual([[r['sha256'] for r in t['received_images']] for t in store.tasks],expected)
   recovered=store.recover('CHAIR(1)',automatic=True);self.assertTrue(recovered['image_job']);self.assertEqual(recovered['expected_images'],1);self.assertIn(main['id'],recovered['source_marker'])
if __name__=='__main__':unittest.main()
