(()=>{
 function contentRoots(doc){return [...(doc.querySelectorAll?.('main,[role="main"]')||[])];}
 function main(doc){
  const roots=contentRoots(doc);
  if(!roots.length)return doc.querySelector?.('main,[role="main"]')||null;
  const score=n=>{
   const text=(n.innerText||n.textContent||'').trim().length;
   const images=n.querySelectorAll?.('img').length||0;
   const replies=n.querySelectorAll?.('[data-message-author-role="assistant"],.markdown').length||0;
   const visible=n.getClientRects?!!n.getClientRects().length:true;
   return (visible?1:0.01)*(Math.min(text,200000)+images*1000+replies*500);
  };
  return roots.reduce((best,n)=>score(n)>score(best)?n:best,roots[0]);
 }
 function userOwned(node){return node.closest?.('[data-message-author-role="user"],[data-turn="user"],[class*="group/user-message"]')!=null;}
 function assistantNodes(doc){
  const roots=[...doc.querySelectorAll('[data-message-author-role="assistant"], [data-turn="assistant"]')];
  // Some page layouts expose markdown siblings outside the role wrapper. Include only
  // bounded reply blocks; never turn a whole article/conversation into an assistant reply.
  for(const node of doc.querySelectorAll('main .markdown, [role="main"] .markdown')){
   if(userOwned(node))continue;
   if(!roots.some(root=>root.contains?.(node)))roots.push(node);
  }
  return [...new Set(roots)].filter(n=>!userOwned(n)).sort((a,b)=>{
   if(a===b)return 0;const p=a.compareDocumentPosition?.(b)||0;return p&4?-1:p&2?1:0;
  });
 }
 function userNodes(doc){return [...doc.querySelectorAll('[data-message-author-role="user"], [data-turn="user"], [class*="group/user-message"]')].filter(n=>!n.querySelector?.('[data-message-author-role="user"], [data-turn="user"], [class*="group/user-message"]'));}
 function requestReplies(doc,marker){
  const users=userNodes(doc);
  const start=[...users].reverse().find(n=>(n.innerText||n.textContent||'').includes(marker));
  if(!start)return null;
  const next=users.find(n=>n!==start&&!!(start.compareDocumentPosition(n)&4));
  return assistantNodes(doc).filter(n=>!!(start.compareDocumentPosition(n)&4)&&(!next||!!(n.compareDocumentPosition(next)&4)));
 }
 function imageScopes(doc,{before=new Set(),marker=''}={}){
  let roots=assistantNodes(doc);
  const users=userNodes(doc);
  const start=marker?users.find(n=>(n.innerText||n.textContent||'').includes(marker)):null;
  if(start){
   const next=users.find(n=>n!==start&&!!(start.compareDocumentPosition(n)&4));
   roots=roots.filter(n=>!!(start.compareDocumentPosition(n)&4)&&(!next||!!(n.compareDocumentPosition(next)&4)));
  }else if(before.size){roots=roots.filter(n=>!before.has(n));}
  else{
   // Recovery of legacy tasks: use only the latest image reply's user request.
   const last=[...roots].reverse().find(n=>assistantImages(n).length);
   if(!last)return [];
   const prior=[...users].reverse().find(n=>!!(n.compareDocumentPosition(last)&4));
   roots=prior?roots.filter(n=>!!(prior.compareDocumentPosition(n)&4)&&!(last.compareDocumentPosition(n)&4)):[last];
  }
  return roots;
 }
 function assistantImages(root){
  return [...root.querySelectorAll('img')].filter(i=>!userOwned(i)&&!i.closest?.('aside,[role="complementary"],#prompt-textarea'));
 }
 function generating(doc){
  return !!doc.querySelector('[data-testid="stop-button"],button[aria-label="Stop generating"],button[aria-label="Stop streaming"],button[aria-label="停止生成"],button[aria-label="停止流式传输"],main [data-is-streaming="true"],[role="main"] [data-is-streaming="true"]');
 }
 function region(doc,{marker='',allowPartial=false}={}){
  const root=main(doc);let anchor=null;
  if(root&&marker&&doc.createTreeWalker){const walker=doc.createTreeWalker(root,4);let node;while((node=walker.nextNode()))if(node.nodeValue.includes(marker))anchor=node;}
  const next=anchor?userNodes(doc).find(n=>!!(anchor.compareDocumentPosition(n)&4)):null;
  return {root,anchor,includes:n=>!!root&&!userOwned(n)&&!(allowPartial&&marker&&!anchor)&&(!anchor||!!(anchor.compareDocumentPosition(n)&4))&&(!next||!!(n.compareDocumentPosition(next)&4))};
 }
 globalThis.OzonConversation={assistantNodes,assistantImages,userOwned,imageScopes,requestReplies,main,contentRoots,userNodes,generating,region};
 if(typeof module!=='undefined')module.exports=globalThis.OzonConversation;
})();
