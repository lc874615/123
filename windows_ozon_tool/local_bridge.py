"""Loopback-only authenticated bridge. Does not read Edge cookies or send Ozon writes."""
import base64,hashlib,hmac,io,json,re,secrets,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from PIL import Image
from variants import valid_article
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data';DATA.mkdir(exist_ok=True)
TASKS=[('01_main','双件或多件主图，严格按销售规格显示数量'),('02_dimensions','商品尺寸图，勿将包装尺寸当成商品尺寸'),('03_scene','适用场景一'),('04_scene','适用场景二'),('05_material','材质细节'),('06_structure','结构细节'),('07_details','配件与细节'),('08_contents','套装实际内容')]
class Store:
 def __init__(self,folder):
  self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True);self.lock=threading.Lock();self.path=self.folder/'tasks.json';self.tasks=json.loads(self.path.read_text(encoding='utf-8-sig')) if self.path.exists() else []
  for t in self.tasks:
   if t['state'] in ('claimed','sending','waiting'):t['state']='needs_attention';t['message']='服务重启，请检查网页后人工处理'
   if t.get('copy_state')=='running':t['copy_state']='needs_attention';t['message']='文案任务被重启中断，请保存网页现有结果'
  self.save()
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
  task=dict(group[0]);task.update(id=secrets.token_hex(16),name='00_full_set',state='queued',auto_batch=True,set_mode=True,received_images=[])
  task['prompt']='请一次完成8张独立的Ozon商品图片，必须是8个独立图片文件，不要拼图，不要把8个画面合成一张。按顺序输出：'+ '；'.join(f'{i+1}. {brief}' for i,(_,brief) in enumerate(TASKS))+ '。第1张是商品主图，展示真实销售数量。每张3:4竖版，自然俄文，风格一致，保持原图外观。严禁虚构尺寸、材质、配件和功能，包装尺寸不能当作商品尺寸。商品事实：'+facts
  self.tasks=[t for t in self.tasks if t['sku']!=sku]+[task];self.save()
 def recover(self,sku):
  group=[t for t in self.tasks if t['sku']==sku and t.get('set_mode') and t['state'] in ('waiting','needs_attention','claimed','sending')]
  if len(group)!=1:raise ValueError('没有唯一可恢复的整套任务，请核对货号')
  task=group[0];task.update(state='waiting',message='用户请求从现有网页恢复保存，不重新生成');self.save();return {'id':task['id'],'set_mode':True,'saved_count':len(task.get('received_images',[])),'expected_images':task.get('expected_images',8)}
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
  digest=hashlib.sha256(data).hexdigest()
  if index<len(received):
   if received[index]['sha256']!=digest:raise ValueError('恢复图片与已保存顺序不一致，已有文件保留')
   return {'saved_count':len(received),'complete':task['state']=='saved'}
  if index!=len(received) or task['state']=='saved':raise ValueError('图片顺序错误')
  if any(x['sha256']==digest for x in received):raise ValueError('不同图片位置内容重复，已保留文件，请检查图片列表')
  folder=self.folder/'products'/task['sku']/'images';folder.mkdir(parents=True,exist_ok=True)
  path=folder/f'{TASKS[index][0]}.{ext}';path.write_bytes(data)
  received.append({'file':str(path),'sha256':digest,'role':'primary' if index==0 else 'gallery','order':index+1})
  if task.get('gallery_source') and len(received)==1:
   from product_group import reuse_gallery
   reuse_gallery(folder.parent,task)
  task.update(state='saved' if len(received)==8 else 'waiting',message=f'已保存 {len(received)}/8 张独立图片');self.save()
  if len(received)==8:
   (folder.parent/'image_manifest.json').write_text(json.dumps(received,ensure_ascii=False,indent=2),encoding='utf-8')
   threading.Thread(target=self.render_video,args=(task['sku'],),daemon=True).start()
  return {'saved_count':len(received),'complete':task['state']=='saved'}
 def claim(self):
  if any(t['state'] in ('claimed','sending','waiting','needs_attention','review') for t in self.tasks):raise ValueError('请先审核上一任务或处理异常，不能继续发送')
  t=next((t for t in self.tasks if t['state']=='queued'),None)
  if not t:raise ValueError('没有排队任务，请在本地窗口创建商品')
  t['state']='claimed';self.save();result=dict(t);result['references']=[{'name':r['name'],'mime':r['mime'],'purpose':r.get('purpose','variant_main'),'base64':base64.b64encode(Path(r['path']).read_bytes()).decode()} for r in t.get('references',[])];return result
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
 def next_copy(self):
  for task in self.tasks:
   if task.get('set_mode') and task['state']=='saved' and task.get('video') and not task.get('copy_state'):
    from listing_bundle import prepare
    folder=self.folder/'products'/task['sku']
    if not (folder/'listing_bundle.json').exists():prepare(folder,task)
    if task.get('copy_leader') and task['copy_leader']!=task['sku']:
     leader_path=self.folder/'products'/task['copy_leader']/'listing_bundle.json'
     if leader_path.exists():
      leader=json.loads(leader_path.read_text(encoding='utf-8-sig'))
      if leader['copy'].get('title_ru'):
       bundle=json.loads((folder/'listing_bundle.json').read_text(encoding='utf-8-sig'));bundle['copy']={**leader['copy'],'sku':task['sku']};bundle['copy_source']=task['copy_leader'];bundle['copy_review_status']='pending_human_review';bundle['blockers']=[b for b in bundle['blockers'] if b!='俄文文案待生成'];(folder/'listing_bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8');task['copy_state']='done';self.save()
     continue
    bundle=json.loads((folder/'listing_bundle.json').read_text(encoding='utf-8-sig'))
    if bundle['copy'].get('title_ru'):task['copy_state']='done';self.save();continue
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
     if self.path=='/poll':
      active=any(t['state'] in ('claimed','sending','waiting','needs_attention','review') or t.get('copy_state') in ('running','needs_attention') for t in store.tasks)
      copy_task=store.next_copy() if not active else None
      value={'ready':not active and any(t['state']=='queued' and t.get('auto_batch') for t in store.tasks),'copy_sku':copy_task['sku'] if copy_task else None}
     elif self.path=='/copy-task':
      sku=body['sku']
      if not valid_article(sku):raise ValueError('货号格式无效')
      folder=store.folder/'products'/sku
      if not (folder/'listing_bundle.json').exists():raise ValueError('请先在本地准备上架草稿')
      for task in store.tasks:
       if task['sku']==sku:task['copy_state']='running'
      store.save()
      value={'id':'copy:'+sku,'sku':sku,'prompt':'本次变体货号：'+sku+'。只依据下列当前资料，不得沿用历史商品材质。输出JSON必须额外包含sku字段，值为'+sku+'。'+(folder/'copy_prompt.txt').read_text(encoding='utf-8')}
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
      from category_match import suggest
      threading.Thread(target=suggest,args=(store.folder/'products'/sku,),daemon=True).start()
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
   except Exception as e:self.reply(400,{'error':str(e)[:300]})
 return ThreadingHTTPServer(('127.0.0.1',port),Handler)

