"""Offline reproduction of composer-file false positives; synthetic DOM only."""
import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parent
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);page=await b.new_page()
  await page.set_content('<main><div class="group/user-message">【OZON_TASK:synthetic】</div><div class="block-new"><div class="MarkdownRoot-new">模拟已结束的回复</div></div><div class="ComposerLayoutRoot-new"><div class="ComposerLayoutBody-new"><div class="ComposerLayoutAttachments-new" id="attachments"></div><div class="ProseMirror" contenteditable="true" role="textbox"></div><button aria-label="发送">↑</button></div></div></main>')
  await page.evaluate('''async()=>{const canvas=document.createElement('canvas');canvas.width=600;canvas.height=800;canvas.getContext('2d').fillRect(0,0,600,800);const url=canvas.toDataURL();for(let i=0;i<6;i++){const card=document.createElement('div');card.className='composer-attachment-surface';card.role='button';card.setAttribute('aria-label','original-'+i+'.png');canvas.getContext('2d').fillStyle='rgb('+i*30+',20,40)';canvas.getContext('2d').fillRect(0,0,600,800);const img=new Image();img.src=canvas.toDataURL();img.width=122;img.height=122;await img.decode();const remove=document.createElement('button');remove.setAttribute('aria-label','移除“original-'+i+'.png”');card.append(img,remove);document.querySelector('#attachments').append(card);}}''')
  for f in ['conversation.js','file_links.js','images.js','delivery.js']:await page.add_script_tag(path=str(ROOT/f))
  r=await page.evaluate('''async()=>{const marker='【OZON_TASK:synthetic】';const options={marker,expected:1,allowPartial:true,inventory:true,task:{id:'synthetic',sku:'VARIANT',delivery_policy:'independent_images'}};const files=OzonFiles.candidates(document,options);const images=OzonImages.inspect(document,options);const notices=[];await OzonDelivery.collect(document,{...options,quietMs:0,report:async s=>notices.push(s)});return {candidateTotal:files.candidateTotal,fileCount:files.count,recognizedImageCount:images.count,notices};}''')
  print(json.dumps(r,ensure_ascii=False));assert r['candidateTotal']==0 and r['recognizedImageCount']==0;assert any('尚未发现本任务成品' in s for s in r['notices'])
  await page.evaluate('''async()=>{document.querySelector('.MarkdownRoot-new').insertAdjacentHTML('beforeend','<a download="01_main.jpg" href="https://chatgpt.com/files/synthetic">01_main.jpg</a>');}''')
  result=await page.evaluate('''()=>OzonFiles.candidates(document,{marker:'【OZON_TASK:synthetic】',expected:1,inventory:true})''');assert result['complete'] and result['candidateTotal']==1
  print('PASS Chromium: six original composer attachments and remove buttons excluded; true assistant file remains uniquely collectible')
  await b.close()
asyncio.run(main())
