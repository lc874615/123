const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function fixture({ignoredFirst=false,consume=false,changed=false,already=false,replaced=false}={}){
 let time=0,clicks=0,anchor=already,editor,progress=false;
 const button={isConnected:true,disabled:false,type:'submit',getClientRects:()=>[{}],getAttribute:()=>null,focus(){},click(){clicks++;if(consume)editor.value='';else if(!ignoredFirst||clicks>1)anchor=true;}};
 const root={querySelectorAll:()=>[button],contains:e=>e===editor,requestSubmit(){button.click();}};
 const make=()=>({isConnected:true,value:changed?'user changed':'owned\n【TASK】',closest:()=>root,focus(){},dispatchEvent(){}});editor=make();
 const context={OzonConversation:{requestAnchor:()=>anchor?{}:null,generating:()=>false},OzonUploads:{attachmentState:(doc,e,refs)=>{assert.equal(e,editor);return {progress,ready:refs.length};}}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/composer.js','utf8'),context);
 return {run:()=>context.OzonComposer.submitOwned({doc:{},expected:'owned\n【TASK】',marker:'own',getEditor:()=>editor,references:[{name:'own.png'}],now:()=>time,confirmMs:500,timeout:2000,sleep:async ms=>{time+=ms;progress=false;},report:async()=>{if(replaced){replaced=false;editor=make();}}}),clicks:()=>clicks,uploading:()=>progress=true};
}
test('native submit waits for the owned request marker',async()=>{const f=fixture();assert.equal(await f.run(),true);assert.equal(f.clicks(),1);});
test('an ignored click is retried once with the still intact owned draft',async()=>{const f=fixture({ignoredFirst:true});assert.equal(await f.run(),true);assert.equal(f.clicks(),2);});
test('consumed draft with an unknown receipt is not sent again',async()=>{const f=fixture({consume:true});await assert.rejects(f.run(),/尚未确认/);assert.equal(f.clicks(),1);});
test('changed drafts are preserved and existing requests are collected without another click',async()=>{const f=fixture({changed:true});await assert.rejects(f.run(),/已变化/);assert.equal(f.clicks(),0);const old=fixture({already:true});assert.equal(await old.run(),true);assert.equal(old.clicks(),0);});
test('upload completion and React replacement are rechecked before actual submission',async()=>{const f=fixture({replaced:true});f.uploading();assert.equal(await f.run(),true);assert.equal(f.clicks(),1);});
test('Enter-only fallback is attempted once and never releases an unconfirmed task',async()=>{
 let time=0,keys=0;const editor={isConnected:true,value:'own',closest:()=>null,focus(){},dispatchEvent(e){if(e.type==='keydown')keys++;}};
 const ctx={KeyboardEvent:class{constructor(type){this.type=type;}},OzonConversation:{requestAnchor:()=>null,generating:()=>false}};vm.runInNewContext(fs.readFileSync(__dirname+'/composer.js','utf8'),ctx);
 await assert.rejects(ctx.OzonComposer.submitOwned({doc:{querySelectorAll:()=>[]},expected:'own',marker:'own',getEditor:()=>editor,now:()=>time,confirmMs:500,timeout:2000,sleep:async ms=>time+=ms}),/尚未确认/);assert.equal(keys,1);
});
test('real conversation lookup excludes the owned draft and clicks before accepting a user receipt',async()=>{
 let time=0,clicks=0,users=[];const expected='owned\n【OZON_COPY:fixture】';
 const root={innerText:expected,textContent:expected,querySelectorAll:()=>[]};
 const button={type:'submit',isConnected:true,disabled:false,getClientRects:()=>[{}],getAttribute:()=>null,click(){clicks++;users=[{innerText:expected,textContent:expected,closest:()=>null,querySelector:()=>null}];editor.value='';}};
 const form={querySelectorAll:()=>[button]};const editor={value:expected,isConnected:true,closest:()=>form};
 const doc={querySelector:s=>s==='main,[role="main"]'?root:null,querySelectorAll:s=>s==='main,[role="main"]'?[root]:s.includes('data-message-author-role="user"')?users:[],createTreeWalker:()=>{let seen=false;return {nextNode:()=>seen?null:(seen=true,{nodeValue:expected})};}};
 const ctx={OzonUploads:{attachmentState:()=>({ready:0})}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/conversation.js','utf8'),ctx);vm.runInNewContext(fs.readFileSync(__dirname+'/composer.js','utf8'),ctx);
 assert.equal(ctx.OzonConversation.requestAnchor(doc,'【OZON_COPY:fixture】'),null);
 await ctx.OzonComposer.submitOwned({doc,expected,marker:'【OZON_COPY:fixture】',getEditor:()=>editor,now:()=>time,sleep:async ms=>time+=ms,timeout:2000,confirmMs:500});
 assert.equal(clicks,1);assert.ok(ctx.OzonConversation.requestAnchor(doc,'【OZON_COPY:fixture】'));
});
test('a successful send with a collapsed marker is expanded and confirmed without a second send',async()=>{
 let time=0,clicks=0,sent=false,expanded=false;const expected='owned 【OZON_TASK:folded】';
 const button={disabled:false,type:'submit',isConnected:true,getClientRects:()=>[{}],getAttribute:()=>null,click(){clicks++;sent=true;editor.value='';}};
 const root={querySelectorAll:()=>[button]};const editor={value:expected,isConnected:true,closest:()=>root};
 const ctx={OzonConversation:{requestAnchor:()=>sent&&expanded?{}:null,generating:()=>false,expandUserPrompts:async()=>{if(sent)expanded=true;}}};vm.runInNewContext(fs.readFileSync(__dirname+'/composer.js','utf8'),ctx);
 await ctx.OzonComposer.submitOwned({doc:{},expected,marker:'【OZON_TASK:folded】',getEditor:()=>editor,now:()=>time,sleep:async ms=>time+=ms,timeout:2000,confirmMs:500});assert.equal(clicks,1);assert.equal(expanded,true);
});
