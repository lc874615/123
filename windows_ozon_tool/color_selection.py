"""Shared searchable multi-color picker with optional complete official catalogs."""
from window_registry import lookup,remember
from prefill_rules import COLORS,split,color_values

def is_color_field(field,include_name=True):
 from prefill_rules import name
 return name(field) in ('цвет','цвет товара','颜色','商品颜色')+(('название цвета','颜色名称') if include_name else ())

def choose(parent,initial,save,title='选择颜色（可多选）',close_on_save=True,window_key=None,service=None,bundles=None):
 import copy,os,queue,threading
 import tkinter as tk
 from tkinter import ttk,messagebox
 from PIL import ImageTk
 from ui_layout import dialog_footer
 from color_swatches import swatch
 key=('color_selection',window_key if window_key is not None else (str(parent),title));cached=lookup(parent,key)
 if cached is not None:return cached
 window=remember(parent,key,tk.Toplevel(parent));window.title(title);window.transient(parent.winfo_toplevel());footer=dialog_footer(window,850,700)
 from ui_components import section_header
 section_header(window,'选择商品颜色','支持多选、搜索与官方类目选项；已选内容在保存前保留。')
 window.minsize(min(720,window.winfo_screenwidth()-60),min(540,window.winfo_screenheight()-100));ttk.Style(window).configure('ColorChoice.TCheckbutton',wraplength=215)
 ttk.Label(window,text='选择商品实际包含的颜色。色块仅为近似识别示意，不是商品实拍或官方标准色；“？”表示无法可靠判断。',wraplength=790).pack(fill='x',padx=14,pady=(12,6))
 source=ttk.Label(window,text='常用颜色（非完整官方字典）；选择官方类目后可读取全部分页。',wraplength=790);source.pack(fill='x',padx=14,pady=4)
 toolbar=ttk.Frame(window);toolbar.pack(fill='x',padx=14,pady=5)
 query=tk.StringVar();ttk.Label(toolbar,text='搜索颜色').pack(side='left',padx=(0,8));ttk.Entry(toolbar,textvariable=query).pack(side='left',fill='x',expand=True)
 state={'rows':[],'selected':{},'official':False,'maximum':None,'bundles':copy.deepcopy(bundles or []),'serial':0,'loading':False};photos=[];jobs=queue.Queue()
 def norm(value):return str(value).strip().casefold().replace('ё','е')
 def canonical(value):return ', '.join(color_values(value) or [str(value).strip()])
 for value in split(initial):
  value=canonical(value);state['selected'][norm(value)]={'value':value,'label':value,'official':False}
 seen=set()
 for zh,ru in COLORS.items():
  if ru in seen:continue
  seen.add(ru);state['rows'].append({'value':ru,'label':zh,'official':False})
 frame=ttk.Frame(window);frame.pack(fill='both',expand=True,padx=14,pady=6);frame.rowconfigure(0,weight=1);frame.columnconfigure(0,weight=1)
 canvas=tk.Canvas(frame,highlightthickness=0);canvas.grid(row=0,column=0,sticky='nsew');scroll=ttk.Scrollbar(frame,orient='vertical',command=canvas.yview);scroll.grid(row=0,column=1,sticky='ns');canvas.configure(yscrollcommand=scroll.set)
 body=ttk.Frame(canvas);item=canvas.create_window((0,0),window=body,anchor='nw');body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')));canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width))
 for i in range(3):body.columnconfigure(i,weight=1)
 count=ttk.Label(footer,wraplength=790);count.pack(fill='x',pady=4)
 ttk.Label(footer,text='补充颜色（未匹配的值会保留为待核对参数，不冒充官方选项）').pack(anchor='w');extra=ttk.Entry(footer);extra.pack(fill='x',pady=4)
 def render(*args):
  if not window.winfo_exists():return
  for child in body.winfo_children():child.destroy()
  photos.clear();rows=list(state['rows']);known={norm(r['value']) for r in rows}
  rows.extend({**r,'unmatched':True} for k,r in state['selected'].items() if k not in known)
  needle=query.get().strip().casefold();visible=[r for r in rows if all(word in (r['label']+' '+r['value']).casefold() for word in needle.split())]
  for i,row in enumerate(visible):
   cell=ttk.Frame(body,padding=7);cell.grid(row=i//3,column=i%3,sticky='nsew',padx=3,pady=3)
   photo=ImageTk.PhotoImage(swatch(row['value']),master=window);photos.append(photo)
   ttk.Label(cell,image=photo).pack(anchor='w',pady=(0,5));value=norm(row['value']);var=tk.BooleanVar(value=value in state['selected'])
   def toggle(r=row,k=value,v=var):
    if v.get():state['selected'][k]=dict(r)
    else:state['selected'].pop(k,None)
    update_count()
   label=row['label']+(' · 待核对' if row.get('unmatched') else '')
   ttk.Checkbutton(cell,text=label,variable=var,command=toggle,style='ColorChoice.TCheckbutton').pack(anchor='w')
   if row['value']!=row['label']:ttk.Label(cell,text=row['value'],style='Muted.TLabel',wraplength=225).pack(anchor='w')
  update_count(len(visible))
 def update_count(shown=None):
  labels=[r['label'] for r in state['selected'].values()];names='；'.join(labels[:6]) or '未选择'
  if len(labels)>6:names+=' …另'+str(len(labels)-6)+'项'
  count.configure(text='已选 '+str(len(state['selected']))+' 项'+(' / 当前官方上限 '+str(state['maximum']) if state['maximum'] else '')+'：'+names+(' · 搜索结果 '+str(shown)+' 项' if shown is not None else ''))
 query.trace_add('write',render)
 def start(action,done):
  state['serial']+=1;serial=state['serial'];state['loading']=True;save_button.configure(state='disabled');source.configure(text='正在后台读取官方数据；已选内容保留…')
  def worker():
   try:result=action();jobs.put((serial,done,result,None))
   except Exception as error:jobs.put((serial,done,None,str(error)))
  threading.Thread(target=worker,daemon=True).start()
 def poll():
  if not window.winfo_exists():return
  try:
   while True:
    serial,done,result,error=jobs.get_nowait()
    if serial!=state['serial']:continue
    state['loading']=False;save_button.configure(state='normal')
    if error:source.configure(text='未完成官方读取：'+error+'。当前已选颜色保留，不视为官方完整列表。')
    else:done(result)
  except queue.Empty:pass
  state['poll_timer']=window.after(100,poll)
 def loaded(result):
  state.update(rows=result['rows'],official=True,maximum=result['maximum'])
  # A single official combination may represent a genuinely multicolored item.
  if result['maximum']==1 and len(state['selected'])>1:
   requested={norm(v) for r in state['selected'].values() for v in (color_values(r['value']) or [r['value']])}
   combinations=[r for r in result['rows'] if {norm(v) for v in (color_values(r['value']) or [r['value']])}==requested]
   if len(combinations)==1:state['selected']={norm(combinations[0]['value']):combinations[0]}
  source.configure(text='官方颜色：全部分页已读取，共 '+str(result['total_read'])+' 项；'+('当前类目可选 ' if result['contexts']==1 else '所选类目共有 ')+str(len(result['rows']))+' 项。未匹配原值另标“待核对”。');render()
 def fetch(force=False):
  if state['loading']:return
  if service is None:source.configure(text='尚未连接官方属性服务，当前只能选择常用色。');return
  if not state['bundles']:select_category();return
  from color_catalog import load
  state['official']=False
  start(lambda:load(service,state['bundles'],force),loaded)
 def select_category():
  if state['loading']:return
  if service is None:source.configure(text='请在本地工具连接Ozon API后读取官方类目与颜色。');return
  picker_key=('color_category_picker',key);old=lookup(window,picker_key)
  if old is not None:return old
  picker=remember(window,picker_key,tk.Toplevel(window));picker.title('选择读取颜色的官方类目');picker.transient(window);bottom=dialog_footer(picker,850,590)
  ttk.Label(picker,text='此选择仅用于读取颜色；不会修改商品上架类目。保存后仍按商品实际类目复核。',wraplength=790).pack(padx=14,pady=10)
  cat_query=tk.StringVar();ttk.Entry(picker,textvariable=cat_query).pack(fill='x',padx=14,pady=5);box=tk.Listbox(picker,exportselection=False);box.pack(fill='both',expand=True,padx=14,pady=5);catalog=[];visible=[]
  note=ttk.Label(bottom,text='正在读取官方中俄类目列表…',wraplength=790);note.pack(fill='x')
  def filter_rows(*args):
   visible[:]=[r for r in catalog if all(word in (r.get('zh_path','')+' '+r.get('path','')).casefold() for word in cat_query.get().casefold().split())][:500];box.delete(0,'end')
   for row in visible:box.insert('end',row.get('zh_path') or row.get('path') or row.get('name'))
   note.configure(text='显示 '+str(len(visible))+' 项（最多500项）；输入关键词缩小类目范围。')
  cat_query.trace_add('write',filter_rows)
  def apply_category():
   if not box.curselection():return
   row=visible[box.curselection()[0]];state['bundles']=[{'sku':'color-reference','category':{**row,'confirmed':True}}];picker.destroy();fetch()
  ttk.Button(bottom,text='读取所选类目的全部颜色',command=apply_category).pack(side='right',pady=5)
  from category_catalog import load_catalog
  def show_categories(rows):
   if not picker.winfo_exists():source.configure(text='类目窗口已关闭，原颜色保留。');return
   catalog[:]=rows;filter_rows();source.configure(text='请选择官方类目，然后读取全部颜色。')
  start(lambda:load_catalog(service,os.environ.get('OZON_CLIENT_ID','')),show_categories)
 ttk.Button(toolbar,text='选择官方类目',command=select_category).pack(side='left',padx=6)
 ttk.Button(toolbar,text='读取 / 刷新官方颜色',command=lambda:fetch(True)).pack(side='left')
 def apply():
  if state['loading']:return
  values=[r['value'] for r in state['selected'].values()]+[canonical(v) for v in split(extra.get())];values=list(dict.fromkeys(values))
  if state['official'] and state['maximum'] and len(values)>state['maximum']:
   messagebox.showerror('超过官方颜色选项数量','该类目最多允许'+str(state['maximum'])+'个官方选项；多色商品请核对是否有对应组合色，不能只保留其中一种。',parent=window);return
  try:save('；'.join(values))
  except ValueError as error:messagebox.showerror('未保存',str(error),parent=window);return
  if close_on_save:window.destroy()
 buttons=ttk.Frame(footer);buttons.pack(fill='x',pady=3)
 def clear():state['selected'].clear();render()
 ttk.Button(buttons,text='清空已选',command=clear).pack(side='left')
 save_button=ttk.Button(buttons,text='保存所选颜色并同步',command=apply);save_button.pack(side='right',padx=5)
 ttk.Button(buttons,text='取消',command=window.destroy).pack(side='right',padx=5)
 window._ozon_color_ui={'state':state,'fetch':fetch,'search':query,'save':save_button,'source':source,'clear':clear}
 render();poll()
 if service is not None and state['bundles']:state['fetch_timer']=window.after(30,fetch)
 def stop_timers(event):
  if event.widget is not window:return
  for timer in ('poll_timer','fetch_timer'):
   if state.get(timer):
    try:window.after_cancel(state[timer])
    except tk.TclError:pass
 window.bind('<Destroy>',stop_timers,add='+')
 return window
