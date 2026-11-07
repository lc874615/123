(()=>{
 let active=null;
 const pause=ms=>new Promise(r=>setTimeout(r,ms));
 const visible=n=>n&&n.getClientRects().length&&!n.disabled&&n.getAttribute('aria-hidden')!=='true';
 function labelled(label){return [...document.querySelectorAll('button,[role="button"]')].filter(n=>visible(n)&&label.test((n.getAttribute('aria-label')||n.getAttribute('title')||n.textContent||'').trim()));}
 async function open(token){
  const element=document.querySelector('[data-ozon-download="'+token+'"]');
  if(!globalThis.OzonFiles?.allowedElement(element))throw Error('图片文件入口已变化或不是允许的图片链接');
  const before=new Set(labelled(/^(?:下载|下载文件|下载图片|download|download file|download image)$/i));
  const beforeDialogs=new Set(document.querySelectorAll('[role="dialog"]'));
  const record={token,dialog:null,close:null};active=record;element.click();
  if(element.getAttribute('data-ozon-direct-download')==='true')return {ok:true,directDownload:true};
  const until=Date.now()+10000;
  while(Date.now()<until&&active===record){
   await pause(150);if(active!==record)return {ok:true};
   const dialogs=[...document.querySelectorAll('[role="dialog"]')].filter(n=>visible(n)&&!beforeDialogs.has(n));
   if(dialogs.length===1)record.dialog=dialogs[0];
   const buttons=labelled(/^(?:下载|下载文件|下载图片|download|download file|download image)$/i).filter(n=>!before.has(n));
   const local=record.dialog?buttons.filter(n=>record.dialog.contains(n)):buttons;
   if(local.length===1){
    const closes=labelled(/^(?:关闭|关闭预览|close|close preview|close file)$/i).filter(n=>!record.dialog||record.dialog.contains(n));
    if(closes.length===1)record.close=closes[0];
    local[0].click();return {ok:true,previewDownload:true};
   }
  }
  if(active!==record)return {ok:true};
  // Some links download immediately and never open a preview; the background
  // listener owns the download-completion timeout in that case.
  return {ok:true};
 }
 function finish(token){
  if(active?.token!==token)return {ok:true};
  if(active.close&&visible(active.close))active.close.click();
  else if(active.dialog){const buttons=[...active.dialog.querySelectorAll('button')].filter(n=>/^(?:关闭|关闭预览|close|close preview)$/i.test((n.getAttribute('aria-label')||n.getAttribute('title')||n.textContent||'').trim()));if(buttons.length===1)buttons[0].click();}
  active=null;return {ok:true};
 }
 function cancel(){if(active)finish(active.token);}
 globalThis.OzonDownloadUI={open,finish,cancel};
})();
