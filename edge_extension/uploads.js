(()=>{
 function score(input){
  if(input.disabled||input.isConnected===false)return -1;
  const a=(input.accept||'').toLowerCase();
  if(a.includes('image'))return 100+(input.multiple?10:0);
  if(/\.(png|jpe?g|webp)/.test(a))return 80+(input.multiple?10:0);
  if(!a||a==='*/*')return 20+(input.multiple?10:0);
  return -1;
 }
 function pick(inputs){return [...inputs].filter(x=>score(x)>=0).sort((a,b)=>score(b)-score(a))[0]||null;}
 function batches(files,multiple){return multiple?[files]:files.map(f=>[f]);}
 function editorRoot(editor){return editor?.closest('form,[class*="ComposerLayoutRoot"],[data-testid="composer"],[data-composer-root]')||editor?.parentElement?.parentElement||editor?.parentElement;}
 function liveEditor(doc,previous){
  const found=[...new Set(doc.querySelectorAll('#prompt-textarea,[contenteditable="true"][data-lexical-editor="true"],[contenteditable="true"].ProseMirror,[role="textbox"][contenteditable="true"],textarea[placeholder]'))].filter(e=>e.isConnected!==false&&e.getClientRects().length&&!e.disabled&&e.getAttribute('aria-hidden')!=='true');
  if(found.includes(previous))return previous;
  if(found.length===1)return found[0];
  throw Error(found.length?'发现多个输入框，未猜选上传位置、未发送任务':'当前输入框已变化或不可见，未发送任务');
 }
 const cards='[class*="composer-attachment-surface"],[data-testid="composer-attachment"],[data-testid="attachment-preview"],[data-testid="file-upload"]';
 function attachmentImages(doc,editor){
  const root=editorRoot(editor);
  return [...(root?.querySelectorAll('img')||[])].filter(i=>!i.closest('[class*="group/user-message"],[data-message-author-role]'));
 }
 function attachmentState(doc,editor,references){
  const root=editorRoot(editor),images=attachmentImages(doc,editor),nodes=new Set();
  for(const image of images)if(image.complete&&image.naturalWidth>0)nodes.add(image.closest(cards)||image);
  const attachments=[...(root?.querySelectorAll(cards)||[])].filter(n=>!n.closest('[class*="group/user-message"],[data-message-author-role]'));
  for(const node of attachments){
   if(node.querySelector('img'))continue;
   const text=[node.textContent,node.getAttribute('aria-label'),node.getAttribute('title')].join(' ');
   const named=references.some(r=>r.name&&text.includes(r.name));
   const remove=node.querySelector('button[aria-label*="Remove"],button[aria-label*="remove"],button[aria-label*="移除"],button[aria-label*="删除"]');
   if(named&&remove&&!node.querySelector('[role="progressbar"],[aria-busy="true"]'))nodes.add(node);
  }
  const alert=[...(root?.querySelectorAll('[role="alert"]')||[])].map(x=>x.textContent).join(' ');
  const progress=root?.querySelector('[role="progressbar"],[aria-busy="true"],button[aria-label*="Cancel upload"],button[aria-label*="取消上传"]');
  return {ready:nodes.size,present:images.length+attachments.filter(n=>!n.querySelector('img')).length,progress:!!progress,error:/fail|error|失败|错误/i.test(alert),root};
 }
 function filesFor(references){
  const transfer=new DataTransfer();
  for(const ref of references){const bytes=Uint8Array.from(atob(ref.base64),c=>c.charCodeAt(0));transfer.items.add(new File([bytes],ref.name,{type:ref.mime}));}
  return transfer;
 }
 async function upload(references,{doc=document,editor,sleep,stopped,report,timeout=90000}){
  editor=liveEditor(doc,editor);let root=editorRoot(editor);if(!root)throw Error('未找到当前输入框附件区域，未发送任务');
  if(attachmentState(doc,editor,references).present)throw Error('输入框已有附件，请先处理后重试；未追加参考图、未发送任务');
  // Never select another image-generation form's hidden input from the whole document.
  let input=pick(root.querySelectorAll('input[type="file"]'));
  const mode=input?'input':'paste';
  globalThis.__ozonUploadInfo={mode,expected:references.length,recognized:0,scope:'current_composer'};
  for(const group of batches(references,input?input.multiple:true)){
   if(stopped())throw Error('已暂停，未发送任务');
   editor=liveEditor(doc,editor);root=editorRoot(editor);const before=attachmentState(doc,editor,references).ready;
   const transfer=filesFor(group);
   if(mode==='input'){
    input=pick(root.querySelectorAll('input[type="file"]'));if(!input)throw Error('当前输入框上传控件变化，未发送任务');
    if(group.length>1&&!input.multiple)throw Error('当前上传控件已切换为单文件，未发送任务');
    input.value='';input.files=transfer.files;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));
   }else{
    editor.focus();editor.dispatchEvent(new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData:transfer}));
   }
   await report((mode==='paste'?'正在向当前输入框粘贴上传 ':'正在向当前输入框上传 ')+group.map(x=>x.name).join('、'));
   const end=Date.now()+timeout;let stable=0,lastReport=0;
   while(Date.now()<end){
    if(stopped())throw Error('已暂停，未发送任务');
    editor=liveEditor(doc,editor);const state=attachmentState(doc,editor,references);
    if(state.error)throw Error('原图上传失败，未发送任务');
    const complete=Math.max(0,state.ready-before);
    globalThis.__ozonUploadInfo={mode,expected:group.length,recognized:complete,progress:state.progress,scope:'current_composer'};
    if(complete>group.length)throw Error('当前输入框附件数量超过本批参考图，未发送任务，请核对已有附件');
    if(Date.now()-lastReport>=2000){await report('原图附件已识别 '+complete+'/'+group.length+'；'+(mode==='paste'?'当前输入框粘贴上传':'当前输入框文件上传')+'，确认完成后才发送');lastReport=Date.now();}
    if(complete===group.length&&!state.progress){if(++stable>=3)break;}else stable=0;
    await sleep(600);
   }
   if(stable<3)throw Error('当前输入框未确认'+group.length+'张原图上传完成，已暂停且未发送任务；请核对原页面附件或导出页面诊断，不会跳过原图直接作图');
   await report('原图附件上传已确认 '+group.length+'/'+group.length+'；准备发送作图任务');
  }
 }
 globalThis.OzonUploads={score,pick,batches,upload,attachmentImages,attachmentState,editorRoot,liveEditor};
})();
