(()=>{
 const text=editor=>editor.value??editor.innerText??editor.textContent??'';
 const marker=task=>task.marker||task.recovery_marker||task.source_marker||'【OZON_TASK:'+task.id+'】';
 async function prepare(task,{doc=document,findEditor,sleep,stopped,report}){
  let editor=findEditor();if(!editor)throw Error('未找到当前输入框');
  await globalThis.OzonConversation.expandUserPrompts?.(doc,{sleep,stopped});
  const ownMarker=marker(task),alreadySent=!!globalThis.OzonConversation.requestAnchor(doc,ownMarker),original=text(editor);
  const state=()=>globalThis.OzonUploads.attachmentState(doc,editor,task.references||[]);
  if(!original.trim()){
   if(alreadySent)return {alreadySent:true,marker:ownMarker};
   if(state().present)throw Error('输入框已有无法确认来源的附件，已保留，未追加或发送');
   return {alreadySent:false,marker:ownMarker};
  }
  if(!/【OZON_(?:TASK|COPY):[^】]+】/.test(original)&&!globalThis.OzonComposer.sameDraft(original,task.replace_unsent_prompt)&&!globalThis.OzonComposer.sameDraft(original,task.prompt)){
   if(alreadySent)return {alreadySent:true,marker:ownMarker};
   throw Error('输入框已有手写内容，已保留，未自动清空');
  }
  if(stopped()||globalThis.OzonConversation.generating(doc))throw Error('任务已暂停或页面仍在生成，未清空草稿');
  const saved=await chrome.runtime.sendMessage({kind:'backup-composer',task_id:task.id,text:original,attachments:(task.references||[]).map(r=>r.name)});
  if(saved?.error)throw Error(saved.error);if(!saved?.ok)throw Error('遗留草稿未完成备份，未清空');
  await report('已备份本任务遗留输入，正在清理后继续');
  const removals='button[aria-label*="Remove"],button[aria-label*="remove"],button[title*="Remove"],button[aria-label*="删除"],button[aria-label*="移除"],button[title*="删除"],button[data-testid="remove-attachment"]';
  for(let n=0;n<20;n++){
   editor=findEditor();if(!editor||stopped()||text(editor)!==original)throw Error('清理期间草稿已变化，停止清理并保留当前内容');
   const before=state().present;if(!before)break;
   const root=globalThis.OzonUploads.editorRoot(editor);const buttons=[...root.querySelectorAll(removals)].filter(b=>!b.disabled);
   if(!buttons.length)throw Error('未识别到遗留附件移除按钮，草稿已备份，未重新发送');
   buttons[0].click();let changed=false;
   for(let k=0;k<20&&!stopped();k++){await sleep(150);editor=findEditor();if(editor&&state().present<before){changed=true;break;}}
   if(!changed)throw Error('遗留附件尚未移除完成，未重新发送');
  }
  editor=findEditor();if(!editor||stopped()||text(editor)!==original||state().present)throw Error('输入框状态已变化或附件仍在，未继续发送');
  editor.focus();
  if(editor instanceof HTMLTextAreaElement){Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(editor,'');editor.dispatchEvent(new Event('input',{bubbles:true}));}
  else{const range=doc.createRange();range.selectNodeContents(editor);const selection=doc.defaultView.getSelection();selection.removeAllRanges();selection.addRange(range);doc.execCommand('delete',false);editor.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'deleteContentBackward'}));}
  await sleep(150);editor=findEditor();if(!editor||text(editor).trim()||state().present)throw Error('输入框未清空完成，未追加新任务');
  return {alreadySent:alreadySent||!!globalThis.OzonConversation.requestAnchor(doc,ownMarker),marker:ownMarker};
 }
 globalThis.OzonComposerCleanup={prepare,marker};
})();
