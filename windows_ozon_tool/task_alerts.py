"""Chinese actionable task alerts, independent of task execution or retry policy."""
import hashlib,json,os,re,time
from pathlib import Path
from pricing_service import read,write

def safe_text(value):
 text=str(value or '')
 for name in ('OZON_API_KEY','COS_SECRET_KEY','COS_SECRET_ID'):
  secret=os.environ.get(name,'')
  if secret:text=text.replace(secret,'[已隐藏]')
 text=re.sub(r'(https?://[^\s?]+)\?[^\s]+',r'\1?[参数已隐藏]',text)
 return text[:1800]

def solution(message):
 m=message.casefold()
 if any(x in m for x in ('不确定','uncertain','结果未知','没有明确导入任务id')):
  return '请求结果尚未确认', ['先到Ozon后台或原ChatGPT对话核对本次请求是否已受理。','已受理就查询/采集已有结果，不要重新创建、清空进度或重复发送。','仅在明确确认未受理后，使用对应异常恢复入口重试。']
 if any(x in m for x in ('blocked','warehouse','仓库已不在','仓库不可用')):
  return '仓库状态或配置需要处理',['在Ozon后台检查该仓库是否启用、配送设置是否完整；blocked表示平台返回受限状态。','整组预览中刷新店铺仓库，核对当前店铺和所选仓库。','仓库恢复后查询上架进度；不要通过重建商品来解决仓库问题。']
 if any(x in m for x in ('barcode','条形码','条码')):
  return '条形码处理未完成',['查看上架进度的条形码及平台错误列；若为403/权限不足，为密钥开启Barcode权限。','若已受理或结果未知，等待查询实际码值，不重复申请。','确认权限或参数修复后，点击“立即查询导入、库存及可售状态”。']
 if any(x in m for x in ('403','forbidden','accessdenied','权限','invalidaccesskey','signaturedoesnotmatch')):
  return '访问权限或签名校验失败',['托管错误请在设置核对COS地域、存储桶、密钥及上传目录权限。','Ozon错误请核对当前店铺Client-Id与API密钥的商品、条形码和库存权限。','修复配置后继续原任务；不要把密钥粘贴到聊天或诊断截图中。']
 if any(x in m for x in ('429','quota','限额','额度','验证码','登录')):
  return '网页验证、登录或额度限制',['打开已绑定的ChatGPT原作图页，完成登录/验证码，或等待额度恢复。','确认已有回复是否已经生成；有结果时只采集已有结果。','处理后在本地点击“继续制作”，不要重复发送已受理请求。']
 if any(x in m for x in ('输入框已有','草稿已被修改','未覆盖')):
  return '输入框中已有草稿，工具已保留原内容',['先在原对话保存你自己的草稿，再整理输入框。','如果本次任务已发送，保留回复并使用自动采集功能，不重新发送。','如果明确尚未发送，恢复输入框可用后点击“继续制作”。']
 if any(x in m for x in ('certificate','ssl','证书')):
  return 'HTTPS证书校验失败',['检查电脑日期、系统根证书以及代理/安全软件的HTTPS配置。','在设置重新获取相关来源，或网络恢复后继续原任务。','不要关闭证书校验；已发送请求先核对回执，不直接重发。']
 if 'product creation incomplete' in m:
  return '平台商品创建尚未完成',['保持原导入任务，等待平台完成创建，不重新导入。','在上架进度点击“立即查询导入、库存及可售状态”。','长期无进展时到Ozon后台查看商品卡片错误；创建完成后才继续库存流程。']
 if any(x in m for x in ('文案','json','copy')):
  return '文案采集或同步需要处理',['先检查原对话的文案是否已生成完整。','已有文案可用插件“自动采集/补全文案并同步全组”，或在预览填写后点击“保存并同步全组文案”。','提示参数/材质冲突时先修改对应内容，再保存；无需重做已有图片。']
 if any(x in m for x in ('ffmpeg','pillow','视频','mp4','依赖')):
  return '本地视频或依赖处理失败',['先检查8张图片是否完整且本地文件可读。','缺少依赖时运行本地工具目录的“修复依赖.bat”。','依赖恢复后重新合成已有8图的视频，不重新作图。']
 if any(x in m for x in ('cos','upload','上传','托管','nosuchbucket')):
  return '图片或视频托管失败',['在设置检查COS存储桶、地域和上传目录；确认允许写入该目录。','确认商品图片链接可公开读取，网络已恢复。','继续原任务进行断点上传；保留已有图片、MP4和成功链接。']
 if any(x in m for x in ('stock','库存')):
  return '库存设置或查询未完成',['先查询商品导入和创建是否已完成，再查看所选仓库的错误回执。','结果不确定时先查询核对，不直接重复写库存。','现有已售商品不重置库存；不要通过清空进度重建来处理。']
 if any(x in m for x in ('图片待','素材待','外观参数')):
  return '图片参数需要核对',['打开整组预览的“图片视频”，查看变化字段和实际图片。','确认图片无误时点击底部“图片无误，沿用本组”。','确实需要修改时才手动启动相应主图或共用详情重做。']
 if any(x in m for x in ('标记','采集','编号','图片','image','文件清单','未找到输入框','发送按钮','作图页','页面','绑定')):
  return '作图页定位或图片采集需要处理',['先暂停制作，打开原商品的ChatGPT对话，确认图片/下载列表已生成。','用插件“定位 / 更换作图页”重新绑定正确对话，再继续。','已有图片优先使用“备份并自动采集已有图片（不重新作图）”；不要重新生成已完成图片。']
 if any(x in m for x in ('timeout','timed out','ssl','certificate','网络','连接','超时')):
  return '连接中断或网络校验失败',['检查网络以及本地工具、浏览器是否仍在运行。','证书错误先检查系统日期/证书和网络代理，不关闭HTTPS证书校验。','写入请求超时应先核对是否受理；只恢复安全查询，不盲目重发。']
 if any(x in m for x in ('属性','参数','类目','validation','required','attribute','invalid_argument','price','价格','资料','材质','售价','税率')):
  return '商品参数或价格未通过校验',['打开整组预览，查看平台结果及缺失必填项。','按当前类目API选项修正参数，核对售价、币种和仓库。','点击“更新整组预览”，核对后提交；保留已有素材。']
 return '任务执行遇到异常',['打开任务中心，查看对应货号的当前阶段及原始错误。','暂停后检查原作图页或上架回执，保留现有文件和请求记录。','明确尚未发送时才重试；已有结果则继续采集或查询。']

