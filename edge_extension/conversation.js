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
  // New Work layouts expose hashed Markdown/DIL blocks instead of author roles.
  const modern=doc.querySelectorAll('main [class*="MarkdownRoot-"],main [class*="DilResponseRoot-"],main [class*="block-"],[role="main"] [class*="MarkdownRoot-"],[role="main"] [class*="DilResponseRoot-"]');
  for(const node of modern){
   if(userOwned(node)||node.querySelector?.('[class*="group/user-message"],[data-message-author-role="user"]'))continue;
   const block=[...(node.classList||[])].some(c=>/^block-[\w]+$/.test(c));
   if(!block&&!/MarkdownRoot-|DilResponseRoot-/.test(String(node.className||'')))continue;
   if(block&&!node.querySelector?.('[class*="MarkdownRoot-"],[class*="DilResponseRoot-"],[data-testid="generated-image-preview"],[class*="group/resource-row"]'))continue;
   if(!roots.some(root=>root.contains?.(node)))roots.push(node);
  }
  const bounded=[...new Set(roots)].filter(n=>!userOwned(n));
  return bounded.filter(n=>!bounded.some(other=>other!==n&&other.contains?.(n))).sort((a,b)=>{
   if(a===b)return 0;const p=a.compareDocumentPosition?.(b)||0;return p&4?-1:p&2?1:0;
  });
 }
 function userNodes(doc){return [...doc.querySelectorAll('[data-message-author-role="user"], [data-turn="user"], [class*="group/user-message"]')].filter(n=>!n.querySelector?.('[data-message-author-role="user"], [data-turn="user"], [class*="group/user-message"]'));}
 function requestReplies(doc,marker){
  const users=userNodes(doc);
  const start=[...users].reverse().find(n=>(String(n.innerText||'')+' '+String(n.textContent||'')).includes(marker));
  if(!start)return null;
  const next=users.find(n=>n!==start&&!!(start.compareDocumentPosition(n)&4));
  return assistantNodes(doc).filter(n=>!!(start.compareDocumentPosition(n)&4)&&(!next||!!(n.compareDocumentPosition(next)&4)));
 }
 function imageScopes(doc,{before=new Set(),marker='',continuations=false}={}){
  let roots=assistantNodes(doc);
  const users=userNodes(doc);
  const start=marker?users.find(n=>(String(n.innerText||'')+' '+String(n.textContent||'')).includes(marker)):null;
  if(start){
   const next=nextUser(doc,start,{continuations});
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
 function nextUser(doc,anchor,{continuations=false}={}){return userNodes(doc).find(n=>!!(anchor.compareDocumentPosition(n)&4)&&(!continuations||/【OZON_(?:TASK|COPY):/.test(String(n.innerText||'')+' '+String(n.textContent||''))));}
 function region(doc,{marker='',allowPartial=false,continuations=false}={}){
  const root=main(doc);let anchor=null;
  if(root&&marker&&doc.createTreeWalker){const walker=doc.createTreeWalker(root,4);let node;while((node=walker.nextNode()))if(node.nodeValue.includes(marker))anchor=node;}
  const next=anchor?nextUser(doc,anchor,{continuations}):null;
  return {root,anchor,includes:n=>!!root&&!userOwned(n)&&!(allowPartial&&marker&&!anchor)&&(!anchor||!!(anchor.compareDocumentPosition(n)&4))&&(!next||!!(n.compareDocumentPosition(next)&4))};
 }
 async function revealRequest(doc,marker,{sleep=ms=>new Promise(r=>setTimeout(r,ms)),stopped=()=>false,report=async()=>{}}={}){
  const find=()=>userNodes(doc).find(n=>(String(n.innerText||'')+' '+String(n.textContent||'')).includes(marker));
  const expanded=new WeakSet();
  async function expandPrompts(){let changed=false;for(const user of userNodes(doc))for(const b of user.querySelectorAll('button,[role="button"]')){const label=(b.textContent||b.getAttribute('aria-label')||'').trim();if(!expanded.has(b)&&/^(?:展开|显示更多|查看更多|read more|show more)$/i.test(label)&&b.getAttribute('aria-expanded')!=='true'){expanded.add(b);b.click();changed=true;}}if(changed)await sleep(250);}
  await expandPrompts();let found=find();if(found){found.scrollIntoView?.({block:'center'});await sleep(350);return true;}
  const root=main(doc);if(!root)return false;
  const candidates=[root,...root.querySelectorAll('*')];for(let n=root.parentElement;n;n=n.parentElement)candidates.push(n);
  const scroller=candidates.filter(n=>n.scrollHeight>n.clientHeight+100&&n.clientHeight>150&&/auto|scroll/.test(doc.defaultView.getComputedStyle(n).overflowY)).sort((a,b)=>b.clientHeight-a.clientHeight)[0]||doc.scrollingElement;
  if(!scroller)return false;const start=scroller.scrollTop;let previous=-1,stalled=0;
  await report('正在自动定位本任务的原始作图回复；只读取已有结果');scroller.scrollTop=0;await sleep(400);
  for(let i=0;i<60;i++){
   if(stopped())throw Error('已暂停，已有文件保留');
   await expandPrompts();found=find();if(found){found.scrollIntoView?.({block:'center'});await sleep(350);return true;}
   const position=scroller.scrollTop;if(position===previous)stalled++;else stalled=0;if(stalled>=3)break;previous=position;
   scroller.scrollTop+=Math.max(scroller.clientHeight*.8,400);await sleep(300);
  }
  scroller.scrollTop=start;return false;
 }
 globalThis.OzonConversation={nextUser,revealRequest,assistantNodes,assistantImages,userOwned,imageScopes,requestReplies,main,contentRoots,userNodes,generating,region};
 if(typeof module!=='undefined')module.exports=globalThis.OzonConversation;
})();
