const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function fixture(latestNames){
 function file(name){return {textContent:name,innerText:name,parentElement:null,getAttribute:k=>k==='href'?'https://chatgpt.com/files/'+name:null,closest:()=>null,querySelectorAll:()=>[],matches:()=>true};}
 function reply(names){const files=names.map(file);return {isConnected:true,files,compareDocumentPosition:()=>4,querySelectorAll:s=>s==='a[href],button,[role="link"],[role="button"]'?files:[]};}
 const old=reply(['01_main.jpg','02_dimensions.jpg']),latest=reply(latestNames),anchor={compareDocumentPosition:()=>4};
 const main={querySelectorAll:s=>s==='a[href],button,[role="link"],[role="button"]'?[...old.files,...latest.files]:[]};
 const ctx={URL,location:{href:'https://chatgpt.com/c/example'},OzonConversation:{main:()=>main,requestAnchor:()=>anchor,nextUser:()=>null,assistantNodes:()=>[old,latest],userOwned:()=>false,auxiliary:()=>false}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/file_links.js','utf8'),ctx);
 return ()=>ctx.OzonFiles.candidates({}, {marker:'current-task',expected:2,inventory:true});
}
test('final reply file list does not collide with older different names for the same number',()=>{
 const found=fixture(['01_main.jpg','02_exterior.jpg'])();assert.equal(found.complete,true);assert.deepEqual(Array.from(found.images,r=>r.name),['01_main.jpg','02_exterior.jpg']);
});
test('incomplete final reply never borrows a file from an older reply',()=>{
 const found=fixture(['01_main.jpg'])();assert.equal(found.complete,false);assert.equal(found.count,1);
});
test('modern summary panel file controls are auxiliary while the conversation shell is not',()=>{
 const ctx={};vm.runInNewContext(fs.readFileSync(__dirname+'/conversation.js','utf8'),ctx);
 const panel={},thread={contains:n=>n===panel};
 const node={closest:s=>s.includes('summary-panel-item')?panel:s==='main,[role="main"]'?thread:null};
 assert.equal(ctx.OzonConversation.auxiliary(node),true);
 const shellNode={closest:s=>s.includes('summary-panel-item')?panel:s==='main,[role="main"]'?{contains:()=>false}:null};
 assert.equal(ctx.OzonConversation.auxiliary(shellNode),false);
});
