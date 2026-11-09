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
