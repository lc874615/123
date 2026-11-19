import http.client,json,tempfile,threading,time,unittest
from local_bridge import Store,server
from automation_wake import AutomationWake,acknowledge
class WakeTests(unittest.TestCase):
 def test_signal_before_wait_and_server_restart_cannot_be_lost(self):
  wake=AutomationWake();first=wake.wait('',0);wake.signal('created');r=wake.wait(first['cursor'],0);self.assertTrue(r['changed']);self.assertNotEqual(r['cursor'],first['cursor']);self.assertTrue(AutomationWake().wait(r['cursor'],0)['changed'])
 def test_messages_and_acknowledgements_do_not_cause_wake_loops(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('A','synthetic');first=store.automation_wake.wait('',0);store.tasks[0]['message']='new progress only';store.save();self.assertFalse(store.automation_wake.wait(first['cursor'],.01)['changed']);store.set_paused(False);second=store.automation_wake.wait(first['cursor'],0);self.assertTrue(second['changed']);acknowledge(store,store.control['command_token']);self.assertFalse(store.automation_wake.wait(second['cursor'],.01)['changed'])
 def test_pause_resume_and_image_job_states_signal(self):
  from test_image_regeneration import ImageRegenerationTests
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=ImageRegenerationTests().setup(tmp);cursor=store.automation_wake.wait('',0)['cursor'];store.image_jobs.create(store.tasks[0]['sku'],'variant_main',[store.tasks[0]['sku']],'');r=store.automation_wake.wait(cursor,0);self.assertTrue(r['changed']);store.set_paused(True);self.assertTrue(store.automation_wake.wait(r['cursor'],0)['changed'])
 def test_command_ack_is_bound_to_current_token_and_measures_server_clock(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.set_paused(False);token=store.control['command_token'];result=acknowledge(store,token);self.assertGreaterEqual(result['ack']['delay_ms'],0);self.assertEqual(acknowledge(store,token),result);store.set_paused(True);self.assertTrue(acknowledge(store,token)['stale']);self.assertNotIn('plugin_ack',store.control)
 def post(self,httpd,path,body,token='fixture'):
  conn=http.client.HTTPConnection('127.0.0.1',httpd.server_address[1],timeout=3);conn.request('POST',path,json.dumps(body),{'Host':'127.0.0.1:0','Origin':'chrome-extension://offline','Authorization':'Bearer '+token,'Content-Type':'application/json'});r=conn.getresponse();value=json.loads(r.read());code=r.status;conn.close();return code,value
 def test_http_event_delivery_is_fast_without_holding_business_lock(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);httpd=server(store,'fixture',port=0);thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start();result=[]
   try:
    _,first=self.post(httpd,'/automation-wait',{'cursor':''});reader=threading.Thread(target=lambda:result.append(self.post(httpd,'/automation-wait',{'cursor':first['cursor'],'auto_enabled':True,'bound':True})));reader.start()
    deadline=time.monotonic()+2
    while store.automation_wake.stats()['waiters']<1 and time.monotonic()<deadline:threading.Event().wait(.005)
    self.assertEqual(store.automation_wake.stats()['waiters'],1)
    t=time.monotonic();self.assertEqual(self.post(httpd,'/health',{})[0],200);self.assertLess(time.monotonic()-t,1)
    t=time.monotonic()
    with store.lock:store.set_paused(False)
    reader.join(1.5);self.assertFalse(reader.is_alive());self.assertTrue(result[0][1]['changed']);self.assertLess(time.monotonic()-t,1.5);self.assertIn('事件通道',store.queue_reason())
   finally:store.automation_wake.signal('cleanup');httpd.shutdown();httpd.server_close();thread.join(2)
 def test_wait_requires_pairing_and_does_not_wait_on_business_lock(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);httpd=server(store,'fixture',port=0);thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
   try:
    with store.lock:
     code,_=self.post(httpd,'/automation-wait',{'cursor':''},'wrong');self.assertEqual(code,403)
     code,value=self.post(httpd,'/automation-wait',{'cursor':''});self.assertEqual(code,200);self.assertTrue(value['changed'])
   finally:httpd.shutdown();httpd.server_close();thread.join(2)
 def test_waiter_count_is_bounded_and_duplicate_signals_do_not_advance(self):
  wake=AutomationWake();wake.signal('same');cursor=wake.wait('',0)['cursor'];wake.signal('same');self.assertFalse(wake.wait(cursor,.01)['changed']);self.assertTrue(wake.slots.acquire(False));self.assertTrue(wake.slots.acquire(False))
  try:self.assertTrue(wake.wait(cursor,0)['busy'])
  finally:wake.slots.release();wake.slots.release()
if __name__=='__main__':unittest.main()
