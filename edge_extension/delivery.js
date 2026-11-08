// Commit only a settled final delivery; a temporary eight-image prefix is not final.
(()=>{
 async function collect(doc,options={}){
  const {task,expected=8,report=async()=>{},stopped=()=>false,quietMs=5000}=options;
  if(!task)throw Error('缺少当前采集任务');
  if(stopped())throw Error('已暂停，已有图片保留');
  const scoped={...options,allowPartial:!options.manual};
  async function waiting(message){
   if(task._deliveryNotice!==message||Date.now()-(task._deliveryNoticeAt||0)>5000){task._deliveryNotice=message;task._deliveryNoticeAt=Date.now();await report(message);}
   return null;
  }
  const foundImages=globalThis.OzonImages.inspect(doc,scoped);
  globalThis.__ozonDeliveryInfo={state:'waiting_final',expected,candidateCount:foundImages.count,generating:globalThis.OzonConversation.generating(doc)};
  if(globalThis.OzonConversation.generating(doc)){
   task._deliveryStable=null;
   return waiting('已发现'+foundImages.count+'张候选图；回复仍在生成，等待最终01—'+String(expected).padStart(2,'0')+'交付，不截取前'+expected+'张');
  }
  await globalThis.OzonFiles.expandFiles(doc,scoped);
  const files=globalThis.OzonFiles.candidates(doc,{...scoped,inventory:true});
  globalThis.__ozonDeliveryInfo.fileCount=files?.count||0;
  if(files?.present&&!files.complete){task._deliveryStable=null;return waiting('最终文件已出现，已识别编号'+files.count+'/'+expected+'；等待完整且唯一的文件列表，不改用前面的过程图');}
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
