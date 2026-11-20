"""Loopback-only authenticated bridge. Does not read Edge cookies or send Ozon writes."""
from window_registry import lookup,remember
import copy,base64,hashlib,hmac,io,json,re,secrets,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from PIL import Image
from variants import valid_article
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data';DATA.mkdir(exist_ok=True)
TASKS=[('01_main','双件或多件主图，严格按销售规格显示数量'),('02_dimensions','商品尺寸图，勿将包装尺寸当成商品尺寸'),('03_scene','适用场景一'),('04_scene','适用场景二'),('05_material','材质细节'),('06_structure','结构细节'),('07_details','配件与细节'),('08_contents','套装实际内容')]
def task_view(task):
 count=len(task.get('received_images',[]))
 progress=f'已保存 {count}/8 图' if task.get('set_mode') else task['name']
 labels={'queued':'排队中','saved':'图片已保存','cancelled':'已取消','needs_attention':'需处理','waiting':'处理中','claimed':'已领取','sending':'发送中','review':'待审核','approved':'已审核'}
 state=('全部素材就绪' if task['state']=='saved' and count==8 and task.get('video') else '图像/视频处理中（文案已保留）') if task.get('copy_state')=='done' else ('文案待处理' if task.get('copy_state')=='needs_attention' else ('文案生成中' if task.get('copy_state')=='running' else labels.get(task['state'],task['state'])))
 message=task.get('message','').strip()
 if message:state+='：'+message
 return (task['sku'],progress,state)

class ImageOrderConflict(ValueError):
 code='IMAGE_ORDER_CONFLICT'

