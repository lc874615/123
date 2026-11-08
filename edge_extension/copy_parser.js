(()=>{
 function readObject(text){
  try{return JSON.parse(text);}catch{}
  // Rendered plaintext replies may insert literal line breaks inside quoted values.
  let fixed='',quoted=false,escaped=false;
  for(const c of text){
   if(quoted){
    if(escaped){fixed+=c;escaped=false;continue;}
    if(c==='\\'){fixed+=c;escaped=true;continue;}
    if(c==='\n'){fixed+='\\n';continue;}if(c==='\r'){fixed+='\\r';continue;}if(c==='\t'){fixed+='\\t';continue;}
   }
   if(c==='"')quoted=!quoted;fixed+=c;
  }
  return JSON.parse(fixed);
 }
 function parseAll(text){
  const clean=String(text||'').replace(/\u00a0/g,' '),values=[];
  for(let start=clean.indexOf('{');start>=0;start=clean.indexOf('{',start+1)){
   let depth=0,quoted=false,escaped=false;
   for(let j=start;j<clean.length;j++){
    const c=clean[j];if(quoted){if(escaped)escaped=false;else if(c==='\\')escaped=true;else if(c==='"')quoted=false;continue;}
    if(c==='"'){quoted=true;continue;}if(c==='{')depth++;if(c==='}'&&--depth===0){
     try{const v=readObject(clean.slice(start,j+1));if((typeof v.title_ru==='string'&&typeof v.description_ru==='string'&&Array.isArray(v.tags_ru)&&Array.isArray(v.missing_facts))||(typeof v.sku==='string'&&v.variant_attributes&&typeof v.variant_attributes==='object'&&!Array.isArray(v.variant_attributes)))values.push(v);}catch{}
     break;
    }
   }
  }return values;
 }
 function parse(text){return parseAll(text)[0]||null;}
 function latest(doc=document,options={}){
  const nodes=options.marker?(globalThis.OzonConversation.requestReplies(doc,options.marker)||[]):globalThis.OzonConversation.assistantNodes(doc);
  const ordered=nodes.reverse();
  for(const node of (options.bindLatest?ordered.slice(0,1):ordered)){
   if(globalThis.OzonConversation.auxiliary(node))continue;
   const prior=options.beforeText?.get(node);
   if(options.before?.has(node)&&(!options.beforeText||prior===(node.innerText||node.textContent||'')))continue;
   const blocks=[node,...node.querySelectorAll('pre,code')];
   for(const b of blocks){if(globalThis.OzonConversation.auxiliary(b))continue;let texts=[b.innerText,b.textContent];
    if(options.assistantOnly&&b.cloneNode){const clean=b.cloneNode(true);for(const n of clean.querySelectorAll('aside,[role="complementary"],[class*="summary-panel"],[class*="summary-card"]'))n.remove();texts=[clean.textContent];}
    for(const text of texts){
    for(const raw of parseAll(text).reverse()){
     if(options.exclude?.has(JSON.stringify(raw)))continue;
     let v=raw;
     // Only a reply created after THIS request may inherit its task identifier.
     if(options.sku&&v.sku==null&&(options.before&&!options.before.has(node)||options.bindLatest))v={...v,sku:options.sku};
     if(!options.sku||v.sku===options.sku)return v;
    }
   }}
  }return options.assistantOnly?null:fromPageText(doc,options);
 }
 function fromPageText(doc,options){
  // Work layouts can render reply text without assistant/markdown attributes.
  // Only accept an explicit exact SKU here. Automatic reads also require the request marker.
  if(!options.sku)return null;
  const main=globalThis.OzonConversation.main(doc);if(!main)return null;
  for(let text of [main.innerText,main.textContent]){
   text=String(text||'');
   if(options.marker){const at=text.lastIndexOf(options.marker);if(at<0)continue;text=text.slice(at+options.marker.length);}
   for(const value of parseAll(text).reverse()){
    if(value.sku===options.sku&&!options.exclude?.has(JSON.stringify(value)))return value;
   }
  }return null;
 }
 function recover(doc,sku){
  const exact=latest(doc,{sku});if(exact)return {copy:exact};
  // An unlabelled historical response needs an explicit selection, not a guessed product binding.
  const selectors=[null];
  const candidates=[],seen=new Set();
  for(const sel of selectors){
   for(const node of globalThis.OzonConversation.assistantNodes(doc).reverse()){
    for(const block of [node,...node.querySelectorAll('pre,code')]){
     for(const text of [block.innerText,block.textContent]){
      for(const value of parseAll(text).reverse()){
       if(value.sku!=null)continue;
       const key=JSON.stringify(value);if(seen.has(key))continue;seen.add(key);candidates.push(value);
       if(candidates.length===10)return {candidates};
      }
     }
    }
   }
  }
  return {candidates};
 }
 function snapshot(doc=document){const values=new Set();for(const node of globalThis.OzonConversation.assistantNodes(doc)){for(const text of [node.innerText,node.textContent])for(const v of parseAll(text))values.add(JSON.stringify(v));}const main=globalThis.OzonConversation.main(doc);if(main)for(const text of [main.innerText,main.textContent])for(const v of parseAll(text))values.add(JSON.stringify(v));return values;}

 function autoExisting(doc,task){
  const full=v=>v&&typeof v.title_ru==='string'&&typeof v.description_ru==='string'&&Array.isArray(v.tags_ru)&&Array.isArray(v.missing_facts);
  if(task.previous_marker){const scoped=latest(doc,{sku:task.sku,marker:task.previous_marker,bindLatest:true,assistantOnly:true});if(full(scoped)&&(!scoped.facts_fingerprint||scoped.facts_fingerprint===task.fingerprint))return {...scoped,facts_fingerprint:task.fingerprint};}
  const value=latest(doc,{sku:task.sku,assistantOnly:true});if(!full(value))return null;
  if(value.facts_fingerprint&&value.facts_fingerprint!==task.fingerprint)return null;
  if(task.needsRefresh&&value.facts_fingerprint!==task.fingerprint)return null;
  return value;
 }
 globalThis.OzonCopy={autoExisting,parse,parseAll,latest,snapshot,recover};
})();
