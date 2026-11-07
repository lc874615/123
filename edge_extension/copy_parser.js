(()=>{
 function parse(text){
  const clean=String(text||'').replace(/\u00a0/g,' ');
  for(let start=clean.indexOf('{');start>=0;start=clean.indexOf('{',start+1)){
   let depth=0,quoted=false,escaped=false;
   for(let j=start;j<clean.length;j++){
    const c=clean[j];if(quoted){if(escaped)escaped=false;else if(c==='\\')escaped=true;else if(c==='"')quoted=false;continue;}
    if(c==='"'){quoted=true;continue;}if(c==='{')depth++;if(c==='}'&&--depth===0){
     try{const v=JSON.parse(clean.slice(start,j+1));if(typeof v.title_ru==='string'&&typeof v.description_ru==='string'&&Array.isArray(v.tags_ru)&&Array.isArray(v.missing_facts))return v;}catch{}
     break;
    }
   }
  }return null;
 }
 function latest(doc=document,options={}){
  const selectors=['[data-message-author-role="assistant"]','main article .markdown','main .markdown','main article','[data-testid^="conversation-turn"]','[role="main"]','main'];
  for(const sel of selectors){const nodes=[...doc.querySelectorAll(sel)];for(let i=nodes.length-1;i>=0;i--){const node=nodes[i];const blocks=[...node.querySelectorAll('pre,code')].reverse();for(const b of [node,...blocks]){for(const text of [b.innerText,b.textContent]){const v=parse(text);if(v&&(!options.sku||v.sku===options.sku)&&!options.exclude?.has(JSON.stringify(v)))return v;}}}}
  return null;
 }
 function snapshot(doc=document){const values=new Set();for(const node of doc.querySelectorAll('[data-message-author-role="assistant"],main article,main .markdown,[data-testid^="conversation-turn"]')){for(const text of [node.innerText,node.textContent]){const v=parse(text);if(v)values.add(JSON.stringify(v));}}return values;}
 globalThis.OzonCopy={parse,latest,snapshot};
})();
