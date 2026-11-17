import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parent
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  page=await browser.new_page()
  for editable in (False,True):
   editor='<div id="prompt-textarea" class="ProseMirror" contenteditable="true" role="textbox"></div>' if editable else '<textarea id="prompt-textarea"></textarea>'
   await page.set_content('<main><div id="history"></div><div class="ComposerLayoutBody-hashed">'+editor+'<button aria-label="发送提示" id="send">↑</button></div></main>')
   for name in ('conversation.js','composer.js'):await page.add_script_tag(path=str(ROOT/name))
   result=await page.evaluate('''async()=>{
    const expected='真实商品资料\\nМатериал: металл\\n【OZON_COPY:local_fixture】',e=document.querySelector('#prompt-textarea');
    if(e.tagName==='TEXTAREA')e.value=expected;else e.innerText=expected;
    let clicks=0;
    document.querySelector('#send').onclick=()=>{clicks++;let n=document.createElement('div');n.className='group/user-message';const span=document.createElement('span');span.textContent='long folded prompt';const expand=document.createElement('button');expand.textContent='显示更多';expand.onclick=()=>{span.textContent=expected;expand.remove();};n.append(span,expand);document.querySelector('#history').append(n);if(e.tagName==='TEXTAREA')e.value='';else e.innerText='';};
    const draftWasAccepted=!!OzonConversation.requestAnchor(document,'【OZON_COPY:local_fixture】');
    await OzonComposer.submitOwned({expected,marker:'【OZON_COPY:local_fixture】',getEditor:()=>e,timeout:1500,confirmMs:100});
    return {draftWasAccepted,clicks,accepted:!!OzonConversation.requestAnchor(document,'【OZON_COPY:local_fixture】')};
   }''')
   assert result=={'draftWasAccepted':False,'clicks':1,'accepted':True},result
   print('real DOM submit', 'contenteditable' if editable else 'textarea',result)
  await page.set_content('''<main><div data-message-author-role="user" id="user"><span>long folded prompt</span><button onclick="this.previousElementSibling.textContent+=' 【OZON_TASK:fixture】';this.remove()">显示更多</button></div><div data-message-author-role="assistant"><img id="generated"></div><div class="ComposerLayoutBody-hashed"><div contenteditable="true">unrelated</div></div></main>''')
  for name in ('conversation.js','delivery.js'):await page.add_script_tag(path=str(ROOT/name))
  result=await page.evaluate('''async()=>{
   let images=0,saved=0;
   globalThis.OzonImages={inspect:()=>({count:1,signature:'actual-generated-image'}),collect:async(d,o)=>{images++;await o.onImage(0,'original-bytes');return ['original-bytes'];}};
   globalThis.OzonFiles={expandFiles:async()=>{},candidates:()=>null};
   const values=await OzonDelivery.collect(document,{task:{delivery_policy:'generated_originals'},marker:'【OZON_TASK:fixture】',expected:1,quietMs:0,sleep:async()=>{},onImage:async()=>saved++});
   return {values,images,saved,located:!!OzonConversation.requestAnchor(document,'【OZON_TASK:fixture】')};
  }''')
  assert result=={'values':['original-bytes'],'images':1,'saved':1,'located':True},result
  print('collapsed request automatically revealed and image collected',result)
  await browser.close()
asyncio.run(main())
