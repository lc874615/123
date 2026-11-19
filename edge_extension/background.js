if(typeof importScripts==='function')importScripts('automation_wake.js');
async function bounded(p,ms,message){let timer;try{return await Promise.race([p,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(message)),ms);})]);}finally{clearTimeout(timer);}}
const BASE='http://127.0.0.1:8765';
let busy=false,runTab=null,current=null,bindingChanging=false,restartingFailure=false,restartCancelled=false;
async function restore(){const x=await chrome.storage.local.get('activeTask');if(x.activeTask){current={...(current?.id===x.activeTask.id?current:{}),...x.activeTask};current.sku=current.sku||(current.id.startsWith('copy:')?current.id.slice(5):undefined);runTab=x.activeTask.tabId;busy=true;}}
async function persist(){if(current)await chrome.storage.local.set({...(current.sku?{lastSku:current.sku}:{}),activeTask:{id:current.id,sku:current.sku,marker:current.marker,tabId:runTab,startedAt:current.startedAt||Date.now(),signature:current.signature,copy_phase:current.copy_phase,image_job:!!current.image_job,sheet_layout:current.sheet_layout,expected_images:current.expected_images,delivery_policy:current.delivery_policy,resumeReadOnly:!!current.resumeReadOnly,automaticRecovery:!!current.automaticRecovery}});else await chrome.storage.local.remove('activeTask');}
let forwardedAlert=null;
async function status(s){
 await chrome.storage.local.set({status:s});
 const intentional=/已暂停|制作已暂停|用户暂停|已恢复/.test(s)&&!/未完成|失败|不确定/.test(s);
 const error=!intentional&&/失败|异常|超时|未找到|未识别|不匹配|需处理|待恢复|未覆盖|已有内容|尚未绑定|作图页关闭|未连接|配对失败|请先输入配对码|自动批次未启用|限额|验证码|登录|blocked|forbidden|accessdenied|结果不确定/i.test(s);
 const signature=error?s:'healthy';if(signature===forwardedAlert)return;forwardedAlert=signature;
 await api('/plugin-status',{message:s,error,task_id:current?.id,sku:current?.sku},2500).catch(()=>{});
}
async function api(path,body,timeoutMs=30000){const {pairToken}=await chrome.storage.local.get('pairToken');if(!pairToken)throw Error('请先输入配对码');const r=await fetch(BASE+path,{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+pairToken},body:JSON.stringify(body),signal:AbortSignal.timeout(timeoutMs)});const d=await r.json();if(!r.ok){const e=Error(d.error||'本地服务错误');e.code=d.code;e.httpStatus=r.status;throw e;}return d;}
function workPage(url){try{const u=new URL(url);return u.origin==='https://chatgpt.com'&&(u.pathname==='/'||/^\/(?:g\/[^/]+\/)?c\/[^/]+\/?$/.test(u.pathname));}catch{return false;}}
async function workTab(fallback){
 const {autoTab,autoUrl}=await chrome.storage.local.get(['autoTab','autoUrl']);
 let tab=null;try{tab=await chrome.tabs.get(autoTab??fallback);}catch{}
 if(tab?.url&&new URL(tab.url).origin==='https://chatgpt.com'&&(!autoUrl||tab.url.split('#')[0]===autoUrl))return tab;
 if(autoUrl){const candidates=(await chrome.tabs.query({url:'https://chatgpt.com/*'})).filter(t=>t.url?.split('#')[0]===autoUrl);if(candidates.length===1){await chrome.storage.local.set({autoTab:candidates[0].id});return candidates[0];}}
 throw Error('已绑定作图页关闭或已切换对话，请打开原对话后重新绑定；不会向其他页面发送');
}
async function inject(tabId){await chrome.scripting.executeScript({target:{tabId},files:['diagnostics.js','conversation.js','composer.js','uploads.js','copy_parser.js','images.js','file_links.js','download_ui.js','delivery.js','generation_failure.js','composer_cleanup.js','content.js']});}
async function copyPageReady(tab){
 await inject(tab.id);
 const check=await chrome.tabs.sendMessage(tab.id,{kind:'preflight'});
 if(check?.version!=='1.0.84')throw Error('网页脚本仍是旧版，请更新插件并刷新ChatGPT页面');
 if(!check.ready){
  if(check.generating||check.imageTaskId||check.copyTaskActive){await status('图片回复仍在生成，结束后自动继续文案；不会重复发送');setTimeout(poll,3000);return false;}
  throw Error(check.message||'文案输入框尚未就绪');
 }
 return true;
}
async function recoverExisting(task,tab){
 current=await api('/recover',{sku:task.sku,task_id:task.id,automatic:true});runTab=tab.id;busy=true;await persist();await inject(tab.id);await chrome.tabs.sendMessage(tab.id,{kind:'recover',task:current});await status('已恢复现有图片采集，不重新发送作图请求');
}
async function copyPipeline(sku,tab){
 if(!await copyPageReady(tab))return {status:'正在等待当前图片采集结束，随后自动处理整组文案'};
 const priorMarker=current?.id==='copy:'+sku?current.marker:undefined;
 const prepared=await api('/copy-task',{sku,prepare_only:true});
 if(prepared.waiting_for_competitor){await status(prepared.message);competitorPoll();setTimeout(poll,2500)?.unref?.();return {status:prepared.message};}
 if(prepared.local_ready){await status('整组现有文案已同步保存到全部变体');return {status:'整组现有文案已同步保存到全部变体'};}
 current=prepared;runTab=tab.id;busy=true;current.startedAt=Date.now();await persist();
 if(prepared.dispatched){current.resumeReadOnly=true;current.marker=prepared.resume_marker?prepared.marker:priorMarker;await persist();await inspectCopy();return {status:'已有文案请求，自动读取结果并同步全组；不重新发送'};}
 if(!prepared.attributesOnly&&!prepared.force_new){
  const extracted=await chrome.tabs.sendMessage(tab.id,{kind:'copy-extract-auto',task:prepared});
  if(extracted?.copy){
   try{await api('/copy-result',{sku:prepared.sku,copy:extracted.copy,existing:true});busy=false;current=null;await persist();await status('已有完整文案已自动采集并保存到全部变体');return {status:'已有完整文案已自动采集并保存到全部变体'};}
   catch(error){if(error.httpStatus!==400)throw error;await status('已有文案未通过当前资料校验，按本组最新参数自动补全');}
  }
 }
 const generated=await api('/copy-task',{sku:prepared.sku});
 if(generated.waiting_for_competitor){busy=false;current=null;await persist();await status(generated.message);competitorPoll();setTimeout(poll,2500)?.unref?.();return {status:generated.message};}
 current=generated;runTab=tab.id;busy=true;current.startedAt=Date.now();await persist();
 await status(prepared.attributesOnly?'正在准备属性读取请求，等待上传与发送确认':'正在准备整组文案请求，等待上传与发送确认');await chrome.tabs.sendMessage(tab.id,{kind:'copy',task:current});return {status:'整组文案自动处理中，完成后应用全部变体'};
}
async function inspectExistingCopy(task,tab){
 const prior=current?.id==='copy:'+task.sku?current.marker:undefined;
 current=await api('/copy-task',{sku:task.sku,prepare_only:true,inspect_only:true});
 if(current.local_ready){busy=false;current=null;await persist();await status('整组文案已恢复并同步全部变体');return;}
 if(current.copy_phase==='inspecting'&&!current.dispatched){busy=false;current=null;await persist();await copyPipeline(task.sku,tab);return;}
 current.resumeReadOnly=true;current.marker=current.resume_marker?current.marker:prior;current.startedAt=Date.now();runTab=tab.id;busy=true;await persist();await inject(tab.id);await inspectCopy();
}
chrome.runtime.onMessage.addListener((m,sender,reply)=>{(async()=>{
 if(bindingChanging&&['enable','run','recover','copy','pair-connect','rebind-work'].includes(m.kind))throw Error('正在更换作图页，请稍后操作');
 if(!bindingChanging)await restore();
 if(m.kind==='image-idle'){
  const x=await chrome.storage.local.get(['autoEnabled','autoTab']);
  if(!bindingChanging&&x.autoEnabled&&sender.tab?.id===(x.autoTab??runTab)&&!current?.id?.startsWith('copy:')){await status('图片采集已退出，正在自动接续整组文案与后续变体');setTimeout(poll,150);}
  return {ok:true};
 }
 if(m.kind==='download-asset'){
  if(sender.tab?.id!==runTab||!current||m.task_id!==current.id)throw Error('文件采集任务与页面不匹配');
  const taskId=current.id;const grant=await api('/download-ticket',{task_id:taskId,extension:m.extension});
  const downloaded=await captureDownload(runTab,m.token,grant.filename);
  if(current?.id!==taskId)throw Error('文件采集已暂停，下载文件已保留');
  if(downloaded?.images)return downloaded;
  return await api('/read-download',{task_id:taskId,ticket:grant.ticket,path:downloaded});
 }
 if(m.kind==='health'){startWakeChannel();const r=await api('/health',{});if(r.protocol!=='1.0.84')throw Error('请同时更新本地工具和插件到1.0.84版');await chrome.alarms.create?.('ozon-poll',{periodInMinutes:0.5});return {connected:true};}
 if(m.kind==='pair-connect'){
  startWakeChannel();
  const r=await api('/health',{});if(r.protocol!=='1.0.84')throw Error('请同时更新本地工具和插件');
  await chrome.alarms.create?.('ozon-poll',{periodInMinutes:0.5});
  const saved=await chrome.storage.local.get(['autoTab','autoUrl']);
  if(saved.autoUrl||saved.autoTab!=null){const note='配对已保存，保留原作图页；本地创建并自动处理后将自动接续';await status(note);setTimeout(poll,100);return {status:note};}
  const tab=await chrome.tabs.get(m.tabId);
  if(!tab?.url||new URL(tab.url).origin!=='https://chatgpt.com'){const note='配对已保存；请在ChatGPT商品作图页点击一次“开始/继续”完成绑定，之后创建任务自动执行';await status(note);return {status:note};}
  await chrome.storage.local.set({autoTab:tab.id,autoUrl:tab.url.split('#')[0],autoTitle:tab.title||'ChatGPT作图页'});
  const note='已配对并绑定当前作图页；本地创建并自动处理后将自动开始';await status(note);setTimeout(poll,100);return {status:note};
 }
 if(m.kind==='binding-info'){
  const tab=await workTab(m.tabId);const x=await chrome.storage.local.get('autoTab');return {bound:x.autoTab!=null,title:tab.title||'ChatGPT',tabId:tab.id};
 }
 if(m.kind==='binding-options'){
  const control=await api('/control',{}),x=await chrome.storage.local.get(['autoTab','autoUrl','autoEnabled']);
  const canRebind=control.paused===true||(!x.autoEnabled&&!busy&&!current);
  const tabs=(await chrome.tabs.query({url:'https://chatgpt.com/*'})).filter(t=>workPage(t.url)).map(t=>({id:t.id,title:t.title||'ChatGPT商品对话',current:t.id===m.tabId,bound:t.id===x.autoTab||!!x.autoUrl&&t.url?.split('#')[0]===x.autoUrl}));
  return {canRebind,paused:control.paused===true,tabs};
 }
 if(m.kind==='rebind-work'){
  if(!Number.isInteger(m.tabId)||m.tabId<=0)throw Error('请选择一个已打开的商品作图页');
  bindingChanging=true;
  try{
   await bounded((async()=>{while(polling)await new Promise(resolve=>setTimeout(resolve,25));})(),35000,'上一轮队列检查尚未结束，请稍后重试；绑定未更改');
   await restore();
   const control=await api('/control',{}),x=await chrome.storage.local.get('autoEnabled');
   if(control.paused!==true&&(x.autoEnabled||busy||current))throw Error('任务正在运行，请先暂停制作，再更换作图页');
   const tab=await chrome.tabs.get(m.tabId);if(!workPage(tab?.url))throw Error('所选页面已关闭或不是ChatGPT商品对话，请刷新列表后重选');
   const pausedTask=current,oldTab=runTab;
   await chrome.storage.local.set({autoEnabled:false});
   const stopped=await api('/automation-control',{paused:true});
   if(pausedTask&&oldTab!=null){
    let old=null;try{old=await chrome.tabs.get(oldTab);}catch{}
    if(old){const ack=await chrome.tabs.sendMessage(oldTab,{kind:'stop'});if(!ack?.ok)throw Error('原作图页尚未确认暂停，请刷新原页后重试');}
    await api('/pause-ack',{task_id:pausedTask.id,allow_missing:true});
   }
   // Validate again after pausing; a selected tab may have navigated meanwhile.
   const fresh=await chrome.tabs.get(tab.id);if(!workPage(fresh?.url)||fresh.url.split('#')[0]!==tab.url.split('#')[0])throw Error('所选页面已变化，暂停已保留，请重新选择');
   busy=false;current=null;runTab=fresh.id;
   await chrome.storage.local.set({autoTab:fresh.id,autoUrl:fresh.url.split('#')[0],autoTitle:fresh.title||'ChatGPT作图页',autoEnabled:false,controlSerial:stopped.serial});await persist();
   await chrome.tabs.update(fresh.id,{active:true});if(chrome.windows?.update&&fresh.windowId!=null)await chrome.windows.update(fresh.windowId,{focused:true});
   const note='已重新绑定作图页：'+(fresh.title||'ChatGPT')+'；任务保持暂停，点击“开始/继续”后接续已有结果';await status(note);return {status:note,paused:true,tabId:fresh.id};
  }finally{bindingChanging=false;}
 }
 if(m.kind==='focus-work'){
  const tab=await workTab(m.tabId);await chrome.tabs.update(tab.id,{active:true});if(chrome.windows?.update&&tab.windowId!=null)await chrome.windows.update(tab.windowId,{focused:true});return {status:'已定位作图页：'+(tab.title||'ChatGPT')};
 }
 if(m.kind==='diagnose'){
  let tab,fallback=false;try{tab=await workTab(m.tabId);}catch(error){tab=await chrome.tabs.get(m.tabId);fallback=true;}
  if(!tab?.url||new URL(tab.url).origin!=='https://chatgpt.com')throw Error('请在ChatGPT商品对话中导出诊断');
  await bounded(chrome.scripting.executeScript({target:{tabId:tab.id},files:['conversation.js','copy_parser.js','file_links.js','diagnostics.js']}),10000,'页面诊断模块加载超时，请刷新页面后重试');
  const result=await bounded(chrome.scripting.executeScript({target:{tabId:tab.id},func:()=>globalThis.OzonDiagnostics.snapshot()}),10000,'页面诊断读取超时，请刷新页面后重试');
  const extension=await chrome.storage.local.get(['autoEnabled','autoTab','status']);
  let queue;try{queue=await api('/queue-diagnostic',{},2500);}catch(e){queue={error:e.message,message:'已跳过本地队列信息，页面诊断仍可导出'};}
  const diagnostic={...result[0].result,target:{selected:fallback?'current-explicit-tab':'bound-work-tab',title:tab.title||'',sameAsOpenedPopup:tab.id===m.tabId},extension:{backgroundVersion:chrome.runtime.getManifest?.().version||null,autoEnabled:!!extension.autoEnabled,busy,hasBoundTab:extension.autoTab!=null,activeTask:current?{id:current.id,sku:current.sku}:null,status:extension.status},queue};
  return {diagnostic};
 }
 if(m.kind==='enable'){
  const tab=await chrome.tabs.get(m.tabId);if(!tab.url||new URL(tab.url).origin!=='https://chatgpt.com')throw Error('请先打开ChatGPT商品对话');
  const health=await api('/health',{});if(health.protocol!=='1.0.84')throw Error('请同时更新本地工具和插件');await api('/automation-control',{paused:false});
  await api('/resume-unsent-upload',{});await api('/heartbeat',{auto_enabled:true});await chrome.storage.local.set({autoTab:tab.id,autoUrl:tab.url.split('#')[0],autoTitle:tab.title||'ChatGPT作图页',autoEnabled:true});await chrome.alarms.create('ozon-poll',{periodInMinutes:0.5});await status('自动批次已启用：本地创建商品后将自动开始。');setTimeout(poll,100);return {status:'已绑定作图页：'+(tab.title||'ChatGPT')+'，等待本地任务'};
 }
 if(m.kind==='copy'){
  await chrome.alarms.create('ozon-poll',{periodInMinutes:0.5});if(busy)throw Error('请先完成或暂停当前任务');const tab=await workTab(m.tabId);return await copyPipeline(m.sku,tab);
 }
 if(m.kind==='copy-paste'){
  if(sender.tab)throw Error('只能从扩展面板提交粘贴文案');
  await api('/copy-result',{sku:m.sku,copy:m.copy,manual:true});
  if(current?.id==='copy:'+m.sku){busy=false;current=null;await persist();}
  await status('文案已保存至本地草稿，待审核');return {status:'文案已保存至本地草稿，待审核'};
 }
 if(m.kind==='copy-recover'){
  const tab=await workTab(m.tabId);if(!tab.url||new URL(tab.url).origin!=='https://chatgpt.com')throw Error('请打开含现有文案的ChatGPT商品对话');
  if(current&&current.id!=='copy:'+m.sku)throw Error('另一个任务尚未完成，请先停止');
  current=await api('/copy-task',{sku:m.sku,inspect_only:true});runTab=tab.id;busy=true;current.startedAt=Date.now();await persist();
  try{
   await status('正在读取本页文案并保存');
   await chrome.scripting.executeScript({target:{tabId:tab.id},files:['diagnostics.js','conversation.js','composer.js','uploads.js','copy_parser.js','images.js','file_links.js','download_ui.js','delivery.js','generation_failure.js','composer_cleanup.js','content.js']});
   const extracted=await bounded(chrome.tabs.sendMessage(tab.id,{kind:'copy-extract-v013',task:current}),10000,'网页提取超时，请刷新ChatGPT页面后重试');
   if(extracted?.candidates?.length){
    const message='已找到无货号文案，请在下方选择并核对后保存';
    const copySku=current.sku;await api('/copy-failed',{sku:copySku,message});busy=false;current=null;await persist();await status(message);
    return {status:message,sku:copySku,candidates:extracted.candidates};
   }
   if(!extracted?.copy)throw Error(extracted?.error||'网页脚本版本未更新，请刷新ChatGPT页面后重试');
   await api('/copy-result',{sku:current.sku,copy:extracted.copy});
   busy=false;current=null;await persist();
   const message='俄文文案已保存至本地草稿，待审核';await status(message);return {status:message};
  }catch(e){
   await api('/copy-failed',{sku:current.sku,message:e.message}).catch(()=>{});
   busy=false;current=null;await persist();throw e;
  }
 }
 if(m.kind==='copy-progress'){if(sender.tab?.id!==runTab||!current||m.task_id!==current.id)throw Error('文案进度任务不匹配');await status(m.message);return {ok:true};}
 if(m.kind==='copy-failed'){if(sender.tab?.id!==runTab||!current||m.task_id!==current.id)throw Error('任务不匹配');await api('/copy-failed',{sku:current.id.slice(5),message:m.message});busy=false;current=null;await persist();await status(m.message);return {ok:true};}
 if(m.kind==='copy-result'){
  if(sender.tab?.id!==runTab||!current||m.task_id!==current.id)throw Error('文案任务不匹配');
  await api('/copy-result',{sku:current.id.slice(5),copy:m.copy});busy=false;current=null;await persist();await status('整组文案已保存并同步全部变体，自动继续后续制作');setTimeout(poll,250);return {ok:true};
 }
 if(m.kind==='recover'){
  if(busy)throw Error('当前仍有任务执行，请先暂停，再采集已有图片');
  const tab=await workTab(m.tabId);if(!tab.url||new URL(tab.url).origin!=='https://chatgpt.com')throw Error('请打开已生成图片的商品对话');
  await api('/automation-control',{paused:false});await chrome.storage.local.set({autoEnabled:true});await chrome.alarms.create?.('ozon-poll',{periodInMinutes:0.5});
  current=await api('/recover',{sku:m.sku,as_sheet:!!m.as_sheet});runTab=tab.id;busy=true;current.startedAt=Date.now();await persist();
  await chrome.scripting.executeScript({target:{tabId:tab.id},files:['diagnostics.js','conversation.js','composer.js','uploads.js','copy_parser.js','images.js','file_links.js','download_ui.js','delivery.js','generation_failure.js','composer_cleanup.js','content.js']});await chrome.tabs.sendMessage(tab.id,{kind:'recover',task:current});return {status:'正在核对并采集最终图片，完成后继续文案；不重新作图'};
 }
 if(m.kind==='repair-order'){
  if(sender.tab?.id!==runTab||!current||m.task_id!==current.id)throw Error('自动重采集任务不匹配');
  const result=await api('/repair-order',{task_id:current.id});
  await chrome.storage.local.set({autoEnabled:true,autoTab:runTab});await chrome.alarms.create('ozon-poll',{periodInMinutes:0.5});
  await status('图片顺序冲突：旧素材已备份，正在自动重新采集，完成后继续');return result;
 }
 if(m.kind==='run'){
  if(busy)throw Error('当前任务尚未结束，请先完成或暂停。');
  const tab=await workTab(m.tabId);if(!tab.url||new URL(tab.url).origin!=='https://chatgpt.com')throw Error('请在 ChatGPT 标签页点击扩展');
  busy=true;runTab=tab.id;
  try{await chrome.scripting.executeScript({target:{tabId:tab.id},files:['diagnostics.js','conversation.js','composer.js','uploads.js','copy_parser.js','images.js','file_links.js','download_ui.js','delivery.js','generation_failure.js','composer_cleanup.js','content.js']});const check=await chrome.tabs.sendMessage(tab.id,{kind:'preflight'});if(check?.version!=='1.0.84')throw Error('网页脚本仍是旧版，请刷新ChatGPT页面后重试');if(!check?.ready)throw Error(check?.message||'当前页面尚未就绪');current=await api('/claim',{tab_id:tab.id,page_url:tab.url});await persist();await chrome.tabs.sendMessage(tab.id,{kind:'start',task:current});await status('任务已启动，保持此标签页打开。');return {status:'任务已启动'};}
  catch(e){if(current)await api('/event',{task_id:current.id,state:'needs_attention',message:e.message}).catch(()=>{});busy=false;current=null;await persist();throw e;}
 }
 if(m.kind==='stop'){
  restartCancelled=true;
  const paused=current,tabId=runTab;
  await chrome.storage.local.set({autoEnabled:false});await chrome.alarms.create?.('ozon-poll',{periodInMinutes:0.5});
  busy=false;current=null;await persist();
  if(tabId!==null)await chrome.tabs.sendMessage(tabId,{kind:'stop'}).catch(()=>{});
  let notice='';
  try{
   await api('/automation-control',{paused:true});
   if(paused){if(paused.id.startsWith('copy:'))await api('/copy-failed',{sku:paused.id.slice(5),message:'用户暂停文案任务，请保存现有结果'});else await api('/event',{task_id:paused.id,state:'needs_attention',message:'用户暂停；请检查网页，禁止直接重发。'});}
   if(paused)await api('/pause-ack',{task_id:paused.id});
   await api('/heartbeat',{auto_enabled:false});
  }catch(e){notice='；本地通知未完成：'+e.message;}
  const message='已暂停自动批次，已有素材保留'+notice;await status(message);return {status:message};
 }
 if(m.kind==='generation-failed'){
  if(sender.tab?.id!==runTab||!current||m.task_id!==current.id||restartingFailure)throw Error('失败重启任务与页面不匹配');
  restartingFailure=true;restartCancelled=false;const owner={...current};
  try{
   await chrome.tabs.sendMessage(runTab,{kind:'stop'});
   const body={task_id:owner.id,marker:m.marker,message:m.message,reply_finished:m.reply_finished,no_images:m.no_images,collector_stopped:true};
   let result=await api('/generation-failed',body);const deadline=Date.now()+90000;
   while(result.pending&&Date.now()<deadline&&!restartCancelled){await new Promise(r=>setTimeout(r,1000));if(!restartCancelled)result=await api('/generation-failed',body);}
   if(restartCancelled)throw Error('用户暂停，已取消自动重启');if(result.pending)throw Error('等待自动重启超时，原数据保留');
   current=null;busy=false;await persist();await chrome.storage.local.set({autoEnabled:true,lastSku:owner.sku});await chrome.alarms.create?.('ozon-poll',{periodInMinutes:0.5});
   await status('作图失败后已自动重启本条队列，第'+result.restart_count+'次；插件将自动执行并继续后续队列');setTimeout(poll,150);return {ok:true};
  }finally{restartingFailure=false;}
 }
 if(['result','set-result','sheet-result','delivery-plan','backup-composer','event'].includes(m.kind)){
  if(sender.tab?.id!==runTab||!current||m.task_id!==current.id)throw Error('任务与标签页不匹配');
  if(m.kind==='backup-composer')return await api('/backup-composer',{task_id:current.id,text:m.text,attachments:m.attachments});
  if(m.kind==='delivery-plan')return await api('/delivery-plan',{task_id:current.id});
  if(m.kind==='set-result'||m.kind==='sheet-result'){
   const owner={...current};const r=await api(m.kind==='sheet-result'?'/sheet-result':'/set-result',{task_id:owner.id,index:m.index,image_b64:m.image_b64});
   if(current?.id!==owner.id)return {ok:true};
   if(r.complete||r.saved_count===8&&!owner.image_job){await persist();await status('本任务图片已保存，等待当前页面采集退出后再启动下一任务');setTimeout(poll,150);}
   else{await status(r.message||'已保存生成图 '+r.saved_count+'/'+(r.expected_images||8));if(owner.image_job&&r.saved_count===r.expected_images)setTimeout(poll,500);}
   return {ok:true};
  }
  if(m.kind==='result'){await api('/result',{task_id:current.id,image_b64:m.image_b64});await persist();await status('图片已保存，等待当前采集结束后继续下一任务');setTimeout(poll,500);return {ok:true};}
  await api('/event',{task_id:current.id,state:m.state,message:m.message});await status(m.message);
  if(m.state==='needs_attention'){busy=false;current=null;await persist();await chrome.storage.local.set({autoEnabled:false});}return {ok:true};
 }
 throw Error('未知请求');
})().then(reply).catch(async e=>{await status(e.message);reply({error:e.message,code:e.code});});return true;});

