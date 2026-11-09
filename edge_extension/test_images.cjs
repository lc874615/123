require('./conversation.js');
const test=require('node:test'),assert=require('node:assert/strict');
const {ordered,collect}=require('./images.js');
function image(src,width=48){return {src,complete:true,naturalWidth:1024,naturalHeight:1365,getBoundingClientRect:()=>({width,height:width*4/3})};}
test('gallery strip retains main-first order when dimension preview is selected',()=>{
 const strip=Array.from({length:8},(_,i)=>image('image'+i));
 assert.deepEqual(ordered([image('image1',320),...strip],8),strip);
});
test('does not accept low resolution thumbnails as originals',()=>{
 const small={...image('small'),naturalWidth:48,naturalHeight:64};assert.deepEqual(ordered([small],8),[]);
});
global.crypto=require('node:crypto').webcrypto;
global.FileReader=class{async readAsDataURL(blob){this.result='data:image/png;base64,'+Buffer.from(await blob.arrayBuffer()).toString('base64');this.onload();}};
function documentWith(images){const scope={querySelectorAll:()=>images};return {querySelector:()=>null,querySelectorAll:sel=>sel.includes('assistant')?[scope]:[]};}
test('same original at different URLs is collected once',async()=>{
 global.fetch=async src=>({ok:true,blob:async()=>new Blob([src==='mirror'?'original':src])});
 assert.deepEqual(await collect(documentWith([image('original',320),image('mirror',320)]),{expected:1}),[Buffer.from('original').toString('base64')]);
});
test('partial reply cannot borrow images from previous reply',async()=>{
 assert.equal(await collect(documentWith([image('only',320)]),{expected:8}),null);
});

function deliveryFixture(count,policy){
 const vm=require('node:vm'),fs=require('node:fs');let fileReads=0,galleryReads=0,saved=0;
 const ctx={OzonConversation:{region:()=>({anchor:{}}),generating:()=>false,main:()=>({textContent:'settled'})},
 OzonImages:{inspect:()=>({count,overflow:count>2,signature:'native'}),collect:async(_d,o)=>{galleryReads++;await o.onImage(0,'original');return ['original'];}},
 OzonFiles:{expandFiles:async()=>{},candidates:()=>{fileReads++;return {present:true,complete:true,count:2,signature:'files'};},collect:async(_d,o)=>{await o.onImage(0,'rebuilt');return ['rebuilt'];}}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/delivery.js','utf8'),ctx);
 return {collect:()=>ctx.OzonDelivery.collect({}, {task:{delivery_policy:policy},expected:2,quietMs:0,onImage:async()=>{saved++;}}),counts:()=>({fileReads,galleryReads,saved})};
}
test('new delivery saves generated originals even when different numbered files exist',async()=>{
 const f=deliveryFixture(2,'generated_originals');assert.deepEqual(Array.from(await f.collect()),['original']);assert.deepEqual(f.counts(),{fileReads:0,galleryReads:1,saved:1});
});
test('incomplete native gallery cannot be replaced by complete rebuilt download files',async()=>{
 const f=deliveryFixture(1,'generated_originals');assert.equal(await f.collect(),null);assert.deepEqual(f.counts(),{fileReads:0,galleryReads:0,saved:0});
});
test('legacy delivery retains numbered file recovery behavior',async()=>{
 const f=deliveryFixture(1);assert.deepEqual(Array.from(await f.collect()),['rebuilt']);assert.equal(f.counts().galleryReads,0);
});
test('sheet task collects exactly one source and sends it once for server pixel-preserving split',async()=>{
 const vm=require('node:vm'),fs=require('node:fs'),source=fs.readFileSync(__dirname+'/content.js','utf8');
 const fn=source.slice(source.indexOf('async function collectImages(task,options){'),source.indexOf('async function saveImage(task,index,image_b64){'));
 let expected,normalSaves=0;const messages=[];
 const ctx={stop:false,chrome:{runtime:{sendMessage:async m=>{messages.push(m);return {ok:true};}}},collectSource:async(_task,o)=>{expected=o.expected;await o.onImage(0,'same-original-sheet-bytes');return ['same-original-sheet-bytes'];}};
 vm.runInNewContext(fn+';globalThis.collectSheet=collectImages;',ctx);
 await ctx.collectSheet({id:'parent',sheet_layout:{columns:3,rows:3}},{expected:7,onImage:()=>normalSaves++});
 assert.equal(expected,1);assert.equal(normalSaves,0);const results=messages.filter(m=>m.kind==='sheet-result');assert.equal(results.length,1);assert.equal(results[0].image_b64,'same-original-sheet-bytes');
});

test('restored content reloads sheet configuration before deciding expected source count',async()=>{
 const vm=require('node:vm'),fs=require('node:fs'),source=fs.readFileSync(__dirname+'/content.js','utf8');
 const fn=source.slice(source.indexOf('async function collectImages(task,options){'),source.indexOf('async function saveImage(task,index,image_b64){'));
 const seen=[];const ctx={stop:false,chrome:{runtime:{sendMessage:async m=>m.kind==='delivery-plan'?{expected_images:7,sheet_layout:{columns:3,rows:3},delivery_policy:'generated_originals'}:{ok:true}}},collectSource:async(t,o)=>{seen.push(o.expected);return null;}};
 vm.runInNewContext(fn+';globalThis.collectSheet=collectImages;',ctx);
 await ctx.collectSheet({id:'restored'},{expected:7});assert.deepEqual(seen,[1]);
});