def main():
 import tkinter as tk
 from tkinter import ttk,messagebox,filedialog
 store=Store(DATA);token=secrets.token_urlsafe(32);http=server(store,token);threading.Thread(target=http.serve_forever,daemon=True).start()
 root=tk.Tk();root.title('Ozon Edge 本地服务 v0.13');root.geometry('1120x850')
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
 grid=VariantGrid(win,base)
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
 ttk.Button(win,text='创建全部变体并自动处理',command=create).pack(pady=6)
 view=ttk.Treeview(win,columns=('sku','progress','status'),show='headings',height=8,selectmode='browse')
 for key,label,width in [('sku','变体货号',180),('progress','进度',140),('status','状态',460)]:view.heading(key,text=label,anchor='center');view.column(key,width=width,stretch=key=='status',anchor='center')
 view.pack(fill='both',expand=True,padx=15)
 visible=[]
 def selected():
  ids=view.selection()
  return next((t for t in visible if ids and t['id']==ids[0]),None)
 def refresh():
  nonlocal visible
  selection=view.selection()
  with store.lock:visible=[dict(t) for t in store.tasks]
  for item in view.get_children():view.delete(item)
  labels={'queued':'排队中','saved':'图片已保存','cancelled':'已取消','needs_attention':'需处理','waiting':'处理中','claimed':'已领取','sending':'发送中','review':'待审核','approved':'已审核'}
  for task in visible:
   count=len(task.get('received_images',[]));progress=f'{count}/8 图' if task.get('set_mode') else task['name']
   state='全部素材就绪' if task.get('copy_state')=='done' else ('文案待处理' if task.get('copy_state')=='needs_attention' else ('文案生成中' if task.get('copy_state')=='running' else labels.get(task['state'],task['state'])))
   view.insert('', 'end',iid=task['id'],values=(task['sku'],progress,state))
  if selection and view.exists(selection[0]):view.selection_set(selection[0])
  win.after(1500,refresh)
 def delete():
  task=selected()
  if not task:return
  try:
   with store.lock:store.delete_task(task['id'])
  except Exception as e:messagebox.showerror('未删除',str(e))
 ttk.Button(win,text='删除选中任务（保留素材文件）',command=delete).pack(pady=4)
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
   target=prepare(DATA/'products'/task['sku'],task)
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
    latest=json.loads(path.read_text(encoding='utf-8-sig'));latest['category']={'description_category_id':c,'type_id':t,'confirmed':True,'attributes_revalidation_required':True};path.write_text(json.dumps(latest,ensure_ascii=False,indent=2),encoding='utf-8');dialog.destroy()
   except Exception as e:messagebox.showerror('未保存',str(e))
  ttk.Button(dialog,text='确认此类目（发布前仍核验必填属性）',command=confirm).pack()
 ttk.Button(win,text='确认或修改所选商品类目',command=category_editor).pack(pady=4)




 ttk.Label(win,text='遇到 needs_attention：停止自动任务，先人工检查网页；不自动重发。图片在本工具 data/products 下。').pack()
 refresh()
 def close():http.shutdown();root.destroy()
 root.protocol('WM_DELETE_WINDOW',close);root.mainloop()
if __name__=='__main__':main()
