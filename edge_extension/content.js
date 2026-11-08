(()=>{if(window.__ozonLocalInstalled)return;window.__ozonLocalInstalled=true;globalThis.__ozonContentVersion='1.0.9';let stop=false,running=false,activeImageTaskId=null;
async function collectSource(task,options){
 if(!globalThis.OzonDelivery)throw Error('最终交付采集模块未加载，请更新插件并刷新作图页');
 return globalThis.OzonDelivery.collect(document,{...options,task});
}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function tell(task,state,message){const r=await chrome.runtime.sendMessage({kind:'event',task_id:task.id,state,message});if(r?.error)throw Error(r.error);}
function findEditor(){
 const selectors=['#prompt-textarea','[contenteditable="true"][data-lexical-editor="true"]','[contenteditable="true"].ProseMirror','[role="textbox"][contenteditable="true"]','textarea[placeholder]'];
 for(const sel of selectors){const found=[...document.querySelectorAll(sel)].filter(e=>e.getClientRects().length&&!e.disabled&&e.getAttribute('aria-hidden')!=='true');if(found.length===1)return found[0];}
 return null;
}
function preflight(){const e=findEditor(),generating=globalThis.OzonConversation.generating(document);return {version:'1.0.9',imageTaskId:running?activeImageTaskId:null,ready:!!e&&!generating&&!running,generating,url:location.origin+location.pathname,message:running?'上一图片采集仍在完成，稍后自动继续':generating?'上一条回复仍在生成，等待完成后自动继续':e?'输入框已识别':'未找到可见输入框。请在普通ChatGPT文字对话中刷新页面，点击输入区后重试；不能在图片查看器或其他应用中执行。'};}
async function run(task){
 if(running)throw Error('本页正在执行任务');running=true;activeImageTaskId=task.id;stop=false;
 try{
  if(location.origin!=='https://chatgpt.com')throw Error('请返回 ChatGPT 对话');
  let editor=findEditor();if(!editor)throw Error(preflight().message);
  if(globalThis.OzonConversation.generating(document))throw Error('上一条回复仍在生成');
  if(editor.textContent.trim()||editor.value?.trim())throw Error('输入框已有内容，请先人工处理，避免覆盖');
  if(task.references?.length){
   await globalThis.OzonUploads.upload(task.references,{editor,sleep,stopped:()=>stop,report:message=>tell(task,'waiting',message)});
  }
  const previousImages=new Set([...document.querySelectorAll('img')].map(i=>i.currentSrc||i.src));
  const oldReplies=new Set(globalThis.OzonConversation.assistantNodes(document));
  const before=oldReplies.size;
  editor=findEditor();if(!editor)throw Error('上传后输入框变化，请刷新对话；未发送');
  editor.focus();
  if(editor instanceof HTMLTextAreaElement){Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(editor,task.prompt+'\n【OZON_TASK:'+task.id+'】');editor.dispatchEvent(new Event('input',{bubbles:true}));}
  else{document.execCommand('insertText',false,task.prompt+'\n【OZON_TASK:'+task.id+'】');editor.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:task.prompt}));}
  let send=null;const sendDeadline=Date.now()+15000;
  while(Date.now()<sendDeadline&&!stop){editor=findEditor();if(editor)send=globalThis.OzonComposer.findSend(editor);if(send)break;await sleep(300);}
  if(!send)throw Error('未识别到唯一可用发送按钮；提示词已保留，请人工检查。未自动发送');
  await tell(task,'sending','即将发送，异常时不会自动重发');send.click();await tell(task,'waiting','已点击发送，等待新回复生成图片');
  const deadline=Date.now()+20*60*1000;let lastReport=0;
  while(Date.now()<deadline){
   if(stop)throw Error('已暂停；请检查网页结果');
   if(task.set_mode){
    const images=await collectImages(task,{allowPartial:true,expected:task.expected_images||8,previous:previousImages,before:oldReplies,marker:task.recovery_marker||'【OZON_TASK:'+task.id+'】',sleep,stopped:()=>stop,report:message=>tell(task,'waiting',message),onImage:(index,b64)=>saveImage(task,index,b64)});
    if(images)return;
    if(Date.now()-lastReport>5000){lastReport=Date.now();if(!task._deliveryNotice)await tell(task,'waiting','等待当前任务的最终图片交付；不会重新发送作图请求');}

   }
   const replies=[...document.querySelectorAll('[data-message-author-role="assistant"]')];
   if(!task.set_mode&&replies.length>before&&!document.querySelector('[data-testid="stop-button"]')){
    const last=replies.at(-1);
    const imgs=globalThis.OzonConversation.assistantImages(last).filter(i=>i.complete&&i.naturalWidth>=512&&i.naturalHeight>=512);
    if(imgs.length===1){
     const image=imgs[0];const response=await fetch(image.currentSrc||image.src,{credentials:'include'});if(!response.ok)throw Error('原图读取失败，请手动下载');const blob=await response.blob();
     if(blob.size>20*1024*1024)throw Error('图片超过20MB，请手动处理');
     const b64=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=reject;r.readAsDataURL(blob);});
     const result=await chrome.runtime.sendMessage({kind:'result',task_id:task.id,image_b64:b64});if(result?.error)throw Error(result.error);return;
    }
    if(imgs.length>1)throw Error('新回复包含多张图片，请人工选择，未自动保存');
   }
   await sleep(1500);
  }
  throw Error(task.set_mode?'未收齐8张独立图片（可能只返回单图或拼图）；已暂停，不自动重发':'等待超时，请检查验证、限额或网页变化；不会重发');
 }catch(e){await tell(task,'needs_attention',e.message).catch(()=>{});}finally{running=false;activeImageTaskId=null;}
}
async function collectImages(task,options){
 const marker=task.recovery_marker||'【OZON_TASK:'+task.id+'】';
 if(task.orderRepairPending){
  const main=globalThis.OzonConversation.main(document);
  if(!(String(main?.innerText||'')+' '+String(main?.textContent||'')).includes(marker))throw Error('自动重采集未找到当前任务标记，已有文件保留，请切回对应作图页面');
  const images=await collectSource(task,{...options,allowPartial:false,onImage:async()=>{}});
  if(!images)return null;
  const reset=await chrome.runtime.sendMessage({kind:'repair-order',task_id:task.id});if(reset?.error)throw Error(reset.error);
  if(reset?.pending){await tell(task,'waiting',reset.reason||'等待旧素材处理结束再替换');return null;}
  task.orderRepairPending=false;task.orderRepairAttempted=true;
  for(let index=0;index<images.length;index++)await saveImage(task,index,images[index]);
  return images;
 }
 try{return await collectSource(task,options);}
 catch(error){
  if(error.code!=='IMAGE_ORDER_CONFLICT'||task.orderRepairAttempted)throw error;
  task.orderRepairPending=true;
  await tell(task,'waiting','发现顺序冲突：等待当前任务最终完整图库，随后自动备份并重新采集');
  return collectImages(task,options);
 }
}
async function saveImage(task,index,image_b64){
 if(stop)throw Error('已暂停，已有图片保留');
 const result=await chrome.runtime.sendMessage({kind:'set-result',task_id:task.id,index,image_b64});
 if(result?.error){const e=Error(result.error);e.code=result.code;throw e;}
}
async function recover(task){
 if(running)throw Error('本页正在执行任务');running=true;activeImageTaskId=task.id;stop=false;
 try{
  if(task.automaticRecovery){
   const found=await globalThis.OzonConversation.revealRequest(document,task.source_marker||'【OZON_TASK:'+task.id+'】',{sleep,stopped:()=>stop,report:message=>tell(task,'waiting',message),alternatives:task.recovery_markers||[],onMarker:marker=>{task.recovery_marker=marker;}});
   if(!found)throw Error('历史回复已自动查找，但未找到本任务的原始作图标记；请保持对应作图对话打开。未采集其他商品、未重新作图');
  }
  let images=await collectImages(task,{manual:!task.automaticRecovery,continuations:!!task.automaticRecovery,expected:task.expected_images||8,marker:task.recovery_marker||'【OZON_TASK:'+task.id+'】',sleep,stopped:()=>stop,report:message=>tell(task,'waiting',message),onImage:(index,b64)=>saveImage(task,index,b64)});
  const until=Date.now()+20*60*1000;while(!images&&Date.now()<until&&!stop){await sleep(1500);images=await collectImages(task,{manual:!task.automaticRecovery,continuations:!!task.automaticRecovery,expected:task.expected_images||8,marker:task.recovery_marker||'【OZON_TASK:'+task.id+'】',sleep,stopped:()=>stop,report:message=>tell(task,'waiting',message),onImage:(index,b64)=>saveImage(task,index,b64)});}
  if(!images)throw Error('等待最终编号图片文件超时，未重新生成；已有图片保留');

 }catch(e){await tell(task,'needs_attention',e.message).catch(()=>{});}finally{running=false;activeImageTaskId=null;}
}

