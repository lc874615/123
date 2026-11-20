const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function fixture({old='copy:SKU',bound=true,paused=false}={}){
 let listener;
 const state={pairToken:'fixture',autoEnabled:false,controlSerial:9,...(bound?{autoTab:7,autoUrl:'https://chatgpt.com/c/original'}:{}),activeTask:{id:old,sku:'SKU',tabId:7,copy_phase:'generating'}};
 const control={serial:9,paused,queue_restart:{token:'restart-once',old_id:'OLD',task_id:'NEW',sku:'SKU'}};const sent=[],calls=[];
 const chrome={storage:{local:{get:async()=>structuredClone(state),set:async o=>Object.assign(state,structuredClone(o)),remove:async k=>delete state[k]}},runtime:{onMessage:{addListener:f=>listener=f}},alarms:{onAlarm:{addListener:()=>{}},create:async()=>{}},scripting:{executeScript:async()=>{}},tabs:{get:async id=>{if(!bound&&state.autoTab==null)throw Error('closed');return {id:id??7,url:'https://chatgpt.com/c/original'};},query:async()=>[],sendMessage:async(id,m)=>{sent.push(m.kind);return m.kind==='preflight'?{ready:true,version:'1.0.88'}:{ok:true};}}};
 function load(){const ctx={chrome,URL,AbortSignal,setTimeout:()=>{},clearTimeout,fetch:async(url,options)=>{const body=JSON.parse(options.body);calls.push([url,body]);let value={ok:true};if(url.endsWith('/control'))value=control;if(url.endsWith('/generation-failed'))value={pending:false,restart_count:1,id:'NEW'};if(url.endsWith('/poll'))value={ready:true};if(url.endsWith('/claim'))value={id:'NEW',sku:'SKU',expected_images:8};if(url.endsWith('/task-status'))value={found:true,id:'NEW',sku:'SKU',state:'waiting'};if(url.endsWith('/queue-restart-ack'))control.queue_restart_ack={token:body.token};return {ok:true,json:async()=>structuredClone(value)};}};vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),ctx);return ctx;}
 let ctx=load();return {state,control,sent,calls,command:(m,sender)=>new Promise(r=>listener(m,sender,r)),poll:()=>vm.runInNewContext('poll()',ctx),restart:()=>{ctx=load();}};
}
test('restart command clears stale copy task and enables queue even with unchanged serial',async()=>{
 const f=fixture();await f.poll();assert.equal(f.state.autoEnabled,true);assert.equal(f.state.activeTask.id,'NEW');assert.ok(f.sent.includes('stop'));assert.ok(f.sent.includes('start'));assert.ok(f.calls.some(([p])=>p.endsWith('/queue-restart-ack')));assert.ok(!f.calls.some(([p])=>p.endsWith('/copy-task')||p.endsWith('/copy-result')));
});
test('repeated polling and service-worker restart do not stop or regenerate the new task',async()=>{
 const f=fixture({old:'OLD_IMAGE'});await f.poll();f.restart();await f.poll();assert.equal(f.sent.filter(x=>x==='stop').length,1);assert.equal(f.calls.filter(([p])=>p.endsWith('/claim')).length,1);assert.equal(f.state.activeTask.id,'NEW');
});
test('a paused control cannot be overridden by a queued restart command',async()=>{
 const f=fixture({paused:true});await f.poll();assert.ok(!f.calls.some(([p])=>p.endsWith('/claim')||p.endsWith('/queue-restart-ack')));assert.equal(f.state.autoEnabled,false);
});
test('missing original binding never sends the restarted task into an arbitrary conversation',async()=>{
 const f=fixture({bound:false});await f.poll();assert.ok(!f.calls.some(([p])=>p.endsWith('/claim')));assert.ok(!f.sent.includes('start'));assert.match(f.state.status,/作图页/);
});

test('confirmed generation failure restarts the queue and the plugin starts it without an enable click',async()=>{
 const f=fixture({old:'OLD_IMAGE'});const result=await f.command({kind:'generation-failed',task_id:'OLD_IMAGE',marker:'own',message:'生成失败',reply_finished:true,no_images:true},{tab:{id:7}});assert.ok(result.ok,result.error);assert.equal(f.state.autoEnabled,true);await f.poll();assert.equal(f.state.activeTask.id,'NEW');assert.equal(f.sent.filter(k=>k==='start').length,1);assert.ok(f.calls.some(([p])=>p.endsWith('/generation-failed')));assert.ok(!f.calls.some(([p])=>p.endsWith('/automation-control')));
});
