const {chromium}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.OZON_TEST_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage();await page.route('https://chatgpt.com/**',r=>r.fulfill({contentType:'text/html',body:'<main></main>'}));await page.goto('https://chatgpt.com/c/direct-download');
  for(const file of ['conversation.js','file_links.js','download_ui.js'])await page.addScriptTag({path:path.join(__dirname,file)});
  const expected=await page.evaluate(()=>{
   window.requests=[];window.previews=0;window.zipClicked=0;window.saved=[];
   const images=Array.from({length:8},(_,i)=>{const c=document.createElement('canvas');c.width=600;c.height=800;const x=c.getContext('2d');x.fillStyle=`rgb(${i*20},30,60)`;x.fillRect(0,0,600,800);return c.toDataURL().split(',')[1];});
   const main=document.querySelector('main');main.innerHTML='<div class="group/user-message">【OZON_TASK:DIRECT】</div>';
   // Reverse DOM order deliberately: output is locked to filename numbering.
   for(let i=8;i>=1;i--){
    const row=document.createElement('span');row.className='group/resource-row';row.dataset.index=String(i);
    const name=String(i).padStart(2,'0')+(i===1?'_main.jpg':'_details.jpg');const label=document.createElement('span');label.textContent=name;row.append(label);
    const cover=document.createElement('button');cover.className='absolute inset-0';cover.setAttribute('aria-label',name);cover.onclick=()=>previews++;row.append(cover);
    row.addEventListener('mouseover',()=>{if(row.querySelector('[title="下载文件"]'))return;const download=document.createElement('button');download.title='下载文件';download.innerHTML='<svg></svg>';download.onclick=()=>requests.push(i);row.append(download);});
    main.append(row);
   }
   const zip=document.createElement('button');zip.setAttribute('role','link');zip.textContent='下载全部图片 ZIP';zip.onclick=()=>zipClicked++;main.append(zip);
   chrome={runtime:{sendMessage:async m=>{const element=document.querySelector('[data-ozon-download="'+m.token+'"]');await OzonDownloadUI.open(m.token);const index=Number(element.closest('[data-index]').dataset.index);OzonDownloadUI.finish(m.token);return {images:[images[index-1]]};}}};
   window.images=images;return images;
  });
  const result=await page.evaluate(()=>OzonFiles.collect(document,{task:{id:'DIRECT'},expected:8,marker:'【OZON_TASK:DIRECT】',onImage:async(i,b)=>saved.push([i,b])}));
  assert.deepEqual(result,expected);assert.deepEqual(await page.evaluate(()=>requests),[1,2,3,4,5,6,7,8]);assert.equal(await page.evaluate(()=>previews),0);assert.equal(await page.evaluate(()=>zipClicked),0);assert.equal(await page.evaluate(()=>saved.length),8);
  console.log('PASS Chromium: real resource-row layout; hover reveals direct download buttons; eight direct clicks in 01-08 order; zero preview opens; zero ZIP clicks; primary fixed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
