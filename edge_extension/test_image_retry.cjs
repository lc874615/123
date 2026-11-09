const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
test('retired retry shim never sends requests even when legacy task enables retry',async()=>{
 let sent=0;const ctx={chrome:{runtime:{sendMessage:()=>sent++}}};vm.runInNewContext(fs.readFileSync(__dirname+'/image_retry.js','utf8'),ctx);
 const result=await ctx.OzonImageRetry.maybe({}, {task:{auto_image_retry:true}});assert.equal(result,false);assert.equal(sent,0);
});
test('active image collection no longer invokes the retry dispatcher',()=>{
 const content=fs.readFileSync(__dirname+'/content.js','utf8'),background=fs.readFileSync(__dirname+'/background.js','utf8');
 assert.ok(!content.includes('OzonImageRetry.maybe'));assert.ok(!background.includes("m.kind==='image-retry'"));assert.ok(!background.includes("'image_retry.js'"));
});
