// Read-only presentation. Never claims, sends or restarts automation work.
(()=>{
 function phase(message){
  const s=String(message||'');
  if(/队列暂停|前序任务.*尚未完成/.test(s))return {key:'paused',label:'等待前序任务',title:'前序任务尚未结束',next:'下方显示阻塞原因。在本地任务中心查看对应货号；已发送的请求先核对结果，避免重复提交。'};
  if(/待上架审核|待预览提交/.test(s))return {key:'done',label:'等待审核',title:'制作完成，等待审核',next:'在本地工具预览并审核商品；待审核本身不会阻止其他商品制作。'};
  if(/失败|异常|超时|不确定|尚未确认|未找到|不匹配|需处理|未连接/.test(s))return {key:'error',label:'需要核对',title:'查看当前提示',next:'先核对下方原因；需要读取已有结果时，展开“异常与恢复”。'};
  if(/已暂停|制作已暂停|保持暂停/.test(s))return {key:'paused',label:'已暂停',title:'任务已暂停',next:'当前素材会保留。确认页面状态后，点击“开始 / 继续”。'};
  if(/全部.*完成|整组.*已完成|已保存并同步|整组.*已上架/.test(s))return {key:'done',label:'本阶段完成',title:'结果已保存',next:'前往本地工具查看素材与文案，核对当前任务的后续操作。'};
  if(/请求已发送并确认|发送已执行|正在生成|仍在生成|等待.*回复|等待.*图片/.test(s))return {key:'generating',label:'等待生成',title:'等待当前回复完成',next:'当前请求已提交；回复完成后会自动检查并采集结果。'};
  if(/正在准备.*请求|正在提交|尚未提交|上传|发送确认|草稿/.test(s))return {key:'sending',label:'提交请求',title:'正在准备与确认发送',next:'等待附件上传及发送确认，插件会核对本任务是否出现在对话中。'};
  if(/采集|校验最终|核对最终|保存|托管|合成/.test(s))return {key:'collecting',label:'采集与保存',title:'正在处理已有结果',next:'保持作图页打开；回复和当前采集完成后自动接续下一任务。'};
  if(/发送/.test(s))return {key:'sending',label:'提交请求',title:'正在准备与确认发送',next:'等待页面确认本任务已发送。'};
  return {key:'idle',label:'等待任务',title:'等待下一步',next:'在本地工具创建商品任务；已有队列可点击“开始 / 继续”。'};
 }
 function render(){
  const state=phase(document.querySelector('#status')?.textContent);document.body.dataset.phase=state.key;
  for(const [id,value] of [['task-state',state.label],['activity-title',state.title],['next-step',state.next]]){const el=document.getElementById(id);if(el)el.textContent=value;}
  document.querySelectorAll('[data-step]').forEach(el=>el.classList.toggle('active',el.dataset.step===state.key));
 }
 globalThis.OzonPopupUI={phase,render};const status=document.getElementById('status');if(status)new MutationObserver(render).observe(status,{childList:true,characterData:true,subtree:true});render();
})();
