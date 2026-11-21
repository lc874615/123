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
 function composerOwned(node){return !!node?.closest?.('[contenteditable="true"],textarea,[role="textbox"],[data-testid="composer"],[data-composer-root],[data-composer-body],[class*="ComposerLayout"],[class*="composer-attachment"],#prompt-textarea');}
 function userOwned(node){return composerOwned(node)||node.closest?.('[data-message-author-role="user"],[data-turn="user"],[class*="group/user-message"]')!=null;}
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
 const USER='[data-message-author-role="user"], [data-turn="user"], [class~="group/user-message"], [data-testid="user-message"]';
 function userNodes(doc,thread=main(doc)||doc){
  const nodes=[...thread.querySelectorAll(USER)].filter(n=>!composerOwned(n)&&!auxiliary(n));
  return nodes.filter(n=>!nodes.some(other=>other!==n&&other.contains(n)));
 }
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
 function auxiliary(node){
  const panel=node.closest?.('aside,[role="complementary"],.summary-panel,.summary-card,[class~="group/summary-panel-item"],[class~="group/summary-panel"],[class~="group/summary-card"]');
  if(!panel)return false;
  const thread=node.closest('main,[role="main"]');
  // The application can mount the whole conversation inside an auxiliary shell.
  return !thread||thread.contains(panel)&&thread!==panel;
 }
 function assistantImages(root){
  return [...root.querySelectorAll('img')].filter(i=>!userOwned(i)&&!auxiliary(i)&&!i.closest?.('#prompt-textarea'));
 }
 function generating(doc){
  if(doc.querySelector('[data-testid="stop-button"],[data-testid="stop-generating-button"],button[aria-label="Stop generating"],button[aria-label="Stop streaming"],button[aria-label="停止生成"],button[aria-label="停止流式传输"],button[aria-label="停止回复"],main [data-is-streaming="true"],[role="main"] [data-is-streaming="true"]'))return true;
  const buttons=doc.querySelectorAll?.('button[aria-label],button[title]')||[];
  return [...buttons].some(button=>{
   if(button.getClientRects&&!button.getClientRects().length)return false;
   const label=button.getAttribute('aria-label')||button.getAttribute('title')||'';
   return /^(?:stop|stop response|stop generating|停止|停止回答|停止响应|停止生成|停止流式传输)$/i.test(label.trim());
  });
 }
 function nextUser(doc,anchor,{continuations=false}={}){
  const thread=main(doc);
  return userNodes(doc,thread?.contains(anchor)?thread:doc).find(n=>!!(anchor.compareDocumentPosition(n)&4)&&(!continuations||/【OZON_(?:TASK|COPY):/.test(String(n.innerText||'')+' '+String(n.textContent||''))));
 }
 function region(doc,{marker='',allowPartial=false,continuations=false}={}){
  const root=main(doc),anchor=requestAnchor(doc,marker);
  const next=anchor?nextUser(doc,anchor,{continuations}):null;
  return {root,anchor,includes:n=>!!root&&!userOwned(n)&&!(allowPartial&&marker&&!anchor)&&(!anchor||!!(anchor.compareDocumentPosition(n)&4))&&(!next||!!(n.compareDocumentPosition(next)&4))};
 }
 function requestAnchor(doc,marker){
  if(!marker)return null;
  if(marker.startsWith('OZON_OWN_REFERENCE:')){
   const sku=marker.slice('OZON_OWN_REFERENCE:'.length);
   const matches=userNodes(doc).filter(node=>[node.innerText,node.textContent].some(value=>{
    const text=value||'';
    const first=text.match(/(?:^|\n)1[：:]\s*[^\n]*?[；;]\s*货号\s+([^；;\n]+)[；;]\s*用途/m);
    return first?.[1].trim()===sku&&text.includes('【任务清单')&&text.includes('01_main.jpg');
   }));
   return matches.length===1?matches[0]:null;
  }
  const matches=n=>[n.innerText,n.textContent].some(text=>String(text||'').replace(/[\s\u200B-\u200D\uFEFF]/g,'').includes(marker));
  // A nested user-message element may contain only the attachment controls.
  // Filter by marker before pruning nested wrappers.
  function marked(root){
   const nodes=[...root.querySelectorAll(USER)].filter(n=>matches(n)&&!composerOwned(n)&&!auxiliary(n));
   return nodes.filter(n=>!nodes.some(other=>other!==n&&n.contains(other)));
  }
  const local=marked(main(doc)||doc);
  if(local.length)return local.length===1?local[0]:null;
  // Some layouts mount the request and its reply in sibling regions.
  const thread=main(doc);
  if(!thread)return null;
  const outside=marked(doc).filter(n=>!!(n.compareDocumentPosition(thread)&4));
  return outside.length===1?outside[0]:null;
 }
 async function expandUserPrompts(doc,{sleep=ms=>new Promise(r=>setTimeout(r,ms)),stopped=()=>false}={}){
  let changed=false;
  for(const user of userNodes(doc))for(const b of user.querySelectorAll('button,[role="button"]')){
   if(stopped())return;
   const label=(b.textContent||b.getAttribute('aria-label')||'').trim();
   if(/^(?:展开|显示更多|查看更多|read more|show more)$/i.test(label)&&b.getAttribute('aria-expanded')!=='true'){b.click();changed=true;}
  }
  if(changed)await sleep(150);
 }
 async function revealRequest(doc,marker,{sleep=ms=>new Promise(r=>setTimeout(r,ms)),stopped=()=>false,report=async()=>{},alternatives=[],onMarker=()=>{}}={}){
  globalThis.__ozonRecoveryInfo={phase:'locating',scrollers:0,checkedSegments:0,historyCandidates:alternatives.filter(m=>m!==marker).length};
  const expanded=new WeakSet();
  async function expandPrompts(){let changed=false;for(const user of userNodes(doc))for(const b of user.querySelectorAll('button,[role="button"]')){const label=(b.textContent||b.getAttribute('aria-label')||'').trim();if(!expanded.has(b)&&/^(?:展开|显示更多|查看更多|read more|show more)$/i.test(label)&&b.getAttribute('aria-expanded')!=='true'){expanded.add(b);b.click();changed=true;}}if(changed)await sleep(300);}
  async function found(wanted){
   await expandPrompts();
   for(const candidate of wanted){const node=requestAnchor(doc,candidate);if(!node)continue;
    node.scrollIntoView?.({block:'center',behavior:'instant'});await sleep(500);
    if(requestAnchor(doc,candidate)){globalThis.__ozonRecoveryInfo={...globalThis.__ozonRecoveryInfo,phase:'located',historical:candidate!==marker};onMarker(candidate);return true;}
   }return false;
  }
  if(await found([marker]))return true;
  const root=main(doc);if(!root)return false;
  const all=[root,...root.querySelectorAll('*')];for(let n=root.parentElement;n;n=n.parentElement)all.push(n);if(doc.scrollingElement)all.push(doc.scrollingElement);
  const width=root.getBoundingClientRect().width;
  // Work can scroll an overflow:hidden surface programmatically. Do not require auto/scroll CSS.
  const scrollers=[...new Set(all)].filter(n=>n.scrollHeight>n.clientHeight+80&&n.clientHeight>=150&&n.getBoundingClientRect().width>=Math.min(width*.6,400)).sort((a,b)=>{const user=userNodes(doc)[0],hasA=!!user&&a.contains(user),hasB=!!user&&b.contains(user);if(hasA!==hasB)return hasB-hasA;if(hasA&&a.contains(b))return 1;if(hasA&&b.contains(a))return -1;return b.clientHeight*b.clientWidth-a.clientHeight*a.clientWidth;}).slice(0,4);
  globalThis.__ozonRecoveryInfo.scrollers=scrollers.length;
  async function scan(wanted){
   globalThis.__ozonRecoveryInfo.phase=wanted[0]===marker?'loading_current_history':'loading_backup_history';
   const deadline=Date.now()+45000;
   if(await found(wanted))return true;
   for(const scroller of scrollers){
    if(Date.now()>deadline)break;
    const start=scroller.scrollTop;let count=0,lastNotice=0;
    for(const direction of [-1,1]){
     if(Date.now()>deadline)break;
     let stable=0,last='';
     for(let i=0;i<120;i++){
      if(Date.now()>deadline)break;
      if(stopped())throw Error('已暂停，已有文件保留');
      if(await found(wanted))return true;
      if(Date.now()-lastNotice>4000){lastNotice=Date.now();await report('正在自动'+(direction<0?'向上加载历史回复':'检查历史回复')+'（第'+(++count)+'段）；只采集本商品已有图片');}
      globalThis.__ozonRecoveryInfo.checkedSegments++;
      const step=Math.max(scroller.clientHeight*.75,250),target=Math.max(0,Math.min(scroller.scrollHeight-scroller.clientHeight,scroller.scrollTop+direction*step));
      scroller.scrollTop=target;scroller.dispatchEvent(new doc.defaultView.Event('scroll'));await sleep(500);
      if(await found(wanted))return true;
      const signature=scroller.scrollTop+'|'+scroller.scrollHeight+'|'+(userNodes(doc)[0]?.textContent||'').slice(-160);
      stable=signature===last?stable+1:0;last=signature;
      // Keep waiting at history boundaries for lazy loading, rather than failing after 400ms.
      if(stable>=8)break;
     }
    }
    scroller.scrollTop=start;await sleep(250);
   }return false;
  }
  if(await scan([marker]))return true;
  const historical=[...new Set(alternatives)].filter(m=>typeof m==='string'&&m!==marker);
  if(historical.length){await report('当前标记未出现，正在核对同货号、同参数的历史任务标记');if(await scan(historical))return true;}
  globalThis.__ozonRecoveryInfo.phase='not_found';
  return false;
 }
 globalThis.OzonConversation={expandUserPrompts,composerOwned,auxiliary,requestAnchor,nextUser,revealRequest,assistantNodes,assistantImages,userOwned,imageScopes,requestReplies,main,contentRoots,userNodes,generating,region};
 if(typeof module!=='undefined')module.exports=globalThis.OzonConversation;
})();
