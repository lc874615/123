const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function fixture(){let listener,remote='processing',pageBusy=false;const state={pairToken:'fixture',autoEnabled:true,autoTab:7,autoUrl:'https://chatgpt.com/c/work',activeTask:{id:'job1',sku:'SKU1',image_job:true,tabId:7}},calls=[],sent=[],timers=[];
 const chrome={storage:{local:{get:async()=>structuredClone(state),set:async o=>Object.assign(state,structuredClone(o)),remove:async k=>delete state[k]}},runtime:{onMessage:{addListener:f=>listener=f},getManifest:()=>({version:'1.0.66'})},alarms:{onAlarm:{addListener:()=>{}}},scripting:{executeScript:async o=>o.func?[{result:{version:'page'}}]:[]},tabs:{get:async id=>({id,url:'https://chatgpt.com/c/work'}),query:async()=>[],sendMessage:async(id,m)=>{sent.push(m);return m.kind==='preflight'?{version:'1.0.66',ready:!pageBusy,imageTaskId:pageBusy&&pageBusy!=='copy'?'job1':null,generating:pageBusy===true,copyTaskActive:pageBusy==='copy'}:{ok:true};}}};
 const ctx={chrome,URL,AbortSignal,setTimeout:(f,ms)=>{timers.push(ms);},clearTimeout,fetch:async(url,opts)=>{calls.push(url);let value={ok:true};if(url.endsWith('/control'))value={serial:0,paused:false};if(url.endsWith('/task-status'))value={found:true,id:'job1',image_job:true,state:remote};if(url.endsWith('/poll'))value={ready:true};if(url.endsWith('/claim'))value={id:'job2',sku:'SKU2',image_job:true};if(url.endsWith('/queue-diagnostic'))value={busy:true};return {ok:true,json:async()=>value};}};vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),ctx);
 return {state,calls,sent,timers,pageBusy:v=>pageBusy=v,remote:v=>remote=v,poll:()=>vm.runInNewContext('poll()',ctx),command:m=>new Promise(resolve=>listener(m,{},resolve))};
}
test('finished main regeneration follows background commit and starts the next variant automatically',async()=>{
 const f=fixture();await f.poll();assert.ok(f.timers.includes(500));assert.ok(!f.calls.some(p=>p.endsWith('/claim')));f.remote('saved');await f.poll();assert.equal(f.state.activeTask.id,'job2');assert.equal(f.sent.filter(m=>m.kind==='start').length,1);assert.ok(!f.calls.some(p=>p.endsWith('/recover')));
});
test('diagnostics are exportable during active generation and skip a busy local queue',async()=>{
 const f=fixture();const r=await f.command({kind:'diagnose',tabId:7});assert.ok(!r.error,r.error);assert.equal(r.diagnostic.queue.busy,true);assert.equal(f.state.activeTask.id,'job1');assert.ok(f.calls.some(p=>p.endsWith('/queue-diagnostic')));assert.ok(!f.calls.some(p=>p.endsWith('/queue-status')));assert.ok(!f.sent.some(m=>m.kind==='stop'));
});
test('diagnostic button gives progress and is reenabled after exporting a busy snapshot',async()=>{
 const source=fs.readFileSync(__dirname+'/popup.js','utf8'),start=source.indexOf("document.querySelector('#diagnose').onclick="),end=source.indexOf("document.querySelector('#sku').addEventListener",start);const button={disabled:false},status={textContent:''};let clicks=0;
 const doc={querySelector:()=>button,createElement:()=>({click:()=>clicks++})};const ctx={document:doc,status,Blob,URL:{createObjectURL:()=> 'blob:fixture',revokeObjectURL:()=>{}},setTimeout:()=>1,clearTimeout,chrome:{tabs:{query:async()=>[{id:7}]},runtime:{sendMessage:async()=>({diagnostic:{queue:{busy:true}}})}}};
 vm.runInNewContext(source.slice(start,end),ctx);const pending=button.onclick();assert.equal(button.disabled,true);assert.match(status.textContent,/正在导出/);await pending;assert.equal(button.disabled,false);assert.equal(clicks,1);assert.match(status.textContent,/已跳过队列快照/);
});

test('saved local task cannot start the next variant while the previous page is still busy',async()=>{
 const f=fixture();f.remote('saved');f.pageBusy(true);await f.poll();assert.equal(f.state.activeTask.id,'job1');assert.ok(!f.calls.some(p=>p.endsWith('/claim')));f.pageBusy(false);await f.poll();assert.equal(f.state.activeTask.id,'job2');assert.equal(f.sent.filter(m=>m.kind==='start').length,1);
});

test('copy collector activity also blocks a following task even after local image save',async()=>{
 const f=fixture();f.remote('saved');f.pageBusy('copy');await f.poll();assert.equal(f.state.activeTask.id,'job1');assert.ok(!f.calls.some(p=>p.endsWith('/claim')));f.pageBusy(false);await f.poll();assert.equal(f.state.activeTask.id,'job2');
});
