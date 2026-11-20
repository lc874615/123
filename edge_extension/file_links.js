(()=>{
 function allowed(href){
  try{const u=new URL(href,location.href);
   return u.protocol==='sandbox:'||u.protocol==='https:'&&(u.hostname==='chatgpt.com'||u.hostname.endsWith('.oaiusercontent.com'))||u.protocol==='blob:'&&u.origin==='https://chatgpt.com'||/^data:(?:image\/(?:png|jpeg|webp)|application\/octet-stream);/i.test(href);
  }catch{return false;}
 }
 const FILE_NAME=/\b[^\s/\\]+?\.(?:jpe?g|png|webp)\b/i,FILE_NAMES=/\b[^\s/\\]+?\.(?:jpe?g|png|webp)\b/gi;
 function oneFile(text){return new Set(String(text||'').match(FILE_NAMES)||[]).size===1;}
 // Work's current file card is often a plain div and no longer carries the
 // historical group/resource-row class.  Keep the card bounded to one file.
 function resourceRow(element){
  const known=element.closest?.('[class*="group/resource-row"],[class*="resource-row"],[class*="resourceRow"],[data-testid="resource-row"],[data-testid*="resource"],[data-testid*="attachment"],[class*="attachment"]');
  if(known)return known;
  for(let node=element,depth=0;node&&depth<6;node=node.parentElement,depth++){
   // At depth zero a compact, one-file card is itself a safe resource even
   // before its hover-only download button has been mounted.
   if(oneFile(node.textContent)&&(depth===0||(node.matches?.('a,button,[role="link"],[role="button"]'))||node.querySelector?.('a[href],button,[role="link"],[role="button"]')))return node;
  }
  return null;
 }
 function fileLabel(element){
  const row=resourceRow(element);
  const own=element.getAttribute('download')||element.getAttribute('aria-label')||element.textContent||'';
  const rowName=row?.querySelector?.('button[aria-label],a[download]')?.getAttribute('aria-label')||'';
  const names=new Set();
  const parts=[own,row?.innerText||'',rowName];
  for(const label of row?.querySelectorAll?.('[aria-label],[download],span')||[]){
   parts.push(label.getAttribute('aria-label')||label.getAttribute('download')||label.textContent||'');
  }
  for(const part of parts)for(const name of String(part).match(FILE_NAMES)||[])names.add(name);
  return names.size?[...names].join(' '):own.trim();
 }
 function directTarget(element){
  const row=resourceRow(element);if(!row)return null;
  if(/^(?:下载|下载文件|下载图片|download|download file|download image)$/i.test((element.getAttribute?.('aria-label')||element.getAttribute?.('title')||element.textContent||'').trim()))return element;
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
  return !!FILE_NAME.test(text)&&oneFile(text)&&(element.matches('button,[role="link"],[role="button"],a')||!!resourceRow(element));
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
   for(let parent=button.parentElement,level=0;parent&&parent!==main&&level<7;parent=parent.parentElement,level++)if(/\.(?:jpe?g|png|webp)\b/i.test(parent.textContent||'')){files=true;break;}
   if(!files)continue;
   await report('正在自动展开生成图片文件列表');button.click();count++;
  }
  if(count)await new Promise(resolve=>setTimeout(resolve,350));
  return count;
 }
 function candidates(doc,{marker='',expected=8,allowPartial=false,manual=false,onlyVisible=false,inventory=false,continuations=false,task=null,fileGroup=null}={}){
  const main=fileGroup||globalThis.OzonConversation.main(doc);if(!main||fileGroup&&!fileGroup.isConnected)return null;
  const anchor=globalThis.OzonConversation.requestAnchor(doc,marker);
  if(allowPartial&&marker&&!anchor)return null;
  const nextUser=anchor?globalThis.OzonConversation.nextUser(doc,anchor,{continuations}):null;
  if(expected===1&&anchor&&!fileGroup){
   const replies=globalThis.OzonConversation.assistantNodes(doc).filter(node=>
    !!(anchor.compareDocumentPosition(node)&4)&&(!nextUser||!!(node.compareDocumentPosition(nextUser)&4)));
   for(const reply of replies.reverse()){
    const found=candidates(doc,{marker,expected,allowPartial,inventory:true,continuations,task,fileGroup:reply});
    if(found?.complete)return inventory?found:{images:found.images};
    if(found?.present)break;
   }
  }
  const images=new Map(),unnumbered=new Map();
  const basic=[...main.querySelectorAll('a[href],button,[role="link"],[role="button"]')];
  // Modern resource cards can be non-semantic wrappers.  Add only short,
  // one-file wrappers so normal answer prose can never become a candidate.
  const wrappers=[...main.querySelectorAll('[data-testid],[class*="resource"],[class*="attachment"],div,span')].filter(node=>{
   const text=node.textContent||'';if(!(text.length<220&&oneFile(text)&&!!FILE_NAME.test(text)&&!!resourceRow(node)))return false;
   // Retain only the outer card, never both it and its filename label.
   for(let parent=node.parentElement,depth=0;parent&&parent!==main&&depth<5;parent=parent.parentElement,depth++)if((parent.textContent||'').length<220&&oneFile(parent.textContent))return false;
   return true;
  });
  const elements=[...new Set([...basic,...wrappers])].filter(element=>!globalThis.OzonConversation.userOwned(element)&&(!anchor||!!(anchor.compareDocumentPosition(element)&4))&&(!nextUser||!!(element.compareDocumentPosition(nextUser)&4)));
  const resourceElements=elements.filter(element=>resourceRow(element)&&allowedElement(element));
  const skuMatches=resourceElements.filter(e=>task?.sku&&fileLabel(e).includes(task.sku));
  const selectedElements=expected===1&&skuMatches.length?skuMatches:resourceElements.length?resourceElements:elements;
  // The final downloadable file cards outrank earlier prose links and image attempts.
  for(const element of selectedElements){
   if(globalThis.OzonConversation.userOwned(element)||anchor&&!(anchor.compareDocumentPosition(element)&4)||nextUser&&!(element.compareDocumentPosition(nextUser)&4))continue;
   if(onlyVisible||manual&&!anchor){const r=element.getBoundingClientRect();if(!r.width||!r.height||r.bottom<=0||r.top>=doc.defaultView.innerHeight)continue;}
   let source=element,href=element.getAttribute('href');
   if(!href){const links=[...(resourceRow(element)?.querySelectorAll?.('a[href],[role="link"][href]')||[])].filter(link=>oneFile(fileLabel(link))&&allowedElement(link));if(links.length===1){source=links[0];href=source.getAttribute('href');}}
   if(!allowedElement(element))continue;let pathname='';try{pathname=decodeURIComponent(new URL(href,location.href).pathname);}catch{}
   const label=fileLabel(element);
   if(new Set(label.match(FILE_NAMES)||[]).size>1)continue;
   const name=(label.match(FILE_NAME)?.[0]||pathname.split('/').at(-1)||'').split(/[?#]/)[0];
   const ext=name.match(/\.(jpe?g|png|webp)$/i)?.[1]?.toLowerCase();if(!ext)continue;
   const target=directTarget(source)||directTarget(element);const link={element:target||source,href:target?target.getAttribute('href'):href,name,extension:ext,direct:!!target};
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
  const token=crypto.randomUUID();if(link.direct)link.element.setAttribute('data-ozon-direct-download','true');link.element.setAttribute('data-ozon-download',token);link.element.setAttribute('data-ozon-filename',link.name);
  try{
   const result=await chrome.runtime.sendMessage({kind:'download-asset',task_id:task.id,token,extension:link.extension});
   if(result?.error)throw Error(result.error);return result.images;
  }catch(error){throw Error('文件链接读取失败：'+error.message+'；直接读取：'+originalError.message);}
  finally{link.element.removeAttribute('data-ozon-filename');link.element.removeAttribute('data-ozon-download');link.element.removeAttribute('data-ozon-direct-download');}
 }
 async function collect(doc,options={}){
  if(globalThis.OzonConversation.generating(doc))return null;
  const expanded=options.fileGroup?0:await expandFiles(doc,options);
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