def issue(owner,stage,message,identity=None):
 message=safe_text(message);cause,steps=solution(message)
 stable=re.sub(r'(?:已用|等待|耗时|重试)[ ：:]?\d+(?:\.\d+)?(?:秒|次)?','[进度]',message)
 key=hashlib.sha256(json.dumps([str(owner),stage,stable,identity],ensure_ascii=False).encode()).hexdigest()
 return {'key':key,'owner':str(owner),'stage':stage,'cause':cause,'steps':steps,'detail':message}

def render(items):
 blocks=[]
 for i,row in enumerate(items,1):blocks.append(f"{i}. 任务：{row['owner']}\n阶段：{row['stage']}\n中文说明：{row['cause']}\n处理办法：\n"+'\n'.join(str(n)+'. '+s for n,s in enumerate(row['steps'],1))+'\n原始信息（供排查）：'+row['detail'])
 return '\n\n'+'\n\n'.join(blocks)

def hosting_failed(state):
 # Older drafts used pending for both safe automatic work and retryable failures.
 status=state.get('state');message=state.get('message','')
 if status in ('failed','error','needs_attention'):return True
 if status!='pending' or not message:return False
 if message=='生成图已更新，等待自动补齐新图片链接':return False
 return not message.startswith(('等待','图片已','视频已'))

