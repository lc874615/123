// Reproduce diagnostic (2): Work-generated preview + 8 full-size entries in a clipped strip.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.OZON_TEST_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:640}});await page.route('https://chatgpt.com/**',r=>r.fulfill({contentType:'text/html',body:'<main></main>'}));await page.goto('https://chatgpt.com/c/synthetic-diagnostic-2');
  for(const file of ['conversation.js','copy_parser.js','images.js'])await page.addScriptTag({path:path.join(__dirname,file)});
  await page.evaluate(()=>{
   function src(n,w=1086,h=1448){const c=document.createElement('canvas');c.width=w;c.height=h;const ctx=c.getContext('2d');ctx.fillStyle=`rgb(${n*22},${n*10},${n*5})`;ctx.fillRect(0,0,w,h);return c.toDataURL();}
   window.generated=Array.from({length:8},(_,i)=>src(i+1));window.references=Array.from({length:5},(_,i)=>src(i+9,1000,1000));window.clicks=0;
   document.querySelector('main').innerHTML='<div class="group/user-message" id="references"></div><div class="group/user-message">【OZON_TASK:CURRENT】</div><div style="display:flex;gap:8px;margin-top:300px"><div class="group/generated-image-gallery-controls"><button data-testid="generated-image-preview"><img id="preview" style="width:400px;height:533px"></button></div><div class="vertical-scroll-fade-mask" id="strip" style="height:176px;overflow-y:auto;width:64px;display:flex;flex-direction:column;gap:8px"></div></div>';
   for(const source of references){const image=new Image();image.src=source;image.style.cssText='width:78px;height:78px';document.querySelector('#references').append(image);}
   document.querySelector('#preview').src=generated[4];
   for(const source of generated){const button=document.createElement('button');button.style.cssText='width:56px;height:56px;flex-shrink:0;padding:0';button.onclick=()=>window.clicks++;const image=new Image();image.src=source;image.style.cssText='width:53px;height:53px';button.append(image);document.querySelector('#strip').append(button);}
  });
  await page.waitForFunction(()=>[...document.images].every(i=>i.complete&&i.naturalWidth>0));
  assert.equal(await page.evaluate(()=>document.querySelectorAll('main img').length),14);
  assert.equal(await page.evaluate(()=>OzonConversation.userOwned(document.querySelector('#references img'))),true);
  const result=await page.evaluate(()=>{window.saved=[];return OzonImages.collect(document,{expected:8,marker:'【OZON_TASK:CURRENT】',onImage:async(index,b64)=>saved.push({index,b64})});});
  assert.deepEqual(result,await page.evaluate(()=>generated.map(s=>s.split(',')[1])));assert.equal(await page.evaluate(()=>saved.length),8);assert.equal(await page.evaluate(()=>clicks),0);
  // An automatic task may not consume a previous task's gallery before its own marker appears.
  assert.equal(await page.evaluate(()=>OzonImages.collect(document,{expected:8,allowPartial:true,marker:'【OZON_TASK:DIFFERENT】'})),null);
  // Stop preserves the prefix instead of continuing to save behind the user's back.
  const stopped=await page.evaluate(async()=>{let count=0;try{await OzonImages.collect(document,{expected:8,marker:'【OZON_TASK:CURRENT】',stopped:()=>count>=2,onImage:async()=>count++});return {count};}catch(e){return {count,message:e.message};}});
  assert.equal(stopped.count,2);assert.match(stopped.message,/暂停/);
  await page.evaluate(()=>{
   window.messages=[];let fail=true;
   window.chrome={runtime:{onMessage:{addListener:f=>window.listener=f},sendMessage:async m=>{messages.push(m);if(m.kind==='set-result'&&fail){fail=false;return {error:'恢复图片与已保存顺序不一致',code:'IMAGE_ORDER_CONFLICT'};}return {ok:true};}}};
  });
  await page.addScriptTag({path:path.join(__dirname,'content.js')});
  await page.evaluate(()=>listener({kind:'recover',task:{id:'CURRENT',sku:'GROUP(1)',expected_images:8,set_mode:true}},{},()=>{}));
  await page.waitForFunction(()=>messages.filter(m=>m.kind==='set-result').length===9);
  const recovery=await page.evaluate(()=>({repairs:messages.filter(m=>m.kind==='repair-order').length,indexes:messages.filter(m=>m.kind==='set-result').map(m=>m.index),errors:messages.filter(m=>m.kind==='event'&&m.state==='needs_attention').length}));
  assert.equal(recovery.repairs,1);assert.deepEqual(recovery.indexes,[0,0,1,2,3,4,5,6,7]);assert.equal(recovery.errors,0);
  await page.evaluate(()=>document.querySelector('#strip').remove());
  const single=await page.evaluate(()=>OzonImages.collect(document,{expected:1,marker:'【OZON_TASK:CURRENT】'}));assert.deepEqual(single,[result[4]]);
  console.log('PASS diagnostic (2): 14 images, five user references excluded, all eight 1086x1448 gallery entries saved despite clipped/offscreen strip, zero clicks, wrong automatic marker rejected, stop preserves prefix');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
