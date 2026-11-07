"""Loopback-only authenticated bridge. Does not read Edge cookies or send Ozon writes."""
import base64,hashlib,hmac,io,json,re,secrets,threading,time
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
  self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True);self.lock=threading.Lock();self.client={};self.download_tickets={};self.path=self.folder/'tasks.json';self.tasks=json.loads(self.path.read_text(encoding='utf-8-sig')) if self.path.exists() else []
  for t in self.tasks:
   if t['state'] in ('claimed','sending','waiting'):t['state']='needs_attention';t['message']='服务重启，请检查网页后人工处理'
   if t.get('copy_state')=='running':t['copy_state']='needs_attention';t['message']='文案任务被重启中断，请保存网页现有结果'
  self.save()
  self.sync_shared_copies()
 def save(self):
  temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(self.tasks,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(self.path)
 def create(self,sku,facts,references=None):
  if not valid_article(sku):raise ValueError('货号格式无效')
  if not facts.strip() or len(facts)>20000:raise ValueError('商品资料为空或过长')
  if any(t['sku']==sku for t in self.tasks):raise ValueError('SKU已经存在，避免重复建立任务')
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
  task['prompt']='请一次完成8张独立的Ozon商品图片，必须是8个独立图片文件，不要拼图，不要把8个画面合成一张。按顺序输出：'+ '；'.join(f'{i+1}. {brief}' for i,(_,brief) in enumerate(TASKS))+ '。请直接交付8张独立图片及各自下载入口，不要提供ZIP。文件须按01_至08_编号，01_为主图，不得混入原始参考图。第1张是商品主图，展示真实销售数量。每张3:4竖版，自然俄文，风格一致，保持原图外观。严禁虚构尺寸、材质、配件和功能，包装尺寸不能当作商品尺寸。商品事实：'+facts
  self.tasks=[t for t in self.tasks if t['sku']!=sku]+[task];self.save()
 def resume_unsent_upload(self):
  count=0
  for task in self.tasks:
   if task['state']=='needs_attention' and not task.get('received_images') and task.get('message')=='未找到图片上传控件，已暂停，未发送任务':
    task.update(state='queued',message='上传适配已更新，恢复尚未发送的任务');count+=1
  self.save();return {'resumed':count}
 def blockers(self):
  return [{'id':t['id'],'sku':t['sku'],'state':t['state'],'copy_state':t.get('copy_state'),'message':t.get('message','')} for t in self.tasks if t['state'] in ('claimed','sending','waiting','needs_attention','review') or t.get('copy_state') in ('running','needs_attention')]
 def queue_reason(self):
  blockers=self.blockers()
  if blockers:
   t=blockers[0];return '前序任务 '+t['sku']+' 尚未完成：'+t.get('message','')
  if time.time()-self.client.get('last_seen',0)>75:return '等待扩展连接：请保存配对码，并绑定当前ChatGPT标签'
  if not self.client.get('auto_enabled'):return '扩展已连接，但自动批次未启用'
  return '扩展已连接，等待下一次轮询领取（最长约30秒）'
 def task_status(self,tid):
  task=next((t for t in self.tasks if t['id']==tid),None)
  if not task:return {'found':False}
  return {'found':True,'id':task['id'],'sku':task['sku'],'state':task['state'],'copy_state':task.get('copy_state'),'saved_count':len(task.get('received_images',[])),'expected_images':task.get('expected_images',8),'message':task.get('message','')}
 def recover(self,sku):
  group=[t for t in self.tasks if t['sku']==sku and t.get('set_mode') and t['state'] in ('waiting','needs_attention','claimed','sending')]
  if len(group)!=1:raise ValueError('没有唯一可恢复的整套任务，请核对货号')
  task=group[0];task.update(state='waiting',message='用户请求从现有网页恢复保存，不重新生成');self.save();return {'id':task['id'],'sku':task['sku'],'set_mode':True,'saved_count':len(task.get('received_images',[])),'expected_images':task.get('expected_images',8)}
 def set_result(self,tid,index,encoded):
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
  digest=hashlib.sha256(data).hexdigest()
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
  task.update(state='saved' if complete else 'waiting',message=f'已保存 {len(received)}/8 张独立图片');self.save()
  if complete:threading.Thread(target=self.render_video,args=(task['sku'],),daemon=True).start()
  return {'saved_count':len(received),'complete':complete}
 def repair_order(self,tid):
  import shutil
  task=self.find(tid)
  if not task.get('set_mode') or task['state'] not in ('waiting','claimed','sending','needs_attention'):raise ValueError('当前任务不允许自动重新采集')
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
  selected=self.find(tid);leader=selected.get('copy_leader',selected['sku'])
  group=[t for t in self.tasks if t.get('copy_leader',t['sku'])==leader]
  if any(t['state'] in ('claimed','sending','waiting') or t.get('copy_state')=='running' for t in group):raise ValueError('请先停止扩展自动批次，再备份并重新采集')
  stamp=time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)
  names=('images','video','image_manifest.json','listing_bundle.json','copy_prompt.txt')
  planned=[];affected=[]
  for task in group:
   folder=self.folder/'products'/task['sku']
   if not task.get('received_images') and not any((folder/name).exists() for name in names):continue
   affected.append(task);backup=folder/'recovery_backups'/stamp
   backup.mkdir(parents=True,exist_ok=False)
   (backup/'task.json').write_text(json.dumps(task,ensure_ascii=False,indent=2),encoding='utf-8')
   for name in names:
    src=folder/name
    if not src.exists():continue
    dst=backup/name
    if src.is_dir():shutil.copytree(src,dst)
    else:shutil.copy2(src,dst)
    planned.append(src)
  # Only remove live outputs once every backup completed successfully.
  for src in planned:
   if src.is_dir():shutil.rmtree(src)
   else:src.unlink()
  for task in affected:
   task.update(state='needs_attention',received_images=[],message='已备份旧素材；等待从网页重新采集生成图，不重新发送作图')
   task.pop('copy_state',None);task.pop('video',None)
  self.save();return stamp
 def claim(self):
  if any(t['state'] in ('claimed','sending','waiting','needs_attention','review') for t in self.tasks):raise ValueError('请先审核上一任务或处理异常，不能继续发送')
  t=next((t for t in self.tasks if t['state']=='queued'),None)
  if not t:raise ValueError('没有排队任务，请在本地窗口创建商品')
  t['state']='claimed';t['prompt']=t['prompt'].replace('。如以文件或ZIP交付，8张文件须按01_至08_编号，01_为主图，ZIP不得包含原始参考图。','。仅交付8张独立图片，按01_至08_编号。');t['prompt']+='\n交付要求：仅输出独立图片及逐张下载入口，不要打包，不提供ZIP或其他压缩包。';self.save();result=dict(t);result['references']=[{'name':r['name'],'mime':r['mime'],'purpose':r.get('purpose','variant_main'),'base64':base64.b64encode(Path(r['path']).read_bytes()).decode()} for r in t.get('references',[])];return result
 def find(self,tid):
  t=next((t for t in self.tasks if t['id']==tid),None)
  if not t:raise ValueError('任务不存在')
  return t
 def retry(self,tid):
  t=self.find(tid)
  if t['state']!='needs_attention':raise ValueError('仅可恢复异常任务')
  if any(x['state'] in ('claimed','sending','waiting') for x in self.tasks):raise ValueError('还有执行中的任务，请先暂停')
  t.update(state='queued',message='用户确认网页未发送后重新排队');self.save()
 def cancel_product(self,sku):
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
 def delete_task(self,tid):
  task=self.find(tid)
  if task['state'] in ('claimed','sending','waiting') or task.get('copy_state')=='running':raise ValueError('任务正在运行，请先停止后再删除')
  self.tasks=[t for t in self.tasks if t['id']!=tid];self.save()
 def sync_shared_copies(self):
  from listing_bundle import copy_complete,share_copy,prepare,copy_hash
  leaders={t.get('copy_leader',t['sku']) for t in self.tasks if t.get('set_mode')}
  for source in leaders:
   path=self.folder/'products'/source/'listing_bundle.json'
   if not path.exists():continue
   try:leader=json.loads(path.read_text(encoding='utf-8-sig'))
   except (ValueError,OSError):continue
   if not copy_complete(leader.get('copy')):
    for task in self.tasks:
     if task.get('copy_leader',task['sku'])==source and task.get('copy_state')=='done':task.pop('copy_state',None);task['message']='共用文案不完整，等待整组生成并同步'
    continue
   for task in self.tasks:
    if not task.get('set_mode') or task.get('copy_leader',task['sku'])!=source:continue
    folder=self.folder/'products'/task['sku'];target=folder/'listing_bundle.json'
    if task['state']!='saved' or not task.get('video'):continue
    try:
     if not target.exists():prepare(folder,task)
     current=json.loads(target.read_text(encoding='utf-8-sig'))
     if not copy_complete(current.get('copy')) or copy_hash(current['copy'])!=copy_hash(leader['copy']) or current.get('copy_source')!=source:
      share_copy(folder,source,leader['copy'])
     task['copy_state']='done';task['copy_source']=source
     task['message']='8图、视频、共用俄语文案及草稿已完成；文案来源：'+source+'；待上架审核'
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
 def next_copy(self):
  self.sync_shared_copies()
  for task in self.tasks:
   if task.get('set_mode') and task['state']=='saved' and task.get('video') and not task.get('copy_state'):
    from listing_bundle import prepare,copy_complete
    folder=self.folder/'products'/task['sku']
    if not (folder/'listing_bundle.json').exists():prepare(folder,task)
    if task.get('copy_leader') and task['copy_leader']!=task['sku']:continue
    bundle=json.loads((folder/'listing_bundle.json').read_text(encoding='utf-8-sig'))
    if copy_complete(bundle.get('copy')):task['copy_state']='done';self.save();continue
    return task
  return None
 def render_video(self,sku):
  from video import make_video
  with self.lock:group=sorted([dict(x) for x in self.tasks if x['sku']==sku],key=lambda x:x['name'])
  try:
   files=[x['file'] for x in group[0]['received_images']] if len(group)==1 and group[0].get('set_mode') else [x['file'] for x in group]
   output=make_video(files,self.folder/'products'/sku/'video'/'product_8s.mp4')
   with self.lock:
    for x in self.tasks:
     if x['sku']==sku:x.update(video=output,message='8张图片及8秒视频已完成，待上架前审核')
    from listing_bundle import refresh_assets
    refresh_assets(self.folder/'products'/sku)
    self.sync_shared_copies()
    self.save()
  except Exception as e:
   with self.lock:
    for x in self.tasks:
     if x['sku']==sku:x['message']='图片已保存，视频合成失败：'+str(e)[:160]
    self.save()


