(()=>{
 function visible(el){return !!el&&el.getClientRects().length>0&&el.getAttribute('aria-hidden')!=='true';}
 function enabled(el){return visible(el)&&!el.disabled&&el.getAttribute('aria-disabled')!=='true';}
 function findSend(editor,doc=document){
  const root=editor.closest('form,[class*="ComposerLayoutRoot"],[data-testid="composer"],[data-composer-root]');
  const scope=root||doc;
  const explicit=[...scope.querySelectorAll('[data-testid="send-button"], [data-testid="composer-send-button"], button[aria-label="Send"], button[aria-label="Send prompt"], button[aria-label="Send message"], button[aria-label="Отправить"], button[aria-label="发送"], button[aria-label="发送提示"], button[aria-label="发送消息"], button[aria-label="提交"], button[title="Send"], button[title="发送"]')].filter(enabled);
  if(explicit.length===1)return explicit[0];
  if(!root)return null;
  const local=[...root.querySelectorAll('button')].filter(b=>enabled(b)&&(/^(send|send prompt|send message|отправить|发送|发送消息|发送提示|提交)$/i.test((b.getAttribute('aria-label')||b.getAttribute('title')||b.textContent||'').trim())||b.type==='submit'));
  return local.length===1?local[0]:null;
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
 function sameDraft(a,b){const text=v=>String(v||'').replace(/[\u200b\ufeff]/g,'').replace(/\s+/g,' ').trim();return !!text(b)&&text(a)===text(b);}
 globalThis.OzonComposer={findSend,visible,enabled,waitSend,sameDraft,sendOwnedByEnter};
})();
