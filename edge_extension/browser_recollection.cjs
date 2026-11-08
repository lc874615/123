const {chromium}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{const browser=await chromium.launch({executablePath:process.env.OZON_TEST_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});try{
 const page=await browser.newPage();await page.route('https://chatgpt.com/**',r=>r.fulfill({contentType:'text/html',body:'<main></main>'}));await page.goto('https://chatgpt.com/c/synthetic-recollection');
 await page.evaluate(()=>{
  const picture=n=>{const c=document.createElement('canvas');c.width=600;c.height=800;const x=c.getContext('2d');x.fillStyle=`rgb(${n*25},50,100)`;x.fillRect(0,0,600,800);return c.toDataURL('image/png');};window.pictures=Array.from({length:8},(_,i)=>picture(i+1));
  const rows=(start,end)=>Array.from({length:end-start},(_,i)=>`<span class="group/resource-row"><span role="link" href="${pictures[start+i]}">${String(start+i+1).padStart(2,'0')}_chair.png</span></span>`).join('');
  document.querySelector('main').innerHTML='<div class="block-user"><div class="group/user-message">Chair <button id="expand-request" aria-expanded="false">展开</button><span id="request-marker"></span><img src="'+pictures[0]+'"></div></div><div class="block-response"><div class="DilResponseRoot-Abc">准备最终图片</div></div><div class="block-followup"><div class="group/user-message">请提供8个下载文件</div></div><div class="block-files" style="margin-top:2200px"><div class="MarkdownRoot-Abc">最终8张图片</div><section class="resource-card">'+rows(0,3)+'<button aria-expanded="false">另外5个</button></section></div><div class="group/user-message">Other product 【OZON_TASK:OTHER】</div><div class="block-other"><div class="MarkdownRoot-Other">其他商品</div>'+rows(0,8).replaceAll('_chair','_unrelated')+'</div>';
  document.querySelector('#expand-request').onclick=e=>{document.querySelector('#request-marker').textContent='【OZON_TASK:EXISTING】';e.currentTarget.textContent='收起';e.currentTarget.setAttribute('aria-expanded','true');};
  document.querySelector('section button').onclick=e=>{e.currentTarget.insertAdjacentHTML('beforebegin',rows(3,8));e.currentTarget.remove();};
 });
 for(const name of ['conversation.js','file_links.js','images.js','delivery.js','copy_parser.js'])await page.addScriptTag({path:path.join(__dirname,name)});
 const result=await page.evaluate(async()=>{
  const task={id:'EXISTING'},saved=[];
  const scope=OzonConversation.assistantNodes(document);const found=await OzonConversation.revealRequest(document,'【OZON_TASK:EXISTING】',{sleep:async()=>{}});
  const strict=OzonFiles.candidates(document,{marker:'【OZON_TASK:EXISTING】',expected:8,inventory:true});
  const values=await OzonDelivery.collect(document,{task,expected:8,marker:'【OZON_TASK:EXISTING】',continuations:true,quietMs:0,onImage:async(i,b)=>saved.push([i,b])});
  const missing=await OzonConversation.revealRequest(document,'【OZON_TASK:MISSING】',{sleep:async()=>{}});
  return {scope:scope.length,found,strict:strict.count,names:OzonFiles.candidates(document,{marker:'【OZON_TASK:EXISTING】',continuations:true,expected:8}).images.map(x=>x.name),saved:saved.map(x=>x[0]),count:values?.length,source:task.deliverySource,missing};
 });
 assert.equal(result.found,true);assert.equal(result.missing,false);assert.ok(result.scope>=3);assert.equal(result.strict,0);assert.equal(result.count,8);assert.equal(result.source,'numbered_files');assert.deepEqual(result.saved,[0,1,2,3,4,5,6,7]);assert.ok(result.names.every(n=>n.endsWith('_chair.png')));
 // Exercise the real content recovery entry point: no editor, no generation request.
 await page.evaluate(()=>{window.recoveryMessages=[];window.chrome={runtime:{onMessage:{addListener:f=>window.recoveryListener=f},sendMessage:async m=>{recoveryMessages.push(m);return m.kind==='set-result'?{saved_count:m.index+1,complete:m.index===7}:{ok:true};}}};});
 await page.addScriptTag({path:path.join(__dirname,'content.js')});
 await page.evaluate(()=>recoveryListener({kind:'recover',task:{id:'EXISTING',sku:'GROUP(1)',set_mode:true,expected_images:8,automaticRecovery:true}},null,()=>{}));
 await page.waitForFunction(()=>recoveryMessages.filter(m=>m.kind==='set-result').length===8,{},{timeout:20000});
 const messages=await page.evaluate(()=>recoveryMessages);assert.equal(messages.filter(m=>m.kind==='set-result').length,8);assert.ok(!messages.some(m=>['start','copy','claim'].includes(m.kind)||m.state==='sending'));assert.ok(!messages.some(m=>m.state==='needs_attention'));
 // One image per follower can be a single unnumbered file, but only inside its matched request.
 await page.evaluate(()=>{document.querySelector('main').innerHTML='<div class="group/user-message">【OZON_TASK:FOLLOWER】</div><div class="block-file"><div class="MarkdownRoot-X">主图</div><span class="group/resource-row"><span role="link" href="'+pictures[0]+'">main_chair.png</span></span></div>';});
 assert.equal(await page.evaluate(()=>OzonFiles.candidates(document,{marker:'【OZON_TASK:FOLLOWER】',expected:1}).images.length),1);
 console.log('PASS modern recollection: hashed reply blocks, offscreen expansion, follow-up final eight files, next-task exclusion, missing-marker refusal, and one-image follower file.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1);});
