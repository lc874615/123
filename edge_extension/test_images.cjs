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

test('independent delivery accepts final independent files when preview is only one image',async()=>{
 const f=deliveryFixture(1,'independent_images');assert.deepEqual(Array.from(await f.collect()),['rebuilt']);
});
test('independent delivery prefers complete native originals over file remakes',async()=>{
 const f=deliveryFixture(2,'independent_images');assert.deepEqual(Array.from(await f.collect()),['original']);assert.equal(f.counts().fileReads,0);
});

test('followup collection uses its own marker and maps images only into missing positions',async()=>{
 const vm=require('node:vm'),fs=require('node:fs'),source=fs.readFileSync(__dirname+'/content.js','utf8');
 const fn=source.slice(source.indexOf('async function collectImages(task,options){'),source.indexOf('async function saveImage(task,index,image_b64){'));const saved=[];let expected,marker;
 const ctx={stop:false,document:{},chrome:{runtime:{sendMessage:async()=>({expected_images:7,collection_expected:5,collection_offset:2,recovery_marker:'retry-marker',delivery_policy:'independent_images',auto_image_retry:true})}},saveImage:async(_t,i,b)=>saved.push([i,b]),collectSource:async(t,o)=>{expected=o.expected;marker=o.marker;await o.onImage(0,'new-image');return ['new-image'];}};
 vm.runInNewContext(fn+';globalThis.collectFollowup=collectImages;',ctx);await ctx.collectFollowup({id:'parent'},{expected:7,marker:'old'});assert.equal(expected,5);assert.equal(marker,'retry-marker');assert.deepEqual(saved,[[2,'new-image']]);
});
