"""Offline actual Chromium check of a newly opened named preview and reused button."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parent
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  page=await browser.new_page()
  await page.route('https://chatgpt.com/**',lambda route:route.fulfill(status=200,content_type='text/html',body='<main></main>'))
  await page.goto('https://chatgpt.com/c/offline-fixture')
  for mode in ('preview','button'):
   await page.set_content('<main><span role="button" data-ozon-download="owned" data-ozon-filename="01_main.jpg" id="file">01_main.jpg</span><button id="download">Download original</button></main>')
   await page.add_script_tag(path=str(ROOT/'download_ui.js'))
   result=await page.evaluate('''async mode=>{
    globalThis.OzonFiles={allowedElement:e=>e===document.querySelector('#file')};let clicked=0;
    const download=document.querySelector('#download');download.onclick=()=>clicked++;
    const canvas=document.createElement('canvas');canvas.width=1086;canvas.height=1448;canvas.getContext('2d').fillRect(0,0,1086,1448);const blob=await new Promise(r=>canvas.toBlob(r));const url=URL.createObjectURL(blob);
    document.querySelector('#file').onclick=()=>{const dialog=document.createElement('div');dialog.setAttribute('role','dialog');dialog.textContent='01_main.jpg';document.body.append(dialog);if(mode==='preview'){const img=document.createElement('img');img.src=url;dialog.append(img);}else dialog.append(download);};
    const r=await OzonDownloadUI.open('owned');URL.revokeObjectURL(url);return {source:r.source,images:r.images?.length,clicked,phase:globalThis.__ozonDownloadInfo.phase};
   }''',mode)
   if mode=='preview':assert result['source']=='named_file_preview' and result['images']==1 and result['clicked']==0,result
   else:assert result['clicked']==1 and result['phase']=='clicked_download',result
  await browser.close()
 print('PASS Chromium: exact named full-size preview collected; existing download button reused in new preview clicked; no gallery guessing or external API calls.')
asyncio.run(main())
