const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function fixture({name='01_main.jpg',title='01_main.jpg',images=false,ambiguous=false}={}){
 let opened=false,clicked=0,fetched=0,clock=0;
 function node(text='',attrs={}){return {textContent:text,disabled:false,getClientRects:()=>[{}],getAttribute:k=>attrs[k]??null,click:()=>clicked++};}
 const button=node('Download original'),other=node('Save image'),close=node('Close'),image={...node(),complete:true,naturalWidth:1086,naturalHeight:1448,currentSrc:'blob:https://chatgpt.com/named-image'};
 const dialog={...node(title),contains:n=>[button,other,close].includes(n),querySelectorAll:s=>s==='img'&&images?[image]:[]};
 const element={...node(name,{'data-ozon-filename':name}),click:()=>opened=true,scrollIntoView:()=>{}};
 const document={querySelector:()=>element,querySelectorAll:s=>s.startsWith('button')?[button,...(ambiguous?[other]:[]),close]:opened?[dialog]:[]};
 const ctx={document,location:{href:'https://chatgpt.com/c/current'},URL,setTimeout:f=>{queueMicrotask(f);return 1;},Date:{now:()=>clock+=500},OzonFiles:{allowedElement:()=>true},fetch:async()=>{fetched++;return {ok:true,blob:async()=>({size:10})};},createImageBitmap:async()=>({width:1086,height:1448,close:()=>{}}),FileReader:class{readAsDataURL(){this.result='data:image/png;base64,TkFNRUQ=';this.onload();}}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/download_ui.js','utf8'),ctx);return {ctx,run:()=>ctx.OzonDownloadUI.open('owned-token'),clicked:()=>clicked,fetched:()=>fetched};
}
test('a reused download control inside the new preview is clicked even if already present before opening',async()=>{const h=fixture();const r=await h.run();assert.equal(r.previewDownload,true);assert.equal(h.clicked(),1);});
test('a uniquely named full resolution file preview can be collected without browser download',async()=>{const h=fixture({images:true});const r=await h.run();assert.equal(r.source,'named_file_preview');assert.equal(r.images[0],'TkFNRUQ=');assert.equal(h.clicked(),0);assert.equal(h.fetched(),1);});
test('an unrelated preview or ambiguous controls never selects a gallery image or arbitrary download',async()=>{const h=fixture({images:true,title:'old-image.jpg',ambiguous:true});const r=await h.run();assert.equal(r.unresolved,true);assert.equal(h.clicked(),0);assert.equal(h.fetched(),0);});
