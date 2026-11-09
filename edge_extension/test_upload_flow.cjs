const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function fixture({input=false,rerender=false,cardsOnly=false,progressTicks=0,ignored=false,existing=false}={}){
 let now=0,wrong=0,scoped=0,pasted=0,ticks=0,queries=0;const refs=Array.from({length:6},(_,i)=>({name:'ref-'+i+'.png',mime:'image/png',base64:'YQ=='}));
 const image=()=>({complete:true,naturalWidth:1024,closest:()=>null});
 const card=name=>({textContent:name,getAttribute:()=>null,closest:()=>null,querySelector:s=>s==='img'?null:s.includes('button')?{}:null});
 function root(){return {images:[],cards:[],querySelectorAll(s){if(s==='input[type="file"]')return input?[local]:[];if(s==='img')return this.images;if(s==='[role="alert"]')return [];return this.cards;},querySelector(){return ticks<progressTicks?{}:null;}};}
 let currentRoot=root();if(existing)currentRoot.cards=[card('user-existing.pdf')];let doc;
 function makeEditor(r){return {isConnected:true,root:r,disabled:false,getClientRects:()=>[{}],getAttribute:()=>null,closest:()=>r,focus(){},dispatchEvent(e){if(e.type==='paste'){pasted++;attach(e.clipboardData.files.length);}}};}
 let editor=makeEditor(currentRoot);
 function attach(n){if(ignored)return;if(rerender){editor.isConnected=false;currentRoot=root();editor=makeEditor(currentRoot);}if(cardsOnly)currentRoot.cards.push(...refs.slice(0,n).map(r=>card(r.name)));else currentRoot.images.push(...Array.from({length:n},image));}
 const wrongInput={accept:'image/*',multiple:true,dispatchEvent:()=>wrong++};const local={accept:'image/*',multiple:true,value:'',files:[],dispatchEvent(e){if(e.type==='change'){scoped++;attach(this.files.length);}}};
 doc={querySelectorAll(s){if(s==='input[type="file"]'){queries++;return [wrongInput];}return [editor];}};
 class Transfer{constructor(){this.files=[];this.items={add:f=>this.files.push(f)};}}class E{constructor(type,props){this.type=type;Object.assign(this,props);}}
 const ctx={Date:{now:()=>now},DataTransfer:Transfer,File:class{},Event:E,ClipboardEvent:E,Uint8Array,atob:s=>Buffer.from(s,'base64').toString('binary')};vm.runInNewContext(fs.readFileSync(__dirname+'/uploads.js','utf8'),ctx);
 return {upload:()=>ctx.OzonUploads.upload(refs,{doc,editor,sleep:async ms=>{now+=ms;ticks++;},stopped:()=>false,report:async()=>{},timeout:6000}),counts:()=>({wrong,scoped,pasted,queries,ticks}),info:()=>ctx.__ozonUploadInfo};
}
test('unrelated image-generation file inputs are never used for the active chat composer',async()=>{const f=fixture();await f.upload();assert.equal(f.counts().wrong,0);assert.equal(f.counts().queries,0);assert.equal(f.counts().pasted,1);assert.equal(f.info().recognized,6);});
test('uses a file input only when it belongs to the current composer',async()=>{const f=fixture({input:true});await f.upload();assert.equal(f.counts().scoped,1);assert.equal(f.counts().pasted,0);assert.equal(f.counts().wrong,0);});
test('React editor replacement does not strand attachment recognition on detached nodes',async()=>{const f=fixture({rerender:true});await f.upload();assert.equal(f.info().recognized,6);});
test('completed filename cards can acknowledge uploads without img elements',async()=>{const f=fixture({cardsOnly:true});await f.upload();assert.equal(f.info().recognized,6);});
test('preview thumbnails do not finish while upload progress is still present',async()=>{const f=fixture({progressTicks:4});await f.upload();assert.ok(f.counts().ticks>=6);assert.equal(f.info().progress,false);});
test('ignored paste fails without using the wrong input or sending a task',async()=>{const f=fixture({ignored:true});await assert.rejects(f.upload(),/未发送任务/);assert.equal(f.counts().wrong,0);assert.equal(f.counts().pasted,1);assert.equal(f.info().recognized,0);});
test('existing user attachment is preserved and blocks automatic upload',async()=>{const f=fixture({existing:true});await assert.rejects(f.upload(),/已有附件/);assert.equal(f.counts().pasted,0);assert.equal(f.counts().scoped,0);});
