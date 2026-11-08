const {chromium}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.OZON_TEST_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:420,height:920}});
  await page.addInitScript(()=>{
   const data={pairToken:'synthetic',autoEnabled:false,lastSku:'SAMPLE(1)'},listeners=[];window.messages=[];window.statusChange=text=>{data.status=text;listeners.forEach(f=>f({status:{newValue:text}}));};
   window.chrome={storage:{local:{get:async()=>({...data}),set:async value=>Object.assign(data,value)},onChanged:{addListener:f=>listeners.push(f)}},tabs:{query:async()=>[{id:1,url:'https://chatgpt.com/c/synthetic'}]},runtime:{sendMessage:async m=>{messages.push(m.kind);if(m.kind==='health')return {connected:true};if(m.kind==='binding-info')return {bound:true,title:'测试作图页'};if(m.kind==='binding-options')return {canRebind:true,paused:true,tabs:[{id:1,title:'测试作图页',bound:true,current:true},{id:2,title:'另一个窗口中的商品对话'}]};if(m.kind==='rebind-work'){window.selectedBinding=m.tabId;return {status:'已重新绑定，任务保持暂停'};}return {status:'已处理'};}}};
  });
  await page.route('https://chatgpt.com/**',route=>{const name=path.basename(new URL(route.request().url()).pathname);const file=['popup.js','copy_parser.js'].includes(name)?name:'popup.html';return route.fulfill({contentType:file.endsWith('.js')?'application/javascript':'text/html',body:require('node:fs').readFileSync(path.join(__dirname,file),'utf8')});});
  await page.goto('https://chatgpt.com/c/synthetic-popup');await page.waitForFunction(()=>document.querySelector('#connection-state').textContent==='本地工具已连接');
  assert.equal(await page.locator('#advanced').evaluate(e=>e.open),false);assert.equal(await page.locator('#connection-settings').evaluate(e=>e.open),false);assert.equal(await page.locator('#current-sku').textContent(),'SAMPLE(1)');
  assert.equal(await page.locator('#run').isVisible(),true);assert.equal(await page.locator('#recover').isVisible(),false);assert.equal(await page.locator('#copy').isVisible(),false);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:'/tmp/ozon-final-plugin.png',fullPage:true});
  await page.evaluate(()=>statusChange('图片采集超时，需处理'));assert.equal(await page.locator('#advanced').evaluate(e=>e.open),true);assert.equal(await page.locator('#recover').isVisible(),true);
  await page.locator('#recover').click();assert.ok(await page.evaluate(()=>messages.includes('recover')));
  await page.locator('#focus-work').click();assert.equal(await page.locator('#binding-picker').isVisible(),true);await page.locator('#binding-tabs').selectOption('2');await page.locator('#binding-save').click();assert.equal(await page.evaluate(()=>selectedBinding),2);assert.equal(await page.locator('#binding-picker').isVisible(),false);assert.ok(!await page.evaluate(()=>messages.includes('enable')));
  console.log('Popup layout: compact normal controls, bound connection, responsive width, and automatic recovery expansion, and paused cross-window page selection without starting passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
