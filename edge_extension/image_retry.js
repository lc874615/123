// A completed, stable reply with no complete deliverable may trigger a bounded follow-up.
(()=>{
 async function maybe(doc,{task,marker,stopped,findEditor,sleep,report}){
  if(!task.auto_image_retry||stopped()||globalThis.OzonConversation.generating(doc)){task._missingSince=null;return false;}
  const replies=globalThis.OzonConversation.requestReplies(doc,marker);
  if(!replies?.length)return false;
  const signature=replies.map(n=>n.innerText||n.textContent||'').join('\n')+'|'+(globalThis.__ozonDeliveryInfo?.candidateCount||0)+'|'+(globalThis.__ozonDeliveryInfo?.fileCount||0);
  const now=Date.now();if(task._missingSignature!==signature){task._missingSignature=signature;task._missingSince=now;return false;}
  if(now-task._missingSince<60000)return false;
  let editor=findEditor();if(!editor)throw Error('未找到输入框，未自动补生成');
  if((editor.value??editor.innerText??editor.textContent??'').trim())throw Error('输入框已有内容，未覆盖，未自动补生成');
  const retry=await chrome.runtime.sendMessage({kind:'image-retry',task_id:task.id,source_marker:marker,reply_finished:true,no_collectable_result:true});
  if(retry?.error)throw Error(retry.error);if(retry?.done)return false;
  if(stopped())throw Error('已暂停，补图请求未点击发送；恢复时先核对原页面');
  editor=findEditor();if(!editor)throw Error('补图准备后输入框变化，未点击发送');
  if((editor.value??editor.innerText??editor.textContent??'').trim())throw Error('输入框已有内容，未覆盖，补图未点击发送');
  const text=retry.prompt+'\n'+retry.marker;editor.focus();
  if(editor instanceof HTMLTextAreaElement){Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(editor,text);editor.dispatchEvent(new Event('input',{bubbles:true}));}
  else{document.execCommand('insertText',false,text);editor.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:text}));}
  let send=null;const deadline=Date.now()+15000;
  while(Date.now()<deadline&&!stopped()){const current=findEditor();if(current)send=globalThis.OzonComposer.findSend(current);if(send)break;await sleep(300);}
  if(stopped()||!send)throw Error('补图请求未确认发送，请核对输入框；不重复发送');
  if(globalThis.OzonConversation.generating(doc))throw Error('原回复继续生成，未点击补图请求；请核对原页面');
  task.recovery_marker=retry.marker;task.collection_expected=retry.count;task.collection_offset=retry.offset;task._missingSince=null;task._deliveryStable=null;task._deliveryNotice=null;task._retrySentAt=Date.now();
  send.click();await report('回复已结束但独立成品缺失，已自动补生成第'+retry.attempt+'次；等待对应原图');
  return true;
 }
 globalThis.OzonImageRetry={maybe};
})();