let inspectingCopy=false;
async function inspectCopy(){
 if(inspectingCopy||!current?.id?.startsWith('copy:'))return;
 inspectingCopy=true;const task={...current};
 try{
  const tab=await workTab(runTab);runTab=tab.id;await inject(runTab);
  const extracted=await bounded(chrome.tabs.sendMessage(runTab,{kind:'copy-inspect-v016',task}),10000,'文案自动检测无响应，请刷新ChatGPT页面后保存现有文案');
  if(current?.id!==task.id)return;
  if(extracted?.copy&&!extracted.generating){
   const signature=JSON.stringify(extracted.copy);
   if(task.signature!==signature){current.signature=signature;await chrome.storage.local.set({activeTask:{...current,tabId:runTab}});return;}
   await api('/copy-result',{sku:task.sku,copy:extracted.copy});
   busy=false;current=null;await persist();await status('整组文案已自动采集并同步保存到全部变体');return;
  }
  if(Date.now()-(task.startedAt||Date.now())>7*60*1000)throw Error('文案自动提取超时，未重新发送；请展开当前文案并保存现有文案');
 }catch(e){
  if(current?.id===task.id){await api('/copy-failed',{sku:task.sku,message:e.message}).catch(()=>{});busy=false;current=null;await persist();await status(e.message);}
 }finally{inspectingCopy=false;}
}
let polling=false,pollRequested=false;
async function poll(){
 if(polling){pollRequested=true;return;}
 polling=true;
 try{await pollOnce();}catch(e){await status('自动接续待恢复：'+e.message).catch(()=>{});setTimeout(poll,3000)?.unref?.();}finally{
  polling=false;
  if(pollRequested){pollRequested=false;setTimeout(poll,0)?.unref?.();}
 }
}
async function pollOnce(){
 if(bindingChanging||restartingFailure)return;
 await restore();
 try{
  const control=await api('/control',{});const prior=await chrome.storage.local.get(['controlSerial','controlToken']);
  if(control.serial!==prior.controlSerial||(control.command_token&&control.command_token!==prior.controlToken)){
   await chrome.storage.local.set({controlSerial:control.serial,controlToken:control.command_token||null,...(control.serial>0?{autoEnabled:!control.paused}:{})});
   if(control.command_token)await api('/control-ack',{command_token:control.command_token}).catch(()=>{});
  }
  // Pause is authoritative even if the worker died after storing the token
  // but before removing activeTask; an unchanged token must never resume copy.
  if(control.paused){
   const paused=current;
   if(paused&&runTab!=null)await chrome.tabs.sendMessage(runTab,{kind:'stop'}).catch(()=>{});
   busy=false;current=null;await chrome.storage.local.set({autoEnabled:false});await persist();
   if(paused)await api('/pause-ack',{task_id:paused.id}).catch(()=>{});
   await status('制作已暂停，继续时读取已有结果');return;
  }
  const command=control.queue_restart;
  if(!control.paused&&command?.token){
   const saved=await chrome.storage.local.get('queueRestartToken');
   if(saved.queueRestartToken!==command.token){
    const tab=await workTab(runTab);
    await chrome.tabs.sendMessage(tab.id,{kind:'stop'}).catch(()=>{});
    busy=false;current=null;runTab=tab.id;await persist();
    await chrome.storage.local.set({queueRestartToken:command.token,autoEnabled:true,lastSku:command.sku});
    await chrome.alarms.create?.('ozon-poll',{periodInMinutes:0.5});
    await status('已接收重启请求：'+command.sku+'；已退出旧任务，正在自动领取新队列');
   }
   if(control.queue_restart_ack?.token!==command.token)await api('/queue-restart-ack',{token:command.token});
  }
 }catch(e){await status('本地连接待恢复：'+e.message);setTimeout(poll,3000)?.unref?.();return;}
 if(bindingChanging)return;

 if(busy&&current?.id?.startsWith('copy:')){
  try{if(current.copy_phase==='inspecting')await inspectExistingCopy(current,await workTab(runTab));else await inspectCopy();}
  finally{if(busy&&current?.id?.startsWith('copy:'))setTimeout(poll,1500)?.unref?.();}
  return;
 }
 const x=await chrome.storage.local.get(['autoEnabled','autoTab','autoUrl']);
 await api('/heartbeat',{auto_enabled:!!x.autoEnabled}).catch(()=>{});
 if(!x.autoEnabled)return;
 if(x.autoTab==null&&!x.autoUrl){await status('队列已启动，尚未绑定作图页：请在ChatGPT商品作图页保存配对并绑定当前页，或点击一次开始/继续');return;}
 if(busy){
  try{
   await api('/heartbeat',{auto_enabled:true});
   const remote=await api('/task-status',{task_id:current.id});if(bindingChanging)return;
   if(remote.state==='needs_attention'&&remote.resume_mode==='inspect_only'){await recoverExisting(remote,await workTab(runTab));return;}
   if((remote.recollection_requested||remote.image_job)&&remote.state==='waiting'){
    const tab=await workTab(runTab);await inject(tab.id);const check=await chrome.tabs.sendMessage(tab.id,{kind:'preflight'});
    if(check?.version!=='1.0.84')throw Error('请更新插件并刷新原作图页；将自动恢复采集，无需逐个操作');
    if(check.imageTaskId!==current.id){await recoverExisting(remote,tab);return;}
   }
   if(remote.image_job&&['processing','committing'].includes(remote.state)){await status(remote.message||'图片已收齐，本地正在校验替换，完成后自动继续下一变体');setTimeout(poll,500);return;}
   if(!remote.found||['saved','cancelled','approved'].includes(remote.state)){
    const tab=await workTab(runTab);await inject(tab.id);const page=await chrome.tabs.sendMessage(tab.id,{kind:'preflight'});
    if(page?.generating||page?.imageTaskId||page?.copyTaskActive){await status('上一任务尚在完成回复或采集，结束后才启动下一任务');setTimeout(poll,500);return;}
    if(!page?.ready)throw Error(page?.message||'尚未确认上一任务页面已空闲');
    busy=false;current=null;await persist();
   }
   else{await status((remote.state==='needs_attention'?'任务需处理：':'正在处理：')+remote.sku+'，'+(remote.message||remote.state));return;}
  }catch(e){await status('核对前序任务失败：'+e.message);setTimeout(poll,1500);return;}
 }
 try{const q=await api('/poll',{execution_idle:!busy&&!current});if(bindingChanging)return;if(q.copy_waiting){competitorPoll();setTimeout(poll,2500)?.unref?.();if(!q.ready&&!q.copy_sku){await status(q.copy_waiting);return;}}if(q.recovery_sku){await recoverExisting({sku:q.recovery_sku},await workTab(x.autoTab));return;}if(q.copy_sku){
 const tab=await workTab(x.autoTab);if(!tab.url||new URL(tab.url).origin!=='https://chatgpt.com')throw Error('绑定页面已关闭');await copyPipeline(q.copy_sku,tab);return;
 }if(!q.ready){const recoverable=q.blockers?.find(t=>['inspect_only','copy_inspect_only'].includes(t.resume_mode));if(recoverable){const tab=await workTab(x.autoTab);if(recoverable.resume_mode==='copy_inspect_only')await inspectExistingCopy(recoverable,tab);else await recoverExisting(recoverable,tab);return;}if(q.blocked_reason)await status('队列暂停：'+q.blocked_reason);else if(q.summary)await status(q.summary);return;}
 const tab=await workTab(x.autoTab);if(!tab.url||new URL(tab.url).origin!=='https://chatgpt.com')throw Error('绑定标签已关闭或离开ChatGPT');
 // Reuse the same guarded run path, without sending a runtime message to ourselves.
 await runAuto(tab);
 }catch(e){await status('等待自动恢复：'+e.message);setTimeout(poll,3000)?.unref?.();}
}
async function runAuto(tab){
 if(busy||bindingChanging)return;busy=true;runTab=tab.id;
 try{await chrome.scripting.executeScript({target:{tabId:tab.id},files:['diagnostics.js','conversation.js','composer.js','uploads.js','copy_parser.js','images.js','file_links.js','download_ui.js','delivery.js','generation_failure.js','composer_cleanup.js','content.js']});const check=await chrome.tabs.sendMessage(tab.id,{kind:'preflight'});if(bindingChanging){busy=false;return;}if(check?.version!=='1.0.84')throw Error('网页脚本仍是旧版，请刷新ChatGPT页面后重试');if(!check?.ready&&(check?.generating||check?.imageTaskId||check?.copyTaskActive)){busy=false;await status('上一条回复仍在生成，结束后自动执行排队的图片任务');setTimeout(poll,3000);return;}if(!check?.ready)throw Error(check?.message||'页面未就绪');current=await api('/claim',{tab_id:tab.id,page_url:tab.url});await persist();await chrome.tabs.sendMessage(tab.id,{kind:'start',task:current});}
 catch(e){if(current)await api('/event',{task_id:current.id,state:'needs_attention',message:e.message}).catch(()=>{});busy=false;current=null;await persist();throw e;}
}
chrome.alarms.onAlarm.addListener(a=>{if(a.name==='ozon-poll'){startWakeChannel();poll();competitorPoll();}});