def collect(tasks,bundles,jobs,image_jobs=(),plugin=None):
 found=[]
 for task in list(tasks)+list(image_jobs):
  if task.get('state')=='cancelled':continue
  owner=task.get('sku') or task.get('id','未知任务');m=task.get('message','')
  intentional=task.get('pause_requested') or any(s in m for s in ('已请求暂停','用户暂停','制作已暂停','服务已重启，等待自动读取','等待恢复已有结果','已备份旧素材，已加入','等待自动定位原始图片','文案被重启中断，等待自动读取'))
  if not intentional and (task.get('state') in ('needs_attention','failed','error') or task.get('copy_state')=='needs_attention'):found.append(issue(owner,'文案处理' if task.get('copy_state')=='needs_attention' else '图片制作/采集',m or '任务状态异常，需检查原页面',task.get('id')))
  if task.get('state')=='saved' and '视频合成失败' in m:found.append(issue(owner,'视频合成',m,task.get('id')))
 for b in bundles:
  manual=b.get('manual_pricing') or {}
  if b.get('manual_price') and manual.get('valid') is False:found.append(issue(b['sku'],'售价计算','手动售价无适用费用/物流方案：'+str(manual.get('message') or '需要核对成本、尺寸、重量及定价来源')))
  for name,title in (('hosting','图片托管'),('video_hosting','视频托管')):
   state=b.get(name) or {};m=state.get('message','')
   if hosting_failed(state):found.append(issue(b['sku'],title,m or '托管失败'))
 seen_offers=set()
 for job in sorted(jobs,key=lambda j:j.get('created_at',0),reverse=True):
  items=job.get('items') or {}
  if not isinstance(items,dict):
   found.append(issue(job.get('id','本地记录'),'读取上架记录','本地上架记录格式异常，请保留原文件并导出诊断，不要删除或重复提交',job.get('id')));continue
  current_items={owner:row for owner,row in items.items() if owner not in seen_offers};seen_offers.update(items)
  if job.get('state') in ('cancelled_followup','superseded'):continue
  for owner,row in current_items.items():
   errors=row.get('barcode_errors') or row.get('stock_errors') or row.get('price_errors') or row.get('errors') or row.get('platform_errors')
   if isinstance(errors,list):errors=[e for e in errors if not isinstance(e,dict) or str(e.get('level','ERROR')).upper() not in ('WARNING','WARN','INFO','ERROR_LEVEL_WARNING')]
   query_failed=job.get('retry_count',0)>0 and str(job.get('message','')).startswith('安全查询待重试')
   bad=query_failed or job.get('state') in ('validation_failed','rejected','failed','import_uncertain','local_changed') or job.get('needs_attention') or row.get('import_state')=='failed' or row.get('stock_state') in ('uncertain','rejected') or row.get('barcode_state') in ('uncertain','rejected') or bool(errors)
   if bad:
    fallback=(job.get('message') or row.get('status')) if query_failed or job.get('state') in ('validation_failed','rejected','failed','import_uncertain','local_changed') else (row.get('status') or job.get('message'))
    detail=row.get('error_summary') or (json.dumps(errors,ensure_ascii=False) if errors else fallback or '上架进度异常')
    if job.get('state')=='import_uncertain':detail='导入请求结果不确定；'+detail
    if row.get('barcode_state') in ('uncertain','rejected'):detail='条形码：'+detail
    if row.get('stock_state') in ('uncertain','rejected'):detail='库存：'+detail
    found.append(issue(owner,'提交与上架',detail,job.get('id')))
 if plugin and plugin.get('error'):
  m=plugin.get('message','')
  if m and not any(m in x['detail'] or x['detail'] in m for x in found):found.append(issue(plugin.get('sku') or '浏览器插件','插件运行',m,plugin.get('incident')))
 return list({x['key']:x for x in found}.values())

class AlertState:
 def __init__(self,path):
  self.path=Path(path);self.active=set()
  try:
   saved=read(self.path);values=saved.get('acknowledged',[]) if isinstance(saved,dict) else [];self.acked={v for v in values if isinstance(v,str)} if isinstance(values,list) else set()
  except (OSError,ValueError):self.acked=set()
 def update(self,items):
  active={r['key'] for r in items};old=set(self.acked);self.active=active;self.acked&=active
  if self.acked!=old:self.save()
  return [r for r in items if r['key'] not in self.acked]
 def acknowledge(self,keys):self.acked|=set(keys)&self.active;self.save()
 def save(self):
  try:write(self.path,{'acknowledged':sorted(self.acked)})
  except OSError:pass

