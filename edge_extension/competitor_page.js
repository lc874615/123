/* Public product characteristics only. No account data or hidden API calls. */
(()=>{
 globalThis.__ozonCompetitorRead=()=>{
  const url=new URL(location.href);
  if(url.protocol!=='https:'||!['ozon.ru','www.ozon.ru'].includes(url.hostname)||!/^\/product\/(?:[^/]+-)?\d+\/?$/.test(url.pathname))throw Error('竞品页已跳转，停止采集');
  const rows=[];seen=new Set();add=(name,value,values=null)=>{
   name=String(name||'').replace(/\s+/g,' ').trim();value=String(value||'').replace(/\s+/g,' ').trim();
   if(!name||!value||name.length>180||value.length>800)return;
   const key=name+'\0'+value;if(!seen.has(key)&&rows.length<400){seen.add(key);rows.push({name,value,...(Array.isArray(values)&&values.length>1?{values}: {})});}
  };
  const visible=el=>!!el.getClientRects().length&&getComputedStyle(el).visibility!=='hidden';
  for(const section of document.querySelectorAll('[data-widget="webCharacteristics"], [data-widget="webCharacteristicsContainer"], #section-characteristics')){
   if(!visible(section))continue;
   for(const dl of section.querySelectorAll('dl'))for(const dt of dl.querySelectorAll('dt')){
    const dd=dt.nextElementSibling;if(dd?.tagName==='DD'&&visible(dt)&&visible(dd))add(dt.innerText,dd.innerText,[...dd.querySelectorAll('a')].map(a=>a.innerText.trim()).filter(Boolean));
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
  return {url:url.origin+url.pathname,rows};
 };
})();
