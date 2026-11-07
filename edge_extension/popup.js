const status=document.querySelector('#status');
chrome.storage.local.get(['pairToken','status']).then(x=>{document.querySelector('#token').value=x.pairToken||'';if(x.status)status.textContent=x.status;});
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
 }catch(e){status.textContent=e.message;}finally{clearTimeout(timer);button.disabled=false;}
};

document.querySelector('#copy-paste').onclick=async()=>{try{const copy=globalThis.OzonCopy.parse(document.querySelector('#copy-json').value);if(!copy)throw Error('JSON不完整或缺少标题、简介、标签、缺失参数字段');const r=await chrome.runtime.sendMessage({kind:'copy-paste',sku:document.querySelector('#sku').value.trim(),copy});status.textContent=r.error||r.status;}catch(e){status.textContent=e.message;}};
