const status=document.querySelector('#status');
chrome.storage.local.get(['pairToken','status']).then(x=>{document.querySelector('#token').value=x.pairToken||'';if(x.status)status.textContent=x.status;});
document.querySelector('#pair').onclick=async()=>{await chrome.storage.local.set({pairToken:document.querySelector('#token').value.trim()});status.textContent='配对码已保存在本机扩展中。';};
document.querySelector('#run').onclick=async()=>{const [tab]=await chrome.tabs.query({active:true,currentWindow:true});try{const r=await chrome.runtime.sendMessage({kind:'run',tabId:tab.id});status.textContent=r.error||r.status;}catch(e){status.textContent=e.message;}};
document.querySelector('#stop').onclick=async()=>{const r=await chrome.runtime.sendMessage({kind:'stop'});status.textContent=r.status||r.error;};
chrome.storage.onChanged.addListener(x=>{if(x.status)status.textContent=x.status.newValue;});
