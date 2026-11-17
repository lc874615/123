(()=>{
 function visible(el){return !!el&&el.getClientRects().length>0&&el.getAttribute('aria-hidden')!=='true';}
 function enabled(el){return visible(el)&&!el.disabled&&el.getAttribute('aria-disabled')!=='true';}
 function findSend(editor,doc=document){
  const roots=[...new Set([editor.closest('form'),editor.closest('[class*="ComposerLayoutRoot"],[class*="ComposerLayoutBody"],[data-testid="composer"],[data-composer-root]')].filter(Boolean))];
  const scopes=roots.length?roots:[doc];
  for(const scope of scopes){
   const explicit=[...scope.querySelectorAll('[data-testid="send-button"], [data-testid="composer-send-button"], button[aria-label="Send"], button[aria-label="Send prompt"], button[aria-label="Send message"], button[aria-label="Отправить"], button[aria-label="发送"], button[aria-label="发送提示"], button[aria-label="发送消息"], button[aria-label="提交"], button[title="Send"], button[title="发送"]')].filter(enabled);
   if(explicit.length===1)return explicit[0];
   if(explicit.length>1)return null;
   if(scope===doc)continue;
   const local=[...scope.querySelectorAll('button')].filter(b=>enabled(b)&&(/^(send|send prompt|send message|отправить|发送|发送消息|发送提示|提交)$/i.test((b.getAttribute('aria-label')||b.getAttribute('title')||b.textContent||'').trim())||b.type==='submit'));
   if(local.length===1)return local[0];
   if(local.length>1)return null;
  }
  return null;
 }
 async function waitSend(editor,{doc=document,sleep=ms=>new Promise(r=>setTimeout(r,ms)),stopped=()=>false,now=Date.now,timeout=20000,getEditor=()=>editor}={}){
  const deadline=now()+timeout;
  while(now()<deadline){if(stopped())throw Error('文案任务已暂停，未点击发送');const live=getEditor();const found=live?findSend(live,doc):null;if(found)return found;await sleep(250);}
  return null;
 }
 async function sendOwnedByEnter(editor,{doc=document,expected,marker,sleep,stopped,report,timeout=5000,now=Date.now,getEditor=()=>editor}){
  if(globalThis.OzonConversation.requestAnchor(doc,marker))return true;
  const draft=()=>{editor=getEditor();if(!editor||editor.isConnected===false)return '';return editor.value??editor.innerText??editor.textContent??'';};
  if(stopped()||!sameDraft(draft(),expected)||globalThis.OzonConversation.generating(doc))throw Error('输入框内容或页面状态已变化，未发送任务');
  await report('发送按钮未识别，正在确认当前任务草稿并尝试一次Enter发送');
  if(globalThis.OzonConversation.requestAnchor(doc,marker))return true;
  if(stopped()||!sameDraft(draft(),expected)||globalThis.OzonConversation.generating(doc))throw Error('任务已暂停或草稿改变，未发送');
  editor.focus();editor.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true}));editor.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));
  const end=now()+timeout;
  while(now()<end&&!stopped()){
   if(globalThis.OzonConversation.requestAnchor(doc,marker))return true;
   await sleep(250);
  }
  throw Error('Enter发送结果不确定，提示词和附件已保留；请核对原对话，不会自动重发');
 }
 async function submitOwned({doc=document,expected,marker,getEditor,references=[],sleep=ms=>new Promise(r=>setTimeout(r,ms)),stopped=()=>false,report=async()=>{},now=Date.now,timeout=45000,confirmMs=12000}){
  const conversation=globalThis.OzonConversation;
  const accepted=()=>!!conversation.requestAnchor(doc,marker);
  await conversation.expandUserPrompts?.(doc,{sleep,stopped});
  const draft=e=>e?.value??e?.innerText??e?.textContent??'';
  let actions=0,sawConsumption=false,enterUsed=false;const deadline=now()+timeout;
  while(now()<deadline){
   if(stopped())throw Error('已暂停，未继续发送任务');
   if(accepted())return true;
   const e=getEditor();
   if(conversation.generating(doc)){sawConsumption=true;await sleep(250);continue;}
   if(!e||e.isConnected===false){await sleep(250);continue;}
   if(!sameDraft(draft(e),expected)){
    if(actions){sawConsumption=true;await sleep(250);continue;}
    throw Error('输入框内容或页面状态已变化，未发送任务');
   }
   if(sawConsumption){await sleep(250);continue;}
   const attachments=globalThis.OzonUploads?.attachmentState?.(doc,e,references);
   if(attachments&&(attachments.progress||references.length&&attachments.ready<references.length)){await report('附件仍在上传，完成后自动发送当前任务');await sleep(500);continue;}
   if(attachments?.error)throw Error('原图附件上传失败，未发送任务');
   const button=findSend(e,doc),form=e.closest?.('form');
   // The first click may be ignored during React updates. Only retry once when the
   // exact owned draft remains, no generation began and no request marker exists.
   if(actions>=2)break;
   await report(actions?'当前草稿尚未提交，正在重新确认并发送':'正在提交当前任务并核对发送回执');
   if(stopped())throw Error('已暂停，未继续发送任务');
   if(accepted())return true;
   const live=getEditor();if(live!==e||!sameDraft(draft(live),expected)||conversation.generating(doc))continue;
   const freshButton=findSend(live,doc);if(button!==freshButton)continue;
   if(actions>0&&form?.requestSubmit&&form.contains(live))form.requestSubmit();
   else if(freshButton&&freshButton.isConnected!==false){freshButton.focus?.();freshButton.click();}
   else if(form?.requestSubmit&&form.contains(live))form.requestSubmit();
   else{
    if(enterUsed)break;enterUsed=true;
    live.focus();live.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true}));live.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));
   }
   actions++;let expandedAt=-Infinity;const until=Math.min(deadline,now()+confirmMs);
   while(now()<until){
    if(stopped())throw Error('已暂停；发送可能已执行，请核对已有请求');
    if(accepted())return true;
    if(now()-expandedAt>=1000){expandedAt=now();await conversation.expandUserPrompts?.(doc,{sleep,stopped});if(accepted())return true;}
    const current=getEditor();
    if(conversation.generating(doc)||current&&!sameDraft(draft(current),expected))sawConsumption=true;
    await sleep(250);
   }
  }
  if(accepted())return true;
  throw Error('发送结果尚未确认，已保留当前任务；请核对页面回执，不会启动下一任务或重复生成');
 }
 function sameDraft(a,b){const text=v=>String(v||'').replace(/[\u200b\ufeff]/g,'').replace(/\s+/g,' ').trim();return !!text(b)&&text(a)===text(b);}
 globalThis.OzonComposer={submitOwned,findSend,visible,enabled,waitSend,sameDraft,sendOwnedByEnter};
})();
