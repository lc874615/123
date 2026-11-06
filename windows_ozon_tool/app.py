"""Visible, user-driven Windows ChatGPT browser workflow. No CAPTCHA bypass."""
import hashlib,json,re,threading,time,queue
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from playwright.sync_api import sync_playwright
from browser_flow import send_once,wait_and_download
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data';DATA.mkdir(exist_ok=True)
TASKS=[('01_main','主图，完整展示每套准确数量，明确俄文数量'),('02_dimensions','商品本体尺寸图，尺寸箭头对应部位，严禁使用包装尺寸'),('03_office','适用场景图，布景注明不在套装内'),('04_scene','另一真实适用场景，布景注明不在套装内'),('05_material','真实材质细节，不夸大纹理'),('06_structure','结构细节，禁止虚构功能'),('07_details','配件与局部细节，只展示真实存在的部分'),('08_contents','套装内容，明确销售数量，不新增配件')]
def slug(s):return re.sub(r'[^\w-]+','_',s).strip('_')[:80] or 'product'
def prompt(facts,task):
 return ('制作一张独立的Ozon俄文商品图，不要拼接多张上架图。3:4竖图，统一浅灰背景、黑色俄文排版。'
 '先读取本对话附件中的商品原图与参数，只使用提供的事实，保持商品结构、颜色、材质、配件一致。'
 '所有文字使用自然俄文。不得编造品牌、认证、承重、人体工学、组装方式或性能。'
 '商品尺寸与包装尺寸必须区分，未知尺寸不要补全。销售单位数量必须准确。'
 f'\n商品资料：{facts}\n本张任务：{task}\n只生成本张图片。')
def accept_image(body,content_type):
 return bool(body) and len(body)>10000 and (body.startswith(b'\x89PNG\r\n\x1a\n') or body.startswith(b'\xff\xd8\xff') or (body.startswith(b'RIFF') and body[8:12]==b'WEBP'))
