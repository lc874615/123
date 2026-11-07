(()=>{
 function userOwned(node){return node.closest?.('[data-message-author-role="user"],[data-turn="user"]')!=null;}
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
 function userNodes(doc){return [...doc.querySelectorAll('[data-message-author-role="user"], [data-turn="user"]')].filter(n=>!n.querySelector?.('[data-message-author-role="user"], [data-turn="user"]'));}
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
 globalThis.OzonConversation={assistantNodes,assistantImages,userOwned,imageScopes,requestReplies};
 if(typeof module!=='undefined')module.exports=globalThis.OzonConversation;
})();
