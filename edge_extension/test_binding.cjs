const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function fixture({paused=true,active=false,closed=false}={}){
 let listener,pauseHook;const state={pairToken:'fixture',autoEnabled:!paused,autoTab:7,autoUrl:'https://chatgpt.com/c/old',autoTitle:'旧作图页',...(active?{activeTask:{id:'IMAGE',sku:'SKU(1)',tabId:7}}:{})};const calls=[],sent=[];
 const tabs=new Map([[7,{id:7,url:'https://chatgpt.com/c/old',title:'旧作图页',windowId:1}],[9,{id:9,url:'https://chatgpt.com/c/new',title:'新作图页',windowId:2}],[10,{id:10,url:'https://example.com/',title:'其他页'}],[11,{id:11,url:'https://chatgpt.com/images',title:'图片列表'}],[12,{id:12,url:'https://chatgpt.com/g/project/c/thread',title:'项目对话',windowId:2}]]);if(closed)tabs.delete(7);
 const chrome={storage:{local:{get:async()=>structuredClone(state),set:async x=>Object.assign(state,structuredClone(x)),remove:async k=>delete state[k]}},runtime:{onMessage:{addListener:f=>listener=f}},alarms:{onAlarm:{addListener:()=>{}},create:async()=>{}},tabs:{get:async id=>{if(!tabs.has(id))throw Error('closed');return structuredClone(tabs.get(id));},query:async()=>[...tabs.values()].map(t=>structuredClone(t)),update:async(id,body)=>calls.push(['focus',id,body]),sendMessage:async(id,m)=>{sent.push([id,m.kind]);return {ok:true};}},windows:{update:async(id,body)=>calls.push(['window',id,body])}};
 const ctx={chrome,URL,AbortSignal,setTimeout,clearTimeout,fetch:async(url,opts)=>{const p=new URL(url).pathname,b=JSON.parse(opts.body);calls.push([p,b]);let value={};if(p==='/control')value={paused,serial:5};if(p==='/automation-control'){paused=b.paused;if(pauseHook)await pauseHook();value={paused,serial:6};}return {ok:true,json:async()=>value};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/background.js','utf8'),ctx);
 return {state,tabs,calls,sent,ctx,hook:f=>pauseHook=f,command:m=>new Promise(resolve=>listener(m,{},resolve)),poll:()=>vm.runInNewContext('poll()',ctx)};
}
test('paused task can replace an obsolete or closed page binding without starting work',async()=>{
 const f=fixture({closed:true});const r=await f.command({kind:'rebind-work',tabId:9});assert.equal(r.paused,true);assert.equal(f.state.autoTab,9);assert.equal(f.state.autoUrl,'https://chatgpt.com/c/new');assert.equal(f.state.autoEnabled,false);assert.equal(f.state.activeTask,undefined);assert.match(r.status,/保持暂停/);assert.deepEqual(f.sent,[]);assert.ok(!f.calls.some(([p])=>['/claim','/recover','/copy-task','/automation-control'].includes(p)&&p!=='/automation-control'));await f.poll();assert.ok(!f.calls.some(([p])=>p==='/claim'));
});
test('running tasks cannot be rebound and keep their original page',async()=>{
 const f=fixture({paused:false,active:true});const r=await f.command({kind:'rebind-work',tabId:9});assert.match(r.error,/先暂停/);assert.equal(f.state.autoTab,7);assert.equal(f.state.activeTask.id,'IMAGE');assert.ok(!f.calls.some(([p])=>p==='/automation-control'));assert.deepEqual(f.sent,[]);
});
test('local paused active content is stopped and acknowledged before changing the binding',async()=>{
 const f=fixture({paused:true,active:true});const r=await f.command({kind:'rebind-work',tabId:9});assert.ok(!r.error,r.error);assert.deepEqual(f.sent,[[7,'stop']]);assert.ok(f.calls.some(([p,b])=>p==='/pause-ack'&&b.task_id==='IMAGE'));assert.equal(f.state.autoTab,9);assert.equal(f.state.activeTask,undefined);assert.equal(f.state.autoEnabled,false);
});
test('picker lists conversations across windows and excludes unrelated and image pages',async()=>{
 const f=fixture();const r=await f.command({kind:'binding-options',tabId:9});assert.equal(r.canRebind,true);assert.deepEqual(r.tabs.map(t=>t.id),[7,9,12]);assert.equal(r.tabs.find(t=>t.id===9).current,true);assert.equal(r.tabs.find(t=>t.id===7).bound,true);
});
test('invalid or navigated target never replaces saved binding',async()=>{
 const f=fixture();let r=await f.command({kind:'rebind-work',tabId:10});assert.match(r.error,/不是ChatGPT/);assert.equal(f.state.autoTab,7);assert.ok(!f.calls.some(([p])=>p==='/automation-control'));
 f.hook(async()=>{f.tabs.get(9).url='https://chatgpt.com/c/different';});r=await f.command({kind:'rebind-work',tabId:9});assert.match(r.error,/页面已变化/);assert.equal(f.state.autoTab,7);assert.equal(f.state.autoEnabled,false);
});
test('poll and start cannot send while a page binding change is awaiting pause',async()=>{
 const f=fixture();let release,arrived;const waiting=new Promise(r=>arrived=r);f.hook(()=>{arrived();return new Promise(r=>release=r);});const pending=f.command({kind:'rebind-work',tabId:9});await waiting;await f.poll();const r=await f.command({kind:'enable',tabId:9});assert.match(r.error,/正在更换/);assert.ok(!f.calls.some(([p])=>p==='/claim'));release();assert.ok(!(await pending).error);assert.deepEqual(f.sent,[]);
});
