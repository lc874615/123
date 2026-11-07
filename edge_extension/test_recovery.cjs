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
