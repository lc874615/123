/* Public product characteristics only. No account data or hidden API calls. */
(()=>{
 const selectors='[data-widget^="webCharacteristics"], #section-characteristics, [id="section-characteristics"]';
 globalThis.__ozonCompetitorPrepare=()=>{
  const visible=el=>!!el.getClientRects().length&&getComputedStyle(el).visibility!=='hidden';
  const section=[...document.querySelectorAll(selectors)].find(visible);
  if(section){section.scrollIntoView({block:'center'});const button=[...section.querySelectorAll('button,a')].find(el=>visible(el)&&/^(развернуть|показать все|все характеристики|показать полностью)$/i.test(el.innerText.trim()));if(button)button.click();return;}
  const tab=[...document.querySelectorAll('button,a,[role="tab"]')].find(el=>visible(el)&&/^(характеристики|все характеристики)$/i.test(el.innerText.trim())&&(el.tagName!=='A'||(el.getAttribute('href')||'').startsWith('#')));
  if(tab)tab.click();
 };
 globalThis.__ozonCompetitorRead=(fields=[])=>{
  const url=new URL(location.href);
  if(url.protocol!=='https:'||!['ozon.ru','www.ozon.ru'].includes(url.hostname)||!/^\/product\/(?:[^/]+-)?\d+\/?$/.test(url.pathname))throw Error('竞品页已跳转，停止采集');
  const rows=[],seen=new Set();const add=(name,value,values=null)=>{
   name=String(name||'').replace(/\s+/g,' ').trim();value=String(value||'').replace(/\s+/g,' ').trim();
   if(!name||!value||name.length>180||value.length>800)return;
   const key=name+'\0'+value;if(!seen.has(key)&&rows.length<400){seen.add(key);rows.push({name,value,...(Array.isArray(values)&&values.length>1?{values}: {})});}
  };
  const visible=el=>!!el.getClientRects().length&&getComputedStyle(el).visibility!=='hidden';
  for(const section of document.querySelectorAll(selectors)){
   if(!visible(section))continue;
   for(const dl of section.querySelectorAll('dl'))for(const dt of dl.querySelectorAll('dt')){
    const dd=dt.nextElementSibling?.tagName==='DD'?dt.nextElementSibling:dt.parentElement?.nextElementSibling?.querySelector('dd');if(dd?.tagName==='DD'&&visible(dt)&&visible(dd))add(dt.innerText,dd.innerText,[...dd.querySelectorAll('a')].map(a=>a.innerText.trim()).filter(Boolean));
   }
   // Some product layouts use div/span rows rather than semantic dl/table.
   // Only exact labels supplied by the current official schema are eligible.
   const key=text=>String(text||'').toLocaleLowerCase().replace(/ё/g,'е').replace(/[^\p{L}\p{N}]+/gu,' ').trim();
   const official=new Set(fields.flatMap(f=>[f.name,f.name_ru]).filter(x=>typeof x==='string').map(key));
   for(const label of section.querySelectorAll('span,dt,th')){
    if(!visible(label)||!official.has(key(label.innerText)))continue;
    let node=label;
    for(let level=0;level<3&&node&&node!==section;level++,node=node.parentElement){
     const value=node.nextElementSibling;
     if(value&&visible(value)&&value.innerText.trim()&&!official.has(key(value.innerText))&&node.parentElement?.children.length===2){add(label.innerText,value.innerText,[...value.querySelectorAll('a')].map(a=>a.innerText.trim()).filter(Boolean));break;}
    }
   }
   for(const tr of section.querySelectorAll('tr')){const cells=tr.querySelectorAll('th,td');if(cells.length===2&&visible(tr))add(cells[0].innerText,cells[1].innerText);}
  }
  // JSON-LD Product.additionalProperty is publicly supplied product metadata.
  const products=[];
  for(const script of document.querySelectorAll('script[type="application/ld+json"]')){
   if(script.textContent.length>1000000)continue;
   try{
    const walk=(obj,depth=0)=>{
     if(depth>8||!obj||typeof obj!=='object')return;
     if(Array.isArray(obj)){obj.slice(0,100).forEach(x=>walk(x,depth+1));return;}
     if([].concat(obj['@type']||[]).includes('Product'))products.push(obj);
     if(obj['@graph'])walk(obj['@graph'],depth+1);
    };walk(JSON.parse(script.textContent));
   }catch{}
  }
  const id=url.pathname.match(/(\d+)\/?$/)[1];
  const owns=p=>{
   const refs=[p.url,p['@id']].filter(x=>typeof x==='string');
   if(refs.length)return refs.some(ref=>{try{const u=new URL(ref,url.origin);return ['ozon.ru','www.ozon.ru'].includes(u.hostname)&&u.pathname.match(/(\d+)\/?$/)?.[1]===id;}catch{return false;}});
   if(p.sku!=null)return String(p.sku)===id;
   return products.length===1;
  };
  for(const obj of products.filter(owns))for(const p of [].concat(obj.additionalProperty||[]))if(p&&Array.isArray(p.value)&&p.value.every(v=>typeof v==='string'))add(p.name,p.value.join('；'),p.value);else if(p&&typeof p.value!=='object')add(p.name,p.unitText?String(p.value)+' '+p.unitText:p.value);
  const body=(document.body?.innerText||'').slice(0,12000);
  const blocked=/подтвердите.{0,40}(человек|робот)|доступ ограничен|проверка безопасности|captcha|access denied|verify.{0,30}(human|identity)|провер.{0,30}(робот|человек)/i.test(body);
  const diagnostics={sections:document.querySelectorAll(selectors).length,rows:rows.length,blocked};
  return {url:url.origin+url.pathname,rows,diagnostics,error_code:blocked&&!rows.length?'verification':null};
 };
})();