function captureDownload(tabId,token,filename){
 if(!chrome.downloads?.onDeterminingFilename)return Promise.reject(Error('扩展未获得下载权限，请重新加载扩展并允许下载权限'));
 return new Promise((resolve,reject)=>{
  let id=null,timer,idleTimer;
  const allowed=url=>{try{const u=new URL(url);return u.hostname==='chatgpt.com'||u.hostname.endsWith('.oaiusercontent.com')||url.startsWith('blob:https://chatgpt.com/')||url.startsWith('data:image/');}catch{return false;}};
  function cleanup(){chrome.tabs.sendMessage(tabId,{kind:'download-finished',token}).catch(()=>{});clearTimeout(timer);clearTimeout(idleTimer);chrome.downloads.onDeterminingFilename.removeListener(determine);chrome.downloads.onChanged.removeListener(changed);}
  function fail(error){cleanup();reject(error);}
  function determine(item,suggest){
   if(id!==null||!allowed(item.finalUrl||item.url)){suggest();return;}
   id=item.id;suggest({filename,conflictAction:'uniquify'});
  }
  async function changed(delta){
   if(delta.id!==id)return;
   if(delta.error||delta.state?.current==='interrupted'){fail(Error('浏览器下载中断，已有文件保留'));return;}
   if(delta.state?.current==='complete'){
    try{const [item]=await chrome.downloads.search({id});if(!item?.filename)throw Error('浏览器未返回下载文件位置');cleanup();resolve(item.filename);}catch(e){fail(e);}
   }
  }
  chrome.downloads.onDeterminingFilename.addListener(determine);chrome.downloads.onChanged.addListener(changed);
  timer=setTimeout(()=>fail(Error('等待浏览器下载超时，请导出含文件链接的页面诊断')),120000);
  chrome.tabs.sendMessage(tabId,{kind:'download-click',token}).then(r=>{if(r?.error)fail(Error(r.error));else if(r?.images?.length===1){cleanup();resolve(r);}else if(r?.unresolved&&id===null){idleTimer=setTimeout(()=>{if(id===null)fail(Error(r.message+'；浏览器未启动下载，请保留原作图页'));},3000);}}).catch(fail);
 });
}