class Store:
 def __init__(self,folder):
  from automation_wake import AutomationWake
  self.automation_wake=AutomationWake()
  self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True);self.lock=threading.Lock();self.client={};self.download_tickets={};self.path=self.folder/'tasks.json';self.video_running=set();self.video_slots=threading.BoundedSemaphore(1);self.tasks=json.loads(self.path.read_text(encoding='utf-8-sig')) if self.path.exists() else []
  for t in self.tasks:
   if t['state'] in ('claimed','sending','waiting'):t['state']='needs_attention';t['resume_mode']='inspect_only';t['message']='服务已重启，等待自动读取现有网页结果；不重新发送'
   if t.get('copy_state')=='running':t['copy_state']='needs_attention';t['resume_mode']='copy_inspect_only';t['message']='文案被重启中断，等待自动读取现有结果，不重新生成'
   if t.get('state')=='needs_attention' and t.get('message')=='已备份旧素材；等待从网页重新采集生成图，不重新发送作图':
    t.update(resume_mode='inspect_only',recollection_requested=True,message='旧版备份任务已恢复到自动采集队列；不重新作图')
    folder=self.folder/'products'/t['sku'];target=folder/'listing_bundle.json'
    backups=sorted((folder/'recovery_backups').glob('*/listing_bundle.json'),reverse=True)
    if not target.exists() and backups:
     bundle=json.loads(backups[0].read_text(encoding='utf-8-sig'));bundle.update(images=[],recollection_pending=True,video={'local_file':'video/product_8s.mp4','exists':False,'https_url':None});target.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
  try:self.plugin_status=json.loads((self.folder/'plugin_status.json').read_text(encoding='utf-8'))
  except (OSError,ValueError):self.plugin_status={}
  if not isinstance(self.plugin_status,dict):self.plugin_status={}
  self.repair_recollection_queue()
  self.control_path=self.folder/'automation_control.json';self.control=json.loads(self.control_path.read_text()) if self.control_path.exists() else {'paused':False,'serial':0}
  self.rebase_paths()
  self.save()
  self.sync_shared_copies()
  self.normalize_saved_images()
  self.resume_local_media()
  from image_regeneration import ImageJobs
  self.image_jobs=ImageJobs(self)
  from asset_reconcile import reconcile
  with self.lock:
   reconcile(self)
   from queue_completion import retire_legacy_attribute_save_error
   retire_legacy_attribute_save_error(self)
 def repair_recollection_queue(self):
  # Older backups may have removed the leader's files before setting its recovery flag.
  groups={t.get('copy_leader',t['sku']) for t in self.tasks if t.get('recollection_requested')}
  for task in self.tasks:
   if task.get('copy_leader',task['sku']) not in groups or task['state'] in ('saved','cancelled','queued'):continue
   folder=self.folder/'products'/task['sku'];backups=sorted((folder/'recovery_backups').glob('*/listing_bundle.json'),reverse=True)
   task.update(recollection_requested=True,resume_mode='inspect_only')
   target=folder/'listing_bundle.json'
   if not target.exists() and backups:
    bundle=json.loads(backups[0].read_text(encoding='utf-8-sig'));bundle.update(images=[],recollection_pending=True,video={'local_file':'video/product_8s.mp4','exists':False,'https_url':None});target.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
 def next_recollection(self):
  tasks=[t for t in self.tasks if t.get('recollection_requested') and t['state'] not in ('saved','cancelled')]
  return min(tasks,key=lambda t:(bool(t.get('gallery_source')),t.get('variant_index') or 0)) if tasks else None
 def save(self):
  if hasattr(self,'image_jobs'):self.image_jobs.save()
  temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(self.tasks,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(self.path)
  from automation_wake import notify
  notify(self)
 def create(self,sku,facts,references=None):
  if not valid_article(sku):raise ValueError('货号格式无效')
  if not facts.strip() or len(facts)>20000:raise ValueError('商品资料为空或过长')
  if any(t['sku']==sku for t in self.tasks):raise ValueError('SKU已经存在，避免重复建立任务')
  if (self.folder/'products'/sku/'listing_bundle.json').exists():raise ValueError('该货号有保留草稿，请在设置恢复已删除记录，或使用新货号；不覆盖旧素材')
  refs=[]
  if references:
   if len(references)>8:raise ValueError('最多选择8张原图')
   prepared=[]
   for ref in references:
    raw=Path(ref).read_bytes()
    if len(raw)>3*1024*1024:raise ValueError('单张原图限3MB，请压缩后选择')
    with Image.open(io.BytesIO(raw)) as im:
     im.verify();fmt=im.format
    mime={'PNG':'image/png','JPEG':'image/jpeg','WEBP':'image/webp'}.get(fmt)
    if not mime:raise ValueError('只支持PNG、JPG、WEBP原图')
    prepared.append((raw,mime))
   folder=self.folder/'products'/sku/'references';folder.mkdir(parents=True,exist_ok=True)
   for i,(raw,mime) in enumerate(prepared):
    ext={'image/png':'png','image/jpeg':'jpg','image/webp':'webp'}[mime]
    path=folder/f'{i+1:02d}.{ext}';path.write_bytes(raw)
    refs.append({'path':str(path),'name':path.name,'mime':mime})
  for name,brief in TASKS:
   self.tasks.append({'id':secrets.token_hex(16),'sku':sku,'facts':facts,'name':name,'state':'queued','references':refs,'prompt':'根据本对话已上传原图制作一张独立Ozon商品图，3:4竖版，自然俄文。保持外观一致，禁止虚构属性、数量或尺寸。包装尺寸不得作为商品尺寸。任务：'+brief+'。商品事实：'+facts})
  self.save()
 def create_set(self,sku,facts,references=None):
  self.create(sku,facts,references)
  group=[t for t in self.tasks if t['sku']==sku]
  for t in group:t.update(state='cancelled',message='由一次提交整套任务替代')
  task=dict(group[0]);task.update(id=secrets.token_hex(16),name='00_full_set',state='queued',message='等待扩展领取任务',auto_batch=True,set_mode=True,received_images=[])
  from image_prompts import generation_prompt
  task['prompt']=generation_prompt(facts)
  self.tasks=[t for t in self.tasks if t['sku']!=sku]+[task];self.save()
 def rebase_paths(self):
  for task in self.tasks:
   folder=self.folder/'products'/task['sku'];leader=self.folder/'products'/task.get('copy_leader',task['sku'])
   for row in task.get('received_images') or []:
    path=folder/'images'/Path(str(row.get('file','')).replace('\\','/')).name
    if path.exists():row['file']=str(path)
   for key in ('references','main_references','detail_references'):
    for ref in task.get(key) or []:
     name=Path(str(ref.get('path','')).replace('\\','/')).name
     candidates=[self.folder/'products'/str(ref.get('sku') or task['sku'])/'references'/name,leader/'shared_references'/name,leader/'group_reference_sheets'/name]
     if key=='detail_references' or ref.get('purpose') in ('shared_detail','shared_gallery','shared_information'):candidates.reverse()
     for candidate in candidates:
      if candidate.exists():ref['path']=str(candidate);break
   if task.get('video') and (folder/'video'/'product_8s.mp4').exists():task['video']=str(folder/'video'/'product_8s.mp4')
 def restore_deleted(self,source):
  from asset_audit import inspect
  source=Path(source).resolve()
  if source.parent!=(self.folder/'deleted_tasks').resolve():raise ValueError('只允许恢复本工具的删除备份')
  values=json.loads(source.read_text(encoding='utf-8'));restored=[]
  if not isinstance(values,list):raise ValueError('备份格式无效')
  for old in values:
   if not isinstance(old,dict) or not valid_article(old.get('sku','')):raise ValueError('备份货号无效')
   if any(t['sku']==old['sku'] for t in self.tasks):continue
   task=copy.deepcopy(old);folder=self.folder/'products'/task['sku']
   if inspect(folder)['verified']:
    task['state']='saved'
    if (folder/'video'/'product_8s.mp4').exists():task['video']=str(folder/'video'/'product_8s.mp4')
   else:task.update(state='needs_attention',resume_mode='inspect_only',message='本地记录已恢复，等待读取已有结果；不重新发送')
   task.pop('pause_requested',None);task.pop('pause_ack',None)
   if task.get('copy_state')=='running':task['copy_state']='needs_attention';task['resume_mode']='copy_inspect_only'
   restored.append(task)
  self.tasks.extend(restored);self.rebase_paths();self.save();return len(restored)
 def set_paused(self,paused):
  self.control={'paused':bool(paused),'serial':self.control.get('serial',0)+1,'command_token':secrets.token_hex(16),'issued_at':time.time()}
  self.control_path.write_text(json.dumps(self.control),encoding='utf-8')
  for task in self.tasks+(self.image_jobs.jobs if hasattr(self,'image_jobs') else []):
   if paused and task.get('copy_state')=='running':task.update(copy_state='needs_attention',pause_requested=True,pause_ack=False,resume_mode='copy_inspect_only',message='文案制作已暂停，继续时只读取已有结果')
   if paused and task['state'] in ('claimed','sending','waiting'):
    task.update(state='needs_attention',pause_requested=True,pause_ack=False,message='已请求暂停，等待插件停止；恢复时只读取已有结果')
   elif not paused and task.get('pause_requested'):
    task.update(resume_mode='copy_inspect_only' if task.get('copy_state')=='needs_attention' else 'inspect_only',pause_requested=False,message='等待恢复已有结果采集，不重新发送')
  self.save();return dict(self.control)
 def resume_local_media(self):
  from asset_audit import inspect
  for task in self.tasks:
   folder=self.folder/'products'/task['sku']
   if task.get('state')=='saved' and task.get('set_mode') and (not task.get('video') or not (folder/'video'/'product_8s.mp4').exists()) and inspect(folder)['verified']:
    threading.Thread(target=self.render_video,args=(task['sku'],),daemon=True).start()
 def normalize_saved_images(self):
  from image_format import normalize
  from listing_bundle import refresh_assets
  changed=[]
  for task in self.tasks:
   if task.get('state')!='saved' or not task.get('set_mode'):continue
   folder=self.folder/'products'/task['sku'];manifest=folder/'image_manifest.json'
   if not manifest.exists():continue
   rows=json.loads(manifest.read_text(encoding='utf-8-sig'));converted=False
   for row in rows:
    source=folder/'images'/Path(row['file'].replace('\\','/')).name
    if source.suffix.lower()!='.webp' or not source.exists():continue
    raw,ext=normalize(source.read_bytes(),folder/'original_images');target=source.with_suffix('.'+ext);target.write_bytes(raw)
    row.update(file=str(target),sha256=hashlib.sha256(raw).hexdigest());converted=True
   if converted:
    manifest.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');task['received_images']=rows;task.pop('video',None);refresh_assets(folder);changed.append(task['sku'])
  if changed:self.save()
  for sku in changed:threading.Thread(target=self.render_video,args=(sku,),daemon=True).start()
 def rebuild_group(self,sku):
  import shutil
  from pricing_service import read,write
  selected=next((t for t in self.tasks if t['sku']==sku and t.get('set_mode')),None)
  if not selected:raise ValueError('未找到商品组')
  leader=selected.get('copy_leader',sku);group=[t for t in self.tasks if t.get('copy_leader',t['sku'])==leader and t.get('state')!='cancelled']
  if any(t['state'] in ('claimed','sending','waiting') or t.get('copy_state')=='running' or t['sku'] in self.video_running for t in group):raise ValueError('请先暂停当前制作并等待视频处理完成，再手动更新素材')
  if self.image_jobs.active([t['sku'] for t in group]):raise ValueError('本组正在重做图片，请先在图片视频页等待完成或停止本组重做')
  stamp=time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(4);plans=[]
  # Back up the whole group before changing live tasks.
  for t in group:
   folder=self.folder/'products'/t['sku'];bundle=read(folder/'listing_bundle.json');backup=folder/'regeneration_backups'/stamp;backup.mkdir(parents=True)
   for name in ('images','video','image_manifest.json','listing_bundle.json'):
    path=folder/name
    if path.is_dir():shutil.copytree(path,backup/name)
    elif path.exists():shutil.copy2(path,backup/name)
   write(backup/'task.json',t);plans.append((t,folder,bundle))
  for t,folder,b in plans:
   for name in ('images','video'):
    if (folder/name).exists():shutil.rmtree(folder/name)
   (folder/'image_manifest.json').unlink(missing_ok=True)
   p=b.get('variant_parameters') or {};t.update(id=secrets.token_hex(16),facts=b.get('facts',t['facts']),variant_parameters=p,generation_parameters=dict(p),state='queued',received_images=[],message='用户手动启动素材更新；旧素材已备份')
   t.pop('video',None)
   if (b.get('asset_review') or {}).get('copy'):
    b['copy']={'title_ru':None,'description_ru':None,'tags_ru':[]};t.pop('copy_state',None)
   b.update(images=[],regeneration_pending=True,video={'local_file':'video/product_8s.mp4','exists':False,'https_url':None});b['hosting']={'state':'waiting','verified_images':0};b['video_hosting']={'state':'waiting'};write(folder/'listing_bundle.json',b)
   if t['sku']==leader:
    t['expected_images']=8
   else:t['expected_images']=1
   from image_prompts import generation_prompt
   t['prompt']=generation_prompt(t['facts'],t.get('group_facts',''),t['expected_images'])
  self.save();return stamp
 def resume_unsent_upload(self):
  if self.control.get('paused'):return {'resumed':0}
  known={'未找到图片上传控件，已暂停，未发送任务','未识别到唯一可用发送按钮；提示词已保留，请人工检查。未自动发送','输入框内容或页面状态已变化，未发送任务','任务已暂停或草稿改变，未发送','未找到当前任务输入框，未发送','上传后输入框变化，请刷新对话；未发送'}
  count=0
  for task in self.tasks+(self.image_jobs.jobs if hasattr(self,'image_jobs') else []):
   if task['state']=='needs_attention' and not task.get('received_images') and not task.get('pause_requested') and task.get('message') in known and task.get('automatic_unsent_retries',0)<2:
    task['automatic_unsent_retries']=task.get('automatic_unsent_retries',0)+1
    task.update(state='queued',message='已知尚未发送的任务已恢复，自动备份清理遗留输入后继续');count+=1
  if count:self.save()
  return {'resumed':count}
 def blockers(self):
  if hasattr(self,'image_jobs'):self.image_jobs.tick()
  from queue_completion import completed_skus,optional_failure_skus
  completed=(completed_skus(self)|optional_failure_skus(self)) if hasattr(self,'image_jobs') else set()
  tasks=[t for t in self.tasks if t['sku'] not in completed]+([j for j in self.image_jobs.jobs if j['state'] not in ('saved','cancelled','queued')] if hasattr(self,'image_jobs') else [])
  return [{'id':t['id'],'sku':t['sku'],'state':t['state'],'copy_state':t.get('copy_state'),'copy_mode':t.get('copy_mode'),'copy_phase':t.get('copy_phase'),'message':t.get('message',''),'resume_mode':t.get('resume_mode'),'recollection_requested':bool(t.get('recollection_requested')),'expected_images':t.get('expected_images',8)} for t in tasks if t['state'] in ('claimed','sending','waiting','needs_attention','review','processing','committing') or t.get('copy_state') in ('running','needs_attention')]
 def queue_reason(self):
  if self.control.get('paused'):return '制作已暂停；点击继续制作或在插件继续'
  restart=self.control.get('queue_restart') or {};ack=self.control.get('queue_restart_ack') or {}
  if restart and ack.get('token')!=restart.get('token'):return '等待插件接收重启请求：'+restart.get('sku','')+'；请保持插件与原作图页打开'
  blockers=self.blockers()
  if blockers:
   t=blockers[0]
   detail=('属性读取' if t.get('copy_mode')=='attributes' else '文案任务')+'（'+str(t.get('copy_state'))+' / '+str(t.get('copy_phase') or '未记录阶段')+'）；' if t.get('copy_state') in ('running','needs_attention') else ''
   return '前序任务 '+t['sku']+' 尚未完成：'+detail+t.get('message','')
  if time.time()-self.client.get('last_seen',0)>75:return '等待扩展连接：请保存配对码，并绑定当前ChatGPT标签'
  if not self.client.get('auto_enabled'):return '扩展已连接，但自动批次未启用'
  if self.client.get('bound') is False:return '扩展已连接，请先绑定ChatGPT商品作图页'
  if time.time()-self.client.get('wake_seen',0)<45:return '本地事件通道已连接，任务变化后自动领取'
  return '扩展已连接，等待下一次轮询领取（最长约30秒；事件通道正在恢复）'
 def task_status(self,tid):
  if hasattr(self,'image_jobs') and self.image_jobs.get(tid):
   self.image_jobs.tick();job=self.image_jobs.get(tid);return {'found':True,**job,'saved_count':len(job['received_images'])}
  task=next((t for t in self.tasks if t['id']==tid),None)
  if not task:return {'found':False}
  return {'found':True,'id':task['id'],'sku':task['sku'],'state':task['state'],'copy_state':task.get('copy_state'),'saved_count':len(task.get('received_images',[])),'expected_images':task.get('expected_images',8),'message':task.get('message',''),'resume_mode':task.get('resume_mode'),'pause_requested':task.get('pause_requested',False),'recollection_requested':bool(task.get('recollection_requested'))}
 def recover(self,sku,automatic=False):
  group=[t for t in self.tasks if t['sku']==sku and t.get('set_mode') and t['state'] in ('waiting','needs_attention','claimed','sending','saved')]
  if len(group)!=1:raise ValueError('没有唯一可恢复的整套任务，请核对货号')
  if any(str(r.get('generation_task_id','')).startswith('image-') for r in group[0].get('received_images') or []):
   leader=group[0].get('copy_leader',sku);products=[t for t in self.tasks if t.get('copy_leader',t['sku'])==leader and t['state']!='cancelled'];jobs=self.image_jobs.active([t['sku'] for t in products])
   if any(j['state']=='queued' for j in jobs):raise ValueError('本组有尚未发送的图片重做任务，请先完成或停止重做')
   if not jobs:self.image_jobs.recollect(products);jobs=self.image_jobs.active([t['sku'] for t in products])
   return self.image_jobs.recover(jobs[0]['id'])
  from recovery_targets import markers
  from image_retry import configure
  configure(group[0])
  task=group[0];validate_complete=len(task.get('received_images',[]))==8;task.pop('resume_mode',None);task.update(state='waiting',message='用户请求核对最终编号文件，不重新生成');self.save();return {'id':task['id'],'sku':task['sku'],'set_mode':True,'saved_count':len(task.get('received_images',[])),'expected_images':task.get('expected_images',8),**__import__('image_retry').plan(task),'delivery_policy':'independent_images','orderRepairPending':validate_complete,'automaticRecovery':bool(automatic or task.get('recollection_requested')),'recovery_markers':markers(self.folder/'products'/sku,task)}
 def set_result(self,tid,index,encoded):
  if hasattr(self,'image_jobs') and self.image_jobs.get(tid):return self.image_jobs.accept(tid,index,encoded)
  task=self.find(tid)
  if not task.get('set_mode') or task['state'] not in ('claimed','sending','waiting','saved'):raise ValueError('整套任务状态无效')
  received=task.setdefault('received_images',[])
  if type(index) is not int or not 0<=index<task.get('expected_images',8):raise ValueError('图片序号无效')
  if index>len(received):raise ValueError('图片顺序错误')
  data=base64.b64decode(encoded,validate=True)
  if len(data)>20*1024*1024:raise ValueError('图片过大')
  with Image.open(io.BytesIO(data)) as im:im.verify();fmt=im.format
  with Image.open(io.BytesIO(data)) as im:
   if min(im.size)<512:raise ValueError('图片分辨率不足')
  ext={'PNG':'png','JPEG':'jpg','WEBP':'webp'}.get(fmt)
  if not ext:raise ValueError('图片格式无效')
  from asset_guard import reject_reference
  reject_reference(data,task.get('references',[]))
  from image_format import normalize
  data,ext=normalize(data,self.folder/'products'/task['sku']/'original_images');digest=hashlib.sha256(data).hexdigest()
  if index<len(received):
   if received[index]['sha256']!=digest:raise ImageOrderConflict('恢复图片与已保存顺序不一致，已有文件保留')
   if task.get('gallery_source') and len(received)<8:
    from product_group import reuse_gallery
    folder=self.folder/'products'/task['sku'];trial={**task,'received_images':received[:1]}
    reuse_gallery(folder,trial);task['received_images']=trial['received_images'];return self.finish_set(task)
   if len(received)==8 and task['state']!='saved':return self.finish_set(task)
   return {'saved_count':len(received),'complete':task['state']=='saved'}
  if index!=len(received) or task['state']=='saved':raise ValueError('图片顺序错误')
  if any(x['sha256']==digest for x in received):raise ValueError('不同图片位置内容重复，已保留文件，请检查图片列表')
  folder=self.folder/'products'/task['sku']/'images';folder.mkdir(parents=True,exist_ok=True)
  path=folder/f'{TASKS[index][0]}.{ext}';path.write_bytes(data)
  received.append({'file':str(path),'sha256':digest,'role':'primary' if index==0 else 'gallery','order':index+1,'source':'assistant_generated'})
  if task.get('image_retry_attempts'):
   attempt=task['image_retry_attempts'][-1];received[-1].update(generation_task_id=attempt['request_id'],source_index=index-attempt['offset'],source_expected=attempt['count'])
  if task.get('gallery_source') and len(received)==1:
   from product_group import reuse_gallery
   reuse_gallery(folder.parent,task)
  return self.finish_set(task)
 def finish_set(self,task):
  received=task['received_images'];folder=self.folder/'products'/task['sku'];complete=len(received)==8
  if complete:
   target=folder/'image_manifest.json';temp=target.with_suffix('.tmp');temp.write_text(json.dumps(received,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(target)
   from listing_bundle import refresh_assets
   refresh_assets(folder)
   target=folder/'listing_bundle.json'
   if target.exists() and task.get('generation_parameters') is not None:
    from pricing_service import read,write
    bundle=read(target);bundle['asset_basis']=dict(task['generation_parameters']);bundle.pop('regeneration_pending',None)
    review=bundle.get('asset_review') or {}
    from asset_state import differs,VISUAL
    own=differs(bundle['asset_basis'],bundle.get('variant_parameters') or {},VISUAL)
    gallery_basis=task.get('generation_variants') or []
    if task.get('gallery_source'):
     source=folder.parent/task['gallery_source']/'listing_bundle.json'
     if source.exists():gallery_basis=read(source).get('gallery_basis') or gallery_basis
    bundle['gallery_basis']=gallery_basis
    original={r.get('sku'):r.get('variant_parameters') or {} for r in gallery_basis};now={r.get('sku'):r.get('variant_parameters') or {} for r in task.get('group_variants') or []}
    gallery=bool(original and (set(original)!=set(now) or any(differs(original[k],now.get(k) or {},VISUAL) for k in original)))
    review.update(main=own,gallery=gallery);bundle['asset_review']=review;write(target,bundle)
  task.update(state='saved' if complete else 'waiting',message=f'已保存 {len(received)}/8 张独立图片');self.save()
  if complete:
   task.pop('resume_mode',None);task.pop('recollection_requested',None);self.save()
   self.sync_shared_galleries(task)
   threading.Thread(target=self.render_video,args=(task['sku'],),daemon=True).start()
  return {'saved_count':len(received),'complete':complete}
 def sync_shared_galleries(self,source):
  import shutil
  from product_group import reuse_gallery
  from listing_bundle import refresh_assets
  if source.get('gallery_source'):return
  expected=[r['sha256'] for r in source['received_images'][1:]]
  for task in self.tasks:
   rows=task.get('received_images') or []
   if task.get('gallery_source')!=source['sku'] or task.get('state')!='saved' or len(rows)!=8:continue
   if [r['sha256'] for r in rows[1:]]==expected:continue
   folder=self.folder/'products'/task['sku'];backup=folder/'shared_gallery_backups'/(str(time.time_ns()))
   backup.mkdir(parents=True)
   for name in ('images','video','image_manifest.json','listing_bundle.json'):
    old=folder/name
    if old.is_dir():shutil.copytree(old,backup/name)
    elif old.exists():shutil.copy2(old,backup/name)
   trial={**task,'received_images':rows[:1]};reuse_gallery(folder,trial)
   live_names={Path(r['file'].replace('\\','/')).name for r in trial['received_images']}
   for old in rows[1:]:
    name=Path(old['file'].replace('\\','/')).name
    if name not in live_names:(folder/'images'/name).unlink(missing_ok=True)
   if (folder/'video').exists():shutil.rmtree(folder/'video')
   task['received_images']=trial['received_images'];task.pop('video',None)
   manifest=folder/'image_manifest.json';temp=manifest.with_suffix('.tmp');temp.write_text(json.dumps(task['received_images'],ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(manifest)
   refresh_assets(folder);task['message']='已按首变体最终编号文件更新共用7张详情，旧素材已备份；重新合成视频'
   threading.Thread(target=self.render_video,args=(task['sku'],),daemon=True).start()
  self.save()
 def repair_order(self,tid):
  if hasattr(self,'image_jobs') and self.image_jobs.get(tid):return self.image_jobs.reset(tid)
  import shutil
  task=self.find(tid)
  if not task.get('set_mode') or task['state'] not in ('waiting','claimed','sending','needs_attention'):raise ValueError('当前任务不允许自动重新采集')
  affected={t['sku'] for t in self.tasks if t['sku']==task['sku'] or t.get('gallery_source')==task['sku']}
  if affected & self.video_running:return {'pending':True,'reason':'等待旧视频处理结束，再备份并替换最终图片'}
  folder=self.folder/'products'/task['sku'];stamp=time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(4);backup=folder/'auto_recovery'/stamp;backup.mkdir(parents=True)
  (backup/'task.json').write_text(json.dumps(task,ensure_ascii=False,indent=2),encoding='utf-8')
  for name in ('images','video','image_manifest.json','listing_bundle.json'):
   src=folder/name
   if not src.exists():continue
   if src.is_dir():shutil.copytree(src,backup/name)
   else:shutil.copy2(src,backup/name)
  for name in ('images','video','image_manifest.json'):
   src=folder/name
   if src.is_dir():shutil.rmtree(src)
   elif src.exists():src.unlink()
  target=folder/'listing_bundle.json'
  if target.exists():
   bundle=json.loads(target.read_text(encoding='utf-8-sig'));bundle.update(images=[],recollection_pending=True);bundle['video']={'local_file':'video/product_8s.mp4','exists':False,'https_url':None};bundle['blockers']=list(dict.fromkeys(bundle.get('blockers',[])+['图片重新采集中']));temp=target.with_suffix('.tmp');temp.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(target)
  task.update(state='waiting',received_images=[],message='图片顺序冲突已自动备份，正在按最终图库重新采集',auto_recovery_backup=str(backup));task.pop('video',None)
  self.save();return {'ok':True,'backup_created':True}
 def recollect(self,tid):
  import shutil
  self.repair_recollection_queue()
  selected=self.find(tid);leader=selected.get('copy_leader',selected['sku'])
  group=[t for t in self.tasks if t.get('copy_leader',t['sku'])==leader and t['state']!='cancelled']
  active_jobs=self.image_jobs.active([t['sku'] for t in group])
  if active_jobs:
   if any(j['state']=='queued' for j in active_jobs):raise ValueError('本组还有未发送的图片重做任务，请先完成或在图片视频页停止重做，再采集已有图片')
   if any(j.get('pause_requested') and not j.get('pause_ack') for j in active_jobs):raise ValueError('等待图片任务停止回执后自动恢复采集')
   for j in active_jobs:j.update(state='needs_attention',resume_mode='inspect_only',pause_requested=False)
   self.set_paused(False);return 'existing-image-jobs'
  if any(any(r.get('generation_task_id') for r in t.get('received_images') or []) for t in group):return self.image_jobs.recollect(group)
  if any(t['state'] in ('claimed','sending','waiting') or t.get('copy_state')=='running' for t in group):raise ValueError('请先停止扩展自动批次，再备份并重新采集')
  if any(t.get('pause_requested') and not t.get('pause_ack') for t in group):raise ValueError('插件尚未确认停止，等待暂停回执后自动采集')
  if any(t['sku'] in self.video_running for t in group):raise ValueError('旧视频仍在处理中，请等待完成再采集')
  stamp=time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)
  names=('images','video','image_manifest.json','listing_bundle.json','copy_prompt.txt')
  planned=[];affected=[]
  for task in group:
   folder=self.folder/'products'/task['sku']
   if task['state']=='queued' and not task.get('received_images') and not any((folder/name).exists() for name in names):continue
   affected.append(task);backup=folder/'recovery_backups'/stamp
   backup.mkdir(parents=True,exist_ok=False)
   (backup/'task.json').write_text(json.dumps(task,ensure_ascii=False,indent=2),encoding='utf-8')
   for name in names:
    src=folder/name
    if not src.exists():continue
    dst=backup/name
    if src.is_dir():shutil.copytree(src,dst)
    else:shutil.copy2(src,dst)
    if name in ('images','video','image_manifest.json'):planned.append(src)
  # Only remove live outputs once every backup completed successfully.
  for src in planned:
   if src.is_dir():shutil.rmtree(src)
   else:src.unlink()
  for task in affected:
   target=self.folder/'products'/task['sku']/'listing_bundle.json'
   if target.exists():
    bundle=json.loads(target.read_text(encoding='utf-8-sig'));bundle.update(images=[],recollection_pending=True,video={'local_file':'video/product_8s.mp4','exists':False,'https_url':None},hosting={'state':'waiting','verified_images':0},video_hosting={'state':'waiting'});bundle['blockers']=list(dict.fromkeys(bundle.get('blockers',[])+['图片重新采集中']));target.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
   task.update(state='needs_attention',resume_mode='inspect_only',recollection_requested=True,recollection_backup=stamp,received_images=[],message='已备份旧素材，已加入整组自动采集队列；不重新发送作图')
   task.pop('copy_state',None);task.pop('video',None);task.pop('pause_requested',None);task.pop('pause_ack',None)
  self.set_paused(False);self.save();return stamp
 def claim(self):
  if self.control.get('paused'):raise ValueError('制作已暂停')
  if self.blockers():raise ValueError('请先审核上一任务或处理异常，不能继续发送')
  if self.shared_copy_pending():raise ValueError('等待首变体竞品参数及共用文案完成，再制作后续变体')
  if hasattr(self,'image_jobs') and self.image_jobs.next():return self.image_jobs.claim()
  t=next((t for t in self.tasks if t['state']=='queued'),None)
  if not t:raise ValueError('没有排队任务，请在本地窗口创建商品')
  t['generation_parameters']=copy.deepcopy(t.get('variant_parameters') or {});t['generation_variants']=copy.deepcopy(t.get('group_variants') or []);t['state']='claimed'
  if t.get('set_mode'):
   from image_prompts import generation_prompt,reference_contract
   from group_references import compile_references
   t['delivery_policy']='generated_originals';t['expected_images']=t.get('expected_images',8)
   try:t['references']=compile_references(self,t,'full' if t.get('expected_images',8)==8 else 'main')
   except (ValueError,OSError) as exc:
    t.update(state='needs_attention',message='原始资料校验未通过，未发送：'+str(exc));self.save();raise ValueError(t['message']) from None
   from image_retry import configure
   configure(t)
   from visual_plans import context as visual_context
   t['visual_plan']=visual_context(self,t)
   t['prompt']=generation_prompt(expected=t.get('expected_images',8),visual_plan=t['visual_plan'])+'\n'+reference_contract(t)
  t['prompt']=t['prompt'].replace('。如以文件或ZIP交付，8张文件须按01_至08_编号，01_为主图，ZIP不得包含原始参考图。','。仅交付8张独立图片，按01_至08_编号。');t['prompt']+=('\n只交付一张原始拼图，不提供ZIP。' if t.get('sheet_layout') else '\n交付要求：仅输出独立图片及逐张下载入口，不要打包，不提供ZIP或其他压缩包。');self.save();result=dict(t);result['references']=[{'name':r['name'],'mime':r['mime'],'purpose':r.get('purpose','variant_main'),'base64':base64.b64encode(Path(r['path']).read_bytes()).decode()} for r in t.get('references',[])];return result
 def find(self,tid):
  t=next((t for t in self.tasks if t['id']==tid),None)
  if not t and hasattr(self,'image_jobs'):t=self.image_jobs.get(tid)
  if not t:raise ValueError('任务不存在')
  return t
 def retry(self,tid):
  t=self.find(tid)
  if t['state']!='needs_attention':raise ValueError('仅可恢复异常任务')
  if any(x['state'] in ('claimed','sending','waiting') for x in self.tasks):raise ValueError('还有执行中的任务，请先暂停')
  t.update(state='queued',message='用户确认网页未发送后重新排队');self.save()
 def cancel_product(self,sku):
  if self.image_jobs.active([sku]):raise ValueError('该商品正在重做图片，请先在图片视频页停止本组重做')
  group=[t for t in self.tasks if t['sku']==sku]
  if not group:raise ValueError('商品不存在')
  if any(t['state'] in ('claimed','sending','waiting') for t in group):raise ValueError('请先在扩展停止自动批次，等待任务暂停后再取消')
  for t in group:
   if t['state'] in ('queued','needs_attention','review'):t.update(state='cancelled',message='用户取消剩余任务；已有文件保留')
  self.save()
 def result(self,tid,encoded):
  t=self.find(tid)
  if t['state'] not in ('claimed','sending','waiting'):raise ValueError('任务不接受图片')
  data=base64.b64decode(encoded,validate=True)
  if len(data)>20*1024*1024:raise ValueError('图片过大')
  with Image.open(io.BytesIO(data)) as im:
   im.verify();fmt=im.format
  with Image.open(io.BytesIO(data)) as im:
   if min(im.size)<512:raise ValueError('图片分辨率不足')
  ext={'PNG':'png','JPEG':'jpg','WEBP':'webp'}.get(fmt)
  if not ext:raise ValueError('不支持的图片格式')
  folder=self.folder/'products'/t['sku']/'images';folder.mkdir(parents=True,exist_ok=True)
  path=folder/(t['name']+'_'+t['id']+'.'+ext);path.write_bytes(data)
  t.update(state='saved' if t.get('auto_batch') else 'review',file=str(path),sha256=hashlib.sha256(data).hexdigest());self.save()
  if t.get('auto_batch'):
   group=[x for x in self.tasks if x['sku']==t['sku']]
   if len(group)==8 and all(x['state']=='saved' for x in group):
    threading.Thread(target=self.render_video,args=(t['sku'],),daemon=True).start()
  return {'saved':str(path),'state':t['state']}
 def delete_task(self,tid):return self.delete_tasks([tid])
 def delete_tasks(self,ids):
  selected=[self.find(tid) for tid in ids];skus={t['sku'] for t in selected}
  if self.image_jobs.active(skus):raise ValueError('本组有图片重做任务，请先在图片视频页停止本组重做')
  for task in selected:
   if task.get('pause_requested') and not task.get('pause_ack'):raise ValueError('插件尚未确认停止，请等候暂停回执后删除')
   if task['state'] in ('claimed','sending','waiting') or task.get('copy_state')=='running' or task['sku'] in self.video_running:raise ValueError('任务正在执行，请先暂停并核对后删除')
   if task.get('copy_leader',task['sku'])==task['sku'] and any(t['sku'] not in skus and t.get('copy_leader')==task['sku'] and t.get('state') not in ('saved','cancelled') for t in self.tasks):raise ValueError('其他变体仍依赖首变体，请保留首变体到完成，或选择整组删除')
  backup=self.folder/'deleted_tasks';backup.mkdir(exist_ok=True);stamp=str(time.time_ns());(backup/(stamp+'.json')).write_text(json.dumps(selected,ensure_ascii=False,indent=2),encoding='utf-8')
  self.tasks=[t for t in self.tasks if t['id'] not in set(ids)];self.save();return len(selected)
 def sync_shared_copies(self):
  from listing_bundle import copy_complete,share_copy,prepare,copy_hash
  leaders={t.get('copy_leader',t['sku']) for t in self.tasks if t.get('set_mode') and t['state']!='cancelled'}
  for source in leaders:
   path=self.folder/'products'/source/'listing_bundle.json'
   if not path.exists():continue
   try:leader=json.loads(path.read_text(encoding='utf-8-sig'))
   except (ValueError,OSError):continue
   if not copy_complete(leader.get('copy')) or (leader.get('asset_review') or {}).get('copy') or leader.get('copy_regeneration_requested'):

    for task in self.tasks:
     if task.get('copy_leader',task['sku'])==source and task.get('copy_state')=='done':task.pop('copy_state',None);task['message']='共用文案不完整，等待整组生成并同步'
    continue
   for task in self.tasks:
    if not task.get('set_mode') or task.get('state')=='cancelled' or task.get('copy_leader',task['sku'])!=source:continue
    folder=self.folder/'products'/task['sku'];target=folder/'listing_bundle.json'
    try:
     folder.mkdir(parents=True,exist_ok=True)
     pending_copy={'source':source,'copy':{**leader['copy'],'sku':task['sku']},'copy_basis':leader.get('copy_basis')}
     pending_path=folder/'shared_copy.json';pending_tmp=pending_path.with_suffix('.tmp')
     pending_tmp.write_text(json.dumps(pending_copy,ensure_ascii=False,indent=2),encoding='utf-8');pending_tmp.replace(pending_path)
     if not target.exists():
      if task['state']!='saved' or not task.get('video'):
       task.update(copy_state='done',copy_source=source)
       continue
      prepare(folder,task)
     current=json.loads(target.read_text(encoding='utf-8-sig'))
     if not copy_complete(current.get('copy')) or copy_hash(current['copy'])!=copy_hash(leader['copy']) or current.get('copy_source')!=source:
      share_copy(folder,source,leader['copy'])
     if leader.get('copy_basis'):
      current=json.loads(target.read_text(encoding='utf-8-sig'))
      if current.get('copy_basis')!=leader['copy_basis']:current['copy_basis']=leader['copy_basis'];from pricing_service import write;write(target,current)
     task['copy_source']=source
     if task.get('copy_mode')!='attributes' or task.get('copy_state') not in ('running','needs_attention'):task['copy_state']='done'
     if not task.get('recollection_requested') or task['state']=='saved':task.pop('resume_mode',None)
     if task['state']=='saved' and task.get('video') and task.get('copy_state')=='done':task['message']='8图、视频、共用俄语文案及草稿已完成；文案来源：'+source+'；待上架审核'
    except (ValueError,OSError,KeyError) as error:
     task.update(copy_state='needs_attention',message='共用文案同步失败：'+str(error)[:160])
  self.save()
 def listing_status(self):
  from listing_bundle import copy_complete,copy_hash
  from asset_audit import inspect
  audits={t['sku']:inspect(self.folder/'products'/t['sku']) for t in self.tasks if t.get('set_mode')}
  result=[]
  for task in self.tasks:
   if not task.get('set_mode'):continue
   folder=self.folder/'products'/task['sku'];row={'sku':task['sku'],'state':task['state'],'image_count':len(task.get('received_images',[])),'video_exists':(folder/'video'/'product_8s.mp4').exists(),'copy_state':task.get('copy_state'),'copy_source':task.get('copy_source'),'copy_complete':False}
   audit=audits[task['sku']];row['image_files_verified']=audit['verified']
   if audit['verified']:
    row['primary_order']=audit['primary_order'];row['primary_hash']=audit['primary_hash']
    leader_audit=audits.get(task.get('gallery_source',task['sku']),{})
    row['shared_gallery_matches']=bool(leader_audit.get('verified') and audit['gallery_hashes']==leader_audit['gallery_hashes'])
   else:row['image_check_message']=audit['reason']
   try:
    bundle=json.loads((folder/'listing_bundle.json').read_text(encoding='utf-8-sig'));row['copy_complete']=bool(copy_complete(bundle.get('copy')));row['copy_source']=bundle.get('copy_source',task.get('copy_leader',task['sku']));row['copy_hash']=copy_hash(bundle['copy']) if row['copy_complete'] else None;row['listing_blockers']=bundle.get('blockers',[]);row['category_confirmed']=bool(bundle.get('category',{}).get('confirmed'));row['price_set']=bundle.get('price_cny') is not None;row['all_image_urls_set']=len(bundle.get('images',[]))==8 and all(i.get('https_url') for i in bundle.get('images',[]))
   except (ValueError,OSError):pass
   if (folder/'listing_bundle.json').exists():
    try:
     latest=json.loads((folder/'listing_bundle.json').read_text(encoding='utf-8-sig'))
     row['asset_review']=latest.get('asset_review',{});row['asset_validation']=latest.get('asset_validation',{});row['category_match_status']=latest.get('category_match_status','未开始')
     row['pricing_status']=latest.get('pricing_status','未开始')
     row['price_confirmed']=bool(latest.get('pricing_confirmed_fingerprint') and latest.get('pricing_confirmed_fingerprint')==latest.get('pricing_fingerprint'))
     hosted=latest.get('hosting') or {};row['hosting_state']=hosted.get('state','not_configured');row['hosting_verified_images']=hosted.get('verified_images',0);row['video_hosting_state']=(latest.get('video_hosting') or {}).get('state','not_started');row['video_url_set']=bool((latest.get('video') or {}).get('https_url'))
    except (OSError,ValueError,TypeError):pass
   if row['copy_complete']:
    try:
     leader=json.loads((self.folder/'products'/row['copy_source']/'listing_bundle.json').read_text(encoding='utf-8-sig'));row['shared_copy_matches']=copy_complete(leader.get('copy')) and copy_hash(leader['copy'])==row['copy_hash']
    except (ValueError,OSError):row['shared_copy_matches']=False
   result.append(row)
  return result
 def queue_summary(self):
  from listing_bundle import copy_complete
  group=[t for t in self.tasks if t.get('set_mode') and t['state']!='cancelled']
  if not group:return '暂无任务，等待创建商品'
  complete=0
  for task in group:
   folder=self.folder/'products'/task['sku']
   try:copy=copy_complete(json.loads((folder/'listing_bundle.json').read_text(encoding='utf-8-sig')).get('copy'))
   except (ValueError,OSError):copy=False
   rows=task.get('received_images',[]);images_present=len(rows)==8 and all(r.get('file') and (folder/'images'/Path(r['file'].replace('\\','/')).name).is_file() for r in rows)
   if task['state']=='saved' and images_present and (folder/'video'/'product_8s.mp4').exists() and copy:complete+=1
  if complete==len(group):return f'{complete}个变体素材已完成：8图、视频、共用俄语文案；待上架审核'
  return f'素材处理中：已完成{complete}/{len(group)}个变体，等待图片、视频或文案完成'
 def repair_unsent_copy(self):
  quota_recovery=False
  for task in self.tasks:
   if task.get('copy_mode')=='attributes' and task.get('copy_state')=='needs_attention' and 'kQuotaBytes' in task.get('message','') and not task.get('quota_recovery_requested'):
    task.update(resume_mode='copy_inspect_only',quota_recovery_requested=True,message='插件存储修复后，正在自动核对原属性回复')
    quota_recovery=True
  if quota_recovery:self.save()
  known={'未找到可用发送按钮','图片回复尚未结束，文案等待下一次自动继续','上一条回复仍在生成','未找到输入框','文案任务已暂停，未点击发送'};changed=False
  for task in self.tasks:
   if task.get('copy_state')=='needs_attention' and task.get('message') in known and task.get('copy_phase') in (None,'inspecting'):
    task.pop('copy_state',None);task.pop('resume_mode',None);task['message']='前次文案未发送，待页面就绪后自动继续';changed=True
  if changed:self.save()
 def repair_uncertain_send_collection(self):
  # A missing UI receipt is never proof that a request was not sent.
  # Recover matching existing results only; never enqueue a generation request.
  if self.control.get('paused'):return
  known=('发送结果尚未确认','Enter发送结果不确定')
  for task in self.tasks+self.image_jobs.jobs:
   if task.get('state')=='needs_attention' and not task.get('pause_requested') and str(task.get('message','')).startswith('文件链接读取失败：') and any(text in task['message'] for text in ('等待浏览器下载超时','浏览器未启动下载','未识别到对应原图')) and task.get('download_recovery_attempts',0)<2 and task.get('resume_mode')!='inspect_only':
    task['resume_mode']='inspect_only';task['download_recovery_attempts']=task.get('download_recovery_attempts',0)+1;self.save()
  changed=False
  for task in self.tasks+self.image_jobs.jobs:
   if task.get('state')=='needs_attention' and not task.get('pause_requested') and any(str(task.get('message','')).startswith(m) for m in known):
    if task.get('resume_mode')!='inspect_only':task['resume_mode']='inspect_only';changed=True
  if changed:self.save()
 def shared_copy_pending(self):
  from listing_bundle import copy_complete
  from pricing_service import read
  for task in self.tasks:
   if not task.get('set_mode') or task.get('copy_leader',task['sku'])!=task['sku'] or task['state']!='saved':continue
   try:bundle=read(self.folder/'products'/task['sku']/'listing_bundle.json')
   except (OSError,ValueError):return True
   if not copy_complete(bundle.get('copy')) or bundle.get('copy_regeneration_requested') or (bundle.get('asset_review') or {}).get('copy'):return True
  return False
 def poll_state(self,extension_idle=False):
  from asset_reconcile import reconcile
  if extension_idle is True:
   from queue_completion import reconcile_idle_attributes
   reconcile_idle_attributes(self)
  from queue_completion import retire_legacy_attribute_save_error
  retire_legacy_attribute_save_error(self)
  from reference_prefill import repair_failed_save
  repair_failed_save(self)
  reconcile(self);self.sync_shared_copies();self.repair_unsent_copy();self.resume_unsent_upload();self.repair_uncertain_send_collection()
  active=bool(self.blockers()) or self.control.get('paused',False)
  # Missing shared copy has priority over queued image work; active requests still block.
  copy_task=self.next_copy() if not active else None
  image_pending=bool(self.image_jobs.next())
  shared_pending=self.shared_copy_pending()
  recovery=self.next_recollection()
  copy_waiting=next(((t.get('competitor_wait') or {}).get('message') for t in self.tasks if (t.get('competitor_wait') or {}).get('state')=='waiting'),None)
  return {'copy_waiting':copy_waiting,'recovery_sku':recovery['sku'] if recovery else None,'ready':not active and not shared_pending and not copy_task and (image_pending or any(t['state']=='queued' and t.get('auto_batch') for t in self.tasks)),'copy_sku':copy_task['sku'] if copy_task else None,'blocked_reason':self.queue_reason() if active else '等待首变体竞品参数及共用文案' if shared_pending else None,'blockers':self.blockers(),'summary':self.queue_summary()}
 def next_copy(self):
  from asset_reconcile import reconcile
  from listing_bundle import prepare,copy_complete
  from pricing_service import read
  from reference_prefill import needed
  reconcile(self);self.sync_shared_copies();self.repair_unsent_copy()
  from queue_completion import completed_skus
  completed=completed_skus(self)
  leaders=[t for t in self.tasks if t['sku'] not in completed and t.get('set_mode') and t['state']=='saved' and t.get('copy_leader',t['sku'])==t['sku']]
  for task in leaders:
   group=[t['sku'] for t in self.tasks if t.get('copy_leader',t['sku'])==task['sku'] and t['state']!='cancelled']
   if self.image_jobs.active(group):continue
   folder=self.folder/'products'/task['sku'];path=folder/'listing_bundle.json'
   if not path.exists():
    if not (folder/'image_manifest.json').exists():continue
    prepare(folder,task)
   bundle=read(path);complete=copy_complete(bundle.get('copy'));fresh=complete and not (bundle.get('asset_review') or {}).get('copy') and not bundle.get('copy_regeneration_requested')
   if fresh:
    if task.get('copy_state') not in ('running','needs_attention'):task['copy_state']='done'
    continue
   if task.get('copy_state')=='done':task.pop('copy_state',None)
   if task.get('copy_state') in ('running','needs_attention'):continue
   from competitor_flow import before_copy
   if not before_copy(self,task):continue
   task['copy_mode']='copy_refresh' if complete else 'copy';self.save();return task
  # Reading optional reference attributes must not precede a group's missing text.
  for task in leaders:
   if task.get('copy_state')=='done' and needed(self,task):
    group=[t['sku'] for t in self.tasks if t.get('copy_leader',t['sku'])==task['sku']]
    if not self.image_jobs.active(group):task['copy_mode']='attributes';return task
  self.save();return None
 def render_video(self,sku):
  from video import make_video
  with self.lock:
   if sku in self.video_running:return
   self.video_running.add(sku);group=sorted([dict(x) for x in self.tasks if x['sku']==sku],key=lambda x:x['name'])
  # Reserve the SKU before waiting; media replacement must wait for queued videos too.
  # Never wait for an encoder slot while holding the shared material lock.
  self.video_slots.acquire()
  try:
   files=[x['file'] for x in group[0]['received_images']] if len(group)==1 and group[0].get('set_mode') else [x['file'] for x in group]
   output=make_video(files,self.folder/'products'/sku/'video'/'product_8s.mp4')
   with self.lock:
    for x in self.tasks:
     if x['sku']==sku:x.update(video=output,message='8张图片及8秒视频已完成；'+('共用文案已保存' if x.get('copy_state')=='done' else '整组文案自动处理中' if x.get('copy_state')=='running' else '等待自动接续整组文案'))
    from listing_bundle import refresh_assets
    refresh_assets(self.folder/'products'/sku)
    self.sync_shared_copies()
    self.save()
  except Exception as e:
   with self.lock:
    for x in self.tasks:
     if x['sku']==sku:x['message']='图片已保存，视频合成失败：'+str(e)[:160]
    self.save()
  finally:
   with self.lock:self.video_running.discard(sku)
   self.video_slots.release()


def server(store,token,port=8765):
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def reply(self,code,value):
   body=json.dumps(value,ensure_ascii=False).encode()
   try:
    self.send_response(code)
    self.send_header('Content-Type','application/json; charset=utf-8')
    self.send_header('Cache-Control','no-store')
    self.send_header('Content-Length',str(len(body)))
    self.end_headers()
    self.wfile.write(body)
   except (ConnectionError,TimeoutError):
    # The client may have gone away after the operation was already saved.
    self.close_connection=True
  def allowed(self):
   return self.headers.get('Host')==f'127.0.0.1:{port}' and self.headers.get('Origin','').startswith('chrome-extension://')
  def do_OPTIONS(self):
   if not self.allowed():return self.reply(403,{'error':'扩展来源无效'})
   self.send_response(204);self.send_header('Access-Control-Allow-Origin',self.headers['Origin']);self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type');self.send_header('Access-Control-Allow-Methods','POST');self.end_headers()
  def end_headers(self):
   if self.allowed() and self.command!='OPTIONS':self.send_header('Access-Control-Allow-Origin',self.headers['Origin'])
   super().end_headers()
  def do_POST(self):
   if not self.allowed() or not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):return self.reply(403,{'error':'配对失败'})
   try:
    n=int(self.headers.get('Content-Length','0'))
    if not 0<n<29*1024*1024:raise ValueError('请求大小无效')
    body=json.loads(self.rfile.read(n))
    if self.path=='/automation-wait':
     store.client.update(last_seen=time.time(),wake_seen=time.time(),auto_enabled=bool(body.get('auto_enabled')),bound=bool(body.get('bound')))
     return self.reply(200,store.automation_wake.wait(str(body.get('cursor') or '')))
    if self.path=='/queue-diagnostic':
     if not store.lock.acquire(blocking=False):return self.reply(200,{'busy':True,'message':'本地正在处理素材，已跳过队列快照；页面诊断仍可导出'})
     try:value={'wake':store.automation_wake.stats(),'command_ack':store.control.get('plugin_ack'),'busy':False,'paused':store.control.get('paused',False),'tasks':[{'id':t['id'],'sku':t['sku'],'state':t['state'],'received':len(t.get('received_images') or []),'copy_state':t.get('copy_state'),'copy_mode':t.get('copy_mode'),'copy_phase':t.get('copy_phase'),'resume_mode':t.get('resume_mode'),'pause_requested':bool(t.get('pause_requested')),'recollection_requested':bool(t.get('recollection_requested')),'message':t.get('message',''),'attribute_deferred_reason':t.get('attribute_deferred_reason')} for t in store.tasks],'image_jobs':[{'id':j['id'],'sku':j['sku'],'state':j['state'],'received':len(j.get('received_images') or []),'expected':j.get('expected_images'),'kind':j.get('kind'),'resume_mode':j.get('resume_mode'),'message':j.get('message','')} for j in store.image_jobs.jobs if j['state'] not in ('saved','cancelled')]}
     finally:store.lock.release()
     return self.reply(200,value)
    with store.lock:
     store.client['last_seen']=time.time()
     if self.path=='/health':value={'protocol':'1.0.92','paired':True}
     elif self.path=='/plugin-status':
      from task_alerts import save_plugin_status
      value=save_plugin_status(store,body)
     elif self.path=='/competitor-task':
      from competitor_reference import claim
      value=claim(store)
     elif self.path=='/competitor-result':
      from competitor_reference import receive
      body['diagnostics']={**(body.get('diagnostics') or {}),'collector':'browser_extension'}
      value=receive(store,body)
     elif self.path=='/control-ack':
      from automation_wake import acknowledge
      value=acknowledge(store,body.get('command_token'))
     elif self.path=='/control':value=store.control
     elif self.path=='/automation-control':value=store.set_paused(bool(body.get('paused')))
     elif self.path=='/pause-ack':
      tid=body['task_id']
      try:task=next((t for t in store.tasks if t['sku']==tid[5:]),None) if tid.startswith('copy:') else store.find(tid)
      except ValueError:task=None
      if task is None:
       if not body.get('allow_missing') or not store.control.get('paused'):raise ValueError('未找到需要暂停的任务')
       value={'ok':True,'found':False}
      else:task['pause_ack']=True;store.save();value={'ok':True,'found':True}
     elif self.path=='/queue-restart-ack':
      command=store.control.get('queue_restart') or {}
      if not command.get('token') or body.get('token')!=command['token']:raise ValueError('重启回执已过期，未改变当前队列')
      store.control['queue_restart_ack']={'token':command['token'],'received_at':time.time()}
      store.control_path.write_text(json.dumps(store.control),encoding='utf-8');value={'ok':True}
     elif self.path=='/heartbeat':
      store.client.update(last_seen=time.time(),auto_enabled=bool(body.get('auto_enabled')))
      value={'ok':True,'queue_reason':store.queue_reason(),'blockers':store.blockers()}
     elif self.path=='/resume-unsent-upload':value=store.resume_unsent_upload()
     elif self.path=='/queue-status':value={'blockers':store.blockers(),'queue_reason':store.queue_reason(),'queued_count':sum(t['state']=='queued' for t in store.tasks),'listings':store.listing_status()}
     elif self.path=='/download-ticket':
      task=store.find(body['task_id']);ext=body['extension'].lower()
      if ext not in ('jpg','jpeg','png','webp'):raise ValueError('下载文件格式不支持')
      store.download_tickets={k:v for k,v in store.download_tickets.items() if v['expires']>time.time()}
      ticket=secrets.token_hex(16);name=ticket+'.'+ext
      store.download_tickets[ticket]={'task_id':task['id'],'name':name,'extension':ext,'expires':time.time()+180}
      value={'ticket':ticket,'filename':'OzonImports/'+task['id']+'/'+name}
     elif self.path=='/read-download':
      from file_assets import decode
      ticket=store.download_tickets.pop(body['ticket'],None)
      if not ticket or ticket['task_id']!=body['task_id'] or ticket['expires']<time.time():raise ValueError('下载凭证已失效')
      path=Path(body['path']).resolve();task=store.find(ticket['task_id'])
      if path.name!=ticket['name'] or path.parent.name!=task['id'] or path.parent.parent.name!='OzonImports' or not path.is_file():raise ValueError('下载文件与本次凭证不匹配')
      if path.stat().st_size>96*1024*1024:raise ValueError('下载文件过大')
      value={'images':decode(path.read_bytes(),ticket['extension'],task.get('expected_images',8),task.get('references',[]))}
     elif self.path=='/repair-order':value=store.repair_order(body['task_id'])
     elif self.path=='/task-status':value=store.task_status(body['task_id'])
     elif self.path=='/poll':
      store.client={'last_seen':time.time(),'auto_enabled':bool(body.get('auto_enabled',True))}
      value=store.poll_state(extension_idle=body.get('execution_idle') is True)
     elif self.path=='/copy-task':
      from copy_pipeline import prepare as prepare_copy
      value=prepare_copy(store,body)
     elif self.path=='/copy-failed':
      sku=body['sku']
      for task in store.tasks:
       if task['sku']==sku:
        message=str(body.get('message','文案保存待处理'))[:300];task.update(copy_state='needs_attention',resume_mode='copy_inspect_only',message=message)
        if message in ('未找到可用发送按钮','图片回复尚未结束，文案等待下一次自动继续','上一条回复仍在生成','未找到输入框','文案任务已暂停，未点击发送'):task['copy_phase']='inspecting'
      store.save();value={'ok':True}
     elif self.path=='/copy-result':
      from copy_pipeline import save as save_pipeline_copy
      value=save_pipeline_copy(store,body)
      if next(t for t in store.tasks if t['sku']==body['sku']).get('copy_mode')!='attributes':
       from category_match import suggest
       threading.Thread(target=suggest,args=(store.folder/'products'/body['sku'],),kwargs={'lock':store.lock},daemon=True).start()
     elif self.path=='/delivery-plan':
      from image_retry import plan
      value=plan(store.find(body['task_id']))
     elif self.path=='/backup-composer':
      from composer_cleanup import backup
      value=backup(store,body['task_id'],body.get('text'),body.get('attachments'))
     elif self.path=='/generation-failed':
      from failed_generation import request
      value=request(store,body['task_id'],body)
     elif self.path=='/image-retry':
      from image_retry import reserve
      value=reserve(store,body['task_id'],body)
     elif self.path=='/recover':
      value=store.image_jobs.recover(body['task_id']) if body.get('task_id') and store.image_jobs.get(body['task_id']) else store.recover(body['sku'],automatic=bool(body.get('automatic')))
     elif self.path=='/claim':value=store.claim()
     elif self.path=='/sheet-result':
      from contact_sheet import accept
      value=accept(store,body['task_id'],body['image_b64'])
     elif self.path=='/set-result':value=store.set_result(body['task_id'],body['index'],body['image_b64'])
     elif self.path=='/result':value=store.result(body['task_id'],body['image_b64'])
     elif self.path=='/event':
      t=store.find(body['task_id']);state=body['state']
      if state not in ('sending','waiting','needs_attention') or (t['state'] not in ('claimed','sending','waiting') and not (t['state']=='needs_attention' and state=='needs_attention')):raise ValueError('状态变更无效')
      t.update(state=state,message=str(body.get('message',''))[:500]);store.save();value={'ok':True}
     else:return self.reply(404,{'error':'接口不存在'})
    self.reply(200,value)
   except Exception as e:self.reply(400,{'error':str(e)[:300],'code':getattr(e,'code',None)})
 return ThreadingHTTPServer(('127.0.0.1',port),Handler)

def main(test_mode=False,on_ready=None):
 import tkinter as tk
 from tkinter import ttk,messagebox,filedialog
 from pairing import token as pairing_token,InstanceLock
 instance=InstanceLock(DATA);instance.acquire()
 store=Store(DATA);store.image_jobs.defer_commits=not test_mode;token=pairing_token(DATA);http=server(store,token) if not test_mode else None
 if http:threading.Thread(target=http.serve_forever,daemon=True).start()
 root=tk.Tk()
 def show_task_error(title,error,**options):
  from task_alerts import issue,render
  return messagebox.showerror(title,render([issue('本地工具',title,error)]),**({'parent':root}|options))
 from ui_layout import build
 notebook,pages,connection=build(root);win=pages['product_body'];settings_page=pages['settings_body'];tasks_page=pages['tasks']
 def set_connection(summary,detail=''):
  """Keep the persistent status bar to one line; full errors are opt-in."""
  compact=' '.join(str(summary or '').split())
  connection.configure(text=(compact[:160]+'…') if len(compact)>160 else compact)
  setter=getattr(connection,'_ozon_set_detail',None)
  if setter:setter(detail,hashlib.sha256(str(detail or '').encode()).hexdigest() if detail else '')
 account_panel=ttk.LabelFrame(settings_page,text='账户与配对',padding=16);account_panel.pack(fill='x',pady=(0,16))
 ttk.Label(account_panel,text='连接与来源设置',font=('TkDefaultFont',13,'bold')).pack(anchor='w',pady=8)
 ttk.Label(account_panel,text='插件配对信息仅保存在本机；首次安装或重置后复制到插件，重启后无需重复配对。',wraplength=1050).pack(anchor='w',pady=6)
 code=ttk.Entry(account_panel,width=65,show='*');code.insert(0,token);code.pack(anchor='w')
 def copy_pair():root.clipboard_clear();root.clipboard_append(token);messagebox.showinfo('已复制','请在插件连接设置中保存配对码。',parent=root)
 ttk.Button(account_panel,text='复制配对码',command=copy_pair).pack(anchor='w',pady=6)
 def restore_records():
  selected_file=filedialog.askopenfilename(title='恢复已删除记录',initialdir=DATA/'deleted_tasks',filetypes=[('本地任务备份','*.json')])
  if not selected_file:return
  try:
   with store.lock:count=store.restore_deleted(selected_file)
   messagebox.showinfo('记录已恢复',str(count)+' 个变体记录已恢复；素材保留，不重复生成。')
  except Exception as exc:show_task_error('恢复未完成',str(exc))
 ttk.Button(account_panel,text='恢复已删除的本地记录',command=restore_records).pack(anchor='w',pady=6)

 setup_card=ttk.Frame(win,style='Card.TFrame',padding=(10,6));setup_card.pack(fill='x',pady=(0,4))
 identity=ttk.Frame(setup_card,style='Card.TFrame');identity.pack(fill='x');identity.columnconfigure(0,weight=1);identity.columnconfigure(1,weight=1)
 ttk.Label(identity,text='基础货号',style='Card.TLabel').grid(row=0,column=0,sticky='w',pady=(0,5))
 ttk.Label(identity,text='商品类目',style='Card.TLabel').grid(row=0,column=1,sticky='w',padx=(12,0),pady=(0,5))
 base=tk.StringVar();ttk.Entry(identity,textvariable=base).grid(row=1,column=0,sticky='ew')
 category_row=ttk.Frame(identity,style='Card.TFrame');category_row.grid(row=1,column=1,sticky='ew',padx=(12,0));category_selection={}
 color_catalog_note=ttk.Label(category_row,text='',style='Muted.TLabel');color_catalog_note.pack(side='bottom',anchor='w',pady=(3,0))
 def choose_creation_category():
  from creation_category import choose
  from account_context import credentials
  def saved(value):
   category_selection.clear();category_selection.update(value);category_selection['preload_state']='loading';category=dict(value['category']);label=(category.get('zh_path') or category.get('name','')).split(' / ')[-1];category_button.configure(text=label[:30]+' · 正在读取官方字段');color_catalog_note.configure(text='正在读取官方字段与颜色；完成后即可创建队列…');grid.color_bundles=[{'sku':'creation-color-catalog','category':{**category,'confirmed':True}}];refresh_visual_label()
   def load_official():
    try:
     from color_catalog import preload
     fields=attributes.prefetch_category(category);result=preload(attributes,category)
     def done():
      if (category_selection.get('category') or {}).get('type_id')!=category.get('type_id'):return
      category_selection['attribute_preload']=fields;category_selection['preload_state']='ready';category_button.configure(text=label[:30]+' · 已选定');color_catalog_note.configure(text='官方字段已读取：'+str(len(fields['fields']))+' 项；官方颜色：'+str(len(result['rows']))+' 项，创建后直接用于预填。')
     root.after(0,done)
    except Exception as exc:
     def failed(text=str(exc)):
      if (category_selection.get('category') or {}).get('type_id')!=category.get('type_id'):return
      category_selection['preload_state']='failed';category_button.configure(text=label[:30]+' · 重试读取');color_catalog_note.configure(text='官方字段读取未完成：'+text[:100]+'；请重新选择类目后重试。')
     root.after(0,failed)
   threading.Thread(target=load_official,daemon=True).start()
  return choose(root,attributes,lambda:credentials()[0],saved)
 category_button=ttk.Button(category_row,text='选择官方类目（可选）',style='Compact.TButton',command=choose_creation_category);category_button.pack(side='left',fill='x',expand=True)
 def clear_creation_category():category_selection.clear();grid.color_bundles=None;category_button.configure(text='选择官方类目（可选）');color_catalog_note.configure(text='');refresh_visual_label()
 ttk.Button(category_row,text='清除',style='Compact.TButton',command=clear_creation_category).pack(side='left',padx=(6,0))
 from variants import VariantGrid
 shared_refs=[]
 reference_row=ttk.Frame(setup_card,style='Card.TFrame');reference_row.pack(fill='x',pady=(8,0))
 def preview_shared():
  from image_viewer import open_viewer
  if shared_refs:return open_viewer(root,'',[{'local_file':p} for p in shared_refs],title='共用详情参考图')
 def choose_shared():
  nonlocal shared_refs
  selected=list(filedialog.askopenfilenames(title='选择全组共用详情图参考',filetypes=[('Images','*.png *.jpg *.jpeg *.webp')]))
  if selected:shared_refs=selected;shared_label.configure(text='已选 '+str(len(selected))+' 张 · 点击查看')
 ttk.Button(reference_row,text='选择共用参考图',style='Compact.TButton',command=choose_shared).pack(side='left')
 shared_label=ttk.Label(reference_row,text='未选择共用参考图',style='CardMuted.TLabel',cursor='hand2');shared_label.pack(side='left',padx=12);shared_label.bind('<Button-1>',lambda e:preview_shared())

 def creation_visual_plan():
  from visual_plans import build
  params=grid.rows[0]['values'] if grid.rows else {}
  return build(category_selection.get('category'),params,len(grid.rows),category_selection.get('visual_style_override'))
 def refresh_visual_label():
  visual_button.configure(text='方案：'+creation_visual_plan()['style_name']+' · 查看')
 def choose_visual_plan():
  from visual_plan_ui import open_plan
  def save(value):
   if value is None:category_selection.pop('visual_style_override',None)
   else:
    if not category_selection.get('category'):raise ValueError('请先选择官方类目，再设置该组风格')
    category_selection['visual_style_override']=value
   refresh_visual_label()
  return open_plan(root,creation_visual_plan,save,key='creation')
 visual_button=ttk.Button(reference_row,text='方案：简洁实物 · 查看',style='Compact.TButton',command=choose_visual_plan);visual_button.pack(side='right')

 variant_card=ttk.LabelFrame(win,text='变体与参数',padding=2);variant_card.pack(fill='both',expand=True,pady=(0,12))
 grid=VariantGrid(variant_card,base)
 from pricing_service import PricingService,read as read_pricing
 from ozon_connection import restore as restore_ozon
 restore_ozon(DATA)
 from shop_state import activate as activate_shop
 import os
 activate_shop(DATA,os.environ.get('OZON_CLIENT_ID',''))
 pricing=PricingService(DATA,store.lock);pricing_stop=threading.Event()
 None if test_mode else threading.Thread(target=pricing.worker,args=(pricing_stop,),daemon=True).start()
 sources_panel=ttk.LabelFrame(settings_page,text='定价与素材托管',padding=16);sources_panel.pack(fill='x',pady=(0,16))
 pricing_label=ttk.Label(sources_panel,wraplength=850,text='自动售价：等待导入定价来源');pricing_label.pack(pady=3)
 from hosting_service import HostingService
 def hosting_skus():
  with store.lock:return {t['sku'] for t in store.tasks if t.get('set_mode') and t['state']!='cancelled'}
 hosting=HostingService(DATA,store.lock,active_skus=hosting_skus)
 None if test_mode else threading.Thread(target=hosting.worker,args=(pricing_stop,),daemon=True).start()
 hosting_label=ttk.Label(sources_panel,wraplength=850,text='图片托管：首次需连接腾讯云COS存储桶');hosting_label.pack(pady=3)
 from video_hosting import VideoHostingService
 video_hosting=VideoHostingService(hosting);None if test_mode else threading.Thread(target=video_hosting.worker,args=(pricing_stop,),daemon=True).start()
 video_label=ttk.Label(sources_panel,wraplength=850,text='视频托管：等待8秒MP4与图片链接');video_label.pack(pady=3)
 from attribute_service import AttributeService
 attributes=AttributeService(DATA,store.lock,active_skus=hosting_skus);attributes.task_store=store;store.attributes=attributes;grid.color_service=attributes
 None if test_mode else threading.Thread(target=attributes.worker,args=(pricing_stop,),daemon=True).start()
 ttk.Label(sources_panel,text='竞品参数由已配对的 Edge 插件采集；请在代理扩展中将 Ozon 设置为直连。',wraplength=850).pack(pady=3)
 from publication_service import PublicationService
 publication=PublicationService(DATA,store.lock,initial_stock=1000)
 if not test_mode and os.environ.get('OZON_CLIENT_ID'):publication.resume_account(os.environ['OZON_CLIENT_ID'])
 None if test_mode else threading.Thread(target=publication.worker,args=(pricing_stop,),daemon=True).start()
 def hosting_settings():
  import os,webbrowser
  cached=lookup(root,('cos_settings',))
  if cached is not None:return cached
  dialog=remember(root,('cos_settings',),tk.Toplevel(root));dialog.title('腾讯云COS图片托管')
  from ui_layout import dialog_footer
  hosting_footer=dialog_footer(dialog,820,760)
  ttk.Label(dialog,text='COS免费存储额度不覆盖请求和外网下载，使用时可能计费。\n托管8张生成原图和本地8秒MP4，主图固定01，共用详情图只上传一次。').pack(padx=12,pady=10)
  ttk.Button(dialog,text='打开腾讯云COS控制台',command=lambda:webbrowser.open('https://console.cloud.tencent.com/cos/bucket')).pack(pady=4)
  try:config,credentials=hosting.settings()
  except (OSError,ValueError):config={};credentials={}
  region=tk.StringVar(value=config.get('region',''));bucket=tk.StringVar(value=config.get('bucket',''));key=tk.StringVar(value=credentials.get('secret_id',''));secret=tk.StringVar(value=credentials.get('secret_key',''))
  for label,variable,masked in [('地域 Region，例如ap-hongkong',region,False),('Bucket完整名称（包含-APPID）',bucket,False),('SecretId',key,True),('SecretKey',secret,True)]:
   ttk.Label(dialog,text=label).pack();ttk.Entry(dialog,textvariable=variable,width=65,show='*' if masked else '').pack(pady=2)
  remember_keys=tk.BooleanVar(value=os.name=='nt')
  ttk.Checkbutton(dialog,text='在当前Windows账户加密记住密钥（重启后继续自动上传）',variable=remember_keys,state='normal' if os.name=='nt' else 'disabled').pack(pady=6)
  ttk.Label(dialog,text='存储桶需设为公有读私有写，允许匿名、空Referer读取上架图片。\n使用拥有该目录PutObject权限的子账号密钥；程序不创建桶或修改权限。\n只上传生成图和MP4，不开CDN、全球加速或媒体处理服务。').pack(pady=6)
  state=ttk.Label(dialog,text=hosting.status,wraplength=690);state.pack(pady=6)
  def save_hosting():
   try:
    hosting.configure(region.get(),bucket.get(),key.get(),secret.get(),remember_keys.get());video_hosting.wake.set();state.configure(text='配置已保存，正在后台上传并校验已有及后续生成图片…')
   except Exception as e:show_task_error('托管设置未保存',str(e),parent=dialog)
  ttk.Button(hosting_footer,text='保存并自动上传已有及后续生成图片',command=save_hosting).pack(pady=4)
  def switch(enabled):
   try:hosting.set_enabled(enabled);video_hosting.retry_at.clear();video_hosting.wake.set()
   except ValueError as e:show_task_error('托管状态',str(e),parent=dialog)
  buttons=ttk.Frame(dialog);buttons.pack(pady=3)
  ttk.Button(buttons,text='暂停上传（保留已有链接）',command=lambda:switch(False)).pack(side='left',padx=5)
  ttk.Button(buttons,text='恢复 / 重试未完成图片',command=lambda:switch(True)).pack(side='left',padx=5)
  def update_hosting_state():
   if not dialog.winfo_exists():return
   state.configure(text=hosting.status);dialog.after(1500,update_hosting_state)
  update_hosting_state()
 ttk.Button(sources_panel,text='腾讯云COS托管设置 / 自动生成链接',command=hosting_settings).pack(pady=4)
 def pricing_settings():
  cached=lookup(root,('pricing_settings',))
  if cached is not None:return cached
  dialog=remember(root,('pricing_settings',),tk.Toplevel(root));dialog.title('自动定价设置与来源');dialog.geometry('820x620')
  actions=ttk.Frame(dialog,padding=10);actions.pack(side='bottom',fill='x')
  for col in range(2):actions.columnconfigure(col,weight=1)
  info=tk.Text(dialog,height=13,wrap='word');info.pack(fill='both',expand=True,padx=10,pady=8)
  def show():
   info.delete('1.0','end')
   for name,label in [('ogl','OGL运输表'),('commissions','rFBS佣金表'),('fx','央行汇率')]:
    path=pricing.root/(name+'.json')
    if not path.exists():info.insert('end',label+'：未配置\n');continue
    value=read_pricing(path)
    text=(value.get('filename','')+' '+value.get('effective_note','')) if name!='fx' else value['rub_per_cny']+' RUB/CNY，日期 '+value['date']+'\n'+value['source']+' '+value['url']
    info.insert('end',label+'：'+text+'\n')
   info.insert('end',pricing.commission_status+'\n')
   info.insert('end','\nOGL边界已确认按表中文字：重量及货值按文字，三边之和含上限。\n售价单位人民币；利润率=净利润/售价。每套成本不乘套装件数。\n计入rFBS佣金、OGL运输、贴单1元、尾程2.2%、提现1.2%、收单2%。\n央行汇率仅作参考；显示的售价为估算，提交上架前确认。\n基准为2025-12-01表；工具运行时每6小时核对店铺商品rFBS费率。仅校准已有商品覆盖价格档，冲突不采用，观察值24小时过期；不代表全平台最新官方费率。')
  def run(action):
   def work():
    try:action()
    except Exception as e:
     root.after(0,lambda text=str(e):show_task_error('定价来源更新失败',text,parent=dialog));return
    # The source is already saved. Refresh it even if a product cannot be priced.
    root.after(0,show)
    try:pricing.calculate_all()
    except Exception as e:root.after(0,lambda text=str(e):show_task_error('来源已保存，商品定价未完成',text,parent=dialog))
   threading.Thread(target=work,daemon=True).start()
  def choose(kind):
   path=filedialog.askopenfilename(parent=dialog,title='导入'+kind,filetypes=[('Excel','*.xlsx')])
   if path:run(lambda:pricing.import_ogl(path) if kind=='OGL' else pricing.import_commissions(path))
  ttk.Button(actions,text='导入本地OGL计算表（一次配置）',command=lambda:choose('OGL')).grid(row=0,column=0,sticky='ew',padx=4,pady=4)
  ttk.Button(actions,text='导入官方rFBS佣金表',command=lambda:choose('佣金')).grid(row=0,column=1,sticky='ew',padx=4,pady=4)
  ttk.Button(actions,text='下载官方佣金表（2025-12-01版）',command=lambda:run(pricing.update_commissions)).grid(row=1,column=0,sticky='ew',padx=4,pady=4)
  def export_commissions():
   path=filedialog.asksaveasfilename(parent=dialog,title='下载当前最新版佣金表（店铺校准版）',defaultextension='.xlsx',initialfile='Ozon_店铺佣金校准表.xlsx',filetypes=[('Excel','*.xlsx')])
   if path:run(lambda:(pricing.sync_commissions(force=True),pricing.export_commissions(path)))
  ttk.Button(actions,text='立即比对店铺API佣金',command=lambda:run(lambda:pricing.sync_commissions(force=True))).grid(row=1,column=1,sticky='ew',padx=4,pady=4)
  ttk.Button(actions,text='下载最新版佣金表（店铺校准版）',command=export_commissions).grid(row=2,column=0,sticky='ew',padx=4,pady=4)
  ttk.Button(actions,text='立即获取央行参考汇率',command=lambda:run(pricing.update_fx)).grid(row=2,column=1,sticky='ew',padx=4,pady=4)
  show()
 ttk.Button(sources_panel,text='自动定价设置 / 运费表 / 央行汇率',command=pricing_settings).pack(pady=3)
 def create():
  try:
   for row in grid.rows:row['values']['stock']='1000'
   records=grid.records()
   from creation_category import apply_task
   from account_context import credentials
   current_account=credentials()[0]
   if category_selection and category_selection.get('account_id')!=current_account:raise ValueError('店铺已切换，请重新选择商品类目')
   if category_selection.get('preload_state')=='loading':raise ValueError('正在读取所选类目的官方字段，请等待完成后再创建队列')
   if category_selection.get('preload_state')=='failed':raise ValueError('所选类目的官方字段读取失败，请重新选择类目后重试')
   if len(records)>100:raise ValueError('每组最多100个变体，请拆分后创建')
   if not shared_refs:raise ValueError('请选择共用详情图参考')
   if len(shared_refs)>8:raise ValueError('共用详情参考最多8张')
   for ref in shared_refs:
    if Path(ref).stat().st_size>3*1024*1024:raise ValueError('原图单张限3MB')
    with Image.open(ref) as image:image.verify()
   with store.lock:
    if any(any(t['sku']==r['article'] for t in store.tasks) for r in records):raise ValueError('部分变体货号已有任务，请勿重复创建')
    # Validate all references before creating any variant task.
    for r in records:
     if not r['references']:raise ValueError(r['article']+' 请选择原图')
     if len(r['references'])>8:raise ValueError('每个变体最多8张参考图')
     for ref in r['references']:
      if Path(ref).stat().st_size>3*1024*1024:raise ValueError('原图单张限3MB')
      with Image.open(ref) as image:image.verify()
    previous=list(store.tasks)
    try:
     for r in records:
      store.create_set(r['article'],r['facts'],r['references'])
      task=next(t for t in store.tasks if t['sku']==r['article'])
      task['main_references']=list(task['references'])
      task.update(base_article=r['base_article'],variant_index=r['index'],variant_parameters=r['values'])
      apply_task(task,category_selection,current_account)
     from product_group import configure
     configure(store.tasks,records[0]['base_article'])
     leader=next(t for t in store.tasks if t['sku']==records[0]['article'])
     shared_dir=store.folder/'products'/leader['sku']/'shared_references';shared_dir.mkdir(parents=True,exist_ok=True)
     shared=[]
     for i,ref in enumerate(shared_refs):
      raw=Path(ref).read_bytes()
      with Image.open(ref) as im:fmt=im.format
      mime={'PNG':'image/png','JPEG':'image/jpeg','WEBP':'image/webp'}.get(fmt)
      if not mime:raise ValueError('共用详情参考仅支持PNG/JPG/WEBP')
      dest=shared_dir/(str(i+1)+'.'+{'PNG':'png','JPEG':'jpg','WEBP':'webp'}[fmt])
      dest.write_bytes(raw);shared.append({'path':str(dest),'name':dest.name,'mime':mime,'purpose':'shared_gallery'})
     leader['detail_references']=shared
     leader['references']=leader['main_references']+shared
     leader['prompt']+='。本次附件前'+str(len(leader['main_references']))+'张仅用于变体1主图，之后'+str(len(shared))+'张仅用于7张共用详情图。主图必须与当前变体参数一致。详情图按全组颜色混搭、尺寸对照方式生成，注明不同规格为选项而非全部随货交付。'

     store.save()
     # Explicit Create-and-process starts only after every variant and reference is committed.
     store.set_paused(False)
    except Exception:
     store.tasks=previous;store.save();raise
   notebook.select(pages['tasks'])
  except Exception as e:show_task_error('未创建',str(e))
 product_footer=ttk.Frame(pages['product'],padding=(18,4));product_footer.grid(row=1,column=0,sticky='ew')

 ttk.Button(product_footer,text='创建队列 · 开始自动制作',style='Primary.TButton',command=create).pack(side='right')
 task_table=ttk.Frame(tasks_page,style='Card.TFrame');task_table.pack(fill='both',expand=True);task_table.rowconfigure(0,weight=1);task_table.columnconfigure(0,weight=1)
 view=ttk.Treeview(task_table,columns=('sku','progress','price','hosting','competitor','status'),show='tree headings',height=15,selectmode='browse')
 view.heading('#0',text='商品组');view.column('#0',width=120,stretch=False,anchor='center')
 for key,label,width in [('sku','变体货号',140),('progress','图片',65),('price','售价（元）',85),('hosting','托管链接',105),('competitor','竞品采集 / 参数预填',205),('status','当前阶段 / 原因',255)]:view.heading(key,text=label,anchor='center');view.column(key,width=width,stretch=key=='status',anchor='w' if key in ('sku','status') else 'center')
 view.tag_configure('published',foreground='#16785B',background='#F1FAF5');view.tag_configure('archive',foreground='#687C9D',background='#EAF0F9')
 view.tag_configure('group',background='#EDF1F8',foreground='#334155');view.tag_configure('even',background='#FFFFFF');view.tag_configure('odd',background='#F8FAFE');view.tag_configure('attention',foreground='#B74347',background='#FFF4F2')
 view.grid(row=0,column=0,sticky='nsew');scroll_y=ttk.Scrollbar(task_table,orient='vertical',command=view.yview);scroll_y.grid(row=0,column=1,sticky='ns');scroll_x=ttk.Scrollbar(task_table,orient='horizontal',command=view.xview);scroll_x.grid(row=1,column=0,sticky='ew');view.configure(yscrollcommand=scroll_y.set)
 def task_horizontal(first,last):
  scroll_x.set(first,last)
  if float(first)<=.001 and float(last)>=.999:scroll_x.grid_remove()
  else:scroll_x.grid()
 view.configure(xscrollcommand=task_horizontal)
 def fit_task_columns(event):
  if event.width<200:return
  fixed={'#0':.16,'sku':.19,'progress':.075,'price':.10,'hosting':.14,'status':.235}
  for key,ratio in fixed.items():view.column(key,width=int((event.width-6)*ratio),minwidth=35,stretch=True)
 view.bind('<Configure>',fit_task_columns)

 task_actions=ttk.Frame(tasks_page);task_actions.pack(side='bottom',before=task_table,fill='x',pady=10);task_more=tk.Menu(root,tearoff=False);more_button=ttk.Menubutton(task_actions,text='更多操作',menu=task_more);more_button.pack(side='right')
 note_panel=ttk.Frame(tasks_page)
 note_panel.pack(side='bottom',before=task_table,fill='x',pady=4)
 note_full=['']
 note_closed=[None]
 note_text=tk.Text(note_panel,height=3,wrap='word',state='disabled')
 note_text.pack(side='left',fill='x',expand=True)
 note_controls=ttk.Frame(note_panel);note_controls.pack(side='right',fill='y')
 def set_task_note(value):
  note_full[0]=str(value)
  note_text.configure(state='normal')
  note_text.delete('1.0','end')
  note_text.insert('1.0',note_full[0])
  note_text.configure(state='disabled')
 def open_task_note():
  from tkinter.scrolledtext import ScrolledText
  dialog=tk.Toplevel(root);dialog.title('任务完整原因');dialog.geometry('850x540')
  bar=ttk.Frame(dialog);bar.pack(side='bottom',fill='x')
  ttk.Button(bar,text='关闭',command=dialog.destroy).pack(side='right',padx=12,pady=8)
  details=ScrolledText(dialog,wrap='word');details.pack(fill='both',expand=True,padx=12,pady=8)
  details.insert('1.0',note_full[0]);details.configure(state='disabled')
 def close_task_note():
  ids=view.selection();note_closed[0]=ids[0] if ids else ''
  saved=note_full[0]
  set_task_note('详情已关闭。点击“查看完整原因”可重新查看。')
  note_full[0]=saved
 ttk.Button(note_controls,text='查看完整原因',command=open_task_note).pack(fill='x')
 ttk.Button(note_controls,text='关闭提示',command=close_task_note).pack(fill='x')
 def show_task_note(event=None):
  ids=view.selection();key=ids[0] if ids else ''
  value=row_notes.get(key,'请展开商品组，选择具体变体查看状态。')
  if note_closed[0]==key:
   note_full[0]=value
   return
  set_task_note(value)
 view.bind('<<TreeviewSelect>>',show_task_note)
 from task_alerts import AlertPopup,ProgressWatch,collect as collect_alerts,issue as make_alert
 alert_popup=AlertPopup(root,DATA/'task_alert_state.json',lambda:notebook.select(pages['tasks']));alert_watch=ProgressWatch()
 task_more.add_command(label='查看当前异常及中文处理办法',command=alert_popup.reopen)
 visible=[];last_view=None;refresh_timer=None;row_notes={};group_members={}
 def schedule_refresh(delay=1500):
  nonlocal refresh_timer
  if refresh_timer is not None:root.after_cancel(refresh_timer)
  refresh_timer=root.after(delay,refresh)
 pages['task_search'].trace_add('write',lambda *args:schedule_refresh(100))
 pages['task_filter'].trace_add('write',lambda *args:schedule_refresh(100))
 def selected():
  ids=view.selection()
  return next((t for t in visible if ids and (t['id']==ids[0] or t['id'] in group_members.get(ids[0],()))),None)
 def refresh():
  nonlocal visible,last_view,refresh_timer,row_notes,group_members
  if refresh_timer is not None:root.after_cancel(refresh_timer);refresh_timer=None
  if not store.lock.acquire(blocking=False):
   set_connection('后台正在保存/校验素材，界面稍后自动刷新');schedule_refresh(300);return
  try:visible=[dict(t) for t in store.tasks];image_snapshot=[dict(j) for j in store.image_jobs.jobs];reason=store.queue_reason();plugin_online=time.time()-store.client.get('last_seen',0)<75
  finally:store.lock.release()
  from ui_state import task_summary,matches,task_bucket,partition_task_rows
  from pipeline_status import stage,group_summary
  import os
  merchant=os.environ.get('OZON_CLIENT_ID','');connection_summary=('店铺 '+merchant if merchant else 'Ozon未连接')+' · 插件'+('在线' if plugin_online else '待连接')+' · COS'+('已配置' if (DATA/'hosting'/'config.json').exists() else '待配置')+' · 定价来源'+('已配置' if all((DATA/'pricing'/(name+'.json')).exists() for name in ('ogl','commissions','fx')) else '待配置')
  set_connection(connection_summary+' | '+reason,reason if len(str(reason))>120 else '')
  try:fx=read_pricing(pricing.root/'fx.json');fx_note=' | '+fx['date']+'：1元='+fx['rub_per_cny']+'卢布'
  except (OSError,ValueError,KeyError):fx_note=''
  pricing_label.configure(text='自动定价：'+pricing.status+fx_note);hosting_label.configure(text='图片托管：'+hosting.status);video_label.configure(text='视频托管：'+video_hosting.status)
  jobs=[j for j in publication.jobs() if j.get('account_id')==merchant];groups={};snapshot=[];alert_bundles=[];stage_map={};competitor_states={}
  from competitor_flow import describe as competitor_describe,group_label as competitor_group_label
  for task in visible:
   try:bundle=read_pricing(DATA/'products'/task['sku']/'listing_bundle.json')
   except (OSError,ValueError):bundle={}
   if bundle and task['state']!='cancelled':alert_bundles.append(bundle)
   group_owner=next((t for t in visible if t['sku']==task.get('copy_leader',task['sku'])),task)
   competitor_states[task['id']]=competitor_describe(bundle,{**task,'competitor_wait':group_owner.get('competitor_wait')})
   state=stage(task,bundle,jobs,image_snapshot);stage_map[task['id']]=state;row=(task['sku'],str(len(task.get('received_images') or []))+'/8',bundle.get('price_cny') or '—',str((bundle.get('hosting') or {}).get('verified_images',0))+'/8 · '+('视频✓' if (bundle.get('video_hosting') or {}).get('state')=='done' else '视频…'),competitor_states[task['id']]['label'],state)
   if not matches(task,pages['task_search'].get(),pages['task_filter'].get(),image_snapshot,stage_map):continue
   group=str(task.get('base_article') or task.get('copy_leader') or task['sku']);groups.setdefault(group,[]).append((task,row));snapshot.append((task['id'],group,row))
  for key,value in task_summary(visible,image_snapshot,stage_map).items():pages['metrics'][key].configure(text=str(value))
  pages['task_results'].configure(text=('显示 '+str(len(snapshot))+' 个变体 · '+str(len(groups))+' 个商品组') if snapshot else ('当前没有需要人工核对或修正的任务。' if pages['task_filter'].get()=='需处理' else '没有匹配的任务，可清除筛选查看全部。' if visible else '还没有制作任务，请前往“商品制作”创建第一组商品。'))
  row_notes={k:v+'\n'+competitor_states[k]['detail'] for k,v in stage_map.items()}
  active_groups,published=partition_task_rows(groups)
  group_members={'group:'+group:[t['id'] for t,row in items] for group,items in active_groups.items()}
  for group,items in active_groups.items():row_notes['group:'+group]=group_summary([row[-1] for t,row in items])+'；展开后查看本组当前任务。'
  if published:row_notes['archive:published']='已上架 '+str(len(published))+' 个变体；展开可查看商品、预览与原有素材。当前重做或待处理任务会显示在上方。'
  if snapshot:pages['task_results'].configure(text='显示 '+str(len(snapshot))+' 个变体 · 当前任务 '+str(len(snapshot)-len(published))+' · 已上架 '+str(len(published))+'（归档栏目）')
  view_key=(pages['task_filter'].get(),pages['task_search'].get(),snapshot)
  if view_key!=last_view:
   selection=view.selection();position=view.yview()[0];expanded={i:view.item(i,'open') for i in view.get_children()};view.delete(*view.get_children())
   for group,items in active_groups.items():
    key='group:'+group;group_members[key]=[t['id'] for t,row in items]
    stages=[row[-1] for task,row in items];row_notes[key]=group_summary(stages)+'；展开后查看本组当前任务。'
    view.insert('','end',iid=key,text=group,values=(str(len(items))+' 个变体','','','',competitor_group_label([competitor_states[t['id']] for t,row in items]),group_summary(stages)),open=True if pages['task_filter'].get()!='全部任务' else expanded.get(key,True),tags=('group',))
    for n,(task,row) in enumerate(items):
     tag='attention' if task_bucket(task,image_snapshot,stage_map)=='需处理' else 'even' if n%2==0 else 'odd'
     view.insert(key,'end',iid=task['id'],text='',values=row,tags=(tag,))
   if published:
    archive='archive:published';row_notes[archive]='已上架 '+str(len(published))+' 个变体；展开可查看商品、预览与原有素材。当前重做或待处理任务会显示在上方。'
    view.insert('','end',iid=archive,text='已上架',values=(str(len(published))+' 个变体','','','','','展开查看历史商品'),open=bool(pages['task_search'].get().strip()) or pages['task_filter'].get()=='已上架' or expanded.get(archive,False),tags=('archive',))
    for group,task,row in published:view.insert(archive,'end',iid=task['id'],text=group,values=row,tags=('published',))
   if selection and view.exists(selection[0]):view.selection_set(selection[0])
   view.yview_moveto(position);last_view=view_key
  if not test_mode:
   if not store.lock.acquire(blocking=False):schedule_refresh(300);return
   try:alert_jobs=[dict(j) for j in store.image_jobs.jobs];plugin=dict(store.plugin_status);paused=bool(store.control.get('paused'));client=dict(store.client)
   finally:store.lock.release()
   live={t['sku'] for t in visible if t['state']!='cancelled'};current_jobs=[]
   for j in jobs:
    items=j.get('items')
    if isinstance(items,dict):
     subset={sku:row for sku,row in items.items() if sku in live}
     if subset:current_jobs.append({**j,'items':subset})
    elif live:current_jobs.append(j)
   if plugin.get('sku') and plugin['sku'] not in live:plugin={}
   alerts=collect_alerts(visible,alert_bundles,current_jobs,alert_jobs,plugin)+alert_watch.update(visible,client,paused)
   if any(word in pricing.status for word in ('更新失败','补查失败')):alerts.append(make_alert('自动定价','定价来源',pricing.status))
   alert_popup.update(alerts)
  schedule_refresh(1500)
 def delete():
  task=selected()
  if not task:return
  try:
   ids=view.selection();targets=[t for t in visible if t['id'] in group_members.get(ids[0],())] if ids and ids[0] in group_members else [task]
   job=publication.active([t['sku'] for t in targets])
   if job:publication.cancel_followup(job['id'])
   with store.lock:store.delete_tasks([t['id'] for t in targets])
  except Exception as e:show_task_error('未删除',str(e))
 def pricing_details(task=None):
  task=task or selected()
  if not task:return
  path=DATA/'products'/task['sku']/'listing_bundle.json'
  if not path.exists():messagebox.showinfo('定价','等待素材完成及草稿创建');return
  bundle=read_pricing(path);cached=lookup(root,('price_details',str(path.resolve())))
  if cached is not None:return cached
  dialog=remember(root,('price_details',str(path.resolve())),tk.Toplevel(root));dialog.title(task['sku']+' 售价明细');dialog.geometry('780x600')
  text=tk.Text(dialog,wrap='word');text.pack(fill='both',expand=True)
  result=None;rendered=None
  def render_details():
   nonlocal bundle,result,rendered
   fresh=read_pricing(path)
   if fresh==rendered:return
   bundle=fresh;rendered=fresh
   position=text.yview()[0]
   text.configure(state='normal');text.delete('1.0','end')
   result=(bundle.get('manual_pricing') if bundle.get('manual_price') else bundle.get('auto_pricing'))
   if result and result.get('valid') is False:
    text.insert('end','手动价无适用物流方案：'+result.get('message','')+'\n');result=None
   category=bundle.get('category') or {}
   text.insert('end',bundle.get('pricing_status','等待定价')+'\n类目状态：'+bundle.get('category_match_status','尚未推荐')+'\n')
   if category.get('type_id'):
    text.insert('end','官方商品类型：'+str(category.get('name') or '未返回名称')+'（ID '+str(category['type_id'])+'）\n')
   if '佣金表未找到' in str(bundle.get('pricing_status','')):
    text.insert('end','\n需要处理：该官方类型在本地 rFBS 佣金表中没有精确同名行。请在下方选择一条佣金表行并确认；系统不会自动采用较低费率。\n')
   if result:
    text.insert('end',('实际手动售价：¥' if bundle.get('manual_price') else '自动建议售价：¥')+result['price_cny']+'\n预计净利润：¥'+result['profit_cny']+'\n预计净利率：'+format(float(result['net_margin'])*100,'.2f')+'%\n物流渠道：'+result['logistics_tier']+'\n')
    labels={'product_cost':'每套成本（含国内运费）','ogl_transport':'OGL运输','label':'贴单','commission':'rFBS佣金','last_mile':'尾程','withdrawal':'提现','acquiring':'收单'}
    for key,value in result['fees_cny'].items():text.insert('end',labels.get(key,key)+'：¥'+value+'\n')
    text.insert('end','\n参考汇率：'+result['fx']['rub_per_cny']+' RUB/CNY\n日期：'+result['fx']['date']+'\n来源：'+result['fx'].get('url','')+'\n佣金版本：'+result['commission_version']+'\n'+result['commission_source']+'\n运费来源：'+result['logistics_source']+'\n'+result.get('boundary_policy_note','')+'\n\n以上为参考汇率下的估算，实际结算与运输账单可能不同。')
   text.configure(state='disabled');text.yview_moveto(position)
  render_details()
  def select_type():
   try:
    cfg=read_pricing(pricing.root/'commissions.json')
    from category_search import commission_options,commission_suggestions
    cached=lookup(dialog,('commission_picker',str(path.resolve())))
    if cached is not None:return cached
    picker=remember(dialog,('commission_picker',str(path.resolve())),tk.Toplevel(dialog));picker.title('中文搜索官方佣金类型');picker.geometry('1100x520');picker.minsize(850,420)
    official=(read_pricing(path).get('category') or {}).get('name','')
    ttk.Label(picker,text='当前 Ozon 官方类型：'+(official or '尚未确认')+'\n以下仅为候选佣金行，必须由你确认后才会用于 rFBS 定价；不判断 FBP。确认后，同一官方商品类型会自动沿用该映射；佣金表更新时才要求复核。',justify='left').pack(pady=6)
    query=tk.StringVar();entry=ttk.Entry(picker,textvariable=query,width=70);entry.pack(pady=4);entry.focus_set()
    frame=ttk.Frame(picker);frame.pack(fill='both',expand=True,padx=8)
    cols=('zh','ru','category','low','mid','high')
    box=ttk.Treeview(frame,columns=cols,show='headings',selectmode='browse')
    for col,label,width in [('zh','中文类型',210),('ru','俄文原名',230),('category','所属类目（中文）',230),('low','≤1500卢布',100),('mid','1500.01–5000卢布',140),('high','>5000卢布',100)]:
     box.heading(col,text=label);box.column(col,width=width,anchor='center',stretch=True)
    scroll=ttk.Scrollbar(frame,orient='vertical',command=box.yview);scroll.pack(side='right',fill='y');box.configure(yscrollcommand=scroll.set);box.pack(fill='both',expand=True)
    count=ttk.Label(picker);count.pack(pady=4);choices={}
    def rows_for_query():
     return commission_options(cfg,query.get()) if query.get().strip() else commission_suggestions(cfg,official)
    def filter_names(*args):
     nonlocal choices
     box.delete(*box.get_children());choices={str(r['source_row']):r for r in rows_for_query()}
     for iid,row in choices.items():
      rates=[format(float(rate)*100,'.2f')+'%' for rate in row['rates']]
      box.insert('','end',iid=iid,values=(row.get('type_zh') or '暂无官方中文',row['type_ru'],row.get('category_zh') or row.get('category_ru',''),*rates))
     count.configure(text=('候选 ' if not query.get().strip() else '搜索匹配 ')+str(len(choices))+' 项；佣金表版本：'+cfg.get('effective_note',''))
    query.trace_add('write',filter_names);filter_names()
    def apply():
     if not box.selection():messagebox.showinfo('请选择','先选择一项商品类型',parent=picker);return
     type_id=(read_pricing(path).get('category') or {}).get('type_id')
     if not type_id:show_task_error('尚未匹配上架类目','请先点击下方入口匹配并确认上架类目，再选择佣金类型。',parent=picker);return
     row=choices[box.selection()[0]]
     pricing.map_type(type_id,row['type_ru'],row['source_row'],cfg['sha256'],official);picker.destroy()
     threading.Thread(target=pricing.calculate_all,daemon=True).start()
    # Double-click is the fast confirmation path.  ``after_idle`` lets the
    # Treeview finish selecting the clicked row before ``apply`` reads it.
    box.bind('<Double-1>',lambda event:picker.after_idle(apply))
    box.bind('<Return>',lambda event:apply())
    actions=ttk.Frame(picker,padding=(8,6));actions.pack(side='bottom',fill='x')
    ttk.Button(actions,text='确认所选类型及该行佣金',style='Primary.TButton',command=apply).pack(side='left',fill='x',expand=True,padx=(0,4))
    ttk.Button(actions,text='修改上架类目',command=lambda:category_editor(task)).pack(side='left',padx=(4,0))
   except Exception as e:show_task_error('无法选择',str(e))
  def refresh_details():
   dialog.destroy();pricing_details(task)
  def update_details():
   if not dialog.winfo_exists():return
   try:
    render_details()
   except (OSError,ValueError):pass
   dialog.after(1500,update_details)
  update_details()
  commission_missing='佣金表未找到' in str(bundle.get('pricing_status',''))
  # Keep the blocking action outside the price text. On small Windows
  # displays stacked controls used to be pushed below the dialog.
  actions=ttk.Frame(dialog,padding=(10,8));actions.pack(side='bottom',fill='x')
  ttk.Label(actions,text='估算售价自动采用；请在整组预览核对数据。',style='Status.TLabel').grid(row=0,column=0,columnspan=3,sticky='w',pady=(0,5))
  ttk.Button(actions,text=('立即匹配 rFBS 佣金行（需要确认）' if commission_missing else '查看 / 修改 rFBS 佣金类型'),style='Primary.TButton' if commission_missing else 'TButton',command=select_type).grid(row=1,column=0,sticky='ew',padx=(0,5))
  ttk.Button(actions,text='修改上架类目',command=lambda:category_editor(task)).grid(row=1,column=1,sticky='ew',padx=5)
  ttk.Button(actions,text='刷新',command=refresh_details).grid(row=1,column=2,sticky='ew',padx=(5,0))
  actions.columnconfigure(0,weight=3);actions.columnconfigure(1,weight=2);actions.columnconfigure(2,weight=1)
 task_more.add_command(label='查看所选变体售价明细 / 佣金类型',command=pricing_details)
 ttk.Button(task_actions,text='匹配 rFBS 佣金',command=pricing_details).pack(side='left',padx=4)
 task_more.add_command(label='删除选中本地记录（保留平台商品）',command=delete)
 def recollect():
  task=selected()
  if not task:return
  with store.lock:store.set_paused(True)
  deadline=time.time()+75
  def ready():
   with store.lock:
    leader=task.get('copy_leader',task['sku']);group=[t for t in store.tasks if t.get('copy_leader',t['sku'])==leader]
    waiting=any(t.get('pause_requested') and not t.get('pause_ack') or t['sku'] in store.video_running for t in group+store.image_jobs.active([t['sku'] for t in group]))
   if waiting:
    if time.time()<deadline:root.after(1000,ready);return
    show_task_error('采集等待中','插件尚未确认停止或旧视频仍在处理；原文件保留。请保持插件已连接后重试。');return
   try:
    with store.lock:store.recollect(task['id'])
   except Exception as e:show_task_error('未重新采集',str(e))
  ready()
 task_more.add_command(label='备份并自动采集已有图片（不重新作图）',command=recollect)

 def approve():
  task=selected()
  if not task:return
  with store.lock:
   t=store.find(task['id'])
   if t['state']!='review':messagebox.showinfo('提示','仅可确认已保存并待审核的图片。异常请先在网页处理。');return
   t['state']='approved';store.save()

 def retry():
  task=selected()
  if not task:return
  if not messagebox.askyesno('检查网页后恢复','请先在扩展中暂停并刷新ChatGPT。确认此任务没有发送、没有生成结果，才重新排队。是否确认？'):return
  try:
   with store.lock:store.retry(task['id'])
  except Exception as e:show_task_error('未恢复',str(e))
 task_more.add_command(label='所选异常任务未发送，重新排队',command=retry)
 def cancel_product():
  task=selected()
  if not task:return
  product=task['sku']
  if not messagebox.askyesno('取消商品任务',f'取消 {product} 的剩余任务？已有图片和视频不会删除。请先停止扩展自动批次。'):return
  try:
   with store.lock:store.cancel_product(product)
  except Exception as e:show_task_error('未取消',str(e))
 task_more.add_command(label='取消所选商品剩余任务（保留文件）',command=cancel_product)
 def listing():
  from listing_bundle import prepare
  import os
  task=selected()
  if not task:return
  try:
   task=selected()
   target=DATA/'products'/task['sku']/'listing_bundle.json'
   if not target.exists():target=prepare(DATA/'products'/task['sku'],task)
   messagebox.showinfo('草稿已准备',str(target)+'\n已保留素材与主图顺序；尚未提交Ozon。')
   if os.name=='nt':os.startfile(str(target.parent))
  except Exception as e:show_task_error('未准备',str(e))
 task_more.add_command(label='打开本地商品文件夹',command=listing)
 def listing_editor():
  task=selected()
  if not task:return
  folder=DATA/'products'/task['sku'];path=folder/'listing_bundle.json'
  for key in list(getattr(root,'_ozon_windows',{})):
   if isinstance(key,tuple) and len(key)==2 and key[0]=='group_preview' and str(path.resolve()) in key[1]:
    cached=lookup(root,key)
    if cached is not None:return cached
  if not path.exists():messagebox.showinfo('等待草稿','请先等待素材和文案完成');return
  from category_match import group_key
  from group_editor import open_editor
  if not store.lock.acquire(blocking=False):
   connection.configure(text='后台正在更新共用素材，整组预览将在保存完成后打开；其他按钮仍可操作')
   root.after(250,listing_editor);return
  try:
   current=read_pricing(path)
   if not isinstance(current,dict):show_task_error('草稿无效','当前草稿不是JSON对象，请检查本地文件；原文件保留。');return
   key=group_key(current);folders=[]
   for item in store.tasks:
    target=DATA/'products'/item['sku']/'listing_bundle.json'
    if item.get('set_mode') and item['state']!='cancelled' and target.exists():
     try:candidate=read_pricing(target)
     except (OSError,ValueError):continue
     if isinstance(candidate,dict) and group_key(candidate)==key:folders.append(target.parent)
  finally:store.lock.release()
  def show_price(index=0):
   with store.lock:item=next((dict(t) for t in store.tasks if t['sku']==folders[index].name),None)
   if item:pricing_details(item)
  return open_editor(root,folder,attributes,folders,lambda:category_editor(task),show_price,connect_category,pricing=pricing,store=store,publication=publication,hosting=hosting)
 def restart_competitor_selected():
  ids=view.selection();task=selected()
  if not ids or not task:
   messagebox.showinfo('请选择','请先选中一个商品组或具体变体',parent=root);return
  try:
   with store.lock:
    if ids[0] in group_members:
     key=ids[0][len('group:'):];targets=[t['sku'] for t in store.tasks if str(t.get('base_article') or t.get('copy_leader') or t['sku'])==key]
    else:targets=[task['sku']]
   from competitor_reference import restart
   result=restart(store,targets)
   set_task_note('已重启竞品采集：'+('、'.join(result['restarted']) or '无可重启变体')+('；链接不可用或尚无草稿：'+'、'.join(result['skipped']) if result['skipped'] else '')+'。已填写参数保留。')
   schedule_refresh(100)
  except Exception as exc:messagebox.showerror('竞品采集未重启',str(exc),parent=root)
 ttk.Button(task_actions,text='重启竞品采集',command=restart_competitor_selected).pack(side='left',padx=4)
 ttk.Button(task_actions,text='打开整组预览',style='Primary.TButton',command=listing_editor).pack(side='left',padx=4)
 view.bind('<Double-1>',lambda e:listing_editor())
 def change_pause(paused):
  if not store.lock.acquire(blocking=False):
   connection.configure(text='后台正在保存素材，完成后自动应用'+('暂停' if paused else '继续')+'操作');root.after(150,lambda:change_pause(paused));return
  try:store.set_paused(paused)
  finally:store.lock.release()
 def pause_making():change_pause(True)
 def resume_making():change_pause(False)
 ttk.Button(task_actions,text='暂停制作',command=pause_making).pack(side='left',padx=4)
 ttk.Button(task_actions,text='继续制作',style='Primary.TButton',command=resume_making).pack(side='left',padx=4)
 restart_pending=False
 def restart_current_queue():
  nonlocal restart_pending
  if restart_pending:return
  task=selected();ids=view.selection()
  if not task:return
  if not ids or ids[0].startswith('group:'):
   messagebox.showinfo('请选择具体变体','请展开商品组，选择需要重启的具体变体行。',parent=root);return
  from queue_restart import choose,ready,restart
  restart_pending=True;connection.configure(text='正在后台准备重启 '+task['sku']+'；等待插件停止确认并备份素材')
  def finish(error=None,result=None):
   nonlocal restart_pending
   restart_pending=False
   if error:show_task_error('未重启队列',error);return
   connection.configure(text='已重启 '+result['sku']+'，等待插件接收并自动执行后续队列')
   def select_new():
    if view.exists(result['id']):view.selection_set(result['id']);view.see(result['id'])
   root.after(1800,select_new)
  def work():
   try:
    with store.lock:
     target=choose(store,task['id']);skus=[t['sku'] for t in target['targets']] if target.get('image_job') else [target['sku']]
     if publication.active(skus):raise ValueError('该条仍有上架任务跟进中，请先在上架进度停止跟进')
     store.set_paused(True)
    deadline=time.time()+90
    while True:
     with store.lock:target=choose(store,task['id']);waiting=not ready(store,target)
     if not waiting:break
     if time.time()>deadline:raise ValueError('插件尚未确认暂停或视频仍在处理，原队列与文件保留')
     time.sleep(.3)
    with store.lock:result=restart(store,task['id'])
    root.after(0,lambda:finish(result=result))
   except Exception as error:root.after(0,lambda error=str(error):finish(error=error))
  threading.Thread(target=work,daemon=True).start()
 ttk.Button(task_actions,text='重启本条队列',command=restart_current_queue).pack(side='left',padx=4)
 task_more.add_command(label='重启本条队列（备份后重新制作并自动继续）',command=restart_current_queue)
 def rebuild_assets():
  task=selected()
  if not task:return
  if publication.active([task['sku']]):messagebox.showinfo('正在上架','请先在上架进度页停止跟进，再手动更新素材。');return
  try:
   with store.lock:stamp=store.rebuild_group(task['sku'])
   messagebox.showinfo('已排队更新','整组旧素材已备份。请保持插件开始状态，将按最新参数重新制作本组图片及视频。')
  except Exception as exc:show_task_error('未启动更新',str(exc))
 task_more.add_command(label='手动更新本组素材（先备份）',command=rebuild_assets)

 def retry_video():
  task=selected()
  if not task:return
  if len(task.get('received_images',[]))!=8:messagebox.showinfo('等待图片','8张图片完整后才能重新合成视频');return
  threading.Thread(target=store.render_video,args=(task['sku'],),daemon=True).start()
  video_hosting.retry_at.clear();video_hosting.wake.set()
 task_more.add_command(label='重新合成所选变体8秒视频并自动托管',command=retry_video)
 def connect_category():
  import os
  cached=lookup(root,('ozon_connection',))
  if cached is not None:return cached
  dialog=remember(root,('ozon_connection',),tk.Toplevel(root));dialog.title('连接Ozon API与类目匹配')
  ttk.Label(dialog,text='填写店铺API连接；读取类目、仓库和状态。只有点击提交才写入商品。\n可使用Windows加密保存密钥；切换店铺会隔离任务和仓库配置。').pack(padx=12,pady=8)
  client=tk.StringVar(value=os.environ.get('OZON_CLIENT_ID',''));key=tk.StringVar(value=os.environ.get('OZON_API_KEY',''))
  ttk.Label(dialog,text='Client-Id').pack();ttk.Entry(dialog,textvariable=client,width=55).pack()
  ttk.Label(dialog,text='Api-Key').pack();ttk.Entry(dialog,textvariable=key,show='*',width=55).pack()
  remember_api=tk.BooleanVar(value=os.name=='nt')
  ttk.Checkbutton(dialog,text='在当前Windows用户加密记住Ozon API，重启后自动连接',variable=remember_api,state='normal' if os.name=='nt' else 'disabled').pack(pady=5)
  status=ttk.Label(dialog,text='已有类目和已确认的手动修改将保留');status.pack(pady=6)
  def connect():
   if not client.get().strip() or not key.get().strip():show_task_error('未连接','请填写Client-Id和Api-Key',parent=dialog);return
   try:
    from ozon_connection import save as save_ozon
    save_ozon(DATA,client.get(),key.get(),remember_api.get(),store_lock=store.lock)
    publication.resume_account(client.get().strip())
   except (OSError,ValueError) as exc:show_task_error('API连接未保存',str(exc),parent=dialog);return
   button.configure(state='disabled');status.configure(text='正在补查所有未匹配商品组，请稍候…')
   def work():
    try:
     from category_match import repair_groups
     repair_groups(DATA/'products',store.lock);pricing.calculate_all();attributes.retry_at.clear();attributes.wake.set()
     root.after(0,lambda:status.configure(text='补查完成；请打开类目窗口确认。失败原因显示在各商品类目状态中。'))
    except Exception:root.after(0,lambda:status.configure(text='匹配未完成，请检查连接后重试；已有素材保留。'))
    finally:root.after(0,lambda:button.configure(state='normal'))
   threading.Thread(target=work,daemon=True).start()
  button=ttk.Button(dialog,text='连接并补查未匹配商品',command=connect);button.pack(pady=8)
 ttk.Button(account_panel,text='连接Ozon API / 店铺设置',command=connect_category).pack(pady=4)
 def category_editor(task=None):
  task=task or selected()
  if not task:return
  path=DATA/'products'/task['sku']/'listing_bundle.json'
  if not path.exists():show_task_error('提示','请等待生成上架草稿');return
  data=json.loads(path.read_text(encoding='utf-8-sig'));cached=lookup(win,('category_edit',str(path.resolve())))
  if cached is not None:return cached
  dialog=remember(win,('category_edit',str(path.resolve())),tk.Toplevel(win));dialog.title('类目确认/修改')
  ttk.Label(dialog,text=data.get('category_match_status','尚未推荐；可手动填写官方类目与类型ID')).pack()
  candidates=data.get('category_candidates') or [];current=data.get('category') or {}
  if current.get('type_id') and not any(x.get('type_id')==current['type_id'] for x in candidates):candidates=[dict(current,path=current.get('path') or current.get('name') or str(current['type_id']))]+candidates
  from category_search import category_label
  try:commission_config=read_pricing(pricing.root/'commissions.json')
  except (OSError,ValueError):commission_config={}
  choice=ttk.Combobox(dialog,values=[category_label(c,commission_config) for c in candidates],width=80,state='readonly');choice.pack()
  cat=tk.StringVar(value=str(current.get('description_category_id') or ''));typ=tk.StringVar(value=str(current.get('type_id') or ''))
  ttk.Label(dialog,text='类目ID（可手动修改）').pack();ttk.Entry(dialog,textvariable=cat).pack();ttk.Label(dialog,text='商品类型ID').pack();ttk.Entry(dialog,textvariable=typ).pack()
  def pick(e):
   c=candidates[choice.current()];cat.set(str(c['description_category_id']));typ.set(str(c['type_id']))
  choice.bind('<<ComboboxSelected>>',pick)
  def confirm():
   try:
    c=int(cat.get());t=int(typ.get())
    if min(c,t)<=0:raise ValueError('ID须为正整数')
    from category_match import confirm_group
    category={**next((x for x in candidates if x['description_category_id']==c and x['type_id']==t),{}),'description_category_id':c,'type_id':t}
    confirm_group(path.parent,category,apply_group=apply_group.get(),lock=store.lock)
    threading.Thread(target=pricing.calculate_all,daemon=True).start()
    dialog.destroy()
   except Exception as e:show_task_error('未保存',str(e))
  apply_group=tk.BooleanVar(value=True)
  ttk.Checkbutton(dialog,text='同时应用于同组尚未确认的变体（保留已单独确认的类目）',variable=apply_group).pack(pady=6)
  ttk.Button(dialog,text='连接Ozon API / 重新匹配类目',command=connect_category).pack(pady=4)
  ttk.Button(dialog,text='确认此类目（发布前仍核验必填属性）',command=confirm).pack()
 





 refresh()
 def close():pricing_stop.set();hosting.wake.set();video_hosting.wake.set();attributes.wake.set();publication.wake.set();(http.shutdown() if http else None);root.destroy();instance.release()
 root.protocol('WM_DELETE_WINDOW',close)
 if on_ready:on_ready(root,{'store':store,'notebook':notebook,'pages':pages,'view':view,'open_preview':listing_editor,'creation_grid':grid,'close':close,'visual_plan':choose_visual_plan,'creation_category':choose_creation_category,'category_selection':category_selection,'shared_preview':preview_shared,'shared_choose':choose_shared,'create':create})
 root.mainloop()
if __name__=='__main__':main()
