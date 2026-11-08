const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
async function run(extracted,{saveError}={}){
 let listener;const state={pairToken:'test'},calls=[];
 const chrome={storage:{local:{get:async()=>({...state}),set:async x=>Object.assign(state,x),remove:async key=>delete state[key]}},runtime:{onMessage:{addListener:f=>listener=f}},tabs:{get:async()=>({id:3,url:'https://chatgpt.com/c/test'}),sendMessage:async()=>extracted},scripting:{executeScript:async()=>{}},alarms:{onAlarm:{addListener:()=>{}}}};
 const context={chrome,setTimeout,clearTimeout,AbortSignal,URL,fetch:async(url,options)=>{calls.push(url);const body=JSON.parse(options.body);if(url.endsWith('/copy-task'))return {ok:true,json:async()=>({id:'copy:'+body.sku,sku:body.sku})};if(url.endsWith('/copy-result')&&saveError)return {ok:false,json:async()=>({error:saveError})};return {ok:true,json:async()=>({saved:true})};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),context);
 const response=await new Promise(resolve=>listener({kind:'copy-recover',tabId:3,sku:'TEST(1)'},{},resolve));return {response,state,calls};
}
test('recovery returns final saved status, never overwrites it with started status',async()=>{
 const r=await run({copy:{sku:'TEST(1)',title_ru:'test'}});assert.match(r.response.status,/已保存/);assert.equal(r.state.status,r.response.status);assert.equal(r.state.activeTask,undefined);assert.ok(r.calls.some(x=>x.endsWith('/copy-result')));
});
test('old page script gives explicit refresh error and releases task',async()=>{
 const r=await run(undefined);assert.match(r.response.error,/刷新/);assert.equal(r.state.activeTask,undefined);assert.ok(r.calls.some(x=>x.endsWith('/copy-failed')));
});
test('local validation failure is returned to panel',async()=>{
 const r=await run({copy:{}},{saveError:'材质冲突'});assert.equal(r.response.error,'材质冲突');assert.equal(r.state.status,'材质冲突');assert.equal(r.state.activeTask,undefined);
});
test('unlabelled copy candidates return for explicit confirmation without saving',async()=>{
 const r=await run({candidates:[{title_ru:'Корзина'}]});assert.match(r.response.status,/选择/);assert.equal(r.response.candidates.length,1);assert.equal(r.state.activeTask,undefined);assert.ok(!r.calls.some(x=>x.endsWith('/copy-result')));
});
test('alarm restores SKU and finishes copy after background suspension without resending prompt',async()=>{
 let alarm;const state={pairToken:'test',activeTask:{id:'copy:GROUP(1)',tabId:3,startedAt:Date.now()}},bodies=[];
 const chrome={storage:{local:{get:async()=>structuredClone(state),set:async x=>Object.assign(state,structuredClone(x)),remove:async k=>delete state[k]}},runtime:{onMessage:{addListener:()=>{}}},scripting:{executeScript:async()=>{}},alarms:{onAlarm:{addListener:f=>alarm=f}},tabs:{get:async()=>({id:3,url:'https://chatgpt.com/c/test'}),sendMessage:async(tab,m)=>{assert.equal(m.task.sku,'GROUP(1)');assert.equal(m.kind,'copy-inspect-v016');return {copy:{sku:'GROUP(1)',title_ru:'saved'},generating:false};}}};
 const ctx={chrome,setTimeout,clearTimeout,AbortSignal,URL,fetch:async(url,options)=>{bodies.push([url,JSON.parse(options.body)]);return {ok:true,json:async()=>({saved:true})};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),ctx);
 // Simulate fresh service workers on two separate alarm events.
 await vm.runInNewContext('poll()',ctx);assert.equal(state.activeTask.sku,'GROUP(1)');
 const restarted={...ctx};vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),restarted);
 await vm.runInNewContext('poll()',restarted);
 assert.equal(state.activeTask,undefined);assert.match(state.status,/同步保存到全部变体/);const saved=bodies.filter(([u])=>u.endsWith('/copy-result'));assert.equal(saved.length,1);assert.equal(saved[0][1].sku,'GROUP(1)');assert.ok(!bodies.some(([u])=>u.endsWith('/copy-task')));
});
test('obsolete persisted image task is reconciled before claiming one queued task',async()=>{
 const state={pairToken:'test',autoEnabled:true,autoTab:3,activeTask:{id:'DELETED',sku:'OLD',tabId:3}},calls=[],sent=[];
 const chrome={storage:{local:{get:async()=>structuredClone(state),set:async x=>Object.assign(state,structuredClone(x)),remove:async k=>delete state[k]}},runtime:{onMessage:{addListener:()=>{}}},alarms:{onAlarm:{addListener:()=>{}}},scripting:{executeScript:async()=>{}},tabs:{get:async()=>({id:3,url:'https://chatgpt.com/c/test'}),sendMessage:async(id,m)=>{sent.push(m.kind);return m.kind==='preflight'?{ready:true,version:'1.0.12'}:{ok:true};}}};
 const ctx={chrome,setTimeout,clearTimeout,AbortSignal,URL,fetch:async(url,options)=>{calls.push(url);let value={ok:true};if(url.endsWith('/task-status'))value={found:false};if(url.endsWith('/poll'))value={ready:true};if(url.endsWith('/claim'))value={id:'NEW_TASK',sku:'NEW'};return {ok:true,json:async()=>value};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),ctx);await vm.runInNewContext('poll()',ctx);
 assert.equal(state.activeTask.id,'NEW_TASK');assert.deepEqual(sent,['preflight','start']);assert.equal(calls.filter(x=>x.endsWith('/claim')).length,1);
});
test('authorized automatic order repair keeps active task and enables later pipeline',async()=>{
 let listener,alarms=0;const state={pairToken:'test',autoEnabled:false,activeTask:{id:'IMAGE',sku:'GROUP(1)',tabId:3}};
 const chrome={storage:{local:{get:async()=>structuredClone(state),set:async x=>Object.assign(state,structuredClone(x)),remove:async k=>delete state[k]}},runtime:{onMessage:{addListener:f=>listener=f}},alarms:{create:async()=>{alarms++;},onAlarm:{addListener:()=>{}}}};
 const ctx={chrome,setTimeout,clearTimeout,AbortSignal,URL,fetch:async(url)=>{assert.ok(url.endsWith('/repair-order'));return {ok:true,json:async()=>({ok:true,backup_created:true})};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),ctx);
 const result=await new Promise(resolve=>listener({kind:'repair-order',task_id:'IMAGE'},{tab:{id:3}},resolve));
 assert.equal(result.backup_created,true);assert.equal(state.autoEnabled,true);assert.equal(state.autoTab,3);assert.equal(state.activeTask.id,'IMAGE');assert.equal(alarms,1);
});
test('download capture renames only the intended service file and cleans listeners',async()=>{
 let determine,changed,renamed,removed=0;
 const chrome={runtime:{onMessage:{addListener:()=>{}}},alarms:{onAlarm:{addListener:()=>{}}},downloads:{onDeterminingFilename:{addListener:f=>determine=f,removeListener:()=>removed++},onChanged:{addListener:f=>changed=f,removeListener:()=>removed++},search:async()=>[{filename:'C:\\Downloads\\OzonImports\\TASK\\nonce.png'}]},tabs:{sendMessage:async(tab,message)=>{if(message.kind==='download-finished')return {ok:true};determine({id:9,url:'blob:https://chatgpt.com/file'},value=>renamed=value.filename);setTimeout(()=>changed({id:9,state:{current:'complete'}}),0);return {ok:true};}}};
 const ctx={chrome,setTimeout,clearTimeout,AbortSignal,URL};vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),ctx);
 const filename=await vm.runInNewContext('captureDownload(3,"TOKEN","OzonImports/TASK/nonce.png")',ctx);
 assert.equal(filename,'C:\\Downloads\\OzonImports\\TASK\\nonce.png');assert.equal(renamed,'OzonImports/TASK/nonce.png');assert.equal(removed,2);
});
test('manual recovery and diagnostics use the bound work tab even when popup opens elsewhere',async()=>{
 let listener;const state={pairToken:'test',autoTab:7,autoEnabled:false};const injected=[],sent=[];
 const chrome={storage:{local:{get:async()=>structuredClone(state),set:async x=>Object.assign(state,structuredClone(x)),remove:async k=>delete state[k]}},runtime:{onMessage:{addListener:f=>listener=f}},alarms:{onAlarm:{addListener:()=>{}}},tabs:{get:async id=>({id,url:'https://chatgpt.com/c/'+id,title:id===7?'生成8张Ozon商品图':'工具沟通'}),sendMessage:async(id,m)=>{sent.push([id,m.kind]);return {ok:true};}},scripting:{executeScript:async args=>{injected.push(args.target.tabId);return args.func?[{result:{version:'1.0.12'}}]:[];}}};
 const ctx={chrome,setTimeout,clearTimeout,AbortSignal,URL,fetch:async(url)=>({ok:true,json:async()=>url.endsWith('/recover')?{id:'TASK',sku:'GROUP(1)'}:{blockers:[]}})};
 vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),ctx);
 const call=message=>new Promise(resolve=>listener(message,{},resolve));
 await call({kind:'recover',tabId:3,sku:'GROUP(1)'});assert.deepEqual(sent,[[7,'recover']]);assert.equal(state.activeTask.tabId,7);
 const diag=await call({kind:'diagnose',tabId:3});assert.equal(diag.diagnostic.target.title,'生成8张Ozon商品图');assert.equal(diag.diagnostic.target.sameAsOpenedPopup,false);assert.ok(injected.every(id=>id===7));
});
test('overlapping polls cannot claim two tasks and completed summary replaces stale video status',async()=>{
 const state={pairToken:'test',autoEnabled:true,autoTab:3,status:'本地正在合成8秒视频。'},calls=[];
 const chrome={storage:{local:{get:async()=>structuredClone(state),set:async x=>Object.assign(state,structuredClone(x)),remove:async k=>delete state[k]}},runtime:{onMessage:{addListener:()=>{}}},alarms:{onAlarm:{addListener:()=>{}}}};
 const ctx={chrome,setTimeout,clearTimeout,AbortSignal,URL,fetch:async(url)=>{calls.push(url);await new Promise(r=>setTimeout(r,10));return {ok:true,json:async()=>({ready:false,summary:'3个变体素材已完成：8图、视频、共用俄语文案；待上架审核'})};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),ctx);await vm.runInNewContext('Promise.all([poll(),poll(),poll()])',ctx);
 assert.equal(calls.filter(u=>u.endsWith('/poll')).length,1);assert.match(state.status,/3个变体素材已完成/);assert.ok(!state.status.includes('正在合成'));
});
test('stop clears extension activity even when the local notification fails',async()=>{
 let listener;const state={pairToken:'old-token',autoEnabled:true,activeTask:{id:'TASK',tabId:3,sku:'GROUP(1)'}};
 const chrome={storage:{local:{get:async()=>structuredClone(state),set:async x=>Object.assign(state,structuredClone(x)),remove:async k=>delete state[k]}},runtime:{onMessage:{addListener:f=>listener=f}},alarms:{clear:async()=>{},onAlarm:{addListener:()=>{}}},tabs:{sendMessage:async()=>({ok:true})}};
 const ctx={chrome,setTimeout,clearTimeout,AbortSignal,URL,fetch:async()=>({ok:false,json:async()=>({error:'配对失败'})})};vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),ctx);
 const result=await new Promise(resolve=>listener({kind:'stop'},{},resolve));assert.equal(state.autoEnabled,false);assert.equal(state.activeTask,undefined);assert.match(result.status,/已暂停/);assert.match(result.status,/配对失败/);
});

