(()=>{
 function ordered(images,expected){
  const full=images.filter(i=>i.complete&&i.naturalWidth>=512&&i.naturalHeight>=512);
  // The selected preview precedes the strip in the DOM. Use the strip order instead.
  const strip=full.filter(i=>{const r=i.getBoundingClientRect();return r.width>0&&r.width<=160&&r.height<=220;});
  if(strip.length===expected)return strip;
  return full;
 }
 async function collect(doc,{expected=8,previous=new Set(),before=new Set(),marker=''}={}){
  const scopes=globalThis.OzonConversation.imageScopes(doc,{before,marker});
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
   if(results.length===expected)return results;
   if(results.length>expected)throw Error('当前回复原图数量超过预期，无法确认顺序；未覆盖已有图片');
   // Never fill a partial reply with unrelated images from older replies.
   return null;
  }
  return null;
 }
 globalThis.OzonImages={ordered,collect};
 if(typeof module!=='undefined')module.exports={ordered,collect};
})();
