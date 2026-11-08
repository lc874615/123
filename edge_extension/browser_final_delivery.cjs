// Reproduce >8 process images followed by a collapsed, numbered final delivery.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.OZON_TEST_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:1000}});
  await page.route('https://chatgpt.com/**',r=>r.fulfill({contentType:'text/html',body:'<main></main>'}));await page.goto('https://chatgpt.com/c/final-delivery');
  for(const file of ['conversation.js','images.js','file_links.js','download_ui.js','delivery.js'])await page.addScriptTag({path:path.join(__dirname,file)});
  await page.evaluate(()=>{
   function src(n){const c=document.createElement('canvas');c.width=600;c.height=800;const x=c.getContext('2d');x.fillStyle=`rgb(${n*6},${n*4},${n*3})`;x.fillRect(0,0,600,800);return c.toDataURL();}
   window.processImages=Array.from({length:12},(_,i)=>src(i+1));window.finalImages=Array.from({length:8},(_,i)=>src(i+20).split(',')[1]);window.saved=[];window.clicks=[];window.expanded=0;window.previews=0;window.task={id:'FINAL'};
   document.querySelector('main').innerHTML='<div data-message-author-role="user">【OZON_TASK:FINAL】</div><div data-message-author-role="assistant"><section><button data-testid="generated-image-preview"><img id="preview" style="width:320px;height:426px"></button><nav class="vertical-scroll-fade-mask" id="strip"></nav></section><section id="files"></section></div><button data-testid="stop-button">Stop</button>';
   document.querySelector('#preview').src=processImages[1];
   window.addProcess=()=>{const n=document.querySelectorAll('#strip img').length;const b=document.createElement('button');const i=new Image();i.src=processImages[n];i.style.cssText='width:36px;height:48px';b.append(i);document.querySelector('#strip').append(b);};
   for(let i=0;i<8;i++)addProcess();
   window.options={task,marker:'【OZON_TASK:FINAL】',expected:8,allowPartial:true,quietMs:0,onImage:async(i,b)=>saved.push([i,b])};
   window.addFile=n=>{
    const row=document.createElement('span');row.className='group/resource-row';row.dataset.index=n;const label=document.createElement('span');label.textContent=String(n).padStart(2,'0')+'_role.jpg';row.append(label);
    const cover=document.createElement('button');cover.className='inset-0';cover.setAttribute('aria-label',label.textContent);cover.onclick=()=>previews++;row.append(cover);
    row.onmouseover=()=>{if(row.querySelector('[title]'))return;const button=document.createElement('button');button.title='下载文件';button.onclick=()=>clicks.push(n);row.append(button);};document.querySelector('#files').append(row);
   };
   window.chrome={runtime:{sendMessage:async m=>{const el=document.querySelector('[data-ozon-download="'+m.token+'"]');await OzonDownloadUI.open(m.token);const n=Number(el.closest('[data-index]').dataset.index);OzonDownloadUI.finish(m.token);return {images:[finalImages[n-1]]};}}};
  });
  await page.waitForFunction(()=>[...document.images].every(i=>i.complete));
  assert.equal(await page.evaluate(()=>OzonDelivery.collect(document,options)),null);assert.equal(await page.evaluate(()=>saved.length),0);
  await page.evaluate(()=>{for(let i=0;i<4;i++)addProcess();});await page.waitForFunction(()=>[...document.images].every(i=>i.complete));
  assert.equal(await page.evaluate(()=>OzonDelivery.collect(document,options)),null);assert.equal(await page.evaluate(()=>saved.length),0);
  // Generation ends before the final file card has finished rendering: no fallback to process images.
  await page.evaluate(()=>document.querySelector('[data-testid="stop-button"]').remove());
  assert.equal(await page.evaluate(()=>OzonDelivery.collect(document,options)),null);
  await page.evaluate(()=>{for(let i=1;i<=3;i++)addFile(i);for(let i=1;i<=8;i++){const a=document.createElement('a');a.href=processImages[i-1];a.setAttribute('download','0'+i+'_old_attempt.png');a.textContent='过程链接'+i;document.querySelector('#files').before(a);}const more=document.createElement('button');more.textContent='另有5个';more.onclick=()=>{expanded++;more.remove();setTimeout(()=>{for(let i=8;i>=4;i--)addFile(i);},450);};document.querySelector('#files').append(more);});
  assert.equal(await page.evaluate(()=>OzonDelivery.collect(document,options)),null);assert.equal(await page.evaluate(()=>saved.length),0);
  await page.waitForTimeout(300);
  const values=await page.evaluate(()=>OzonDelivery.collect(document,options));
  assert.deepEqual(values,await page.evaluate(()=>finalImages));assert.deepEqual(await page.evaluate(()=>clicks),[1,2,3,4,5,6,7,8]);assert.equal(await page.evaluate(()=>expanded),1);assert.equal(await page.evaluate(()=>previews),0);assert.equal(await page.evaluate(()=>task.deliverySource),'numbered_files');
  assert.deepEqual(await page.evaluate(()=>saved.map(r=>r[0])),[0,1,2,3,4,5,6,7]);
  // Nine numbered files must not be silently truncated to the first eight.
  await page.evaluate(()=>{addFile(9);saved=[];});assert.equal(await page.evaluate(()=>OzonDelivery.collect(document,options)),null);assert.equal(await page.evaluate(()=>saved.length),0);
  // Quiet time resets when the final response is still being edited.
  await page.evaluate(()=>{document.querySelector('[data-index="9"]').remove();window.realNow=Date.now;window.clock=1000;Date.now=()=>clock;window.stableTask={id:'FINAL'};window.stableOptions={...options,task:stableTask,quietMs:5000};});
  assert.equal(await page.evaluate(()=>OzonDelivery.collect(document,stableOptions)),null);
  await page.evaluate(()=>{clock+=4999;});assert.equal(await page.evaluate(()=>OzonDelivery.collect(document,stableOptions)),null);
  await page.evaluate(()=>{clock+=1;document.querySelector('#files').append('最终交付已核对');});assert.equal(await page.evaluate(()=>OzonDelivery.collect(document,stableOptions)),null);
  await page.evaluate(()=>{clock+=5000;});assert.deepEqual(await page.evaluate(()=>OzonDelivery.collect(document,stableOptions)),await page.evaluate(()=>finalImages));
  // Exercise the actual content-script recovery, not only the selector helper.
  await page.evaluate(()=>{
   Date.now=realNow;window.messages=[];const download=chrome.runtime.sendMessage;
   chrome.runtime.onMessage={addListener:f=>window.contentListener=f};
   chrome.runtime.sendMessage=async m=>{messages.push(m);return m.kind==='download-asset'?download(m):{ok:true};};
  });
  await page.addScriptTag({path:path.join(__dirname,'content.js')});
  await page.evaluate(()=>contentListener({kind:'recover',task:{id:'FINAL',sku:'CHAIR(1)',expected_images:8,set_mode:true}},{},()=>{}));
  await page.waitForFunction(()=>messages.filter(m=>m.kind==='set-result').length===8,{timeout:20000});
  assert.deepEqual(await page.evaluate(()=>messages.filter(m=>m.kind==='set-result').map(m=>m.image_b64)),await page.evaluate(()=>finalImages));
  assert.equal(await page.evaluate(()=>messages.filter(m=>m.kind==='event'&&m.state==='needs_attention').length),0);
  console.log('PASS final delivery: transient eight ignored, twelve process images excluded, collapsed final 01-08 auto-expanded and downloaded in order, ninth file rejected, quiet time verified.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
