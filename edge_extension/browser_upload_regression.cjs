const {chromium}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.OZON_TEST_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage();await page.route('https://chatgpt.com/**',r=>r.fulfill({contentType:'text/html',body:'<main><form><textarea id="prompt-textarea"></textarea></form></main><div id="attachments"></div>'}));await page.goto('https://chatgpt.com/c/upload-test');await page.addScriptTag({path:path.join(__dirname,'uploads.js')});
  await page.evaluate(()=>{
   const canvas=document.createElement('canvas');canvas.width=64;canvas.height=64;window.source=canvas.toDataURL();window.refs=Array.from({length:5},(_,i)=>({name:'ref'+i+'.png',mime:'image/png',base64:source.split(',')[1]}));window.pastes=0;window.received=[];window.reports=[];
   document.querySelector('#prompt-textarea').addEventListener('paste',event=>{event.preventDefault();pastes++;received=[...event.clipboardData.files].map(f=>f.name);setTimeout(()=>{for(const file of event.clipboardData.files){const card=document.createElement('div');card.className='composer-attachment-surface';const img=new Image();img.src=source;card.append(img);document.querySelector('#attachments').append(card);}},50);});
  });
  await page.evaluate(()=>OzonUploads.upload(refs,{editor:document.querySelector('#prompt-textarea'),sleep:ms=>new Promise(r=>setTimeout(r,Math.min(ms,20))),stopped:()=>false,report:async message=>reports.push(message),timeout:2000}));
  assert.equal(await page.evaluate(()=>pastes),1);assert.equal(await page.evaluate(()=>received.length),5);assert.equal(await page.evaluate(()=>OzonUploads.attachmentImages(document,document.querySelector('#prompt-textarea')).length),5);assert.ok(await page.evaluate(()=>reports.some(s=>s.includes('5/5'))));
  const preexisting=await page.evaluate(async()=>{try{await OzonUploads.upload(refs,{editor:document.querySelector('#prompt-textarea'),sleep:async()=>{},stopped:()=>false,report:async()=>{}});}catch(e){return e.message;}});assert.match(preexisting,/已有附件/);assert.equal(await page.evaluate(()=>pastes),1);
  // A missing/ignored handler must time out, without repeatedly dispatching or sending a prompt.
  await page.evaluate(()=>{document.querySelector('#attachments').replaceChildren();const old=document.querySelector('#prompt-textarea');const next=old.cloneNode();old.replaceWith(next);window.ignored=0;next.addEventListener('paste',()=>ignored++);});
  const ignored=await page.evaluate(async()=>{try{await OzonUploads.upload(refs,{editor:document.querySelector('#prompt-textarea'),sleep:()=>new Promise(r=>setTimeout(r,10)),stopped:()=>false,report:async()=>{},timeout:80});}catch(e){return e.message;}});assert.match(ignored,/未发送作图任务/);assert.equal(await page.evaluate(()=>ignored),1);
  // Keep native single-file support, with previews mounted outside the form.
  await page.evaluate(()=>{const input=document.createElement('input');input.type='file';input.accept='image/*';input.hidden=true;document.body.append(input);window.files=0;input.addEventListener('change',()=>{files+=input.files.length;const card=document.createElement('div');card.className='composer-attachment-surface';const img=new Image();img.src=source;card.append(img);document.querySelector('#attachments').append(card);});});
  await page.evaluate(()=>OzonUploads.upload(refs.slice(0,2),{editor:document.querySelector('#prompt-textarea'),sleep:()=>new Promise(r=>setTimeout(r,10)),stopped:()=>false,report:async()=>{},timeout:1000}));assert.equal(await page.evaluate(()=>files),2);
  console.log('PASS Chromium upload: no file input -> five pasted files verified via portalled previews; existing attachments guarded; ignored paste dispatched once and never sends; native single-file path retained');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
