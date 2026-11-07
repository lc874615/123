(()=>{if(window.__ozonLocalInstalled)return;window.__ozonLocalInstalled=true;let stop=false,running=false;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function tell(task,state,message){const r=await chrome.runtime.sendMessage({kind:'event',task_id:task.id,state,message});if(r?.error)throw Error(r.error);}
function findEditor(){
 const selectors=['#prompt-textarea','[contenteditable="true"][data-lexical-editor="true"]','[contenteditable="true"].ProseMirror','[role="textbox"][contenteditable="true"]','textarea[placeholder]'];
 for(const sel of selectors){const found=[...document.querySelectorAll(sel)].filter(e=>e.getClientRects().length&&!e.disabled&&e.getAttribute('aria-hidden')!=='true');if(found.length===1)return found[0];}
 return null;
}
function preflight(){const e=findEditor();return {version:'0.17.0',ready:!!e&&!document.querySelector('[data-testid="stop-button"]'),url:location.origin+location.pathname,message:e?'输入框已识别':'未找到可见输入框。请在普通ChatGPT文字对话中刷新页面，点击输入区后重试；不能在图片查看器或其他应用中执行。'};}
async function run(task){
 if(running)throw Error('本页正在执行任务');running=true;stop=false;
 try{
  if(location.origin!=='https://chatgpt.com')throw Error('请返回 ChatGPT 对话');
  let editor=findEditor();if(!editor)throw Error(preflight().message);
  if(document.querySelector('[data-testid="stop-button"]'))throw Error('上一条回复仍在生成');
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
   if(task.set_mode&&!document.querySelector('[data-testid="stop-button"]')){
    const images=await globalThis.OzonImages.collect(document,{expected:task.expected_images||8,previous:previousImages,before:oldReplies,marker:'【OZON_TASK:'+task.id+'】',sleep,stopped:()=>stop,report:message=>tell(task,'waiting',message)});
    if(images){await saveSet(task,images);return;}
    if(Date.now()-lastReport>30000){lastReport=Date.now();await tell(task,'waiting','等待采集：助手区域'+globalThis.OzonConversation.assistantNodes(document).length+'个、页面图片'+document.querySelectorAll('main img,[role="main"] img').length+'张。若网页已生成8张，请导出页面诊断；不会重发');}

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
 }catch(e){await tell(task,'needs_attention',e.message).catch(()=>{});}finally{running=false;}
}
async function saveSet(task,images){
 // Re-submit the prefix too: the bridge checks its hashes before accepting a resumed sequence.
 for(let index=0;index<images.length;index++){
  if(stop)throw Error('已暂停，已有图片保留');
  const result=await chrome.runtime.sendMessage({kind:'set-result',task_id:task.id,index,image_b64:images[index]});
  if(result?.error)throw Error(result.error);
 }
}
async function recover(task){
 if(running)throw Error('本页正在执行任务');running=true;stop=false;
 try{
  const images=await globalThis.OzonImages.collect(document,{expected:task.expected_images||8,marker:'【OZON_TASK:'+task.id+'】',sleep,stopped:()=>stop,report:message=>tell(task,'waiting',message)});
  if(!images)throw Error('本页未收齐完整原图，请展开当前回复的图片列表后重试；不会重新生成');
  await saveSet(task,images);
 }catch(e){await tell(task,'needs_attention',e.message).catch(()=>{});}finally{running=false;}
}

async function copy(task){
 stop=false;
 try{
  const editor=findEditor();if(!editor)throw Error('未找到输入框');
  if(editor.textContent.trim()||editor.value?.trim())throw Error('输入框已有内容，未覆盖');
  const excluded=globalThis.OzonCopy.snapshot();
  const copyNodes=globalThis.OzonConversation.assistantNodes(document);
  const beforeCopy=new Set(copyNodes),beforeText=new Map(copyNodes.map(n=>[n,n.innerText||n.textContent||'']));
  const main=document.querySelector('main,[role="main"]');const oldText=main?.innerText||'';
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
 if(!result.copy&&!result.candidates?.length)throw Error('未读取到匹配文案：助手区域'+globalThis.OzonConversation.assistantNodes(document).length+'个、页面完整JSON '+globalThis.OzonCopy.parseAll(document.querySelector('main,[role="main"]')?.innerText||'').length+'个。请导出页面诊断，无需重新生成');
 return result;
}

chrome.runtime.onMessage.addListener((m,sender,reply)=>{if(m.kind==='copy-inspect-v016'){reply({copy:globalThis.OzonCopy.latest(document,{sku:m.task.sku,marker:m.task.marker}),generating:!!document.querySelector('[data-testid="stop-button"]')});return false;}if(m.kind==='copy-extract-v013'){try{reply(extractCopy(m.task));}catch(e){reply({error:e.message});}return false;}if(m.kind==='copy'){copy(m.task);reply({ok:true});return false;}if(m.kind==='recover'){recover(m.task);reply({ok:true});return false;}if(m.kind==='preflight'){reply(preflight());return false;}if(m.kind==='stop'){stop=true;reply({ok:true});}if(m.kind==='start'){run(m.task);reply({ok:true});}return false;});})();
