// Commit only a settled final delivery; a temporary eight-image prefix is not final.
(()=>{
 async function collect(doc,options={}){
  const {task,expected=8,report=async()=>{},stopped=()=>false,quietMs=5000}=options;
  if(!task)throw Error('缺少当前采集任务');
  if(stopped())throw Error('已暂停，已有图片保留');
  const skuRecovery=options.marker?.startsWith('OZON_OWN_REFERENCE:');
  const scoped={...options,allowPartial:!options.manual,continuations:!skuRecovery&&options.continuations};
  async function waiting(message){
   if(task._deliveryNotice!==message||Date.now()-(task._deliveryNoticeAt||0)>5000){task._deliveryNotice=message;task._deliveryNoticeAt=Date.now();await report(message);}
   return null;
  }
  let region=globalThis.OzonConversation.region(doc,scoped);
  if(scoped.allowPartial&&scoped.marker&&!region.anchor&&globalThis.OzonConversation.revealRequest&&(!task._markerRevealAt||Date.now()-task._markerRevealAt>60000)){
   task._markerRevealAt=Date.now();
   await globalThis.OzonConversation.revealRequest(doc,scoped.marker,{sleep:options.sleep,stopped,report,alternatives:task.recovery_markers||[],onMarker:marker=>{scoped.marker=marker;task.recovery_marker=marker;}});
   region=globalThis.OzonConversation.region(doc,scoped);
  }
  if(scoped.allowPartial&&scoped.marker&&!region.anchor)return waiting('等待本任务原始作图标记加载；不采集其他商品');
  const incomplete=globalThis.OzonGenerationFailure?.incomplete?.(doc,task,{marker:scoped.marker});
  if(incomplete){globalThis.__ozonDeliveryInfo={state:'incomplete',expected,reason:'explicit_partial_delivery'};const error=Error(incomplete.message);error.code='DELIVERY_INCOMPLETE';throw error;}
  const foundImages=globalThis.OzonImages.inspect(doc,scoped);
  globalThis.__ozonDeliveryInfo={state:'waiting_final',expected,candidateCount:foundImages.count,generating:globalThis.OzonConversation.generating(doc)};
  if(globalThis.OzonConversation.generating(doc)){
   task._deliveryStable=null;
   return waiting('已发现'+foundImages.count+'张候选图；回复仍在生成，等待最终01—'+String(expected).padStart(2,'0')+'交付，不截取前'+expected+'张');
  }
  const native=!skuRecovery&&(task.delivery_policy==='generated_originals'||task.delivery_policy==='independent_images'&&foundImages.count===expected);
  if(native&&foundImages.count!==expected){task._deliveryStable=null;return waiting('独立生成原图 '+foundImages.count+'/'+expected+'；等待逐张完成，不采集整套预览图或后续重制下载文件');}
  if(!native)await globalThis.OzonFiles.expandFiles(doc,scoped);
  const files=native?null:globalThis.OzonFiles.candidates(doc,{...scoped,inventory:true});
  globalThis.__ozonDeliveryInfo.fileCount=files?.count||0;
  if(skuRecovery&&!files?.complete)return waiting('已定位本货号的原始请求，等待该回复的完整编号下载文件 '+(files?.count||0)+'/'+expected);
  if(files?.present&&!files.complete){task._deliveryStable=null;return waiting(expected===1?'本任务只需1张主图，但识别到'+(files.candidateTotal||files.count)+'个文件候选，正在核对对应回复，不猜取其他变体图片':'最终文件已出现，已识别编号'+files.count+'/'+expected+'；等待完整且唯一的文件列表，不改用前面的过程图');}
  if(!files?.present&&foundImages.count===0){
   const controls=region.root?.querySelectorAll?.('button,[role="button"],a[href]')||[];
   const counts={outside:0,user:0,sidebar:0,inScope:0};
   for(const el of controls){
    if(!/\.(?:jpg|jpeg|png|webp)\b/i.test(el.textContent||el.getAttribute('aria-label')||''))continue;
    const conv=globalThis.OzonConversation;
    const key=conv.userOwned(el)?'user':conv.auxiliary(el)?'sidebar':region.includes(el)?'inScope':'outside';
    counts[key]++;
   }
   globalThis.__ozonDeliveryInfo.exclusions=counts;globalThis.__ozonDeliveryInfo.state='waiting_result';task._deliveryStable=null;
   return waiting('等待本任务成品：范围内文件入口 '+counts.inScope+'，范围外 '+counts.outside+'，参考附件 '+counts.user+'，侧栏 '+counts.sidebar);
  }
  if(!files?.complete&&foundImages.overflow){task._deliveryStable=null;return waiting('生成图超过'+expected+'张；等待最终01—'+String(expected).padStart(2,'0')+'编号文件，不截取前'+expected+'张');}
  const main=globalThis.OzonConversation.main(doc);
  const signature=(files?.complete?'files:'+files.signature:'gallery:'+foundImages.signature)+'|'+(main?.innerText||main?.textContent||'');
  const stable=task._deliveryStable;
  if(!stable||stable.signature!==signature){task._deliveryStable={signature,since:Date.now()};if(quietMs>0)return waiting('回复已结束，正在核对最终图片交付与编号');}
  if(quietMs>0&&Date.now()-task._deliveryStable.since<quietMs)return null;
  const source=files?.complete?'numbered_files':'gallery';
  const onImage=async(index,b64)=>{
   if(stopped())throw Error('已暂停，已有图片保留');
   if(globalThis.OzonConversation.generating(doc)){task._deliveryStable=null;const error=Error('回复继续生成，等待最终交付');error.code='DELIVERY_CHANGED';throw error;}
   if(source==='numbered_files'){
    const latest=globalThis.OzonFiles.candidates(doc,{...scoped,inventory:true});
    if(!latest?.complete||latest.signature!==files.signature){task._deliveryStable=null;const error=Error('最终图片文件清单仍在变化，等待稳定后重新核对');error.code='DELIVERY_CHANGED';throw error;}
   }
   await options.onImage?.(index,b64);
  };
  try{
   const values=source==='numbered_files'?await globalThis.OzonFiles.collect(doc,{...scoped,onImage}):await globalThis.OzonImages.collect(doc,{...scoped,allowPartial:false,onImage});
   if(values){task.deliverySource=source;globalThis.__ozonDeliveryInfo={...globalThis.__ozonDeliveryInfo,state:'complete',source,savedCount:values.length};}
   return values;
  }catch(error){
   if(['DELIVERY_AMBIGUOUS','DELIVERY_CHANGED'].includes(error.code)){task._deliveryStable=null;return waiting(error.message);}
   throw error;
  }
 }
 globalThis.OzonDelivery={collect};
})();
