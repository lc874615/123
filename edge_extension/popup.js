let copyCandidates=[],candidateSku='';
const status=document.querySelector('#status');
chrome.storage.local.get(['pairToken','status','lastSku','activeTask']).then(x=>{document.querySelector('#token').value=x.pairToken||'';if(x.status)status.textContent=x.status;document.querySelector('#sku').value=x.activeTask?.sku||x.lastSku||'';});
document.querySelector('#pair').onclick=async()=>{await chrome.storage.local.set({pairToken:document.querySelector('#token').value.trim()});status.textContent='配对码已保存在本机扩展中。';};
document.querySelector('#run').onclick=async()=>{const [tab]=await chrome.tabs.query({active:true,currentWindow:true});try{const r=await chrome.runtime.sendMessage({kind:'enable',tabId:tab.id});status.textContent=r.error||r.status;}catch(e){status.textContent=e.message;}};
document.querySelector('#stop').onclick=async()=>{const r=await chrome.runtime.sendMessage({kind:'stop'});status.textContent=r.status||r.error;};
chrome.storage.onChanged.addListener(x=>{if(x.status)status.textContent=x.status.newValue;});

document.querySelector('#recover').onclick=async()=>{const [tab]=await chrome.tabs.query({active:true,currentWindow:true});const r=await chrome.runtime.sendMessage({kind:'recover',tabId:tab.id,sku:document.querySelector('#sku').value.trim()});status.textContent=r.error||r.status;};

document.querySelector('#copy').onclick=async()=>{const [tab]=await chrome.tabs.query({active:true,currentWindow:true});const r=await chrome.runtime.sendMessage({kind:'copy',tabId:tab.id,sku:document.querySelector('#sku').value.trim()});status.textContent=r.error||r.status;};

document.querySelector('#copy-recover').onclick=async()=>{
 const button=document.querySelector('#copy-recover');button.disabled=true;status.textContent='正在读取并保存现有文案…';
 let timer;
 try{const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  const r=await Promise.race([chrome.runtime.sendMessage({kind:'copy-recover',tabId:tab.id,sku:document.querySelector('#sku').value.trim()}),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('保存等待超时，请检查本地工具是否运行、配对码是否正确；已有素材保留')),55000);})]);
  status.textContent=r?.error||r?.status||'扩展未返回结果，请重新加载扩展并刷新页面';
  if(r?.candidates?.length){if(r.sku)document.querySelector('#sku').value=r.sku;showCandidates(r.candidates,r.sku||document.querySelector('#sku').value.trim());}
 }catch(e){status.textContent=e.message;}finally{clearTimeout(timer);button.disabled=false;}
};

document.querySelector('#copy-paste').onclick=async()=>{try{const copy=globalThis.OzonCopy.parse(document.querySelector('#copy-json').value);if(!copy)throw Error('JSON不完整或缺少标题、简介、标签、缺失参数字段');const r=await chrome.runtime.sendMessage({kind:'copy-paste',sku:document.querySelector('#sku').value.trim(),copy});status.textContent=r.error||r.status;}catch(e){status.textContent=e.message;}};

function showCandidates(values,sku){
 copyCandidates=values;candidateSku=sku;
 const list=document.querySelector('#copy-choice-list');list.replaceChildren();
 values.forEach((v,i)=>{const option=document.createElement('option');option.value=String(i);option.textContent=(i+1)+'. '+v.title_ru;list.append(option);});
 list.onchange=()=>{document.querySelector('#copy-choice-preview').textContent=JSON.stringify(copyCandidates[Number(list.value)],null,2);};
 document.querySelector('#copy-choice').hidden=false;list.onchange();
}
document.querySelector('#copy-choice-save').onclick=async()=>{
 const button=document.querySelector('#copy-choice-save');button.disabled=true;
 try{
  const sku=document.querySelector('#sku').value.trim();if(sku!==candidateSku)throw Error('货号已改变，请重新读取文案后确认');
  const value=copyCandidates[Number(document.querySelector('#copy-choice-list').value)];if(!value)throw Error('请选择文案');
  const r=await chrome.runtime.sendMessage({kind:'copy-paste',sku,copy:{...value,sku}});status.textContent=r.error||r.status;
  if(!r.error)document.querySelector('#copy-choice').hidden=true;
 }catch(e){status.textContent=e.message;}finally{button.disabled=false;}
};

document.querySelector('#diagnose').onclick=async()=>{
 try{const [tab]=await chrome.tabs.query({active:true,currentWindow:true});const result=await chrome.runtime.sendMessage({kind:'diagnose',tabId:tab.id});if(result.error)throw Error(result.error);
  const url=URL.createObjectURL(new Blob([JSON.stringify(result.diagnostic,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='ozon-page-diagnostic.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);status.textContent='诊断文件已导出，不包含配对码、完整图片网址或文案内容';
 }catch(e){status.textContent=e.message;}
};

document.querySelector('#sku').addEventListener('change',()=>chrome.storage.local.set({lastSku:document.querySelector('#sku').value.trim()}));
