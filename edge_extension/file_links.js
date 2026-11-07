(()=>{
 function allowed(href){
  try{const u=new URL(href,location.href);
   return u.protocol==='sandbox:'||u.protocol==='https:'&&(u.hostname==='chatgpt.com'||u.hostname.endsWith('.oaiusercontent.com'))||u.protocol==='blob:'&&u.origin==='https://chatgpt.com'||/^data:(?:image\/(?:png|jpeg|webp)|application\/(?:zip|x-zip-compressed|octet-stream));/i.test(href);
  }catch{return false;}
 }
 function allowedElement(element){
  if(!element||globalThis.OzonConversation.userOwned(element))return false;
  const href=element.getAttribute('href');if(href)return allowed(href);
  const text=(element.getAttribute('aria-label')||element.textContent||'').trim();
  return element.matches('button,[role="link"],[role="button"]')&&(/\b[^\s/\\]+\.(?:jpe?g|png|webp|zip)\b/i.test(text)||/(?:下载|download).*zip/i.test(text));
 }
 async function expandFiles(doc,{report=async()=>{},stopped=()=>false,marker='',manual=false,allowPartial=false}={}){
  const main=globalThis.OzonConversation.main(doc);if(!main)return 0;let count=0;
  let anchor=null;if(marker){const walker=doc.createTreeWalker(main,4);let n;while((n=walker.nextNode()))if(n.nodeValue.includes(marker))anchor=n;}
  if(allowPartial&&marker&&!anchor)return 0;
  const nextUser=anchor?globalThis.OzonConversation.userNodes(doc).find(n=>!!(anchor.compareDocumentPosition(n)&4)):null;
  for(const button of main.querySelectorAll('button,[role="button"],summary')){
   if(stopped())throw Error('已暂停');
   if(globalThis.OzonConversation.userOwned(button))continue;
   if(!manual&&anchor&&(!(anchor.compareDocumentPosition(button)&4)||nextUser&&!(button.compareDocumentPosition(nextUser)&4)))continue;
   if(manual){const r=button.getBoundingClientRect();if(!r.width||!r.height||r.bottom<=0||r.top>=doc.defaultView.innerHeight)continue;}
   const text=(button.textContent||'').trim();
   if(!/^(?:(?:另有|还有)\s*\d+\s*(?:个|项|个文件)|(?:show\s+)?\d+\s+more(?:\s+files)?|show more(?:\s+files)?)$/i.test(text))continue;
   if(button.getAttribute('aria-expanded')==='true'||button.tagName==='SUMMARY'&&button.parentElement.open)continue;
   let files=false;
   for(let parent=button.parentElement,level=0;parent&&parent!==main&&level<5;parent=parent.parentElement,level++)if(/\.(?:jpe?g|png|webp|zip)\b/i.test(parent.textContent||'')){files=true;break;}
   if(!files)continue;
   await report('正在自动展开生成图片文件列表');button.click();count++;
  }
  if(count)await new Promise(resolve=>setTimeout(resolve,350));
  return count;
 }
 function candidates(doc,{marker='',expected=8,allowPartial=false,manual=false,onlyVisible=false}={}){
  const main=globalThis.OzonConversation.main(doc);if(!main)return null;
  let anchor=null;if(marker){const walker=doc.createTreeWalker(main,4);let n;while((n=walker.nextNode()))if(n.nodeValue.includes(marker))anchor=n;}
  if(allowPartial&&marker&&!anchor)return null;
  const nextUser=anchor?globalThis.OzonConversation.userNodes(doc).find(n=>!!(anchor.compareDocumentPosition(n)&4)):null;
  const images=new Map(),zips=[];
  for(const element of main.querySelectorAll('a[href],button,[role="link"],[role="button"]')){
   if(globalThis.OzonConversation.userOwned(element)||anchor&&!(anchor.compareDocumentPosition(element)&4)||nextUser&&!(element.compareDocumentPosition(nextUser)&4))continue;
   if(onlyVisible||manual&&!anchor){const r=element.getBoundingClientRect();if(!r.width||!r.height||r.bottom<=0||r.top>=doc.defaultView.innerHeight)continue;}
   const href=element.getAttribute('href');if(!allowedElement(element))continue;let pathname='';try{pathname=decodeURIComponent(new URL(href,location.href).pathname);}catch{}
   const label=(element.getAttribute('download')||element.getAttribute('aria-label')||element.textContent||'').trim();
   if((label.match(/[^\s/\\]+\.(?:jpe?g|png|webp|zip)\b/gi)||[]).length>1)continue;
   const name=(label.match(/[^\s/\\]+\.(?:jpe?g|png|webp|zip)\b/i)?.[0]||(/zip/i.test(label)?'product_images.zip':pathname.split('/').at(-1))||'').split(/[?#]/)[0];
   const ext=name.match(/\.(jpe?g|png|webp|zip)$/i)?.[1]?.toLowerCase();if(!ext)continue;
   const link={element,href,name,extension:ext};
   if(ext==='zip'){zips.push(link);continue;}
   const match=name.match(/^0*([1-8])(?:[_ .-])/);if(!match)continue;
   const index=Number(match[1]);
   if(images.has(index)&&images.get(index).name!==name)throw Error('同一图片编号出现多个不同下载链接，无法确认顺序');
   images.set(index,link);
  }
  const ordered=Array.from({length:expected},(_,i)=>images.get(i+1));
  if(zips.length===1)return {archive:zips[0],images:ordered.every(Boolean)?ordered:null};
  if(ordered.every(Boolean))return {images:ordered};
  if(manual&&marker)return candidates(doc,{expected,manual:false,onlyVisible:true});
  return null;
 }
 async function blob64(blob){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(blob);});}
 async function read(link,task){
  let originalError;
  try{
   if(!link.href)throw Error('文件由网页按钮提供，使用浏览器下载流程');
   const url=new URL(link.href,location.href);
   if(!['https:','blob:','data:'].includes(url.protocol))throw Error('链接需要通过浏览器下载');
   if(url.protocol==='https:'&&url.hostname!=='chatgpt.com'&&!url.hostname.endsWith('.oaiusercontent.com'))throw Error('下载链接不属于当前GPT文件服务');
   const response=await fetch(url.href,{credentials:'include'});if(!response.ok)throw Error('文件读取HTTP '+response.status);
   const blob=await response.blob();if(blob.size>20*1024*1024)throw Error('文件超过直接读取上限');
   if(link.extension==='zip'){
    const result=await chrome.runtime.sendMessage({kind:'decode-archive',task_id:task.id,archive_b64:await blob64(blob)});if(result?.error)throw Error(result.error);return result.images;
   }
   const bitmap=await createImageBitmap(blob);bitmap.close();
   return [await blob64(blob)];
  }catch(error){originalError=error;}
  const token=crypto.randomUUID();link.element.setAttribute('data-ozon-download',token);
  try{
   const result=await chrome.runtime.sendMessage({kind:'download-asset',task_id:task.id,token,extension:link.extension});
   if(result?.error)throw Error(result.error);return result.images;
  }catch(error){throw Error('文件链接读取失败：'+error.message+'；直接读取：'+originalError.message);}
  finally{link.element.removeAttribute('data-ozon-download');}
 }
 async function collect(doc,options={}){
  const expanded=await expandFiles(doc,options);
  let found=candidates(doc,options);
  const until=Date.now()+(expanded?5000:100);
  while(!found&&Date.now()<until){if(options.stopped?.())throw Error('已暂停');await new Promise(resolve=>setTimeout(resolve,200));found=candidates(doc,options);}
  if(!found)return null;
  const {task,expected=8,report=async()=>{},onImage=async()=>{},stopped=()=>false}=options;
  let images=[];
  if(found.archive){try{await report('正在读取商品图压缩包');images=await read(found.archive,task);}catch(error){if(!found.images||stopped())throw error;await report('压缩包读取失败，正在改为读取独立图片文件');}}
  if(!images.length&&found.images)for(let i=0;i<found.images.length;i++){
   if(stopped())throw Error('已暂停，已有文件保留');await report('正在读取商品图片文件 '+(i+1)+'/'+expected);
   images.push(...await read(found.images[i],task));
  }
  if(images.length!==expected)throw Error('读取到的独立图片数量不符');
  for(let i=0;i<images.length;i++){if(stopped())throw Error('已暂停');await onImage(i,images[i]);}
  return images;
 }
 globalThis.OzonFiles={collect,candidates,allowed,allowedElement,expandFiles};
})();
