(()=>{
 function allowed(href){
  try{const u=new URL(href,location.href);
   return u.protocol==='sandbox:'||u.protocol==='https:'&&(u.hostname==='chatgpt.com'||u.hostname.endsWith('.oaiusercontent.com'))||u.protocol==='blob:'&&u.origin==='https://chatgpt.com'||/^data:(?:image\/(?:png|jpeg|webp)|application\/octet-stream);/i.test(href);
  }catch{return false;}
 }
 function resourceRow(element){return element.closest('[class*="group/resource-row"],[data-testid="resource-row"]');}
 function fileLabel(element){return (element.getAttribute('download')||element.getAttribute('aria-label')||element.textContent||'').trim()+' '+(resourceRow(element)?.textContent||'');}
 function directTarget(element){
  const row=resourceRow(element);if(!row)return null;
  const buttons=[...row.querySelectorAll('button,[role="button"]')];
  const labelled=buttons.filter(b=>/^(?:下载|下载文件|下载图片|download|download file|download image)$/i.test((b.getAttribute('aria-label')||b.getAttribute('title')||b.textContent||'').trim()));
  if(labelled.length===1)return labelled[0];
  const secondary=buttons.filter(b=>!b.classList.contains('inset-0')&&!b.hasAttribute('aria-haspopup')&&!/\.(?:jpe?g|png|webp)\b/i.test((b.getAttribute('aria-label')||b.textContent||'')));
  return secondary.length===1?secondary[0]:null;
 }
 function allowedElement(element){
  if(!element||globalThis.OzonConversation.userOwned(element)||globalThis.OzonConversation.auxiliary(element)||/\.zip\b/i.test(fileLabel(element)))return false;
  const href=element.getAttribute('href');const label=(element.getAttribute('aria-label')||element.textContent||'');if(/\.zip(?:[?#]|$)/i.test(href||'')||/(?:下载|download).*zip/i.test(label))return false;if(href)return allowed(href);
  const text=fileLabel(element);
  return element.matches('button,[role="link"],[role="button"]')&&(/\b[^\s/\\]+\.(?:jpe?g|png|webp)\b/i.test(text));
 }
 async function expandFiles(doc,{report=async()=>{},stopped=()=>false,marker='',manual=false,allowPartial=false,continuations=false}={}){
  const main=globalThis.OzonConversation.main(doc);if(!main)return 0;let count=0;
  const anchor=globalThis.OzonConversation.requestAnchor(doc,marker);
  if(allowPartial&&marker&&!anchor)return 0;
  const nextUser=anchor?globalThis.OzonConversation.nextUser(doc,anchor,{continuations}):null;
  for(const button of main.querySelectorAll('button,[role="button"],summary')){
   if(stopped())throw Error('已暂停');
   if(globalThis.OzonConversation.userOwned(button)||globalThis.OzonConversation.auxiliary(button))continue;
   if(!manual&&anchor&&(!(anchor.compareDocumentPosition(button)&4)||nextUser&&!(button.compareDocumentPosition(nextUser)&4)))continue;
   if(manual&&!anchor){const r=button.getBoundingClientRect();if(!r.width||!r.height||r.bottom<=0||r.top>=doc.defaultView.innerHeight)continue;}
   const text=(button.textContent||button.getAttribute('aria-label')||'').trim();
   if(!/^(?:(?:另有|还有|另外|其余)\s*\d+\s*(?:个|项|个文件)|(?:show\s+)?\d+\s+more(?:\s+files)?|show more(?:\s+files)?|展开(?:全部|更多)?(?:文件|图片)?|显示全部文件)$/i.test(text))continue;
   if(button.getAttribute('aria-expanded')==='true'||button.tagName==='SUMMARY'&&button.parentElement.open)continue;
   let files=false;
   for(let parent=button.parentElement,level=0;parent&&parent!==main&&level<5;parent=parent.parentElement,level++)if(/\.(?:jpe?g|png|webp)\b/i.test(parent.textContent||'')){files=true;break;}
   if(!files)continue;
   await report('正在自动展开生成图片文件列表');button.click();count++;
  }
  if(count)await new Promise(resolve=>setTimeout(resolve,350));
  return count;
 }
 function candidates(doc,{marker='',expected=8,allowPartial=false,manual=false,onlyVisible=false,inventory=false,continuations=false,task=null}={}){
  const main=globalThis.OzonConversation.main(doc);if(!main)return null;
  const anchor=globalThis.OzonConversation.requestAnchor(doc,marker);
  if(allowPartial&&marker&&!anchor)return null;
  const nextUser=anchor?globalThis.OzonConversation.nextUser(doc,anchor,{continuations}):null;
  const images=new Map(),unnumbered=new Map();
  const elements=[...main.querySelectorAll('a[href],button,[role="link"],[role="button"]')].filter(element=>!globalThis.OzonConversation.userOwned(element)&&(!anchor||!!(anchor.compareDocumentPosition(element)&4))&&(!nextUser||!!(element.compareDocumentPosition(nextUser)&4)));
  const resourceElements=elements.filter(element=>resourceRow(element)&&allowedElement(element));
  const skuMatches=resourceElements.filter(e=>task?.sku&&fileLabel(e).includes(task.sku));
  const candidates=expected===1&&skuMatches.length?skuMatches:resourceElements.length?resourceElements:elements;
  // The final downloadable file cards outrank earlier prose links and image attempts.
  for(const element of candidates){
   if(globalThis.OzonConversation.userOwned(element)||anchor&&!(anchor.compareDocumentPosition(element)&4)||nextUser&&!(element.compareDocumentPosition(nextUser)&4))continue;
   if(onlyVisible||manual&&!anchor){const r=element.getBoundingClientRect();if(!r.width||!r.height||r.bottom<=0||r.top>=doc.defaultView.innerHeight)continue;}
   const href=element.getAttribute('href');if(!allowedElement(element))continue;let pathname='';try{pathname=decodeURIComponent(new URL(href,location.href).pathname);}catch{}
   const label=fileLabel(element);
   if(new Set(label.match(/[^\s/\\]+\.(?:jpe?g|png|webp)\b/gi)||[]).size>1)continue;
   const name=(label.match(/[^\s/\\]+\.(?:jpe?g|png|webp)\b/i)?.[0]||pathname.split('/').at(-1)||'').split(/[?#]/)[0];
   const ext=name.match(/\.(jpe?g|png|webp)$/i)?.[1]?.toLowerCase();if(!ext)continue;
   const target=directTarget(element);const link={element:target||element,href:target?target.getAttribute('href'):href,name,extension:ext,direct:!!target};
   const match=name.match(/^0*(\d{1,3})(?:[_ .-])/);if(!match){unnumbered.set(name,link);continue;}
   const index=Number(match[1]);
   if(images.has(index)&&images.get(index).name!==name)throw Error('同一图片编号出现多个不同下载链接，无法确认顺序');
   if(!images.get(index)?.direct||link.direct)images.set(index,link);
  }
  if(expected===1&&anchor&&images.size+unnumbered.size===1){const single=[...images.values(),...unnumbered.values()][0];images.clear();unnumbered.clear();images.set(1,single);}
  const ordered=Array.from({length:expected},(_,i)=>images.get(i+1));
  if(inventory)return {count:images.size,candidateTotal:images.size+unnumbered.size,present:images.size+unnumbered.size,complete:images.size===expected&&ordered.every(Boolean),images:ordered.filter(Boolean),signature:[...images].map(([n,r])=>n+':'+r.name+'|'+(r.href||'')).join('\n')};
  if(images.size===expected&&ordered.every(Boolean))return {images:ordered};
  if(manual&&marker&&!anchor)return candidates(doc,{expected,manual:false,onlyVisible:true});
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
   const bitmap=await createImageBitmap(blob);bitmap.close();
   return [await blob64(blob)];
  }catch(error){originalError=error;}
  const row=resourceRow(link.element);if(row){row.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));await new Promise(r=>setTimeout(r,150));const target=directTarget(link.element);if(target){link.element=target;link.direct=true;}}
  const token=crypto.randomUUID();if(link.direct)link.element.setAttribute('data-ozon-direct-download','true');link.element.setAttribute('data-ozon-download',token);
  try{
   const result=await chrome.runtime.sendMessage({kind:'download-asset',task_id:task.id,token,extension:link.extension});
   if(result?.error)throw Error(result.error);return result.images;
  }catch(error){throw Error('文件链接读取失败：'+error.message+'；直接读取：'+originalError.message);}
  finally{link.element.removeAttribute('data-ozon-download');link.element.removeAttribute('data-ozon-direct-download');}
 }
 async function collect(doc,options={}){
  if(globalThis.OzonConversation.generating(doc))return null;
  const expanded=await expandFiles(doc,options);
  let found=candidates(doc,options);
  const until=Date.now()+(expanded?5000:100);
  while(!found&&Date.now()<until){if(options.stopped?.())throw Error('已暂停');await new Promise(resolve=>setTimeout(resolve,200));found=candidates(doc,options);}
  if(!found)return null;
  const {task,expected=8,report=async()=>{},onImage=async()=>{},stopped=()=>false}=options;
  const images=[];
  for(let i=0;i<found.images.length;i++){
   if(stopped())throw Error('已暂停，已有文件保留');await report('正在下载独立商品图片 '+(i+1)+'/'+expected);
   if(globalThis.OzonConversation.generating(doc))return null;
   const result=await read(found.images[i],task);
   if(result.length!==1)throw Error('单个图片入口返回数量不符');images.push(result[0]);
   await onImage(i,result[0]);
  }
  if(images.length!==expected)throw Error('读取到的独立图片数量不符');
  return images;
 }
 globalThis.OzonFiles={collect,candidates,allowed,allowedElement,expandFiles,directTarget};
})();
