const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function fixture({sent=false,manual=false,rich=false,backupError=false}={}){
 let value=manual?'my own text':'owned prompt【OZON_TASK:T】',files=2;const events=[];class Textarea{get value(){return value;}set value(v){value=v;}focus(){}dispatchEvent(){}}
 const editor=rich?{get innerText(){return value;},focus(){},dispatchEvent(){}}:new Textarea();const root={querySelectorAll:()=>files?[{disabled:false,click:()=>{events.push('remove');files--;}}]:[]};
 const doc={createRange:()=>({selectNodeContents:e=>assert.equal(e,editor)}),defaultView:{getSelection:()=>({removeAllRanges(){},addRange(){}})},execCommand:c=>{assert.equal(c,'delete');events.push('delete');value='';}};
 const ctx={chrome:{runtime:{sendMessage:async m=>{events.push('backup');return backupError?{error:'backup failed'}:{ok:true};}}},HTMLTextAreaElement:Textarea,Event:class{},InputEvent:class{},OzonConversation:{requestAnchor:()=>sent?{}:null,generating:()=>false},OzonComposer:{sameDraft:(a,b)=>a===b},OzonUploads:{attachmentState:()=>({present:files}),editorRoot:()=>root}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/composer_cleanup.js','utf8'),ctx);
 return {events,run:()=>ctx.OzonComposerCleanup.prepare({id:'T',references:[{name:'one.png'},{name:'two.png'}]},{doc,findEditor:()=>editor,sleep:async()=>{},stopped:()=>false,report:async()=>{}}),value:()=>value,files:()=>files};
}
test('owned stale draft and attachments are cleared only after backup and can be replaced',async()=>{const f=fixture();const r=await f.run();assert.equal(r.alreadySent,false);assert.equal(f.events[0],'backup');assert.equal(f.value(),'');assert.equal(f.files(),0);});
test('contenteditable clear is limited to the current editor range',async()=>{const f=fixture({rich:true});await f.run();assert.ok(f.events.includes('delete'));assert.equal(f.value(),'');});
test('already-sent current request clears leftover input but is collected without resending',async()=>{const f=fixture({sent:true});const r=await f.run();assert.equal(r.alreadySent,true);assert.equal(f.value(),'');});
test('unrelated manual draft and backup failures never lose input or attachments',async()=>{for(const opts of [{manual:true},{backupError:true}]){const f=fixture(opts),before=f.value();await assert.rejects(f.run());assert.equal(f.value(),before);assert.equal(f.files(),2);}});
test('image runner skips upload and submission when the current request marker already exists',async()=>{
 const source=fs.readFileSync(__dirname+'/content.js','utf8'),a=source.indexOf('async function run(task){'),b=source.indexOf('async function collectImages',a);let uploads=0,collected=0;
 const ctx={running:false,stop:false,activeImageTaskId:null,location:{origin:'https://chatgpt.com'},document:{},findEditor:()=>({}),tell:async()=>{},sleep:async()=>{},OzonConversation:{generating:()=>false},OzonComposerCleanup:{prepare:async()=>({alreadySent:true,marker:'own-marker'})},OzonUploads:{upload:async()=>uploads++},collectImages:async()=>{collected++;return ['saved'];},chrome:{runtime:{sendMessage:async()=>({ok:true})}}};vm.runInNewContext(source.slice(a,b)+';globalThis.runOwned=run;',ctx);await ctx.runOwned({id:'T',set_mode:true});assert.equal(uploads,0);assert.equal(collected,1);
});
