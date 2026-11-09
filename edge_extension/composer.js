(()=>{
 function visible(el){return !!el&&el.getClientRects().length>0&&el.getAttribute('aria-hidden')!=='true';}
 function enabled(el){return visible(el)&&!el.disabled&&el.getAttribute('aria-disabled')!=='true';}
 function findSend(editor,doc=document){
  const explicit=[...doc.querySelectorAll('[data-testid="send-button"], [data-testid="composer-send-button"], button[aria-label="Send prompt"], button[aria-label="Send message"], button[aria-label="发送"], button[aria-label="发送提示"], button[aria-label="发送消息"], button[aria-label="提交"], button[title="Send"], button[title="发送"]')].filter(enabled);
  if(explicit.length===1)return explicit[0];
  const form=editor.closest('form');if(!form)return null;
  const local=[...form.querySelectorAll('button')].filter(b=>enabled(b)&&(/^(send|send prompt|send message|发送|发送消息|发送提示|提交)$/i.test((b.getAttribute('aria-label')||b.getAttribute('title')||b.textContent||'').trim())||b.type==='submit'));
  return local.length===1?local[0]:null;
 }
 async function waitSend(editor,{doc=document,sleep=ms=>new Promise(r=>setTimeout(r,ms)),stopped=()=>false,now=Date.now,timeout=20000}={}){
  const deadline=now()+timeout;
  while(now()<deadline){if(stopped())throw Error('文案任务已暂停，未点击发送');const found=findSend(editor,doc);if(found)return found;await sleep(250);}
  return null;
 }
 function sameDraft(a,b){const text=v=>String(v||'').replace(/\r\n/g,'\n').trim();return !!text(b)&&text(a)===text(b);}
 globalThis.OzonComposer={findSend,visible,enabled,waitSend,sameDraft};
})();
