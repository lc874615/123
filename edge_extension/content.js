(()=>{if(window.__ozonLocalInstalled)return;window.__ozonLocalInstalled=true;let stop=false,running=false;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function tell(task,state,message){const r=await chrome.runtime.sendMessage({kind:'event',task_id:task.id,state,message});if(r?.error)throw Error(r.error);}
function findEditor(){
 const selectors=['#prompt-textarea','[contenteditable="true"][data-lexical-editor="true"]','[contenteditable="true"].ProseMirror','[role="textbox"][contenteditable="true"]','textarea[placeholder]'];
 for(const sel of selectors){const found=[...document.querySelectorAll(sel)].filter(e=>e.getClientRects().length&&!e.disabled&&e.getAttribute('aria-hidden')!=='true');if(found.length===1)return found[0];}
 return null;
}
function preflight(){const e=findEditor();return {ready:!!e&&!document.querySelector('[data-testid="stop-button"]'),url:location.origin+location.pathname,message:e?'输入框已识别':'未找到可见输入框。请在普通ChatGPT文字对话中刷新页面，点击输入区后重试；不能在图片查看器或其他应用中执行。'};}
async function run(task){
 if(running)throw Error('本页正在执行任务');running=true;stop=false;
 try{
  if(location.origin!=='https://chatgpt.com')throw Error('请返回 ChatGPT 对话');
  let editor=findEditor();if(!editor)throw Error(preflight().message);
  if(document.querySelector('[data-testid="stop-button"]'))throw Error('上一条回复仍在生成');
  if(editor.textContent.trim()||editor.value?.trim())throw Error('输入框已有内容，请先人工处理，避免覆盖');
  if(task.references?.length){
   let input=[...document.querySelectorAll('input[type="file"]')].find(x=>!x.accept||x.accept.includes('image')||x.accept.includes('*'));
   if(!input){const attach=document.querySelector('button[data-testid="composer-plus-btn"], button[aria-label*="Attach"], button[aria-label*="添加"]');if(attach){attach.click();await sleep(500);input=[...document.querySelectorAll('input[type="file"]')].find(x=>!x.accept||x.accept.includes('image')||x.accept.includes('*'));}}
   if(!input)throw Error('未找到原图上传控件，请在ChatGPT手动上传；未发送任务');
   if(task.references.length>1&&!input.multiple)throw Error('当前上传控件不支持多图，请在网页手动上传；未发送任务');
   const transfer=new DataTransfer();
   for(const r of task.references){const bytes=Uint8Array.from(atob(r.base64),c=>c.charCodeAt(0));transfer.items.add(new File([bytes],r.name,{type:r.mime}));}
   input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}));
   await tell(task,'waiting','原图已交给网页上传；请等待附件完成');
   await sleep(3000);
   const uploadDeadline=Date.now()+90000;
   while(document.querySelector('[role="progressbar"],button[aria-label*="Cancel upload"],button[aria-label*="取消上传"]')){if(stop||Date.now()>uploadDeadline)throw Error('原图上传未完成，请检查网页；未发送任务');await sleep(1000);}
   if(document.querySelector('[role="alert"]')?.textContent?.match(/fail|error|失败|错误/i))throw Error('网页报告上传异常；未发送任务');
  }
  const before=document.querySelectorAll('[data-message-author-role="assistant"]').length;
  editor=findEditor();if(!editor)throw Error('上传后输入框变化，请刷新对话；未发送');
  editor.focus();
  if(editor instanceof HTMLTextAreaElement){Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(editor,task.prompt);editor.dispatchEvent(new Event('input',{bubbles:true}));}
  else{document.execCommand('insertText',false,task.prompt);editor.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:task.prompt}));}
  await sleep(800);
  const send=document.querySelector('[data-testid="send-button"],button[aria-label="Send prompt"],button[aria-label="发送提示"],button[aria-label="发送消息"]');if(!send||send.disabled)throw Error('发送按钮不可用，请检查上传、验证或额度；未发送');
  await tell(task,'sending','即将发送，异常时不会自动重发');send.click();await tell(task,'waiting','已点击发送，等待新回复生成图片');
  const deadline=Date.now()+10*60*1000;
  while(Date.now()<deadline){
   if(stop)throw Error('已暂停；请检查网页结果');
   const replies=[...document.querySelectorAll('[data-message-author-role="assistant"]')];
   if(replies.length>before&&!document.querySelector('[data-testid="stop-button"]')){
    const last=replies.at(-1);
    const imgs=[...last.querySelectorAll('img')].filter(i=>i.complete&&i.naturalWidth>=512&&i.naturalHeight>=512);
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
  throw Error('等待超时，请检查验证、限额或网页变化；不会重发');
 }catch(e){await tell(task,'needs_attention',e.message).catch(()=>{});}finally{running=false;}
}
chrome.runtime.onMessage.addListener((m,sender,reply)=>{if(m.kind==='preflight'){reply(preflight());return false;}if(m.kind==='stop'){stop=true;reply({ok:true});}if(m.kind==='start'){run(m.task);reply({ok:true});}return false;});})();
