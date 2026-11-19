/* Paired localhost event lane. It asks the existing guarded scheduler to run;
   it never claims tasks, sends prompts, changes binding or approves a listing. */
(()=>{
 function create({api,getState,onWake,onState=async()=>{},sleep=ms=>new Promise(r=>setTimeout(r,ms)),now=()=>Date.now()}){
  let running=false,stopRequested=false,cursor='',failures=0,pending=null;
  async function loop(){
   try{
    while(!stopRequested){
     const s=await getState();if(!s.pairToken)break;
     try{
      const value=await api('/automation-wait',{cursor,auto_enabled:!!s.autoEnabled,bound:s.autoTab!=null||!!s.autoUrl},25000);
      if(stopRequested)break;
      if(value.busy){await sleep(1000);continue;}
      if(typeof value.cursor!=='string'||!value.cursor||typeof value.changed!=='boolean')throw Error('本地事件通道版本不匹配');
      const received=now();failures=0;
      // Notify the scheduler before opening another wait so wakes cannot race
      // a previous poll and disappear. poll() itself coalesces overlapping runs.
      if(value.changed)cursor=value.cursor;
      await onState({wakeState:'connected',wakeLastSeen:received,wakeLastError:''});
      await onWake(value.changed?'change':'recheck');
      // The server holds each unchanged request up to 20s; no rapid idle polling.
     }catch(e){
      if(stopRequested)break;
      failures++;await onState({wakeState:'retrying',wakeLastError:String(e.message||e).slice(0,180)});
      await sleep(Math.min(5000,500*2**Math.min(failures-1,4)));
     }
    }
   }finally{running=false;pending=null;}
  }
  return {
   start(){if(running)return pending;running=true;stopRequested=false;pending=loop();return pending;},
   stop(){stopRequested=true;},
   get running(){return running;}
  };
 }
 globalThis.OzonAutomationWake={create};
})();
