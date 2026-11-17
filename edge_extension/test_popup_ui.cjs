const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function ui(){const elements={status:{textContent:'制作已暂停'},'task-state':{},'activity-title':{},'next-step':{}};const ctx={document:{body:{dataset:{}},getElementById:id=>elements[id],querySelector:()=>elements.status,querySelectorAll:()=>[]},MutationObserver:class{observe(){}}};vm.runInNewContext(fs.readFileSync(__dirname+'/popup_ui.js','utf8'),ctx);return {api:ctx.OzonPopupUI,elements,ctx};}
test('unconfirmed send offers checking instead of suggesting another generation request',()=>{const {api}=ui();const p=api.phase('发送结果尚未确认，请核对已有请求');assert.equal(p.key,'error');assert.match(p.next,/核对/);assert.doesNotMatch(p.next,/重新生成/);});
test('saved complete copy and in-flight final collection have distinct presentation',()=>{const {api}=ui();assert.equal(api.phase('整组文案已保存并同步全部变体').key,'done');assert.equal(api.phase('回复已结束，正在核对最终图片交付与编号').key,'collecting');});
test('presentation update changes labels only and requires no automation APIs',()=>{const {api,elements,ctx}=ui();assert.equal(ctx.document.body.dataset.phase,'paused');elements.status.textContent='正在提交当前任务';api.render();assert.equal(ctx.document.body.dataset.phase,'sending');assert.equal(elements['task-state'].textContent,'提交请求');});

test('queue blocker takes precedence over completed draft words',()=>{const {api}=ui();assert.equal(api.phase('队列暂停：前序任务 pdd-14(1) 尚未完成：8图、视频、共用俄语文案及草稿已完成；待上架审核').label,'等待前序任务');assert.equal(api.phase('8图、视频、共用俄语文案及草稿已完成；待上架审核').label,'等待审核');});

test('preparing copy never looks like collecting future saved results',()=>{const {api}=ui();assert.equal(api.phase('正在准备整组文案请求，等待上传与发送确认').key,'sending');assert.equal(api.phase('文案请求已发送并确认，等待当前回复完成').key,'generating');});