class App:
 def __init__(self,win):
  self.win=win;win.title('Ozon 本地图片工作台 · 浏览器辅助模式');win.geometry('860x740')
  self.events=queue.Queue();self.commands=queue.Queue();self.refs=[];self.worker=None;self.cancel=threading.Event()
  ttk.Label(win,text='商品名称 / SKU').pack(anchor='w',padx=15,pady=5)
  self.sku=ttk.Entry(win);self.sku.insert(0,'');self.sku.pack(fill='x',padx=15)
  ttk.Label(win,text='商品事实：数量、材质、商品尺寸、包装尺寸、成本（严禁混淆）').pack(anchor='w',padx=15,pady=5)
  self.facts=tk.Text(win,height=8);self.facts.pack(fill='x',padx=15)
  bar=ttk.Frame(win);bar.pack(fill='x',padx=15,pady=10)
  ttk.Button(bar,text='选择原始参考图片',command=self.pick).pack(side='left')
  ttk.Button(bar,text='打开专用浏览器',command=self.start).pack(side='left',padx=8)
  ttk.Button(bar,text='保存商品资料',command=self.save).pack(side='left')
  self.ref_label=ttk.Label(win,text='未选择图片');self.ref_label.pack(anchor='w',padx=15)
  self.task=ttk.Combobox(win,state='readonly',values=[f'{k} · {v}' for k,v in TASKS]);self.task.current(0);self.task.pack(fill='x',padx=15,pady=8)
  ttk.Button(win,text='自动发送当前任务并下载',command=self.send).pack(anchor='w',padx=15)
  ttk.Button(win,text='暂停等待',command=self.cancel.set).pack(anchor='w',padx=15,pady=4)
  ttk.Label(win,text='首次登录和验证由人工完成；请先在商品专用对话上传原图。\n每次生成一张，自动下载后先检查，再开始下一张。异常不会自动重发。').pack(anchor='w',padx=15,pady=10)
  self.log=tk.Text(win,height=16,state='disabled');self.log.pack(fill='both',expand=True,padx=15,pady=8)
  win.after(200,self.pump)
 def emit(self,s):self.events.put(s)
 def pump(self):
  while not self.events.empty():
   self.log.configure(state='normal');self.log.insert('end',self.events.get()+'\n');self.log.see('end');self.log.configure(state='disabled')
  self.win.after(200,self.pump)
 def pick(self):
  self.refs=list(filedialog.askopenfilenames(filetypes=[('Images','*.png *.jpg *.jpeg *.webp')]))
  self.ref_label.configure(text=f'已选择 {len(self.refs)} 张。请在浏览器中将这些原始图片上传至商品专用对话。')
 def save(self):
  folder=DATA/'products'/slug(self.sku.get());folder.mkdir(parents=True,exist_ok=True)
  (folder/'product.json').write_text(json.dumps({'sku':self.sku.get(),'facts':self.facts.get('1.0','end').strip(),'references':self.refs,'default_brand':'no_brand','default_stock':1000},ensure_ascii=False,indent=2),encoding='utf-8')
  self.emit('商品资料已保存：'+str(folder));return folder
 def start(self):
  if self.worker and self.worker.is_alive():self.emit('专用浏览器已在运行。');return
  self.worker=threading.Thread(target=self.browser,daemon=True);self.worker.start()
 def send(self):
  if not self.worker or not self.worker.is_alive():messagebox.showinfo('提示','请先打开专用浏览器并登录。');return
  folder=self.save();idx=self.task.current()
  self.cancel.clear()
  self.commands.put((folder,TASKS[idx][0],prompt(self.facts.get('1.0','end').strip(),TASKS[idx][1])))
 def browser(self):
  active={'folder':None,'task':None,'request':None}
  try:
   with sync_playwright() as p:
    context=p.chromium.launch_persistent_context(str(DATA/'browser-profile'),headless=False,accept_downloads=True,viewport={'width':1280,'height':900})
    page=context.pages[0] if context.pages else context.new_page()
    def download(event):
     if not active['folder']:self.emit('当前没有图片任务，下载请手动保存。');return
     try:
      name=Path(event.suggested_filename).name
      if Path(name).suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):self.emit('忽略非图片下载：'+name);return
      folder=active['folder']/'images'/active['task'];folder.mkdir(parents=True,exist_ok=True)
      dest=folder/(str(time.time_ns())+'_'+name);event.save_as(str(dest))
      body=dest.read_bytes()
      if not accept_image(body,''):dest.unlink();self.emit('下载内容不是有效图片，未登记。');return
      manifest=active['folder']/'downloads.json';rows=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else []
      rows.append({'task':active['task'],'request':active['request'],'file':str(dest),'sha256':hashlib.sha256(body).hexdigest(),'review_status':'pending_human_review'})
      manifest.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');self.emit('已保存原图：'+str(dest))
     except Exception as e:self.emit('下载未完成：'+str(e))
    page.on('download',download)
    page.goto('https://chatgpt.com/',wait_until='domcontentloaded',timeout=60000)
    self.emit('浏览器已打开。人工登录，建立商品专用对话并上传原始参考图后，再发送任务。')
    while not page.is_closed():
     page.wait_for_timeout(300)
     try:folder,task,content=self.commands.get_nowait()
     except queue.Empty:continue
     try:
      host=page.url.split('/')[2]
      if host!='chatgpt.com':raise RuntimeError('请先完成人工登录或验证，返回 chatgpt.com。')
      editor=page.locator('#prompt-textarea')
      if not editor.is_visible():raise RuntimeError('未找到输入框，请人工完成登录/验证或检查页面。')
      stop=page.get_by_test_id('stop-button')
      if stop.count() and stop.is_visible():raise RuntimeError('上一条仍在生成，请完成并下载后再发送。')
      request=str(time.time_ns());(folder/'prompts').mkdir(exist_ok=True)
      (folder/'prompts'/f'{task}_{request}.txt').write_text(content,encoding='utf-8')
      active.update(folder=folder,task=task,request=request)
      before=send_once(page,content)
      event=wait_and_download(page,before,self.cancel,self.emit)
      self.emit('下载请求已完成，请检查图片后再选择下一张。')
     except Exception as e:self.emit('任务暂停，未自动重发：'+str(e))
  except Exception as e:self.emit('浏览器已停止：'+str(e))
if __name__=='__main__':
 win=tk.Tk();App(win);win.mainloop()
