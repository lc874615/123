"""Loopback-only authenticated bridge. Does not read Edge cookies or send Ozon writes."""
import base64,hashlib,hmac,io,json,re,secrets,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data';DATA.mkdir(exist_ok=True)
TASKS=[('01_main','双件或多件主图，严格按销售规格显示数量'),('02_dimensions','商品尺寸图，勿将包装尺寸当成商品尺寸'),('03_scene','适用场景一'),('04_scene','适用场景二'),('05_material','材质细节'),('06_structure','结构细节'),('07_details','配件与细节'),('08_contents','套装实际内容')]
class Store:
 def __init__(self,folder):
  self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True);self.lock=threading.Lock();self.path=self.folder/'tasks.json';self.tasks=json.loads(self.path.read_text(encoding='utf-8-sig')) if self.path.exists() else []
  for t in self.tasks:
   if t['state'] in ('claimed','sending','waiting'):t['state']='needs_attention';t['message']='服务重启，请检查网页后人工处理'
  self.save()
 def save(self):
  temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(self.tasks,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(self.path)
 def create(self,sku,facts,references=None):
  if not re.fullmatch(r'[\w-]{1,80}',sku):raise ValueError('SKU仅允许字母、数字、下划线和连字符')
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
   self.tasks.append({'id':secrets.token_hex(16),'sku':sku,'name':name,'state':'queued','references':refs,'prompt':'根据本对话已上传原图制作一张独立Ozon商品图，3:4竖版，自然俄文。保持外观一致，禁止虚构属性、数量或尺寸。包装尺寸不得作为商品尺寸。任务：'+brief+'。商品事实：'+facts})
  self.save()
 def claim(self):
  if any(t['state'] in ('claimed','sending','waiting','needs_attention','review') for t in self.tasks):raise ValueError('请先审核上一任务或处理异常，不能继续发送')
  t=next((t for t in self.tasks if t['state']=='queued'),None)
  if not t:raise ValueError('没有排队任务，请在本地窗口创建商品')
  t['state']='claimed';self.save();result=dict(t);result['references']=[{'name':r['name'],'mime':r['mime'],'base64':base64.b64encode(Path(r['path']).read_bytes()).decode()} for r in t.get('references',[])];return result
 def find(self,tid):
  t=next((t for t in self.tasks if t['id']==tid),None)
  if not t:raise ValueError('任务不存在')
  return t
 def retry(self,tid):
  t=self.find(tid)
  if t['state']!='needs_attention':raise ValueError('仅可恢复异常任务')
  if any(x['state'] in ('claimed','sending','waiting') for x in self.tasks):raise ValueError('还有执行中的任务，请先暂停')
  t.update(state='queued',message='用户确认网页未发送后重新排队');self.save()
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
 def render_video(self,sku):
  from video import make_video
  with self.lock:group=sorted([dict(x) for x in self.tasks if x['sku']==sku],key=lambda x:x['name'])
  try:
   output=make_video([x['file'] for x in group],self.folder/'products'/sku/'video'/'product_8s.mp4')
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
      active=any(t['state'] in ('claimed','sending','waiting','needs_attention','review') for t in store.tasks)
      value={'ready':not active and any(t['state']=='queued' and t.get('auto_batch') for t in store.tasks)}
     elif self.path=='/claim':value=store.claim()
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
 win=tk.Tk();win.title('Ozon Edge 本地服务 v0.4');win.geometry('850x700')
 ttk.Label(win,text='本地服务已启动。将配对码粘贴至 Edge 扩展；可在下方选择原图，扩展将附加到当前ChatGPT对话。').pack(pady=8)
 code=ttk.Entry(win,width=65);code.insert(0,token);code.pack()
 ttk.Label(win,text='SKU（不含空格）').pack();sku=ttk.Entry(win,width=60);sku.pack()
 ttk.Label(win,text='商品事实：销售数量、尺寸、材质、成本；未知项目留空').pack();facts=tk.Text(win,height=7);facts.pack(fill='x',padx=15)
 references=[]
 ref_label=ttk.Label(win,text='尚未选择原图（也可在ChatGPT网页手动上传）');ref_label.pack()
 def choose():
  nonlocal references
  selected=list(filedialog.askopenfilenames(title='选择商品原图',filetypes=[('Images','*.png *.jpg *.jpeg *.webp')]))
  if selected:references=selected;ref_label.configure(text=f'已选择 {len(references)} 张：'+', '.join(Path(x).name for x in references))
 ttk.Button(win,text='选择商品原图（可多选）',command=choose).pack(pady=5)
 def create():
  try:
   with store.lock:
    store.create(sku.get().strip(),facts.get('1.0','end').strip(),references)
    for task in store.tasks:
     if task['sku']==sku.get().strip():task['auto_batch']=True
    store.save()
   messagebox.showinfo('已创建','8张任务已排队；已启用自动批次的扩展会开始执行。完成后自动合成8秒视频。')
  except Exception as e:messagebox.showerror('未创建',str(e))
 ttk.Button(win,text='创建并自动制作8图＋8秒视频',command=create).pack(pady=6)
 view=tk.Listbox(win,height=12);view.pack(fill='both',expand=True,padx=15)
 visible=[]
 def refresh():
  nonlocal visible
  selected=view.curselection();tid=visible[selected[0]]['id'] if selected and selected[0]<len(visible) else None
  with store.lock:visible=[dict(t) for t in store.tasks]
  view.delete(0,'end')
  for i,t in enumerate(visible):
   view.insert('end',f"{t['sku']} / {t['name']} / {t['state']} / {t.get('message','')}")
   if t['id']==tid:view.selection_set(i)
  win.after(1500,refresh)
 def approve():
  sel=view.curselection()
  if not sel:return
  with store.lock:
   t=store.find(visible[sel[0]]['id'])
   if t['state']!='review':messagebox.showinfo('提示','仅可确认已保存并待审核的图片。异常请先在网页处理。');return
   t['state']='approved';store.save()
 ttk.Button(win,text='所选图片已人工检查，允许下一张',command=approve).pack(pady=6)
 def retry():
  sel=view.curselection()
  if not sel:return
  if not messagebox.askyesno('检查网页后恢复','请先在扩展中暂停并刷新ChatGPT。确认此任务没有发送、没有生成结果，才重新排队。是否确认？'):return
  try:
   with store.lock:store.retry(visible[sel[0]]['id'])
  except Exception as e:messagebox.showerror('未恢复',str(e))
 ttk.Button(win,text='所选异常任务未发送，重新排队',command=retry).pack(pady=4)

 ttk.Label(win,text='遇到 needs_attention：停止自动任务，先人工检查网页；不自动重发。图片在本工具 data/products 下。').pack()
 refresh()
 def close():http.shutdown();win.destroy()
 win.protocol('WM_DELETE_WINDOW',close);win.mainloop()
if __name__=='__main__':main()
