// Real Chromium DOM regression. Uses synthetic fixtures, never a user's ChatGPT account.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.OZON_TEST_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
 const page=await browser.newPage();await page.route('https://chatgpt.com/**',route=>route.fulfill({contentType:'text/html',body:'<main></main>'}));await page.goto('https://chatgpt.com/c/synthetic-fixture');
 await page.evaluate(()=>{
  function src(n){const c=document.createElement('canvas');c.width=768;c.height=1024;const x=c.getContext('2d');x.fillStyle=`rgb(${n*13},${n*7},${n*3})`;x.fillRect(0,0,c.width,c.height);return c.toDataURL();}
  const main=document.querySelector('main');
  main.innerHTML='<article id="mixed"><div data-message-author-role="user" id="request">【OZON_TASK:IMAGE_TASK】</div><div data-message-author-role="assistant" id="answer"><div class="markdown" id="generated"></div></div></article>';
  for(let n=1;n<=4;n++){const i=new Image();i.src=src(n);document.querySelector('#request').append(i);}
  for(let n=5;n<=12;n++){const i=new Image();i.src=src(n);i.style.width='48px';i.style.height='64px';document.querySelector('#generated').append(i);}
  // The selected image preview appears ahead of the thumbnail strip.
  const preview=new Image();preview.src=src(6);preview.style.width='320px';document.querySelector('#generated').prepend(preview);
 });
 await page.waitForFunction(()=>[...document.images].every(i=>i.complete&&i.naturalWidth===768));
 for(const file of ['conversation.js','images.js','copy_parser.js'])await page.addScriptTag({path:path.join(__dirname,file)});
 const result=await page.evaluate(async()=>{
  const values=await OzonImages.collect(document,{expected:8,marker:'【OZON_TASK:IMAGE_TASK】'});
  return {values,expected:[...document.querySelectorAll('#generated img')].slice(1).map(i=>i.src.split(',')[1]),refs:[...document.querySelectorAll('#request img')].map(i=>i.src.split(',')[1])};
 });
 assert.deepEqual(result.values,result.expected);assert.equal(result.values.length,8);assert.ok(result.values.every(v=>!result.refs.includes(v)));
 // Nested user turn wrappers must not look like a second request boundary.
 await page.evaluate(()=>{const request=document.querySelector('#request');const outer=document.createElement('section');outer.dataset.turn='user';request.replaceWith(outer);outer.append(request);});
 assert.deepEqual(await page.evaluate(()=>OzonImages.collect(document,{expected:8,marker:'【OZON_TASK:IMAGE_TASK】'})),result.expected);
 // Recovering a legacy response also excludes reference siblings in the same article.
 const recovered=await page.evaluate(()=>OzonImages.collect(document,{expected:8}));assert.deepEqual(recovered,result.expected);
 await page.evaluate(()=>{
  const main=document.querySelector('main');
  main.insertAdjacentHTML('beforeend','<article><div data-message-author-role="assistant">old reply</div><div class="markdown" id="new-markdown"></div></article>');
  window.testCopy={sku:'GROUP(1)',title_ru:'Корзины для хранения, набор 2 шт.',description_ru:'Основной материал — полипропилен. Вставка — картон. Золотистый или красный цвет на выбор.',tags_ru:['#корзины'],missing_facts:[]};
  document.querySelector('#new-markdown').textContent=JSON.stringify(testCopy);
 });
 assert.deepEqual(await page.evaluate(()=>OzonCopy.latest(document,{sku:'GROUP(1)'})),await page.evaluate(()=>testCopy));
 // Exercise the actual automatic content-script loop with a reused assistant DOM node.
 await page.evaluate(()=>{
  document.querySelector('#new-markdown').remove();
  document.querySelector('main').insertAdjacentHTML('beforeend','<textarea id="prompt-textarea"></textarea><button id="test-send">Send</button><div data-message-author-role="assistant" id="reused-answer">old content</div>');
  const original=setTimeout;window.setTimeout=(fn,ms)=>original(fn,ms===1000?10:ms);
  window.messages=[];window.chrome={runtime:{sendMessage:async m=>{messages.push(m);return {ok:true};},onMessage:{addListener:fn=>window.contentListener=fn}}};
  window.OzonComposer={findSend:()=>document.querySelector('#test-send')};
  document.querySelector('#test-send').onclick=()=>{const user=document.createElement('div');user.dataset.messageAuthorRole='user';user.textContent='【OZON_COPY:TEST】';document.querySelector('#reused-answer').before(user);document.querySelector('#reused-answer').textContent=JSON.stringify(testCopy);};
 });
 await page.addScriptTag({path:path.join(__dirname,'content.js')});
 await page.evaluate(()=>contentListener({kind:'copy',task:{id:'copy:GROUP(1)',sku:'GROUP(1)',marker:'【OZON_COPY:TEST】',prompt:'【OZON_COPY:TEST】 synthetic prompt'}},{},()=>{}));
 await page.waitForFunction(()=>messages.some(m=>m.kind==='copy-result'),{timeout:5000});
 const saved=await page.evaluate(()=>messages.find(m=>m.kind==='copy-result'));
 assert.equal(saved.task_id,'copy:GROUP(1)');assert.equal(saved.copy.sku,'GROUP(1)');assert.equal(saved.copy.title_ru,'Корзины для хранения, набор 2 шт.');
 console.log('PASS Chromium: generated 8 only, reference siblings excluded, gallery order, legacy recovery, mixed DOM copy extraction, automatic copy return from reused node');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
