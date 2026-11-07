(()=>{
 function score(input){
  if(input.disabled)return -1;
  const a=(input.accept||'').toLowerCase();
  if(a.includes('image'))return 100+(input.multiple?10:0);
  if(/\.(png|jpe?g|webp)/.test(a))return 80+(input.multiple?10:0);
  if(!a||a==='*/*')return 20+(input.multiple?10:0);
  return -1;
 }
 function pick(inputs){return [...inputs].filter(x=>score(x)>=0).sort((a,b)=>score(b)-score(a))[0]||null;}
 function batches(files,multiple){return multiple?[files]:files.map(f=>[f]);}
 function editorRoot(editor){return editor.closest('form')||editor.parentElement?.parentElement||editor.parentElement;}
 function attachmentImages(doc,editor){
  const root=editorRoot(editor),nodes=new Set(root?[...root.querySelectorAll('img')]:[]);
  for(const image of doc.querySelectorAll('[class*="composer-attachment-surface"] img,[data-testid="composer-attachment"] img'))nodes.add(image);
  return [...nodes].filter(i=>!i.closest('[class*="group/user-message"],[data-message-author-role]'));
 }
 function filesFor(references){
  const transfer=new DataTransfer();
  for(const ref of references){const bytes=Uint8Array.from(atob(ref.base64),c=>c.charCodeAt(0));transfer.items.add(new File([bytes],ref.name,{type:ref.mime}));}
  return transfer;
 }
 async function upload(references,{doc=document,editor,sleep,stopped,report,timeout=90000}){
  const root=editorRoot(editor);if(!root)throw Error('未找到附件区域，未发送任务');
  if(attachmentImages(doc,editor).length)throw Error('输入框已有附件，请先处理后重试；未追加参考图、未发送任务');
  let input=pick(doc.querySelectorAll('input[type="file"]'));
  // Work may create file inputs only after using an attachment menu. Pasting files
  // invokes its existing attachment handler without opening a native file picker.
  const mode=input?'input':'paste';
  for(const group of batches(references,input?input.multiple:true)){
   if(stopped())throw Error('已暂停，未发送任务');
   const before=new Map();for(const image of attachmentImages(doc,editor)){const src=image.currentSrc||image.src;before.set(src,(before.get(src)||0)+1);}
   const transfer=filesFor(group);
   if(mode==='input'){
    input=pick(doc.querySelectorAll('input[type="file"]'));if(!input)throw Error('上传控件变化，已暂停，未发送任务');
    input.value='';input.files=transfer.files;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));
   }else{
    editor.focus();const paste=new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData:transfer});editor.dispatchEvent(paste);
   }
   await report((mode==='paste'?'正在通过粘贴自动上传 ':'正在自动上传 ')+group.map(x=>x.name).join('、'));
   const end=Date.now()+timeout;let stable=0,lastReport=0;
   while(Date.now()<end){
    if(stopped())throw Error('已暂停，未发送任务');
    const currentRoot=editorRoot(doc.querySelector('#prompt-textarea')||editor);
    const alert=[...(currentRoot?.querySelectorAll('[role="alert"]')||[])].map(x=>x.textContent).join(' ');
    if(/fail|error|失败|错误/i.test(alert))throw Error('原图上传失败，未发送任务');
    const current=new Map();for(const image of attachmentImages(doc,editor).filter(i=>i.complete&&i.naturalWidth>0)){const src=image.currentSrc||image.src;current.set(src,(current.get(src)||0)+1);}
    const complete=[...current].reduce((n,[src,count])=>n+Math.max(0,count-(before.get(src)||0)),0);
    const progress=currentRoot?.querySelector('[role="progressbar"],button[aria-label*="Cancel upload"],button[aria-label*="取消上传"]');
    if(Date.now()-lastReport>=2000){await report('原图附件已识别 '+Math.min(complete,group.length)+'/'+group.length+'；'+(mode==='paste'?'粘贴上传':'文件控件上传')+'，确认完成后才发送');lastReport=Date.now();}
    if(complete>=group.length&&!progress){if(++stable>=3)break;}else stable=0;
    await sleep(600);
   }
   if(stable<3)throw Error(mode==='paste'?'页面未确认粘贴图片上传完成，已暂停；请导出含上传入口的页面诊断，未发送作图任务':'未确认原图附件上传完成，已暂停，未发送任务');
   await report('原图附件上传已确认 '+group.length+'/'+group.length+'；准备发送作图任务');
  }
 }
 globalThis.OzonUploads={score,pick,batches,upload,attachmentImages};
})();
