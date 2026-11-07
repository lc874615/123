const {chromium}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.OZON_TEST_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage();let images=[];
  await page.route('https://chatgpt.com/**',r=>{
   const m=r.request().url().match(/assets\/(\d+)/);
   return m?r.fulfill({contentType:'image/png',body:Buffer.from(images[Number(m[1])-1],'base64')}):r.fulfill({contentType:'text/html',body:'<main></main>'});
  });await page.goto('https://chatgpt.com/c/links');
  for(const file of ['conversation.js','file_links.js'])await page.addScriptTag({path:path.join(__dirname,file)});
  images=await page.evaluate(()=>Array.from({length:8},(_,i)=>{const c=document.createElement('canvas');c.width=600;c.height=800;const x=c.getContext('2d');x.fillStyle=`rgb(${i*22},50,80)`;x.fillRect(0,0,600,800);return c.toDataURL().split(',')[1];}));
  await page.evaluate(()=>{
   document.querySelector('main').innerHTML='<div class="group/user-message">【OZON_TASK:LINKS】</div><ol id="links"></ol>';
   for(let i=8;i>=1;i--){const a=document.createElement('a');a.href='/assets/'+i+'/0'+i+'_role.png';a.textContent='商品图 '+i;const li=document.createElement('li');li.append(a);document.querySelector('#links').append(li);}
  });
  const values=await page.evaluate(()=>{window.saved=[];return OzonFiles.collect(document,{task:{id:'LINKS'},expected:8,marker:'【OZON_TASK:LINKS】',onImage:async(i,b)=>saved.push([i,b])});});
  assert.deepEqual(values,images);assert.deepEqual(await page.evaluate(()=>saved.map(x=>x[0])),[0,1,2,3,4,5,6,7]);
  assert.equal(await page.evaluate(()=>OzonFiles.candidates(document,{marker:'WRONG',expected:8,allowPartial:true})),null);
  // ZIP-only and sandbox file links use the browser download bridge when fetch cannot read them.
  await page.evaluate(images=>{
   document.querySelector('#links').innerHTML='<a href="sandbox:/mnt/data/product_images.zip">下载全部图片 ZIP</a>';
   window.downloads=[];window.chrome={runtime:{sendMessage:async m=>{downloads.push(m);return {images};}}};
  },images);
  const zip=await page.evaluate(()=>OzonFiles.collect(document,{task:{id:'LINKS'},expected:8,marker:'【OZON_TASK:LINKS】'}));
  assert.deepEqual(zip,images);assert.equal(await page.evaluate(()=>downloads[0].kind),'download-asset');assert.equal(await page.evaluate(()=>downloads[0].extension),'zip');
  // Buttons without href, with the last five file cards created only after expansion.
  await page.evaluate(images=>{
   document.querySelector('main').innerHTML='<div class="group/user-message">【OZON_TASK:BUTTONS】</div><section id="files"></section>';
   window.expanded=0;window.actions=[];window.saved=[];
   const card=index=>{const button=document.createElement('button');button.setAttribute('role','link');button.textContent=String(index).padStart(2,'0')+'_role.jpg';document.querySelector('#files').append(button);};
   for(let i=1;i<=3;i++)card(i);
   const more=document.createElement('button');more.textContent='另有5个';more.setAttribute('aria-expanded','false');document.querySelector('#files').append(more);
   more.onclick=()=>{expanded++;more.setAttribute('aria-expanded','true');more.textContent='收起';setTimeout(()=>{for(let i=4;i<=8;i++)card(i);},650);};
   chrome.runtime.sendMessage=async m=>{actions.push(m);const element=document.querySelector('[data-ozon-download="'+m.token+'"]');const index=Number(element.textContent.slice(0,2))-1;return {images:[images[index]]};};
  },images);
  const buttonImages=await page.evaluate(()=>OzonFiles.collect(document,{task:{id:'BUTTONS'},expected:8,marker:'【OZON_TASK:BUTTONS】',onImage:async(i,b)=>saved.push([i,b])}));
  assert.deepEqual(buttonImages,images);assert.equal(await page.evaluate(()=>expanded),1);assert.equal(await page.evaluate(()=>actions.length),8);
  await page.evaluate(()=>OzonFiles.expandFiles(document));assert.equal(await page.evaluate(()=>expanded),1);
  assert.equal(await page.evaluate(()=>OzonFiles.allowed('https://github.com/project/release.zip')),false);
  console.log('PASS Chromium: numbered image links sorted first-to-eighth, no gallery required, wrong request rejected, sandbox ZIP uses download bridge, all images returned');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