async function restoreSchedule(){startWakeChannel();try{const x=await chrome.storage.local.get(['pairToken','autoEnabled']);if(x.pairToken){await chrome.alarms.create('ozon-poll',{periodInMinutes:0.5});await poll();}}catch(e){await status('等待连接恢复：'+e.message);}}
chrome.runtime.onStartup?.addListener(restoreSchedule);chrome.runtime.onInstalled?.addListener(restoreSchedule);

// Independent read-only reference lane; never changes ChatGPT task state,
// bound tab, generation status or the send/collection queue.
let competitorReading=false;
function competitorUrl(value){try{const u=new URL(value);return u.protocol==='https:'&&['ozon.ru','www.ozon.ru'].includes(u.hostname)&&!u.username&&!u.password&&(!u.port||u.port==='443')&&/^\/product\/(?:[^/\s]+-)?\d+\/?$/.test(u.pathname)?'https://www.ozon.ru'+u.pathname.replace(/\/$/,'')+'/':null;}catch{return null;}}
async function competitorPoll(){
 if(competitorReading)return;competitorReading=true;
 let lease=null,completed=false,errorCode='transient';
 try{
  const saved=await chrome.storage.local.get(['pairToken','competitorActive']);if(!saved.pairToken)return;
  lease=saved.competitorActive;
  if(!lease){
   const {job}=await api('/competitor-task',{});if(!job)return;
   if(!competitorUrl(job.url))throw Error('竞品链接不是允许的Ozon商品页');
   lease={job,createdAt:Date.now()};
   await chrome.storage.local.set({competitorActive:lease});
   const prior=await chrome.storage.local.get('competitorRecovery');let tab=null;
   if(prior.competitorRecovery?.url===competitorUrl(job.url))try{const candidate=await chrome.tabs.get(prior.competitorRecovery.tabId);if(competitorUrl(candidate.url)===competitorUrl(job.url))tab=candidate;}catch{}
   if(!tab)tab=await chrome.tabs.create({url:job.url+'#section-characteristics',active:false});
   lease.tabId=tab.id;await chrome.storage.local.set({competitorActive:lease});
  }
  if(lease.tabId==null||Date.now()-lease.createdAt>150000)throw Error('竞品读取被中断，可在预览中重新读取');
  let result=null;
  const deadline=Date.now()+45000;
  while(Date.now()<deadline){
   const tab=await chrome.tabs.get(lease.tabId);
   if(tab.status==='complete'){
    if(competitorUrl(tab.url)!==competitorUrl(lease.job.url)){errorCode='redirect';throw Error('竞品页面跳转或需要验证，未采用其他页面参数；请核对保留的页面');}
    await chrome.scripting.executeScript({target:{tabId:lease.tabId},files:['competitor_page.js']});
    const [{result:page}]=await chrome.scripting.executeScript({target:{tabId:lease.tabId},args:[lease.job.fields||[]],func:fields=>{globalThis.__ozonCompetitorPrepare?.();return globalThis.__ozonCompetitorRead(fields);}});
    if(page?.error_code==='verification'){errorCode='verification';throw Error('竞品页要求人工验证；已保留页面，完成验证后点击重新读取');}
    if(page?.rows?.length){result=page;if(page.diagnostics?.full_sections!==0)break;}
   }
   await new Promise(resolve=>setTimeout(resolve,1000));
  }
  if(!result)throw Error('竞品页面未返回公开参数，可能需要验证或尚未加载；请在预览中打开原链接核对');
  await api('/competitor-result',{token:lease.job.token,...result});completed=true;
 }catch(e){
  if(lease?.job)await api('/competitor-result',{token:lease.job.token,error:String(e.message||e).slice(0,200),error_code:errorCode}).catch(()=>{});
 }finally{
  // Remove only the tab we created, and only if it still shows that product.
  // A tab the user navigated elsewhere is left alone.
  if(lease){
   if(lease.tabId!=null)try{const tab=await chrome.tabs.get(lease.tabId);if(completed&&competitorUrl(tab.url)===competitorUrl(lease.job.url))await chrome.tabs.remove(lease.tabId);}catch{}
   if(!completed&&lease.tabId!=null)await chrome.storage.local.set({competitorRecovery:{tabId:lease.tabId,url:competitorUrl(lease.job.url)}}).catch(()=>{});
   if(completed)await chrome.storage.local.remove('competitorRecovery').catch(()=>{});
   await chrome.storage.local.remove('competitorActive').catch(()=>{});
  }
  competitorReading=false;
  if(lease)setTimeout(competitorPoll,6000)?.unref?.();
 }
}

let wakeChannel=null;
function startWakeChannel(){
 if(!globalThis.OzonAutomationWake)return;
 if(!wakeChannel)wakeChannel=OzonAutomationWake.create({api,
  getState:()=>chrome.storage.local.get(['pairToken','autoEnabled','autoTab','autoUrl']),
  onWake:()=>{competitorPoll();return poll();},onState:value=>chrome.storage.local.set(value)});
 wakeChannel.start()?.catch(()=>{});
}
// A service-worker cold start may be triggered by a page message rather than
// onStartup. Restore the paired event channel in both cases.
startWakeChannel();
