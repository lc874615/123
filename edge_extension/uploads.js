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
 async function upload(references,{doc=document,editor,sleep,stopped,report,timeout=90000}){
  let input=pick(doc.querySelectorAll('input[type="file"]'));
  if(!input){
   const add=doc.querySelector('button[data-testid="composer-plus-btn"],button[aria-label*="Attach"],button[aria-label*="添加"]');
   if(add){add.click();await sleep(500);input=pick(doc.querySelectorAll('input[type="file"]'));}
  }
  if(!input)throw Error('未找到图片上传控件，已暂停，未发送任务');
  const root=editor.closest('form')||editor.parentElement?.parentElement;
  if(!root)throw Error('未找到附件区域，未发送任务');
  const seen=()=>[...root.querySelectorAll('img')].filter(x=>x.complete&&x.naturalWidth>0).length;
  const progress=()=>root.querySelector('[role="progressbar"],button[aria-label*="Cancel upload"],button[aria-label*="取消上传"]');
  for(const group of batches(references,input.multiple)){
   if(stopped())throw Error('已暂停，未发送任务');
   input=pick(doc.querySelectorAll('input[type="file"]'));
   if(!input)throw Error('上传控件变化，已暂停，未发送任务');
   const before=seen(),transfer=new DataTransfer();
   for(const ref of group){const bytes=Uint8Array.from(atob(ref.base64),c=>c.charCodeAt(0));transfer.items.add(new File([bytes],ref.name,{type:ref.mime}));}
   input.value='';input.files=transfer.files;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));
   await report('正在自动上传 '+group.map(x=>x.name).join('、'));
   const end=Date.now()+timeout;let stable=0;
   while(Date.now()<end){
    if(stopped())throw Error('已暂停，未发送任务');
    const alert=[...root.querySelectorAll('[role="alert"]')].map(x=>x.textContent).join(' ');
    if(/fail|error|失败|错误/i.test(alert))throw Error('原图上传失败，未发送任务');
    if(seen()>=before+group.length&&!progress()){if(++stable>=3)break;}else stable=0;
    await sleep(600);
   }
   if(stable<3)throw Error('未确认原图附件上传完成，已暂停，未发送任务');
  }
 }
 globalThis.OzonUploads={score,pick,batches,upload};
})();