async function copy(task){
 stop=false;
 try{
  if(running||globalThis.OzonConversation.generating(document))throw Error('图片回复尚未结束，文案等待下一次自动继续');
  let editor=findEditor();if(!editor)throw Error('未找到输入框');
  if(editor.textContent.trim()||editor.value?.trim())throw Error('输入框已有内容，未覆盖');
  if(task.references?.length){await globalThis.OzonUploads.upload(task.references,{editor,sleep,stopped:()=>stop,report:()=>{}});editor=findEditor();if(!editor)throw Error('原始参考图上传后未找到输入框');}
  const excluded=globalThis.OzonCopy.snapshot();
  const copyNodes=globalThis.OzonConversation.assistantNodes(document);
  const beforeCopy=new Set(copyNodes),beforeText=new Map(copyNodes.map(n=>[n,n.innerText||n.textContent||'']));
  const main=globalThis.OzonConversation.main(document);const oldText=main?.innerText||'';
  editor.focus();if(editor instanceof HTMLTextAreaElement){Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(editor,task.prompt);editor.dispatchEvent(new Event('input',{bubbles:true}));}else{document.execCommand('insertText',false,task.prompt);editor.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:task.prompt}));}
  await sleep(1000);const button=globalThis.OzonComposer.findSend(editor);if(!button)throw Error('未找到可用发送按钮');button.click();
  const until=Date.now()+300000;let stable='',repeats=0,changed=false;
  while(Date.now()<until){
   await sleep(1000);if(stop)throw Error('文案任务已暂停；生成可能仍在继续，请保存现有结果');
   changed=changed||(main?.innerText||'')!==oldText;
   if(document.querySelector('[data-testid="stop-button"]'))continue;
   const value=globalThis.OzonCopy.latest(document,{exclude:excluded,sku:task.sku,before:beforeCopy,beforeText,marker:task.marker});
   if(value){const signature=JSON.stringify(value);repeats=signature===stable?repeats+1:1;stable=signature;
    if(repeats>=3){const r=await chrome.runtime.sendMessage({kind:'copy-result',task_id:task.id,copy:value});if(r?.error)throw Error(r.error);return;}
   }else{stable='';repeats=0;}
  }
  throw Error(changed?'已检测到页面更新，但未提取到新的完整文案JSON；请使用保存现有文案，不要重新生成':'未检测到新回复，可能生成未完成或验证阻塞；未自动重发');
 }catch(e){await chrome.runtime.sendMessage({kind:'copy-failed',task_id:task.id,message:e.message});}
}
function extractCopy(task){
 const result=globalThis.OzonCopy.recover(document,task.sku);
 if(!result.copy&&!result.candidates?.length)throw Error('未读取到匹配文案：助手区域'+globalThis.OzonConversation.assistantNodes(document).length+'个、页面完整JSON '+globalThis.OzonCopy.parseAll(globalThis.OzonConversation.main(document)?.innerText||'').length+'个。请导出页面诊断，无需重新生成');
 return result;
}

chrome.runtime.onMessage.addListener((m,sender,reply)=>{if(m.kind==='download-click'){if(!globalThis.OzonDownloadUI){reply({error:'下载模块未加载，请重新加载扩展并刷新作图页'});return false;}globalThis.OzonDownloadUI.open(m.token).then(reply).catch(e=>reply({error:e.message}));return true;}if(m.kind==='download-finished'){reply(globalThis.OzonDownloadUI.finish(m.token));return false;}if(m.kind==='copy-inspect-v016'){reply({copy:globalThis.OzonCopy.latest(document,{sku:m.task.sku,marker:m.task.marker}),generating:!!document.querySelector('[data-testid="stop-button"]')});return false;}if(m.kind==='copy-extract-v013'){try{reply(extractCopy(m.task));}catch(e){reply({error:e.message});}return false;}if(m.kind==='copy'){copy(m.task);reply({ok:true});return false;}if(m.kind==='recover'){recover(m.task);reply({ok:true});return false;}if(m.kind==='preflight'){reply(preflight());return false;}if(m.kind==='stop'){globalThis.OzonDownloadUI?.cancel();stop=true;reply({ok:true});}if(m.kind==='start'){run(m.task);reply({ok:true});}return false;});})();
