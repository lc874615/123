// Synthetic Work-style DOM: no assistant role/markdown, low-res thumbs, one lazy full preview.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.OZON_TEST_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}});
  await page.route('https://chatgpt.com/**',r=>r.fulfill({contentType:'text/html',body:'<main></main>'}));await page.goto('https://chatgpt.com/c/synthetic-work-gallery');
  for(const file of ['conversation.js','copy_parser.js','images.js','diagnostics.js'])await page.addScriptTag({path:path.join(__dirname,file)});
  await page.evaluate(()=>{
   function src(n,width=768,height=1024){const c=document.createElement('canvas');c.width=width;c.height=height;const ctx=c.getContext('2d');ctx.fillStyle=`rgb(${n*23},${n*11},${n*7})`;ctx.fillRect(0,0,width,height);return c.toDataURL();}
   window.full=Array.from({length:8},(_,i)=>src(i+1));window.low=Array.from({length:8},(_,i)=>src(i+1,48,64));
   OzonConversation.main(document).innerHTML='<div>【OZON_TASK:ROLELESS】</div><section style="display:flex;gap:10px;margin-top:20px"><img id="preview" style="width:320px;height:426px"><nav id="strip" style="display:flex;flex-direction:column;gap:5px"></nav></section><div id="raw-text"></div>';
   document.querySelector('#preview').src=full[3];
   for(let i=0;i<8;i++){
    const button=document.createElement('button');button.style.cssText='padding:0;border:0;width:36px;height:48px';const image=new Image();image.src=low[i];image.style.cssText='width:36px;height:48px';button.append(image);document.querySelector('#strip').append(button);
    button.onclick=()=>setTimeout(()=>{document.querySelector('#preview').src=full[i];},1100);
   }
   window.copyValue={sku:'GROUP(1)',title_ru:'Корзины для хранения',description_ru:'Два цвета на выбор.','tags_ru':['#корзины'],missing_facts:[]};
   document.querySelector('#raw-text').textContent=JSON.stringify(copyValue);
  });
  // Reproduce the uploaded diagnostic: 2 main nodes, the first empty, 14 images in the second.
  await page.evaluate(()=>{
   const actual=OzonConversation.main(document),empty=document.createElement('main');actual.before(empty);
   const references=document.createElement('div');references.id='references';
   for(let i=0;i<5;i++){const image=new Image();image.src=low[i];image.style.cssText='width:36px;height:48px';references.append(image);}actual.prepend(references);
  });
  await page.waitForFunction(()=>[...document.images].every(i=>i.complete&&i.naturalWidth>0));
  assert.equal(await page.evaluate(()=>OzonConversation.assistantNodes(document).length),0);
  assert.deepEqual(await page.evaluate(()=>OzonCopy.recover(document,'GROUP(1)').copy),await page.evaluate(()=>copyValue));
  let finished=false;
  const collecting=page.evaluate(()=>{window.saved=[];return OzonImages.collect(document,{expected:8,marker:'【OZON_TASK:ROLELESS】',onImage:async(index,b64)=>{saved.push({index,b64});}});}).then(value=>{finished=true;return value;});
  await page.waitForFunction(()=>window.saved?.length>=1);assert.equal(finished,false);
  assert.equal(await page.evaluate(()=>saved[0].index),0);
  const values=await collecting;
  assert.equal(await page.evaluate(()=>saved.length),8);
  assert.deepEqual(values,await page.evaluate(()=>full.map(src=>src.split(',')[1])));
  assert.ok(values.every(v=>v.length>1000));
  const diagnostic=await page.evaluate(()=>OzonDiagnostics.snapshot());assert.equal(diagnostic.version,'0.23.0');assert.equal(diagnostic.counts.main,2);assert.equal(diagnostic.images.length,14);assert.equal(diagnostic.roots[0].textLength,0);assert.equal(diagnostic.roots[1].selected,true);assert.equal(diagnostic.json.completeObjects,1);assert.equal(JSON.stringify(diagnostic).includes('Корзины'),false);assert.equal(JSON.stringify(diagnostic).includes('data:image'),false);
  await page.evaluate(()=>{window.removed=[...document.querySelectorAll('#strip button')].slice(3);for(const n of removed)n.remove();window.partial=[];});
  const partial=await page.evaluate(()=>OzonImages.collect(document,{expected:8,allowPartial:true,marker:'【OZON_TASK:ROLELESS】',onImage:async(index,b64)=>partial.push({index,b64})}));
  assert.equal(partial,null);assert.deepEqual(await page.evaluate(()=>window.partial.map(v=>v.b64)),values.slice(0,3));
  await page.evaluate(()=>{for(const n of removed)document.querySelector('#strip').append(n);});
  // Automatic copy reads roleless plain text after the current request marker.
  await page.evaluate(()=>{
   document.querySelector('#raw-text').textContent='old content';
   OzonConversation.main(document).insertAdjacentHTML('beforeend','<textarea id="prompt-textarea"></textarea><button id="send-copy">Send</button>');
   const timer=setTimeout;window.setTimeout=(f,ms)=>timer(f,ms===1000?10:ms);
   window.messages=[];window.chrome={runtime:{onMessage:{addListener:f=>window.listener=f},sendMessage:async m=>{messages.push(m);return {ok:true};}}};window.OzonComposer={findSend:()=>document.querySelector('#send-copy')};
   document.querySelector('#send-copy').onclick=()=>{document.querySelector('#raw-text').textContent='【OZON_COPY:ROLELESS】\n'+JSON.stringify(copyValue);};
  });
  await page.addScriptTag({path:path.join(__dirname,'content.js')});await page.evaluate(()=>listener({kind:'copy',task:{id:'copy:GROUP(1)',sku:'GROUP(1)',marker:'【OZON_COPY:ROLELESS】',prompt:'synthetic prompt'}},{},()=>{}));
  await page.waitForFunction(()=>messages.some(m=>m.kind==='copy-result'),{timeout:5000});
  assert.equal(await page.evaluate(()=>messages.find(m=>m.kind==='copy-result').copy.sku),'GROUP(1)');
  console.log('PASS Chromium Work-style: roleless JSON recovery and automatic return; low-resolution vertical 8-thumb gallery; delayed full-image loading; first image retained; diagnostic excludes content/URLs; 2-main/14-image uploaded structure; per-image saves before completion; partial-prefix streaming');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
