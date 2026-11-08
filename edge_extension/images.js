(()=>{
 function ordered(images,expected){
  const full=images.filter(i=>i.complete&&i.naturalWidth>=512&&i.naturalHeight>=512);
  // The selected preview precedes the strip in the DOM. Use the strip order instead.
  const strip=full.filter(i=>{const r=i.getBoundingClientRect();return r.width>0&&r.width<=160&&r.height<=220;});
  if(strip.length===expected&&full.length<=expected+1)return strip;
  return full;
 }
 function visibleImage(image){
  const r=image.getBoundingClientRect();return image.complete&&image.naturalWidth>0&&r.width>0&&r.height>0&&r.bottom>0&&r.top<(image.ownerDocument.defaultView?.innerHeight||10000);
 }
 function structuralGallery(doc,{expected=8,marker='',allowPartial=false,continuations=false}={}){
  const main=globalThis.OzonConversation.main(doc);if(!main)return null;
  const anchor=globalThis.OzonConversation.requestAnchor(doc,marker);
  if(allowPartial&&marker&&!anchor)return null;
  const nextUser=anchor?globalThis.OzonConversation.nextUser(doc,anchor,{continuations}):null;
  const matches=[];
  for(const button of main.querySelectorAll('button[data-testid="generated-image-preview"]')){
   if(globalThis.OzonConversation.userOwned(button)||anchor&&!(anchor.compareDocumentPosition(button)&4)||nextUser&&!(button.compareDocumentPosition(nextUser)&4))continue;
   const preview=button.querySelector('img');if(!preview)continue;
   if(expected===1&&preview.complete&&preview.naturalWidth>=512&&preview.naturalHeight>=512){matches.push({preview,strip:[preview],structural:true});continue;}
   for(let root=button.parentElement;root&&root!==main;root=root.parentElement){
    if(root.querySelectorAll('button[data-testid="generated-image-preview"]').length!==1)break;
    const strip=root.querySelector('[class*="vertical-scroll-fade-mask"]');if(!strip)continue;
    const thumbs=[...strip.querySelectorAll('button img')].filter(i=>i.complete&&i.naturalWidth>0&&!globalThis.OzonConversation.userOwned(i));
    if(thumbs.length===expected||allowPartial&&anchor&&thumbs.length>0&&thumbs.length<expected)matches.push({preview,strip:thumbs,structural:true});
    break;
   }
  }
  if(matches.length>1)throw Error('当前请求包含多个生成图库，无法确定主图顺序，已暂停');
  return matches[0]||null;
 }
 function gallery(doc,{expected=8,marker='',allowPartial=false,continuations=false}={}){
  const structural=structuralGallery(doc,{expected,marker,allowPartial,continuations});if(structural)return structural;
  const main=globalThis.OzonConversation.main(doc);if(!main)return null;
  const all=[...main.querySelectorAll('img')].filter(i=>visibleImage(i)&&!globalThis.OzonConversation.userOwned(i)&&!i.closest('aside,[role="complementary"],#prompt-textarea'));
  const anchor=globalThis.OzonConversation.requestAnchor(doc,marker);
  if(allowPartial&&marker&&!anchor)return null;
  const images=anchor?all.filter(i=>!!(anchor.compareDocumentPosition(i)&4)):all;
  const large=images.filter(i=>{const r=i.getBoundingClientRect();return r.width>=240&&r.height>=280&&i.naturalWidth>=512&&i.naturalHeight>=512;});
  const found=[];
  for(const preview of large){
   const p=preview.getBoundingClientRect();
   const strip=images.filter(i=>{const r=i.getBoundingClientRect();return i!==preview&&r.width>=20&&r.width<=120&&r.height>=25&&r.height<=180&&r.left>=p.right-8&&r.left<=p.right+110&&r.top>=p.top-25&&r.bottom<=p.bottom+30;}).sort((a,b)=>a.getBoundingClientRect().top-b.getBoundingClientRect().top);
   if((strip.length===expected||(allowPartial&&anchor&&strip.length>0&&strip.length<expected))&&strip.every((i,n)=>!n||i.getBoundingClientRect().top>=strip[n-1].getBoundingClientRect().bottom-3))found.push({preview,strip});
  }
  if(found.length>1)throw Error('发现多个可见图库，请滚动到当前任务的图库后重试，未猜测图片顺序');
  return found[0]||null;
 }
 async function bytesFor(image){
  const response=await fetch(image.currentSrc||image.src,{credentials:'include'});if(!response.ok)throw Error('原图读取失败，HTTP '+response.status);
  const blob=await response.blob();if(blob.size>20*1024*1024)throw Error('图片超过20MB');
  const bytes=await blob.arrayBuffer();const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');
  const base64=await new Promise((resolve,reject)=>{const f=new FileReader();f.onload=()=>resolve(f.result.split(',')[1]);f.onerror=reject;f.readAsDataURL(blob);});
  const bitmap=await createImageBitmap(blob);const canvas=document.createElement('canvas');canvas.width=32;canvas.height=32;const ctx=canvas.getContext('2d');ctx.drawImage(bitmap,0,0,32,32);const pixels=ctx.getImageData(0,0,32,32).data;bitmap.close();
  return {digest,base64,pixels};
 }
 async function readGallery(doc,found,{expected=8,sleep=ms=>new Promise(r=>setTimeout(r,ms)),stopped=()=>false,report=async()=>{},onImage=async()=>{},allowPartial=false,continuations=false}={}){
  const original=found.preview,position=original.getBoundingClientRect(),results=[],hashes=new Set();
  if(found.structural&&found.strip.every(i=>i.naturalWidth>=512&&i.naturalHeight>=512)){
   for(let index=0;index<found.strip.length;index++){
    if(stopped())throw Error('已暂停，已有图片保留');
    await report('读取生成图库原图 '+(index+1)+'/'+expected+'（不受滚动位置影响）');
    const value=await bytesFor(found.strip[index]);if(hashes.has(value.digest))throw Error('生成图库中不同位置的图片内容重复');
    hashes.add(value.digest);results.push(value.base64);await onImage(index,value.base64);
   }
   return results.length===expected?results:null;
  }
  const thumbnails=[];for(const image of found.strip)thumbnails.push(await bytesFor(image));
  for(let index=0;index<found.strip.length;index++){
   if(stopped())throw Error('已暂停，已有图片保留');
   await report('已识别'+found.strip.length+'张生成图缩略图，正在读取原图 '+(index+1)+'/'+expected);
   const thumb=found.strip[index],target=thumb.closest('button,[role="button"]')||thumb;
   target.click();let ready=null,stable='',repeats=0;const deadline=Date.now()+15000;
   while(Date.now()<deadline){
    await sleep(250);if(stopped())throw Error('已暂停');
    const candidates=[...doc.querySelectorAll('main img,[role="main"] img')].filter(i=>{const r=i.getBoundingClientRect();return visibleImage(i)&&i.naturalWidth>=512&&i.naturalHeight>=512&&r.width>=240&&Math.abs(r.left-position.left)<35&&Math.abs(r.top-position.top)<60&&!globalThis.OzonConversation.userOwned(i);});
    if(candidates.length!==1)continue;
    const selected=candidates[0],src=selected.currentSrc||selected.src;
    const key=src+'|'+selected.naturalWidth+'|'+selected.naturalHeight;
    repeats=key===stable?repeats+1:1;stable=key;
    // A lazy image may retain the previous preview while the next one downloads.
    if(repeats<3)continue;
    const value=await bytesFor(selected);
    if(hashes.has(value.digest))continue;
    const distances=thumbnails.map(t=>{let error=0;for(let k=0;k<t.pixels.length;k+=4)for(let c=0;c<3;c++)error+=Math.abs(t.pixels[k+c]-value.pixels[k+c]);return error/(32*32*3);});
    const nearest=distances.indexOf(Math.min(...distances));
    if(nearest!==index||distances[index]>20)continue;
    ready=value;break;
   }
   if(!ready)throw Error('第'+(index+1)+'张原图未加载或仍是上一张；已暂停，不会把缩略图当原图保存');
   hashes.add(ready.digest);results.push(ready.base64);await onImage(index,ready.base64);
  }
  if(results.length!==expected){if(allowPartial)return null;throw Error('图库原图数量不完整');}
  return results;
 }
 async function collect(doc,{expected=8,previous=new Set(),before=new Set(),marker='',sleep,stopped,report,onImage=async()=>{},allowPartial=false,continuations=false}={}){
  if(globalThis.OzonConversation.generating(doc))return null;
  const inventory=inspect(doc,{expected,marker,allowPartial,continuations});
  if(inventory.overflow){const error=Error('当前任务生成图片超过'+expected+'张，等待最终编号文件；不会截取前'+expected+'张');error.code='DELIVERY_AMBIGUOUS';throw error;}
  const found=gallery(doc,{expected,marker,allowPartial,continuations});
  if(found)return readGallery(doc,found,{expected,sleep,stopped,report,onImage,allowPartial});
  const scopes=globalThis.OzonConversation.imageScopes(doc,{before,marker,continuations});
  const nodes=[];
  for(const scope of scopes){
   nodes.push(...globalThis.OzonConversation.assistantImages(scope).filter(i=>!previous.has(i.currentSrc||i.src)));
  }
  {
   const candidates=ordered([...new Set(nodes)],expected);if(!candidates.length)return null;
   const hashes=new Set(),results=[];
   for(const i of candidates){
    const response=await fetch(i.currentSrc||i.src,{credentials:'include'});if(!response.ok)throw Error('原图读取失败，已有文件保留');
    const blob=await response.blob();if(blob.size>20*1024*1024)throw Error('图片超过20MB');
    const bytes=await blob.arrayBuffer();const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');
    if(hashes.has(digest))continue;hashes.add(digest);
    results.push(await new Promise((resolve,reject)=>{const f=new FileReader();f.onload=()=>resolve(f.result.split(',')[1]);f.onerror=reject;f.readAsDataURL(blob);}));
   }
   if(results.length===expected){for(let index=0;index<results.length;index++)await onImage(index,results[index]);return results;}
   if(results.length>expected){const error=Error('当前回复原图数量超过预期，等待最终编号文件；未覆盖已有图片');error.code='DELIVERY_AMBIGUOUS';throw error;}
   // Never fill a partial reply with unrelated images from older replies.
   return null;
  }
  return null;
 }
 function inspect(doc,options={}){
  const scope=globalThis.OzonConversation.region(doc,options),expected=options.expected||8;
  if(!scope.root)return {count:0,overflow:false,signature:''};
  const images=[...scope.root.querySelectorAll('img')].filter(scope.includes);
  let count=0;
  for(const strip of scope.root.querySelectorAll('[class*="vertical-scroll-fade-mask"]')){
   const thumbs=[...strip.querySelectorAll('button img')].filter(scope.includes);count=Math.max(count,thumbs.length);
  }
  for(const preview of images){
   const p=preview.getBoundingClientRect();if(p.width<240||p.height<280)continue;
   const thumbs=images.filter(i=>{const r=i.getBoundingClientRect();return i!==preview&&r.width>=20&&r.width<=160&&r.height>=25&&r.height<=220&&r.left>=p.right-8&&r.left<=p.right+120&&r.top>=p.top-25;});
   count=Math.max(count,thumbs.length);
  }
  const originals=images.filter(i=>i.complete&&i.naturalWidth>=512&&i.naturalHeight>=512);
  if(!count){
   const compact=originals.filter(i=>{const r=i.getBoundingClientRect();return r.width>0&&r.width<=160&&r.height<=220;});
   count=compact.length===expected&&originals.length===expected+1?expected:new Set(originals.map(i=>i.currentSrc||i.src)).size;
  }else{
   const compact=originals.filter(i=>{const r=i.getBoundingClientRect();return r.width>0&&r.width<=160&&r.height<=220;});
   if(!(compact.length===count&&originals.length===count+1))count=Math.max(count,new Set(originals.map(i=>i.currentSrc||i.src)).size);
  }
  return {count,overflow:count>expected,signature:images.map(i=>(i.currentSrc||i.src)+'|'+i.naturalWidth+'x'+i.naturalHeight).join('\n')};
 }
 globalThis.OzonImages={ordered,collect,gallery,readGallery,inspect};
 if(typeof module!=='undefined')module.exports={ordered,collect,gallery,readGallery,inspect};
})();
