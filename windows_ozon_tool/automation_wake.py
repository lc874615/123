"""Authenticated HTTP long-poll notifications, no task work under the wait lock."""
import json,secrets,threading,time
class AutomationWake:
 def __init__(self):
  self.condition=threading.Condition();self.epoch=secrets.token_hex(12);self.revision=0;self.signature=None;self.slots=threading.BoundedSemaphore(2);self.waiters=0;self.signalled_at=None;self.delivered_at=None
 def signal(self,signature):
  with self.condition:
   if signature==self.signature:return
   self.signature=signature;self.revision+=1;self.signalled_at=time.time();self.condition.notify_all()
 def wait(self,cursor='',timeout=20):
  if not self.slots.acquire(blocking=False):return {'busy':True,'retry_ms':1000}
  try:
   with self.condition:
    self.waiters+=1
    try:
     current=lambda:self.epoch+':'+str(self.revision)
     self.condition.wait_for(lambda:current()!=cursor,timeout=max(0,min(float(timeout),20)))
     changed=current()!=cursor
     if changed:self.delivered_at=time.time()
     return {'cursor':current(),'changed':changed,'retry_ms':0}
    finally:self.waiters-=1
  finally:self.slots.release()
 def stats(self):
  with self.condition:return {'waiters':self.waiters,'last_signal_at':self.signalled_at,'last_delivery_at':self.delivered_at}

def notify(store):
 wake=getattr(store,'automation_wake',None)
 if wake is None:return
 # Progress messages, heartbeats and acknowledgements must not wake themselves.
 keys=('id','state','copy_state','copy_phase','resume_mode','pause_requested','recollection_requested')
 rows=[[t.get(k) for k in keys] for t in store.tasks]
 jobs=[[t.get(k) for k in keys] for t in getattr(getattr(store,'image_jobs',None),'jobs',[])]
 control=getattr(store,'control',{})
 wake.signal(json.dumps([control.get('command_token'),control.get('paused'),rows,jobs,getattr(store,'competitor_revision',0)],sort_keys=True,separators=(',',':')))

def acknowledge(store,token):
 control=store.control
 if not token or token!=control.get('command_token'):return {'ok':True,'stale':True}
 if (control.get('plugin_ack') or {}).get('token')!=token:
  now=time.time();issued=control.get('issued_at')
  control['plugin_ack']={'token':token,'received_at':now,'delay_ms':max(0,round((now-issued)*1000)) if isinstance(issued,(int,float)) else None}
  store.control_path.write_text(json.dumps(control),encoding='utf-8')
 return {'ok':True,'ack':control['plugin_ack']}
