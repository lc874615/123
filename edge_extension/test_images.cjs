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
function documentWith(images){const scope={querySelectorAll:()=>images};return {querySelectorAll:sel=>sel.includes('assistant')?[scope]:[]};}
test('same original at different URLs is collected once',async()=>{
 global.fetch=async src=>({ok:true,blob:async()=>new Blob([src==='mirror'?'original':src])});
 assert.deepEqual(await collect(documentWith([image('original',320),image('mirror',320)]),{expected:1}),[Buffer.from('original').toString('base64')]);
});
test('partial reply cannot borrow images from previous reply',async()=>{
 assert.equal(await collect(documentWith([image('only',320)]),{expected:8}),null);
});
