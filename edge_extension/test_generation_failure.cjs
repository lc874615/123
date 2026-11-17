const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const message='本次Ozon主图生成失败，图片生成工具返回错误。因此未能交付01_main.jpg，也没有可用的最终成品下载链接。';
function f(){let generating=false,images=[],text=message;const ctx={OzonConversation:{generating:()=>generating,requestReplies:()=>[{textContent:text}],assistantImages:()=>images}};vm.runInNewContext(fs.readFileSync(__dirname+'/generation_failure.js','utf8'),ctx);const task={};return {ctx,task,check:t=>ctx.OzonGenerationFailure.inspect({},task,{marker:'own',now:t}),generating:v=>generating=v,images:v=>images=v,text:v=>text=v};}
test('explicit failed reply triggers only after stable completion',()=>{const x=f();assert.equal(x.check(0),null);const p=x.check(3100);assert.equal(p.reply_finished,true);assert.equal(p.no_images,true);assert.equal(p.marker,'own');});
test('generating missing results quota and already generated images do not restart',()=>{for(const mode of ['generating','missing','quota','images']){const x=f();if(mode==='generating')x.generating(true);if(mode==='missing')x.text('没有图片，仍在处理中');if(mode==='quota')x.text(message+'额度不足');if(mode==='images')x.images([{complete:true,naturalWidth:1024,naturalHeight:1536}]);assert.equal(x.check(0),null);assert.equal(x.check(5000),null);}});
test('owned draft keyboard fallback clicks no unverified task and confirms the new user marker',async()=>{
 let clock=0,pressed=0;const ctx={KeyboardEvent:class{constructor(type,p){this.type=type;Object.assign(this,p);}},OzonConversation:{generating:()=>false,requestAnchor:()=>pressed?{}:null}};vm.runInNewContext(fs.readFileSync(__dirname+'/composer.js','utf8'),ctx);
 const e={value:'owned',focus(){},dispatchEvent(ev){if(ev.type==='keydown')pressed++;}};assert.equal(await ctx.OzonComposer.sendOwnedByEnter(e,{doc:{},expected:'owned',marker:'own',stopped:()=>false,report:async()=>{},sleep:async ms=>clock+=ms,now:()=>clock}),true);assert.equal(pressed,1);
 ctx.OzonConversation.requestAnchor=()=>null;e.value='user edited';await assert.rejects(ctx.OzonComposer.sendOwnedByEnter(e,{doc:{},expected:'owned',marker:'own',stopped:()=>false,report:async()=>{},sleep:async()=>{},now:()=>clock}),/已变化/);assert.equal(pressed,1);
});
test('exact failed remake reply is recognized despite stale previous delivery metadata',()=>{
 const x=f();x.ctx.__ozonDeliveryInfo={fileCount:7};x.text('本次Ozon主图生成失败，图片生成工具返回错误。因此，暂时无法交付符合要求的01_main.jpg。本次没有生成有效成品文件，因此不提供虚假下载链接。图像生成失败');assert.equal(x.check(0),null);assert.equal(x.check(3100).reply_finished,true);
});
test('failure detection runs before order-repair extraction during automatic collection',async()=>{
 const source=fs.readFileSync(__dirname+'/content.js','utf8');const fn=source.slice(source.indexOf('async function collectImages('),source.indexOf('async function saveImage('));let restarts=0,collections=0;
 const ctx={document:{},OzonGenerationFailure:{inspect:()=>({marker:'source',message:'failed',reply_finished:true,no_images:true})},tell:async()=>{},chrome:{runtime:{sendMessage:async m=>{assert.equal(m.kind,'generation-failed');restarts++;return {ok:true};}}},collectSource:async()=>{collections++;throw Error('must not collect');}};
 vm.runInNewContext(fn,ctx);const result=await ctx.collectImages({id:'image-remake',_deliveryPlanChecked:true,orderRepairPending:true,recovery_marker:'source'},{marker:'source'});assert.equal(result.length,0);assert.equal(restarts,1);assert.equal(collections,0);
});
test('a downloadable image in the current failed reply preserves its result',()=>{
 const x=f();x.ctx.OzonFiles={allowedElement:()=>true};x.ctx.OzonConversation.requestReplies=()=>[{textContent:message,querySelectorAll:()=>[{}]}];assert.equal(x.check(0),null);assert.equal(x.check(5000),null);
});
test('Enter fallback reacquires replaced editor and never resends an existing request',async()=>{
 let pressed=0;const old={isConnected:false,innerText:'stale'};const live={innerText:'owned\n\ntext',focus(){},dispatchEvent(e){if(e.type==='keydown')pressed++;}};
 const ctx={KeyboardEvent:class{constructor(type){this.type=type;}},OzonConversation:{generating:()=>false,requestAnchor:()=>pressed?{}:null}};vm.runInNewContext(fs.readFileSync(__dirname+'/composer.js','utf8'),ctx);
 const options={doc:{},expected:'owned\ntext',marker:'own',getEditor:()=>live,stopped:()=>false,report:async()=>{},sleep:async()=>{}};
 assert.equal(await ctx.OzonComposer.sendOwnedByEnter(old,options),true);assert.equal(pressed,1);
 assert.equal(await ctx.OzonComposer.sendOwnedByEnter(old,options),true);assert.equal(pressed,1);
});

test('failed full set reply saying unable to finish or provide real downloads restarts',()=>{
 const x=f();x.text('本次图片生成失败，未能完成要求的8张独立高清Ozon商品图。因此，暂时无法提供01_main.jpg至08_contents.jpg的真实成品下载链接。没有使用简化模板、占位图或原始图片冒充最终成品。图像生成失败');assert.equal(x.check(0),null);assert.equal(x.check(3100).no_images,true);
});
test('download problem without explicit image generation failure never resends',()=>{
 const x=f();x.text('暂时无法提供下载链接，已生成图片仍在保存中');assert.equal(x.check(0),null);assert.equal(x.check(3100),null);
});