function finalHarness({state={},responses={},send,virtualTimers=false}={}){
 const data={pairToken:'test',autoEnabled:true,autoTab:3,...state},calls=[],sent=[],timers=[];let startup,listener;
 const chrome={storage:{local:{get:async()=>structuredClone(data),set:async x=>Object.assign(data,structuredClone(x)),remove:async k=>delete data[k]}},runtime:{onMessage:{addListener:f=>listener=f},onStartup:{addListener:f=>startup=f}},alarms:{create:async()=>{},onAlarm:{addListener:()=>{}}},tabs:{get:async()=>({id:3,url:'https://chatgpt.com/c/test'}),query:async()=>[],sendMessage:async(id,m)=>{sent.push(m);return send?send(m):m.kind==='preflight'?{ready:true,version:'1.0.12'}:{ok:true};}},scripting:{executeScript:async()=>{}}};
 const ctx={chrome,setTimeout:virtualTimers?(fn,ms)=>{timers.push({fn,ms});return timers.length;}:setTimeout,clearTimeout,AbortSignal,URL,fetch:async(url,o)=>{const p=new URL(url).pathname;calls.push([p,JSON.parse(o.body)]);const value=typeof responses[p]==='function'?responses[p](JSON.parse(o.body)):responses[p];return {ok:true,json:async()=>value??(p==='/control'?{serial:0,paused:false}:{})};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),ctx);return {data,calls,sent,timers,ctx,startup:()=>startup?.(),call:(m,sender={})=>new Promise(resolve=>listener(m,sender,resolve))};
}
test('local pause stops current collection and acknowledges without claiming another task',async()=>{
 const h=finalHarness({state:{activeTask:{id:'OLD',sku:'GROUP(1)',tabId:3}},responses:{'/control':{serial:1,paused:true}}});await vm.runInNewContext('poll()',h.ctx);
 assert.equal(h.data.autoEnabled,false);assert.equal(h.data.activeTask,undefined);assert.ok(h.calls.some(([p])=>p==='/pause-ack'));assert.ok(h.sent.some(m=>m.kind==='stop'));assert.ok(!h.calls.some(([p])=>p==='/claim'));
});
test('default zero control never auto-enables a manually stopped extension',async()=>{
 const h=finalHarness({state:{autoEnabled:false}});await vm.runInNewContext('poll()',h.ctx);assert.equal(h.data.autoEnabled,false);assert.ok(!h.calls.some(([p])=>p==='/poll'||p==='/claim'));
});
test('explicit local continue resumes a queued unsent task exactly once',async()=>{
 const h=finalHarness({state:{autoEnabled:false,controlSerial:1},responses:{'/control':{serial:2,paused:false},'/poll':{ready:true},'/claim':{id:'NEW',sku:'GROUP(1)'}}});await vm.runInNewContext('poll()',h.ctx);
 assert.equal(h.data.autoEnabled,true);assert.equal(h.data.activeTask.id,'NEW');assert.equal(h.sent.filter(m=>m.kind==='start').length,1);assert.equal(h.calls.filter(([p])=>p==='/claim').length,1);
});
test('backend restart recovers existing image results without sending another prompt',async()=>{
 const h=finalHarness({state:{activeTask:{id:'OLD',sku:'GROUP(1)',tabId:3}},responses:{'/task-status':{found:true,id:'OLD',sku:'GROUP(1)',state:'needs_attention',resume_mode:'inspect_only'},'/recover':{id:'OLD',sku:'GROUP(1)',set_mode:true,expected_images:8,saved_count:2}}});await vm.runInNewContext('poll()',h.ctx);
 assert.equal(h.sent.filter(m=>m.kind==='recover').length,1);assert.ok(!h.sent.some(m=>m.kind==='start'));assert.ok(!h.calls.some(([p])=>p==='/claim'));
});
test('copy recovery after a backend restart only reads explicit matching SKU',async()=>{
 const h=finalHarness({responses:{'/poll':{ready:false,blockers:[{sku:'GROUP(1)',resume_mode:'copy_inspect_only'}]},'/copy-task':{id:'copy:GROUP(1)',sku:'GROUP(1)',marker:'NEW_MARKER'}},send:m=>m.kind==='copy-inspect-v016'?{copy:{sku:'GROUP(1)',title_ru:'existing'},generating:false}:{ok:true}});
 await vm.runInNewContext('poll()',h.ctx);await vm.runInNewContext('poll()',h.ctx);assert.ok(!h.sent.some(m=>m.kind==='copy'||m.kind==='start'));assert.equal(h.calls.filter(([p])=>p==='/copy-result').length,1);
});
test('startup recreates polling without generating when paused',async()=>{
 const h=finalHarness({state:{autoEnabled:false}});await h.startup();assert.ok(!h.calls.some(([p])=>p==='/claim'));assert.equal(h.data.autoEnabled,false);
});
test('final image completion schedules the pipeline and starts shared copy exactly once',async()=>{
 const h=finalHarness({virtualTimers:true,state:{activeTask:{id:'IMAGE',sku:'GROUP(1)',tabId:3}},responses:{'/set-result':{complete:true,saved_count:8},'/poll':{ready:false,copy_sku:'GROUP(1)'},'/copy-task':{id:'copy:GROUP(1)',sku:'GROUP(1)'}}});
 const result=await h.call({kind:'set-result',task_id:'IMAGE',index:7,image_b64:'fixture'},{tab:{id:3}});
 assert.equal(result.ok,true);assert.equal(h.data.activeTask,undefined);assert.ok(h.timers.some(t=>t.ms===1500));
 await vm.runInNewContext('poll()',h.ctx);
 assert.equal(h.calls.filter(([p,b])=>p==='/copy-task'&&b.prepare_only).length,1);assert.equal(h.calls.filter(([p,b])=>p==='/copy-task'&&!b.prepare_only).length,1);assert.equal(h.sent.filter(m=>m.kind==='copy-extract-auto').length,1);assert.equal(h.sent.filter(m=>m.kind==='copy').length,1);assert.equal(h.data.activeTask.id,'copy:GROUP(1)');
});
test('a still-generating page delays copy without marking it failed or disabling automation',async()=>{
 let generating=true;
 const h=finalHarness({virtualTimers:true,responses:{'/poll':{copy_sku:'GROUP(1)'},'/copy-task':{id:'copy:GROUP(1)',sku:'GROUP(1)'}},send:m=>m.kind==='preflight'?{version:'1.0.12',ready:!generating,generating}:{ok:true}});
 await vm.runInNewContext('poll()',h.ctx);assert.ok(!h.calls.some(([p])=>p==='/copy-task'||p==='/copy-failed'));assert.equal(h.data.autoEnabled,true);assert.ok(h.timers.some(t=>t.ms===3000));
 generating=false;await vm.runInNewContext('poll()',h.ctx);assert.equal(h.sent.filter(m=>m.kind==='copy').length,1);
});
test('local backup command resumes every existing image task through read-only recovery, never generation',async()=>{
 const state={pairToken:'test',autoEnabled:false,autoTab:7,controlSerial:3},sent=[],calls=[];let done=false;
 const chrome={storage:{local:{get:async()=>structuredClone(state),set:async x=>Object.assign(state,structuredClone(x)),remove:async k=>delete state[k]}},runtime:{onMessage:{addListener:()=>{}}},alarms:{onAlarm:{addListener:()=>{}}},scripting:{executeScript:async()=>{}},tabs:{get:async()=>({id:7,url:'https://chatgpt.com/c/work'}),sendMessage:async(id,m)=>{sent.push(m.kind);return {ok:true};}}};
 const ctx={chrome,setTimeout,clearTimeout,AbortSignal,URL,fetch:async(url,opts)=>{calls.push([url,JSON.parse(opts.body)]);let value={};if(url.endsWith('/control'))value={serial:4,paused:false};if(url.endsWith('/poll'))value={ready:false,blockers:done?[]:[{id:'EXISTING',sku:'GROUP(1)',resume_mode:'inspect_only'}]};if(url.endsWith('/recover'))value={id:'EXISTING',sku:'GROUP(1)',automaticRecovery:true,expected_images:8};if(url.endsWith('/task-status')){done=true;value={found:true,state:'saved'};}return {ok:true,json:async()=>value};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),ctx);await vm.runInNewContext('poll()',ctx);
 assert.equal(state.autoEnabled,true);assert.deepEqual(sent,['recover']);assert.ok(calls.some(([u])=>u.endsWith('/recover')));assert.ok(!calls.some(([u])=>u.endsWith('/claim')));
 await vm.runInNewContext('poll()',ctx);assert.equal(state.activeTask,undefined);assert.deepEqual(sent,['recover']);
});
test('refreshing the work page resumes the active local recollection automatically',async()=>{
 const state={pairToken:'test',autoEnabled:true,autoTab:7,controlSerial:5,activeTask:{id:'LEADER',sku:'GROUP(1)',tabId:7}},sent=[],bodies=[];
 const chrome={storage:{local:{get:async()=>structuredClone(state),set:async x=>Object.assign(state,structuredClone(x)),remove:async k=>delete state[k]}},runtime:{onMessage:{addListener:()=>{}}},alarms:{onAlarm:{addListener:()=>{}}},scripting:{executeScript:async()=>{}},tabs:{get:async()=>({id:7,url:'https://chatgpt.com/c/work'}),sendMessage:async(id,m)=>{sent.push(m.kind);return m.kind==='preflight'?{version:'1.0.12',imageTaskId:null,ready:false}:{ok:true};}}};
 const ctx={chrome,setTimeout,clearTimeout,AbortSignal,URL,fetch:async(url,opts)=>{const body=JSON.parse(opts.body);bodies.push([url,body]);let r={};if(url.endsWith('/control'))r={serial:5,paused:false};if(url.endsWith('/task-status'))r={found:true,id:'LEADER',sku:'GROUP(1)',state:'waiting',recollection_requested:true};if(url.endsWith('/recover'))r={id:'LEADER',sku:'GROUP(1)',automaticRecovery:true};return {ok:true,json:async()=>r};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),ctx);await vm.runInNewContext('poll()',ctx);assert.deepEqual(sent,['preflight','recover']);assert.equal(bodies.find(([u])=>u.endsWith('/recover'))[1].automatic,true);assert.equal(state.activeTask.automaticRecovery,true);assert.ok(!bodies.some(([u])=>u.endsWith('/claim')));
});
async function initialStartFixture({bound=false,paused=false,wrongPage=false,empty=false}={}){
 let listener;const state={pairToken:'first-pair',autoEnabled:false,...(bound?{autoTab:7,autoUrl:'https://chatgpt.com/c/original'}:{})},calls=[],sent=[],timers=[];let control={serial:empty?0:1,paused};
 const chrome={storage:{local:{get:async()=>structuredClone(state),set:async x=>Object.assign(state,structuredClone(x)),remove:async k=>delete state[k]}},runtime:{onMessage:{addListener:f=>listener=f}},alarms:{create:async()=>calls.push('alarm'),onAlarm:{addListener:()=>{}}},tabs:{get:async id=>({id,url:wrongPage?'https://example.org/':id===7?'https://chatgpt.com/c/original':'https://chatgpt.com/c/new',title:'作图页'}),sendMessage:async(id,m)=>{sent.push([id,m.kind]);return m.kind==='preflight'?{version:'1.0.12',ready:true}:{ok:true};}},scripting:{executeScript:async()=>{}}};
 const ctx={chrome,URL,AbortSignal,setTimeout:(f,ms)=>{if(ms===100){timers.push(f);return 1;}return setTimeout(f,ms);},clearTimeout,fetch:async(url,opts)=>{const p=new URL(url).pathname;calls.push(p);const v=p==='/health'?{protocol:'1.0.12'}:p==='/control'?control:p==='/poll'?{ready:!empty,blockers:[]}:p==='/claim'?{id:'FIRST',sku:'GROUP(1)'}:{};return {ok:true,json:async()=>v};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),ctx);
 return {state,calls,sent,timers,ctx,command:m=>new Promise(resolve=>listener(m,{},resolve)),start:async()=>vm.runInNewContext('poll()',ctx),create:()=>{empty=false;control={serial:control.serial+1,paused:false};}};
}
test('first pairing installs poll schedule and starts first queued variant without an enable click',async()=>{
 const f=await initialStartFixture();const r=await f.command({kind:'pair-connect',tabId:3});assert.ok(!r.error);assert.equal(f.state.autoTab,3);assert.ok(f.calls.includes('alarm'));await f.start();assert.deepEqual(f.sent,[[3,'preflight'],[3,'start']]);assert.equal(f.calls.filter(x=>x==='/claim').length,1);
});
test('explicit local create-and-process resumes the bound queue after prior pause',async()=>{
 const f=await initialStartFixture({bound:true,paused:true});await f.start();assert.ok(!f.calls.includes('/claim'));f.create();await f.start();assert.deepEqual(f.sent,[[7,'preflight'],[7,'start']]);assert.equal(f.state.autoEnabled,true);
});
test('pair reconnect preserves original binding and never selects a different current conversation',async()=>{
 const f=await initialStartFixture({bound:true});await f.command({kind:'pair-connect',tabId:3});await f.start();assert.equal(f.state.autoTab,7);assert.deepEqual(f.sent,[[7,'preflight'],[7,'start']]);
});
test('pairing from a non ChatGPT tab schedules checks but cannot send or claim a task',async()=>{
 const f=await initialStartFixture({wrongPage:true});const r=await f.command({kind:'pair-connect',tabId:3});assert.match(r.status,/完成绑定/);await f.start();assert.equal(f.state.autoTab,undefined);assert.ok(!f.calls.includes('/claim'));assert.equal(f.sent.length,0);assert.match(f.state.status,/尚未绑定/);
});

test('pairing before first creation waits, then local creation starts without another plugin click',async()=>{
 const f=await initialStartFixture({empty:true});await f.command({kind:'pair-connect',tabId:3});await f.start();assert.ok(!f.calls.includes('/claim'));f.create();await f.start();assert.deepEqual(f.sent,[[3,'preflight'],[3,'start']]);assert.equal(f.calls.filter(x=>x==='/claim').length,1);
});