class AlertPopup:
 def __init__(self,root,path,open_tasks):self.root=root;self.state=AlertState(path);self.open_tasks=open_tasks;self.window=None;self.shown={};self.previous_grab=None;self.latest=[]
 def update(self,items):
  self.latest=list(items);pending=self.state.update(self.latest);active={r['key'] for r in self.latest};previous=set(self.shown);self.shown={k:v for k,v in self.shown.items() if k in active};new=[r for r in pending if r['key'] not in self.shown]
  if not self.shown and not new:
   if self.window is not None:self.close()
   return
  if not new and previous==set(self.shown):return
  self.shown.update({r['key']:r for r in new})
  import tkinter as tk
  from tkinter import ttk
  from tkinter.scrolledtext import ScrolledText
  if self.window is None or not self.window.winfo_exists():
   self.root.deiconify();self.window=tk.Toplevel(self.root);self.window.title('任务异常，需要处理');self.window.geometry('780x580+'+str(max(0,(self.root.winfo_screenwidth()-780)//2))+'+'+str(max(0,(self.root.winfo_screenheight()-580)//2)));self.window.minsize(620,420);self.window.transient(self.root);self.window.attributes('-topmost',True)
   ttk.Label(self.window,text='检测到任务异常。请按中文步骤处理；弹窗本身不重发请求、不删除文件。',wraplength=730).pack(padx=12,pady=10)
   self.text=ScrolledText(self.window,wrap='word');self.text.pack(fill='both',expand=True,padx=12,pady=5)
   bar=ttk.Frame(self.window);bar.pack(fill='x',padx=12,pady=10)
   ttk.Button(bar,text='我已知晓',command=self.close).pack(side='right',padx=4);ttk.Button(bar,text='打开任务中心',command=lambda:(self.open_tasks(),self.close())).pack(side='right',padx=4)
   self.window.protocol('WM_DELETE_WINDOW',self.close)
   self.window.update_idletasks()
   try:self.previous_grab=self.root.grab_current()
   except (tk.TclError,KeyError):self.previous_grab=None
   try:self.window.grab_set()
   except tk.TclError:pass
  self.text.configure(state='normal');self.text.delete('1.0','end');self.text.insert('1.0',render(self.shown.values()));self.text.configure(state='disabled');self.window.lift();self.window.focus_force();self.window.bell()
 def reopen(self):
  if self.window is not None and self.window.winfo_exists():self.window.lift();self.window.focus_force();return
  if not self.latest:
   from tkinter import messagebox
   messagebox.showinfo('异常处理办法','当前没有检测到需要处理的任务异常。',parent=self.root);return
  self.state.acked-=self.state.active;self.update(self.latest)
 def close(self):
  self.state.acknowledge(self.shown);self.shown={}
  if self.window is not None:
   try:self.window.grab_release();self.window.destroy()
   except Exception:pass
  self.window=None
  try:
   if self.previous_grab and self.previous_grab.winfo_exists():self.previous_grab.grab_set()
  except Exception:pass

class ProgressWatch:
 def __init__(self):self.progress={};self.offline_since=None
 def update(self,tasks,client,paused,now=None):
  now=time.time() if now is None else now;found=[]
  if paused:self.progress={};self.offline_since=None;return found
  active=[t for t in tasks if t.get('state') in ('claimed','sending','waiting') or t.get('copy_state')=='running']
  queued=any(t.get('state')=='queued' and t.get('auto_batch') for t in tasks)
  ids=set()
  for t in active:
   key=t['id'];ids.add(key);signature=(t.get('state'),t.get('copy_state'),t.get('copy_phase'),len(t.get('received_images') or []));previous=self.progress.get(key)
   if previous is None or previous[0]!=signature:self.progress[key]=(signature,now)
   elif now-previous[1]>=1200:found.append(issue(t['sku'],'进度停滞',('文案' if t.get('copy_state')=='running' else '图片')+'任务连续20分钟没有新的阶段或图片进展，请检查原作图页；不要重复发送已受理请求',t['id']))
  self.progress={k:v for k,v in self.progress.items() if k in ids}
  if active or queued:
   last=client.get('last_seen')
   if self.offline_since is None:self.offline_since=now
   if now-(last if last else self.offline_since)>=90:found.append(issue('浏览器插件','插件连接','插件超过90秒未联系本地工具，请检查作图页、插件是否启用、配对和浏览器是否运行'))
  else:self.offline_since=None
  return found

def save_plugin_status(store,body):
 previous=getattr(store,'plugin_status',{})
 value={'message':safe_text(body.get('message','')),'error':body.get('error') is True,'sku':str(body.get('sku') or '')[:100],'task_id':str(body.get('task_id') or '')[:150],'updated_at':time.time()}
 if value['error']:
  import secrets
  value['incident']=previous.get('incident') if previous.get('error') and previous.get('message')==value['message'] else secrets.token_hex(8)
 store.plugin_status=value;write(store.folder/'plugin_status.json',value);return {'ok':True}