def server(store,token,port=8765):
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def reply(self,code,value):
   body=json.dumps(value,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
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
    with store.lock:
     if self.path=='/heartbeat':
      store.client={'last_seen':time.time(),'auto_enabled':bool(body.get('auto_enabled'))}
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
      active=bool(store.blockers())
      copy_task=store.next_copy() if not active else None
      value={'ready':not active and any(t['state']=='queued' and t.get('auto_batch') for t in store.tasks),'copy_sku':copy_task['sku'] if copy_task else None,'blocked_reason':store.queue_reason() if active else None,'blockers':store.blockers(),'summary':store.queue_summary()}
     elif self.path=='/copy-task':
      sku=body['sku']
      if not valid_article(sku):raise ValueError('货号格式无效')
      selected=next((t for t in store.tasks if t['sku']==sku),None)
      if not selected:raise ValueError('货号不存在')
      sku=selected.get('copy_leader',sku)
      group=[t for t in store.tasks if t.get('copy_leader',t['sku'])==sku]
      context={'group_facts':'\n'.join(t['sku']+'：'+t['facts'] for t in group),'group_variants':[{'sku':t['sku'],'facts':t['facts'],'variant_parameters':t.get('variant_parameters',{})} for t in group]}
      folder=store.folder/'products'/sku
      if not (folder/'listing_bundle.json').exists():raise ValueError('请先在本地准备上架草稿')
      from listing_bundle import copy_prompt_for
      (folder/'copy_prompt.txt').write_text(copy_prompt_for(context),encoding='utf-8')
      bundle_path=folder/'listing_bundle.json';bundle=json.loads(bundle_path.read_text(encoding='utf-8-sig'));bundle.update(context)
      temp=bundle_path.with_suffix('.tmp');temp.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(bundle_path)
      for task in store.tasks:
       if task['sku']==sku:task['copy_state']='running'
      store.save()
      marker='【OZON_COPY:'+secrets.token_hex(12)+'】'
      value={'id':'copy:'+sku,'sku':sku,'marker':marker,'prompt':marker+'\n'+'本次商品组文案保存货号：'+sku+'。只依据下列当前资料，不得沿用历史商品材质。主体材质与配件/内衬材质分别对应，不得混写，也不要因内衬含纸板就把主体写成纸板。输出JSON必须额外包含sku字段，值为'+sku+'。'+(folder/'copy_prompt.txt').read_text(encoding='utf-8')}
     elif self.path=='/copy-failed':
      sku=body['sku']
      for task in store.tasks:
       if task['sku']==sku:task.update(copy_state='needs_attention',message=str(body.get('message','文案保存待处理'))[:300])
      store.save();value={'ok':True}
     elif self.path=='/copy-result':
      from listing_bundle import save_copy
      sku=body['sku']
      if not valid_article(sku):raise ValueError('货号格式无效')
      value=save_copy(store.folder/'products'/sku,body['copy'])
      store.sync_shared_copies()
      from category_match import suggest
      threading.Thread(target=suggest,args=(store.folder/'products'/sku,),kwargs={'lock':store.lock},daemon=True).start()
      for task in store.tasks:
       if task['sku']==sku:task.update(copy_state='done',message='8图、视频、俄文文案及草稿已完成；待定价、类目和托管')
      store.save()
     elif self.path=='/recover':value=store.recover(body['sku'])
     elif self.path=='/claim':value=store.claim()
     elif self.path=='/set-result':value=store.set_result(body['task_id'],body['index'],body['image_b64'])
     elif self.path=='/result':value=store.result(body['task_id'],body['image_b64'])
     elif self.path=='/event':
      t=store.find(body['task_id']);state=body['state']
      if state not in ('sending','waiting','needs_attention') or t['state'] not in ('claimed','sending','waiting'):raise ValueError('状态变更无效')
      t.update(state=state,message=str(body.get('message',''))[:500]);store.save();value={'ok':True}
     else:return self.reply(404,{'error':'接口不存在'})
    self.reply(200,value)
   except Exception as e:self.reply(400,{'error':str(e)[:300],'code':getattr(e,'code',None)})
 return ThreadingHTTPServer(('127.0.0.1',port),Handler)

def main():
 import tkinter as tk
 from tkinter import ttk,messagebox,filedialog
 store=Store(DATA);token=secrets.token_urlsafe(32);http=server(store,token);threading.Thread(target=http.serve_forever,daemon=True).start()
 root=tk.Tk();root.title('Ozon Edge 本地服务 v0.26');root.geometry('1120x850')
 shell=ttk.Frame(root);shell.pack(fill='both',expand=True);shell.rowconfigure(0,weight=1);shell.columnconfigure(0,weight=1)
 canvas=tk.Canvas(shell,highlightthickness=0);canvas.grid(row=0,column=0,sticky='nsew')
 outer_scroll=ttk.Scrollbar(shell,orient='vertical',command=canvas.yview);outer_scroll.grid(row=0,column=1,sticky='ns');canvas.configure(yscrollcommand=outer_scroll.set)
 win=ttk.Frame(canvas);window=canvas.create_window((0,0),window=win,anchor='nw')
 win.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
 canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
 def wheel(event):
  if event.widget.winfo_class() not in ('Treeview','Entry','TEntry','Text'):canvas.yview_scroll(-int(event.delta/120),'units')
 root.bind_all('<MouseWheel>',wheel)

 ttk.Label(win,text='本地服务已启动。将配对码粘贴至 Edge 扩展；可在下方选择原图，扩展将附加到当前ChatGPT对话。').pack(pady=8)
 code=ttk.Entry(win,width=65);code.insert(0,token);code.pack()
 ttk.Label(win,text='基础货号（上架货号按变体自动加(1)、(2)…）').pack()
 base=tk.StringVar();ttk.Entry(win,textvariable=base,width=60).pack()
 from variants import VariantGrid
 shared_refs=[]
 shared_label=ttk.Label(win,text='共用详情图参考：未选择');shared_label.pack()
 def choose_shared():
  nonlocal shared_refs
  selected=list(filedialog.askopenfilenames(title='选择全组共用详情图参考',filetypes=[('Images','*.png *.jpg *.jpeg *.webp')]))
  if selected:shared_refs=selected;shared_label.configure(text=f'共用详情图参考：已选 {len(selected)} 张')
 ttk.Button(win,text='选择共用详情图参考（全组一次）',command=choose_shared).pack(pady=4)
 connection=ttk.Label(win,text='等待扩展连接：请保存配对码并绑定ChatGPT标签');connection.pack(pady=4)
 grid=VariantGrid(win,base)
 from pricing_service import PricingService,read as read_pricing
 pricing=PricingService(DATA,store.lock);pricing_stop=threading.Event()
 threading.Thread(target=pricing.worker,args=(pricing_stop,),daemon=True).start()
 pricing_label=ttk.Label(win,text='自动售价：等待导入定价来源');pricing_label.pack(pady=3)
 def pricing_settings():
  dialog=tk.Toplevel(root);dialog.title('自动定价设置与来源');dialog.geometry('760x470')
  info=tk.Text(dialog,height=13,wrap='word');info.pack(fill='both',expand=True,padx=10,pady=8)
  def show():
   info.delete('1.0','end')
   for name,label in [('ogl','OGL运输表'),('commissions','rFBS佣金表'),('fx','央行汇率')]:
    path=pricing.root/(name+'.json')
    if not path.exists():info.insert('end',label+'：未配置\n');continue
    value=read_pricing(path)
    text=(value.get('filename','')+' '+value.get('effective_note','')) if name!='fx' else value['rub_per_cny']+' RUB/CNY，日期 '+value['date']+'\n'+value['source']+' '+value['url']
    info.insert('end',label+'：'+text+'\n')
   info.insert('end','\nOGL边界已确认按表中文字：重量及货值按文字，三边之和含上限。\n售价单位人民币；利润率=净利润/售价。每套成本不乘套装件数。\n计入rFBS佣金、OGL运输、贴单1元、尾程2.2%、提现1.2%、收单2%。\n央行汇率仅作参考；显示的售价为估算，提交上架前确认。\n内置佣金下载为2025-12-01版本；如有更新，请导入新的官方表。')
  def run(action):
   def work():
    try:action();pricing.calculate_all();root.after(0,show)
    except Exception as e:root.after(0,lambda text=str(e):messagebox.showerror('定价来源更新失败',text,parent=dialog))
   threading.Thread(target=work,daemon=True).start()
  def choose(kind):
   path=filedialog.askopenfilename(parent=dialog,title='导入'+kind,filetypes=[('Excel','*.xlsx')])
   if path:run(lambda:pricing.import_ogl(path) if kind=='OGL' else pricing.import_commissions(path))
  ttk.Button(dialog,text='导入本地OGL计算表（一次配置）',command=lambda:choose('OGL')).pack(pady=3)
  ttk.Button(dialog,text='导入官方rFBS佣金表',command=lambda:choose('佣金')).pack(pady=3)
  ttk.Button(dialog,text='下载官方佣金表（2025-12-01版）',command=lambda:run(pricing.update_commissions)).pack(pady=3)
  ttk.Button(dialog,text='立即获取央行参考汇率',command=lambda:run(pricing.update_fx)).pack(pady=3)
  show()
 ttk.Button(win,text='自动定价设置 / 运费表 / 央行汇率',command=pricing_settings).pack(pady=3)
 def create():
  try:
   records=grid.records()
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
    except Exception:
     store.tasks=previous;store.save();raise
   messagebox.showinfo('已创建',f"已创建 {len(records)} 个变体；首变体生成主图及共用详情，其余只生成主图；详情图及文案共用。")
  except Exception as e:messagebox.showerror('未创建',str(e))
 ttk.Label(win,text='每个变体：01固定为独立主图；02—08沿用首变体的7张详情图').pack(pady=3)
 ttk.Button(win,text='创建全部变体并自动处理',command=create).pack(pady=6)
 view=ttk.Treeview(win,columns=('sku','progress','price','status'),show='headings',height=8,selectmode='browse')
 for key,label,width in [('sku','变体货号',180),('progress','进度',140),('price','售价估算（元）',140),('status','状态',460)]:view.heading(key,text=label,anchor='center');view.column(key,width=width,stretch=key=='status',anchor='center')
 view.pack(fill='both',expand=True,padx=15)
 visible=[]
 def selected():
  ids=view.selection()
  return next((t for t in visible if ids and t['id']==ids[0]),None)
 def refresh():
  nonlocal visible
  selection=view.selection()
  with store.lock:
   visible=[dict(t) for t in store.tasks];reason=store.queue_reason()
  connection.configure(text=reason)
  fx_note=''
  try:
   fx=read_pricing(pricing.root/'fx.json');fx_note=' | 俄罗斯央行 '+fx['date']+'：1元='+fx['rub_per_cny']+'卢布'
  except (OSError,ValueError,KeyError):pass
  pricing_label.configure(text='自动售价：'+pricing.status+fx_note)
  for item in view.get_children():view.delete(item)
  for task in visible:
   if task['state']=='queued':task['message']=reason
   price='等待草稿'
   path=DATA/'products'/task['sku']/'listing_bundle.json'
   try:
    bundle=read_pricing(path);price=bundle.get('price_cny') or '待补充'
   except (OSError,ValueError):pass
   sku,progress,status=task_view(task)
   view.insert('', 'end',iid=task['id'],values=(sku,progress,price,status))
  if selection and view.exists(selection[0]):view.selection_set(selection[0])
  win.after(1500,refresh)
 def delete():
  task=selected()
  if not task:return
  try:
   with store.lock:store.delete_task(task['id'])
  except Exception as e:messagebox.showerror('未删除',str(e))
 def pricing_details():
  task=selected()
  if not task:return
  path=DATA/'products'/task['sku']/'listing_bundle.json'
  if not path.exists():messagebox.showinfo('定价','等待素材完成及草稿创建');return
  bundle=read_pricing(path);dialog=tk.Toplevel(root);dialog.title(task['sku']+' 售价明细');dialog.geometry('780x600')
  text=tk.Text(dialog,wrap='word');text.pack(fill='both',expand=True)
  result=bundle.get('auto_pricing')
  text.insert('end',bundle.get('pricing_status','等待定价')+'\n')
  if result:
   text.insert('end','建议售价：¥'+result['price_cny']+'\n预计净利润：¥'+result['profit_cny']+'\n预计净利率：'+format(float(result['net_margin'])*100,'.2f')+'%\n物流渠道：'+result['logistics_tier']+'\n')
   labels={'product_cost':'每套成本（含国内运费）','ogl_transport':'OGL运输','label':'贴单','commission':'rFBS佣金','last_mile':'尾程','withdrawal':'提现','acquiring':'收单'}
   for key,value in result['fees_cny'].items():text.insert('end',labels.get(key,key)+'：¥'+value+'\n')
   text.insert('end','\n参考汇率：'+result['fx']['rub_per_cny']+' RUB/CNY\n日期：'+result['fx']['date']+'\n来源：'+result['fx'].get('url','')+'\n佣金版本：'+result['commission_version']+'\n'+result['commission_source']+'\n运费来源：'+result['logistics_source']+'\n'+result.get('boundary_policy_note','')+'\n\n以上为参考汇率下的估算，实际结算与运输账单可能不同。')
  text.configure(state='disabled')
  def select_type():
   try:
    cfg=read_pricing(pricing.root/'commissions.json')
    names=sorted({r['type_ru'] for r in cfg['records'] if r['brand'].casefold()=='all'})
    picker=tk.Toplevel(dialog);picker.title('选择佣金表中的商品类型')
    query=tk.StringVar();ttk.Entry(picker,textvariable=query,width=60).pack()
    box=tk.Listbox(picker,width=90,height=15,exportselection=False);box.pack()
    def filter_names(*args):
     box.delete(0,'end')
     for name in names:
      if query.get().casefold() in name.casefold():box.insert('end',name)
    query.trace_add('write',filter_names);filter_names()
    def apply():
     if not box.curselection():return
     type_id=bundle.get('category',{}).get('type_id')
     if not type_id:messagebox.showerror('未匹配','请先确认商品类目及类型');return
     pricing.map_type(type_id,box.get(box.curselection()[0]));picker.destroy()
     threading.Thread(target=pricing.calculate_all,daemon=True).start()
    ttk.Button(picker,text='确认该类型对应的官方佣金',command=apply).pack()
   except Exception as e:messagebox.showerror('无法选择',str(e))
  def confirm_price():
   try:
    pricing.calculate_all()
    with store.lock:
     latest=read_pricing(path)
     if not latest.get('auto_pricing'):raise ValueError('当前没有可确认的自动估算')
     if not latest.get('category',{}).get('confirmed'):raise ValueError('请先确认商品类目，再确认售价')
     latest['pricing_confirmed_fingerprint']=latest['pricing_fingerprint']
     latest['blockers']=[b for b in latest.get('blockers',[]) if b!='售价估算待确认']
     latest['pricing_status']='售价已确认'
     from pricing_service import write as write_pricing
     write_pricing(path,latest)
    messagebox.showinfo('已确认','已确认此变体售价；成本、类目、运费或汇率变化后需重新确认。',parent=dialog)
   except Exception as e:messagebox.showerror('未确认',str(e),parent=dialog)
  ttk.Button(dialog,text='确认所选变体售价',command=confirm_price).pack(pady=4)
  ttk.Button(dialog,text='佣金无法匹配时，选择官方商品类型',command=select_type).pack(pady=4)
 ttk.Button(win,text='查看所选变体售价明细 / 佣金类型',command=pricing_details).pack(pady=4)
 ttk.Button(win,text='删除选中任务（保留素材文件）',command=delete).pack(pady=4)
 def recollect():
  task=selected()
  if not task:return
  try:
   with store.lock:backup=store.recollect(task['id'])
   messagebox.showinfo('备份完成','整组原素材已备份到各货号 recovery_backups/'+backup+'。\n请在扩展填写首变体货号，点击保存本页现有8张图；不需要重新作图。')
  except Exception as e:messagebox.showerror('未重新采集',str(e))
 ttk.Button(win,text='备份整组旧素材，重新采集网页生成图',command=recollect).pack(pady=4)

 def approve():
  task=selected()
  if not task:return
  with store.lock:
   t=store.find(task['id'])
   if t['state']!='review':messagebox.showinfo('提示','仅可确认已保存并待审核的图片。异常请先在网页处理。');return
   t['state']='approved';store.save()
 ttk.Button(win,text='所选图片已人工检查，允许下一张',command=approve).pack(pady=6)
 def retry():
  task=selected()
  if not task:return
  if not messagebox.askyesno('检查网页后恢复','请先在扩展中暂停并刷新ChatGPT。确认此任务没有发送、没有生成结果，才重新排队。是否确认？'):return
  try:
   with store.lock:store.retry(task['id'])
  except Exception as e:messagebox.showerror('未恢复',str(e))
 ttk.Button(win,text='所选异常任务未发送，重新排队',command=retry).pack(pady=4)
 def cancel_product():
  task=selected()
  if not task:return
  product=task['sku']
  if not messagebox.askyesno('取消商品任务',f'取消 {product} 的剩余任务？已有图片和视频不会删除。请先停止扩展自动批次。'):return
  try:
   with store.lock:store.cancel_product(product)
  except Exception as e:messagebox.showerror('未取消',str(e))
 ttk.Button(win,text='取消所选商品剩余任务（保留文件）',command=cancel_product).pack(pady=4)
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
  except Exception as e:messagebox.showerror('未准备',str(e))
 ttk.Button(win,text='准备所选商品上架草稿并打开文件夹',command=listing).pack(pady=4)
 def category_editor():
  task=selected()
  if not task:return
  path=DATA/'products'/task['sku']/'listing_bundle.json'
  if not path.exists():messagebox.showerror('提示','请等待生成上架草稿');return
  data=json.loads(path.read_text(encoding='utf-8-sig'));dialog=tk.Toplevel(win);dialog.title('类目确认/修改')
  ttk.Label(dialog,text=data.get('category_match_status','尚未推荐；可手动填写官方类目与类型ID')).pack()
  candidates=data.get('category_candidates',[]);choice=ttk.Combobox(dialog,values=[c['path'] for c in candidates],width=80,state='readonly');choice.pack()
  cat=tk.StringVar(value=str(data.get('category',{}).get('description_category_id') or ''));typ=tk.StringVar(value=str(data.get('category',{}).get('type_id') or ''))
  ttk.Label(dialog,text='类目ID（可手动修改）').pack();ttk.Entry(dialog,textvariable=cat).pack();ttk.Label(dialog,text='商品类型ID').pack();ttk.Entry(dialog,textvariable=typ).pack()
  def pick(e):
   c=candidates[choice.current()];cat.set(str(c['description_category_id']));typ.set(str(c['type_id']))
  choice.bind('<<ComboboxSelected>>',pick)
  def confirm():
   try:
    c=int(cat.get());t=int(typ.get())
    if min(c,t)<=0:raise ValueError('ID须为正整数')
    with store.lock:
     latest=json.loads(path.read_text(encoding='utf-8-sig'));latest['category']={**next((x for x in candidates if x['description_category_id']==c and x['type_id']==t),{}),'description_category_id':c,'type_id':t,'confirmed':True,'attributes_revalidation_required':True};temp=path.with_suffix('.category.tmp');temp.write_text(json.dumps(latest,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
    dialog.destroy()
   except Exception as e:messagebox.showerror('未保存',str(e))
  ttk.Button(dialog,text='确认此类目（发布前仍核验必填属性）',command=confirm).pack()
 ttk.Button(win,text='确认或修改所选商品类目',command=category_editor).pack(pady=4)




 ttk.Label(win,text='遇到 needs_attention：停止自动任务，先人工检查网页；不自动重发。图片在本工具 data/products 下。').pack()
 refresh()
 def close():pricing_stop.set();http.shutdown();root.destroy()
 root.protocol('WM_DELETE_WINDOW',close);root.mainloop()
if __name__=='__main__':main()
