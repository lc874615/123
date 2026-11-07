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
 function latest(doc=document){
  const selectors=['[data-message-author-role="assistant"]','main article .markdown','main .markdown','main article'];
  for(const sel of selectors){const nodes=[...doc.querySelectorAll(sel)];for(let i=nodes.length-1;i>=0;i--){const v=parse(nodes[i].innerText||nodes[i].textContent);if(v)return v;}}
  return null;
 }
 globalThis.OzonCopy={parse,latest};
})();
