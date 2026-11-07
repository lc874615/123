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
 const chrome={storage:{local:{get:async()=>structuredClone(state),set:async x=>Object.assign(state,structuredClone(x)),remove:async k=>delete state[k]}},runtime:{onMessage:{addListener:()=>{}}},alarms:{onAlarm:{addListener:f=>alarm=f}},tabs:{sendMessage:async(tab,m)=>{assert.equal(m.task.sku,'GROUP(1)');assert.equal(m.kind,'copy-inspect-v016');return {copy:{sku:'GROUP(1)',title_ru:'saved'},generating:false};}}};
 const ctx={chrome,setTimeout,clearTimeout,AbortSignal,URL,fetch:async(url,options)=>{bodies.push([url,JSON.parse(options.body)]);return {ok:true,json:async()=>({saved:true})};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),ctx);
 // Simulate fresh service workers on two separate alarm events.
 await vm.runInNewContext('poll()',ctx);assert.equal(state.activeTask.sku,'GROUP(1)');
 const restarted={...ctx};vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),restarted);
 await vm.runInNewContext('poll()',restarted);
 assert.equal(state.activeTask,undefined);assert.match(state.status,/自动保存/);assert.equal(bodies.length,1);assert.equal(bodies[0][1].sku,'GROUP(1)');assert.ok(bodies[0][0].endsWith('/copy-result'));
});
test('obsolete persisted image task is reconciled before claiming one queued task',async()=>{
 const state={pairToken:'test',autoEnabled:true,autoTab:3,activeTask:{id:'DELETED',sku:'OLD',tabId:3}},calls=[],sent=[];
 const chrome={storage:{local:{get:async()=>structuredClone(state),set:async x=>Object.assign(state,structuredClone(x)),remove:async k=>delete state[k]}},runtime:{onMessage:{addListener:()=>{}}},alarms:{onAlarm:{addListener:()=>{}}},scripting:{executeScript:async()=>{}},tabs:{get:async()=>({id:3,url:'https://chatgpt.com/c/test'}),sendMessage:async(id,m)=>{sent.push(m.kind);return m.kind==='preflight'?{ready:true,version:'0.24.0'}:{ok:true};}}};
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
 const chrome={storage:{local:{get:async()=>structuredClone(state),set:async x=>Object.assign(state,structuredClone(x)),remove:async k=>delete state[k]}},runtime:{onMessage:{addListener:f=>listener=f}},alarms:{onAlarm:{addListener:()=>{}}},tabs:{get:async id=>({id,url:'https://chatgpt.com/c/'+id,title:id===7?'生成8张Ozon商品图':'工具沟通'}),sendMessage:async(id,m)=>{sent.push([id,m.kind]);return {ok:true};}},scripting:{executeScript:async args=>{injected.push(args.target.tabId);return args.func?[{result:{version:'0.24.0'}}]:[];}}};
 const ctx={chrome,setTimeout,clearTimeout,AbortSignal,URL,fetch:async(url)=>({ok:true,json:async()=>url.endsWith('/recover')?{id:'TASK',sku:'GROUP(1)'}:{blockers:[]}})};
 vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),ctx);
 const call=message=>new Promise(resolve=>listener(message,{},resolve));
 await call({kind:'recover',tabId:3,sku:'GROUP(1)'});assert.deepEqual(sent,[[7,'recover']]);assert.equal(state.activeTask.tabId,7);
 const diag=await call({kind:'diagnose',tabId:3});assert.equal(diag.diagnostic.target.title,'生成8张Ozon商品图');assert.equal(diag.diagnostic.target.sameAsOpenedPopup,false);assert.ok(injected.every(id=>id===7));
});
