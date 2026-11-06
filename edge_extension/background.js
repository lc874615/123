const BASE='http://127.0.0.1:8765';
let busy=false,runTab=null,current=null;
async function status(s){await chrome.storage.local.set({status:s});}
async function api(path,body){const {pairToken}=await chrome.storage.local.get('pairToken');if(!pairToken)throw Error('请先输入配对码');const r=await fetch(BASE+path,{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+pairToken},body:JSON.stringify(body),signal:AbortSignal.timeout(30000)});const d=await r.json();if(!r.ok)throw Error(d.error||'本地服务错误');return d;}
chrome.runtime.onMessage.addListener((m,sender,reply)=>{(async()=>{
 if(m.kind==='enable'){
  const tab=await chrome.tabs.get(m.tabId);if(!tab.url||new URL(tab.url).origin!=='https://chatgpt.com')throw Error('请先打开ChatGPT商品对话');
  await chrome.storage.local.set({autoTab:tab.id,autoEnabled:true});await chrome.alarms.create('ozon-poll',{periodInMinutes:0.5});await status('自动批次已启用：本地创建商品后将自动开始。');setTimeout(poll,100);return {status:'已绑定，等待本地任务'};
 }
 if(m.kind==='run'){
  if(busy)throw Error('当前任务尚未结束，请先完成或暂停。');
  const tab=await chrome.tabs.get(m.tabId);if(!tab.url||new URL(tab.url).origin!=='https://chatgpt.com')throw Error('请在 ChatGPT 标签页点击扩展');
  busy=true;runTab=tab.id;
  try{await chrome.scripting.executeScript({target:{tabId:tab.id},files:['composer.js','content.js']});const check=await chrome.tabs.sendMessage(tab.id,{kind:'preflight'});if(!check?.ready)throw Error(check?.message||'当前页面尚未就绪');current=await api('/claim',{tab_id:tab.id,page_url:tab.url});await chrome.tabs.sendMessage(tab.id,{kind:'start',task:current});await status('任务已启动，保持此标签页打开。');return {status:'任务已启动'};}
  catch(e){if(current)await api('/event',{task_id:current.id,state:'needs_attention',message:e.message}).catch(()=>{});busy=false;current=null;throw e;}
 }
 if(m.kind==='stop'){await chrome.storage.local.set({autoEnabled:false});await chrome.alarms.clear('ozon-poll');if(runTab!==null)await chrome.tabs.sendMessage(runTab,{kind:'stop'}).catch(()=>{});if(current)await api('/event',{task_id:current.id,state:'needs_attention',message:'用户暂停；请检查网页，禁止直接重发。'});busy=false;current=null;await status('已请求暂停，网页中的生成可能仍在继续。');return {status:'已暂停'};}
 if(['result','event'].includes(m.kind)){
  if(sender.tab?.id!==runTab||!current||m.task_id!==current.id)throw Error('任务与标签页不匹配');
  if(m.kind==='result'){await api('/result',{task_id:current.id,image_b64:m.image_b64});busy=false;current=null;await status('图片已保存，自动继续下一张；全部完成后本地合成视频。');setTimeout(poll,3000);return {ok:true};}
  await api('/event',{task_id:current.id,state:m.state,message:m.message});await status(m.message);
  if(m.state==='needs_attention'){busy=false;current=null;await chrome.storage.local.set({autoEnabled:false});}return {ok:true};
 }
 throw Error('未知请求');
})().then(reply).catch(async e=>{await status(e.message);reply({error:e.message});});return true;});

async function poll(){
 const x=await chrome.storage.local.get(['autoEnabled','autoTab']);if(!x.autoEnabled||busy)return;
 try{const q=await api('/poll',{});if(!q.ready)return;
 const tab=await chrome.tabs.get(x.autoTab);if(!tab.url||new URL(tab.url).origin!=='https://chatgpt.com')throw Error('绑定标签已关闭或离开ChatGPT');
 // Reuse the same guarded run path, without sending a runtime message to ourselves.
 await runAuto(tab);
 }catch(e){await status(e.message);await chrome.storage.local.set({autoEnabled:false});}
}
async function runAuto(tab){
 if(busy)return;busy=true;runTab=tab.id;
 try{await chrome.scripting.executeScript({target:{tabId:tab.id},files:['composer.js','content.js']});const check=await chrome.tabs.sendMessage(tab.id,{kind:'preflight'});if(!check?.ready)throw Error(check?.message||'页面未就绪');current=await api('/claim',{tab_id:tab.id,page_url:tab.url});await chrome.tabs.sendMessage(tab.id,{kind:'start',task:current});}
 catch(e){if(current)await api('/event',{task_id:current.id,state:'needs_attention',message:e.message}).catch(()=>{});busy=false;current=null;throw e;}
}
chrome.alarms.onAlarm.addListener(a=>{if(a.name==='ozon-poll')poll();});
