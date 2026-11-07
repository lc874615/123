(()=>{
 function snapshot(){
  const doc=document,main=globalThis.OzonConversation.main(doc);const text=main?.innerText||'';
  const selectors=['main','[role="main"]','[data-message-author-role="assistant"]','[data-message-author-role="user"]','[data-turn="assistant"]','main .markdown','main img'];
  const ancestry=node=>{const result=[];for(let n=node;n&&result.length<7;n=n.parentElement)result.push({tag:n.tagName,role:n.getAttribute('role'),testid:n.getAttribute('data-testid'),author:n.getAttribute('data-message-author-role'),turn:n.getAttribute('data-turn'),className:String(n.className||'').slice(0,180)});return result;};
  const roots=globalThis.OzonConversation.contentRoots(doc);
  return {roots:roots.map((n,index)=>({index,selected:n===main,textLength:(n.innerText||n.textContent||'').length,images:n.querySelectorAll('img').length,visible:!!n.getClientRects().length,ancestors:ancestry(n)})),version:'0.18.0',origin:location.origin,counts:Object.fromEntries(selectors.map(s=>[s,doc.querySelectorAll(s).length])),assistantScopes:globalThis.OzonConversation?.assistantNodes(doc).length||0,json:{visibleTextLength:text.length,completeObjects:globalThis.OzonCopy?.parseAll(text).length||0,openBraces:(text.match(/\{/g)||[]).length,closeBraces:(text.match(/\}/g)||[]).length},images:[...(main?.querySelectorAll('img')||[])].slice(-60).map(i=>{const r=i.getBoundingClientRect();let host='';try{host=new URL(i.currentSrc||i.src,location.href).hostname;}catch{}return {host,natural:[i.naturalWidth,i.naturalHeight],rendered:[Math.round(r.width),Math.round(r.height)],position:[Math.round(r.left),Math.round(r.top)],complete:i.complete,userOwned:globalThis.OzonConversation?.userOwned(i),ancestors:ancestry(i)};}),textContainers:[...(main?.querySelectorAll('pre,code,.markdown,[data-message-author-role]')||[])].slice(-20).map(n=>({length:(n.innerText||n.textContent||'').length,ancestors:ancestry(n)}))};
 }
 globalThis.OzonDiagnostics={snapshot};
})();
