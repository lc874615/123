(()=>{
 let active=null;
 const pause=ms=>new Promise(r=>setTimeout(r,ms));
 const visible=n=>n&&n.getClientRects().length&&!n.disabled&&n.getAttribute('aria-hidden')!=='true';
 const label=n=>(n.getAttribute('aria-label')||n.getAttribute('title')||n.textContent||'').trim();
 const downloadLabel=/^(?:下载(?:文件|图片|原图|原始文件)?|保存(?:图片|文件)?|另存为|download(?:\s+(?:file|image|original|original image))?|save(?:\s+(?:image|file))?)(?:\s*[（(].*[)）])?$/i;
 function controls(){return [...document.querySelectorAll('button,[role="button"],a[download]')].filter(visible);}
 function containers(){return [...document.querySelectorAll('[role="dialog"],[role="menu"],[data-radix-popper-content-wrapper]')].filter(visible);}
 function safeURL(value){try{const u=new URL(value,location.href);return u.protocol==='https:'&&(u.hostname==='chatgpt.com'||u.hostname.endsWith('.oaiusercontent.com'))||u.protocol==='blob:'&&u.origin==='https://chatgpt.com'||/^data:image\/(?:png|jpeg|webp);/i.test(value);}catch{return false;}}
 async function previewImage(record){
  // Only read a newly opened file preview that explicitly names the clicked file.
  const box=record.dialog;if(!box||!record.name||!(box.textContent||'').includes(record.name))return null;
  const images=[...box.querySelectorAll('img')].filter(n=>visible(n)&&n.complete&&n.naturalWidth>=750&&n.naturalHeight>=1000&&safeURL(n.currentSrc||n.src));
  if(images.length!==1)return null;
  const url=images[0].currentSrc||images[0].src;if(record.triedURL===url)return null;record.triedURL=url;
  const response=await fetch(url,{credentials:'include'});if(!response.ok)return null;
  const blob=await response.blob();if(blob.size>20*1024*1024)throw Error('文件预览原图超过20MB');
  const bitmap=await createImageBitmap(blob);const valid=bitmap.width>=750&&bitmap.height>=1000;bitmap.close();if(!valid)return null;
  return await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve({images:[reader.result.split(',')[1]],source:'named_file_preview'});reader.onerror=reject;reader.readAsDataURL(blob);});
 }
 async function open(token){
  const element=document.querySelector('[data-ozon-download="'+token+'"]');
  const filename=element?.getAttribute('data-ozon-filename')||'';
  const row=element?.closest?.('[class~="group/resource-row"],[data-testid="resource-row"]');
  const rowNames=new Set();
  for(const node of row?.querySelectorAll?.('span,[aria-label],[download]')||[]){
   for(const text of [node.textContent,node.getAttribute('aria-label'),node.getAttribute('download')]){
    const value=String(text||'').trim();
    if(/^[^/\\\n]+\.(?:jpg|jpeg|png|webp)$/i.test(value))rowNames.add(value);
   }
  }
  const verifiedCard=element?.isConnected&&rowNames.size===1&&rowNames.has(filename)&&
   !globalThis.OzonConversation?.userOwned(element)&&!globalThis.OzonConversation?.auxiliary(element);
  if(!verifiedCard&&!globalThis.OzonFiles?.allowedElement(element))throw Error('图片文件入口校验失败：目标='+filename+'；文件卡='+[...rowNames].join('、'));
  const before=new Set(controls());const fingerprint=n=>(n.textContent||'')+'|'+[...n.querySelectorAll('img')].map(i=>i.currentSrc||i.src).join('|');
  const beforeDialogs=new Map(containers().map(n=>[n,fingerprint(n)]));
  globalThis.__ozonDownloadInfo={phase:'opening_file',previewContainers:0,downloadControls:0};
  const record={token,name:element.getAttribute('data-ozon-filename'),dialog:null,close:null};active=record;
  element.scrollIntoView?.({block:'center'});element.click();
  if(element.getAttribute('data-ozon-direct-download')==='true'){
   globalThis.__ozonDownloadInfo.phase='clicked_download';
   return {ok:true,directDownload:true};
  }
  const until=Date.now()+10000;
  while(Date.now()<until&&active===record){
   await pause(150);if(active!==record)return {ok:true};
   const dialogs=containers().filter(n=>!beforeDialogs.has(n)||record.name&&(n.textContent||'').includes(record.name)&&beforeDialogs.get(n)!==fingerprint(n));if(dialogs.length===1)record.dialog=dialogs[0];
   const buttons=controls().filter(n=>downloadLabel.test(label(n)));
   globalThis.__ozonDownloadInfo={phase:'inspecting_preview',previewContainers:dialogs.length,downloadControls:buttons.length};
   const local=record.dialog?buttons.filter(n=>record.dialog.contains(n)):buttons.filter(n=>!before.has(n));
   const closes=controls().filter(n=>/^(?:关闭|关闭预览|close|close preview|close file)$/i.test(label(n))&&(!record.dialog||record.dialog.contains(n)));
   if(closes.length===1)record.close=closes[0];
   const image=await previewImage(record).catch(()=>null);if(image){globalThis.__ozonDownloadInfo.phase='read_named_original';return image;}
   if(local.length===1){globalThis.__ozonDownloadInfo.phase='clicked_download';local[0].click();return {ok:true,previewDownload:true};}
  }
  if(active!==record)return {ok:true};
  globalThis.__ozonDownloadInfo.phase='download_control_not_found';
  return {ok:true,unresolved:true,message:'已点击文件入口，但未识别到对应原图或唯一下载控件'};
 }
 function finish(token){
  if(active?.token!==token)return {ok:true};
  if(active.close&&visible(active.close))active.close.click();
  else if(active.dialog){const buttons=[...active.dialog.querySelectorAll('button')].filter(n=>/^(?:关闭|关闭预览|close|close preview)$/i.test(label(n)));if(buttons.length===1)buttons[0].click();}
  active=null;return {ok:true};
 }
 function cancel(){if(active)finish(active.token);}
 globalThis.OzonDownloadUI={open,finish,cancel};
})();
