async function bounded(p,ms,message){let timer;try{return await Promise.race([p,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(message)),ms);})]);}finally{clearTimeout(timer);}}
const BASE='http://127.0.0.1:8765';
let busy=false,runTab=null,current=null;
async function restore(){const x=await chrome.storage.local.get('activeTask');if(x.activeTask){current={...(current?.id===x.activeTask.id?current:{}),...x.activeTask};current.sku=current.sku||(current.id.startsWith('copy:')?current.id.slice(5):undefined);runTab=x.activeTask.tabId;busy=true;}}
async function persist(){if(current)await chrome.storage.local.set({...(current.sku?{lastSku:current.sku}:{}),activeTask:{id:current.id,sku:current.sku,marker:current.marker,tabId:runTab,startedAt:current.startedAt||Date.now(),signature:current.signature}});else await chrome.storage.local.remove('activeTask');}
async function status(s){await chrome.storage.local.set({status:s});}
async function api(path,body){const {pairToken}=await chrome.storage.local.get('pairToken');if(!pairToken)throw Error('请先输入配对码');const r=await fetch(BASE+path,{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+pairToken},body:JSON.stringify(body),signal:AbortSignal.timeout(30000)});const d=await r.json();if(!r.ok)throw Error(d.error||'本地服务错误');return d;}
chrome.runtime.onMessage.addListener((m,sender,reply)=>{(async()=>{
 await restore();
 if(m.kind==='diagnose'){
  const tab=await chrome.tabs.get(m.tabId);if(!tab.url||new URL(tab.url).origin!=='https://chatgpt.com')throw Error('请在ChatGPT商品对话中导出诊断');
  await chrome.scripting.executeScript({target:{tabId:tab.id},files:['conversation.js','copy_parser.js','diagnostics.js']});
  const result=await chrome.scripting.executeScript({target:{tabId:tab.id},func:()=>globalThis.OzonDiagnostics.snapshot()});
  return {diagnostic:result[0].result};
 }
 if(m.kind==='enable'){
  const tab=await chrome.tabs.get(m.tabId);if(!tab.url||new URL(tab.url).origin!=='https://chatgpt.com')throw Error('请先打开ChatGPT商品对话');
  await chrome.storage.local.set({autoTab:tab.id,autoEnabled:true});await chrome.alarms.create('ozon-poll',{periodInMinutes:0.5});await status('自动批次已启用：本地创建商品后将自动开始。');setTimeout(poll,100);return {status:'已绑定，等待本地任务'};
 }
 if(m.kind==='copy'){
  await chrome.alarms.create('ozon-poll',{periodInMinutes:0.5});
  if(busy)throw Error('请先完成或停止当前作图任务');
  const tab=await chrome.tabs.get(m.tabId);if(!tab.url||new URL(tab.url).origin!=='https://chatgpt.com')throw Error('请打开商品ChatGPT对话');
  current=await api('/copy-task',{sku:m.sku});runTab=tab.id;busy=true;current.startedAt=Date.now();await persist();
  await chrome.scripting.executeScript({target:{tabId:tab.id},files:['diagnostics.js','conversation.js','composer.js','uploads.js','copy_parser.js','images.js','content.js']});await chrome.tabs.sendMessage(tab.id,{kind:'copy',task:current});return {status:'正在生成俄文文案'};
 }
 if(m.kind==='copy-paste'){
  if(sender.tab)throw Error('只能从扩展面板提交粘贴文案');
  await api('/copy-result',{sku:m.sku,copy:m.copy});
  if(current?.id==='copy:'+m.sku){busy=false;current=null;await persist();}
  await status('文案已保存至本地草稿，待审核');return {status:'文案已保存至本地草稿，待审核'};
 }
 if(m.kind==='copy-recover'){
  const tab=await chrome.tabs.get(m.tabId);if(!tab.url||new URL(tab.url).origin!=='https://chatgpt.com')throw Error('请打开含现有文案的ChatGPT商品对话');
  if(current&&current.id!=='copy:'+m.sku)throw Error('另一个任务尚未完成，请先停止');
  current=await api('/copy-task',{sku:m.sku});runTab=tab.id;busy=true;current.startedAt=Date.now();await persist();
  try{
   await status('正在读取本页文案并保存');
   await chrome.scripting.executeScript({target:{tabId:tab.id},files:['diagnostics.js','conversation.js','composer.js','uploads.js','copy_parser.js','images.js','content.js']});
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
 if(m.kind==='copy-failed'){if(sender.tab?.id!==runTab||!current||m.task_id!==current.id)throw Error('任务不匹配');await api('/copy-failed',{sku:current.id.slice(5),message:m.message});busy=false;current=null;await persist();await status(m.message);return {ok:true};}
 if(m.kind==='copy-result'){
  if(sender.tab?.id!==runTab||!current||m.task_id!==current.id)throw Error('文案任务不匹配');
  await api('/copy-result',{sku:current.id.slice(5),copy:m.copy});busy=false;current=null;await persist();await status('俄文文案已保存至本地草稿，待审核');return {ok:true};
 }
 if(m.kind==='recover'){
  const tab=await chrome.tabs.get(m.tabId);if(!tab.url||new URL(tab.url).origin!=='https://chatgpt.com')throw Error('请打开已生成图片的商品对话');
  current=await api('/recover',{sku:m.sku});runTab=tab.id;busy=true;current.startedAt=Date.now();await persist();
  await chrome.scripting.executeScript({target:{tabId:tab.id},files:['diagnostics.js','conversation.js','composer.js','uploads.js','copy_parser.js','images.js','content.js']});await chrome.tabs.sendMessage(tab.id,{kind:'recover',task:current});return {status:'正在读取现有图片，不发送生成请求'};
 }
 if(m.kind==='run'){
  if(busy)throw Error('当前任务尚未结束，请先完成或暂停。');
  const tab=await chrome.tabs.get(m.tabId);if(!tab.url||new URL(tab.url).origin!=='https://chatgpt.com')throw Error('请在 ChatGPT 标签页点击扩展');
  busy=true;runTab=tab.id;
  try{await chrome.scripting.executeScript({target:{tabId:tab.id},files:['diagnostics.js','conversation.js','composer.js','uploads.js','copy_parser.js','images.js','content.js']});const check=await chrome.tabs.sendMessage(tab.id,{kind:'preflight'});if(check?.version!=='0.17.0')throw Error('网页脚本仍是旧版，请刷新ChatGPT页面后重试');if(!check?.ready)throw Error(check?.message||'当前页面尚未就绪');current=await api('/claim',{tab_id:tab.id,page_url:tab.url});await persist();await chrome.tabs.sendMessage(tab.id,{kind:'start',task:current});await status('任务已启动，保持此标签页打开。');return {status:'任务已启动'};}
  catch(e){if(current)await api('/event',{task_id:current.id,state:'needs_attention',message:e.message}).catch(()=>{});busy=false;current=null;await persist();throw e;}
 }
 if(m.kind==='stop'){await chrome.storage.local.set({autoEnabled:false});await chrome.alarms.clear('ozon-poll');if(runTab!==null)await chrome.tabs.sendMessage(runTab,{kind:'stop'}).catch(()=>{});if(current){if(current.id.startsWith('copy:'))await api('/copy-failed',{sku:current.id.slice(5),message:'用户暂停文案任务，请保存现有结果'});else await api('/event',{task_id:current.id,state:'needs_attention',message:'用户暂停；请检查网页，禁止直接重发。'});}busy=false;current=null;await persist();await status('已请求暂停，网页中的生成可能仍在继续。');return {status:'已暂停'};}
 if(['result','set-result','event'].includes(m.kind)){
  if(sender.tab?.id!==runTab||!current||m.task_id!==current.id)throw Error('任务与标签页不匹配');
  if(m.kind==='set-result'){const r=await api('/set-result',{task_id:current.id,index:m.index,image_b64:m.image_b64});if(r.complete||r.saved_count===8){busy=false;current=null;await persist();await status('8张图已保存，第1张为主图；本地正在合成8秒视频。');}return {ok:true};}
  if(m.kind==='result'){await api('/result',{task_id:current.id,image_b64:m.image_b64});busy=false;current=null;await persist();await status('图片已保存，自动继续下一张；全部完成后本地合成视频。');setTimeout(poll,3000);return {ok:true};}
  await api('/event',{task_id:current.id,state:m.state,message:m.message});await status(m.message);
  if(m.state==='needs_attention'){busy=false;current=null;await persist();await chrome.storage.local.set({autoEnabled:false});}return {ok:true};
 }
 throw Error('未知请求');
})().then(reply).catch(async e=>{await status(e.message);reply({error:e.message});});return true;});

let inspectingCopy=false;
async function inspectCopy(){
 if(inspectingCopy||!current?.id?.startsWith('copy:'))return;
 inspectingCopy=true;const task={...current};
 try{
  const extracted=await bounded(chrome.tabs.sendMessage(runTab,{kind:'copy-inspect-v016',task}),10000,'文案自动检测无响应，请刷新ChatGPT页面后保存现有文案');
  if(current?.id!==task.id)return;
  if(extracted?.copy&&!extracted.generating){
   const signature=JSON.stringify(extracted.copy);
   if(task.signature!==signature){current.signature=signature;await chrome.storage.local.set({activeTask:{...current,tabId:runTab}});return;}
   await api('/copy-result',{sku:task.sku,copy:extracted.copy});
   busy=false;current=null;await persist();await status('俄文文案已自动保存至本地草稿，待审核');return;
  }
  if(Date.now()-(task.startedAt||Date.now())>7*60*1000)throw Error('文案自动提取超时，未重新发送；请展开当前文案并保存现有文案');
 }catch(e){
  if(current?.id===task.id){await api('/copy-failed',{sku:task.sku,message:e.message}).catch(()=>{});busy=false;current=null;await persist();await status(e.message);}
 }finally{inspectingCopy=false;}
}
async function poll(){
 await restore();
 if(busy&&current?.id?.startsWith('copy:')){await inspectCopy();return;}
 const x=await chrome.storage.local.get(['autoEnabled','autoTab']);if(!x.autoEnabled||busy)return;
 try{const q=await api('/poll',{});if(q.copy_sku){
 const tab=await chrome.tabs.get(x.autoTab);if(!tab.url||new URL(tab.url).origin!=='https://chatgpt.com')throw Error('绑定页面已关闭');
 current=await api('/copy-task',{sku:q.copy_sku});runTab=tab.id;busy=true;current.startedAt=Date.now();await persist();
 await chrome.scripting.executeScript({target:{tabId:tab.id},files:['diagnostics.js','conversation.js','composer.js','uploads.js','copy_parser.js','images.js','content.js']});await chrome.tabs.sendMessage(tab.id,{kind:'copy',task:current});await status('图片及视频完成，自动生成俄文文案');return;
 }if(!q.ready)return;
 const tab=await chrome.tabs.get(x.autoTab);if(!tab.url||new URL(tab.url).origin!=='https://chatgpt.com')throw Error('绑定标签已关闭或离开ChatGPT');
 // Reuse the same guarded run path, without sending a runtime message to ourselves.
 await runAuto(tab);
 }catch(e){await status(e.message);await chrome.storage.local.set({autoEnabled:false});}
}
async function runAuto(tab){
 if(busy)return;busy=true;runTab=tab.id;
 try{await chrome.scripting.executeScript({target:{tabId:tab.id},files:['diagnostics.js','conversation.js','composer.js','uploads.js','copy_parser.js','images.js','content.js']});const check=await chrome.tabs.sendMessage(tab.id,{kind:'preflight'});if(check?.version!=='0.17.0')throw Error('网页脚本仍是旧版，请刷新ChatGPT页面后重试');if(!check?.ready)throw Error(check?.message||'页面未就绪');current=await api('/claim',{tab_id:tab.id,page_url:tab.url});await persist();await chrome.tabs.sendMessage(tab.id,{kind:'start',task:current});}
 catch(e){if(current)await api('/event',{task_id:current.id,state:'needs_attention',message:e.message}).catch(()=>{});busy=false;current=null;await persist();throw e;}
}
chrome.alarms.onAlarm.addListener(a=>{if(a.name==='ozon-poll')poll();});
