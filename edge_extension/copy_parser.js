(()=>{
 function parseAll(text){
  const clean=String(text||'').replace(/\u00a0/g,' '),values=[];
  for(let start=clean.indexOf('{');start>=0;start=clean.indexOf('{',start+1)){
   let depth=0,quoted=false,escaped=false;
   for(let j=start;j<clean.length;j++){
    const c=clean[j];if(quoted){if(escaped)escaped=false;else if(c==='\\')escaped=true;else if(c==='"')quoted=false;continue;}
    if(c==='"'){quoted=true;continue;}if(c==='{')depth++;if(c==='}'&&--depth===0){
     try{const v=JSON.parse(clean.slice(start,j+1));if(typeof v.title_ru==='string'&&typeof v.description_ru==='string'&&Array.isArray(v.tags_ru)&&Array.isArray(v.missing_facts))values.push(v);}catch{}
     break;
    }
   }
  }return values;
 }
 function parse(text){return parseAll(text)[0]||null;}
 function latest(doc=document,options={}){
  const assistants=[...doc.querySelectorAll('[data-message-author-role="assistant"]')];
  // Never parse the whole conversation: it can return an older product's JSON.
  const nodes=assistants.length?assistants:[...doc.querySelectorAll('main article .markdown,main .markdown')];
  const ordered=nodes.reverse();
  for(const node of (options.bindLatest?ordered.slice(0,1):ordered)){
   if(options.before?.has(node))continue;
   const blocks=[node,...node.querySelectorAll('pre,code')];
   for(const b of blocks){for(const text of [b.innerText,b.textContent]){
    for(const raw of parseAll(text).reverse()){
     if(options.exclude?.has(JSON.stringify(raw)))continue;
     let v=raw;
     // Only a reply created after THIS request may inherit its task identifier.
     if(options.sku&&v.sku==null&&(options.before&&!options.before.has(node)||options.bindLatest))v={...v,sku:options.sku};
     if(!options.sku||v.sku===options.sku)return v;
    }
   }}
  }return null;
 }
 function snapshot(doc=document){const values=new Set();for(const node of doc.querySelectorAll('[data-message-author-role="assistant"],main article .markdown')){for(const text of [node.innerText,node.textContent])for(const v of parseAll(text))values.add(JSON.stringify(v));}return values;}
 globalThis.OzonCopy={parse,parseAll,latest,snapshot};
})();
