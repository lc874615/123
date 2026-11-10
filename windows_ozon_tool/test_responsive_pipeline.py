import base64,http.client,json,tempfile,threading,unittest
from unittest.mock import patch
from group_service import GroupService
from local_bridge import Store,server
from test_image_regeneration import picture

class ResponsiveTests(unittest.TestCase):
 def test_image_commit_is_background_and_next_variant_remains_queued(self):
  from test_image_regeneration import ImageRegenerationTests
  with tempfile.TemporaryDirectory() as tmp:
   store=ImageRegenerationTests().setup(tmp);store.render_video=lambda sku:None;store.image_jobs.defer_commits=True
   store.image_jobs.create('CHAIR(1)','variant_main',['CHAIR(1)','CHAIR(2)'],'');task=store.claim();jobs=store.image_jobs;commit=jobs.commit;started=threading.Event();release=threading.Event()
   def slow(job):started.set();release.wait(5);commit(job)
   with patch.object(jobs,'commit',side_effect=slow):
    result=jobs.accept(task['id'],0,base64.b64encode(picture(99)).decode())
    try:
     self.assertTrue(started.wait(2));self.assertFalse(result['complete']);self.assertEqual(jobs.get(task['id'])['state'],'processing')
     service=GroupService.__new__(GroupService);service.lock=store.lock;service.paths=[];self.assertIsNone(service.try_load())
    finally:release.set();jobs._commit_worker.join(5)
   self.assertEqual(jobs.get(task['id'])['state'],'saved');self.assertEqual(store.image_jobs.next()['sku'],'CHAIR(2)');self.assertEqual(store.claim()['sku'],'CHAIR(2)')
 def test_queue_diagnostic_returns_while_material_lock_is_busy(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);httpd=server(store,'fixture',port=0);worker=threading.Thread(target=httpd.serve_forever,daemon=True);worker.start()
   try:
    with store.lock:
     conn=http.client.HTTPConnection('127.0.0.1',httpd.server_address[1],timeout=2)
     conn.request('POST','/queue-diagnostic','{}',{'Host':'127.0.0.1:0','Origin':'chrome-extension://offline','Authorization':'Bearer fixture','Content-Type':'application/json'})
     response=conn.getresponse();value=json.loads(response.read());conn.close();self.assertEqual(response.status,200);self.assertTrue(value['busy'])
   finally:httpd.shutdown();httpd.server_close();worker.join(2)
if __name__=='__main__':unittest.main()

class SharedRegenerationResponsiveTests(unittest.TestCase):
 def test_video_encoders_are_serial_and_waiting_skus_remain_reserved(self):
  import time
  with tempfile.TemporaryDirectory() as tmp:
   from test_image_regeneration import ImageRegenerationTests
   store=ImageRegenerationTests().setup(tmp);entered=[];release=threading.Event();started=threading.Event();guard=threading.Lock();counts=[0,0]
   def encode(files,output):
    with guard:
     counts[0]+=1;counts[1]=max(counts);entered.append(str(output));started.set()
    release.wait(5)
    with guard:counts[0]-=1
    return str(output)
   with patch('video.make_video',side_effect=encode),patch('listing_bundle.refresh_assets'),patch.object(store,'sync_shared_copies'):
    workers=[threading.Thread(target=store.render_video,args=(t['sku'],)) for t in store.tasks]
    try:
     for worker in workers:worker.start()
     self.assertTrue(started.wait(2))
     deadline=time.monotonic()+2
     while len(store.video_running)<3 and time.monotonic()<deadline:time.sleep(.01)
     self.assertEqual(len(store.video_running),3);self.assertEqual(len(entered),1)
     self.assertTrue(store.lock.acquire(timeout=.2));store.lock.release()
    finally:
     release.set()
     for worker in workers:worker.join(5)
    self.assertEqual(len(entered),3);self.assertEqual(counts[1],1);self.assertFalse(store.video_running)
 def test_failed_encoder_releases_slot_for_next_variant(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.tasks=[{'sku':'one','name':'01','set_mode':True,'received_images':[]}]
   with patch('video.make_video',side_effect=ValueError('fixture error')):store.render_video('one')
   self.assertFalse(store.video_running);self.assertTrue(store.video_slots.acquire(blocking=False));store.video_slots.release()
 def test_preview_entry_does_not_wait_on_material_lock(self):
  import ast
  from pathlib import Path
  from types import SimpleNamespace
  source=Path(__file__).with_name('local_bridge.py');tree=ast.parse(source.read_text());fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='listing_editor');module=ast.Module(body=[fn],type_ignores=[])
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);sku='one';folder=store.folder/'products'/sku;folder.mkdir(parents=True);(folder/'listing_bundle.json').write_text('{}');calls=[];labels=[]
   scope={'selected':lambda:{'sku':sku},'DATA':store.folder,'store':store,'root':SimpleNamespace(after=lambda delay,callback:calls.append((delay,callback))),'connection':SimpleNamespace(configure=lambda **kw:labels.append(kw))}
   exec(compile(module,str(source),'exec'),scope)
   with store.lock:scope['listing_editor']()
   self.assertEqual(len(calls),1);self.assertEqual(calls[0][0],250);self.assertIn('其他按钮仍可操作',labels[0]['text'])
 def test_video_command_caps_encoder_threads(self):
  import ast
  from pathlib import Path
  tree=ast.parse(Path(__file__).with_name('video.py').read_text());command=next(n.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='command' for t in n.targets));values=[n.value for n in command.elts if isinstance(n,ast.Constant)]
  self.assertEqual(values[values.index('-threads')+1],'2');self.assertEqual(values[values.index('-frames:v')+1],'240')
