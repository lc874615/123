"""Unified light workspace, persistent navigation and responsive task controls."""
import os

PALETTE={'bg':'#F3F5FA','surface':'#FFFFFF','ink':'#17243B','muted':'#64748B','line':'#E2E8F2','blue':'#2563EB','soft':'#EAF0FF','green':'#16785B','red':'#B74347'}
def build(root):
 import tkinter as tk
 from tkinter import ttk
 c=PALETTE;root.title('Ozon 商品自动化 · 1.0.50');root.geometry('1440x900');root.minsize(1080,700);root.configure(background=c['bg'])
 style=ttk.Style(root);style.theme_use('clam')
 font='Microsoft YaHei UI' if os.name=='nt' else 'Noto Sans CJK SC'
 style.configure('.',font=(font,10),background=c['bg'],foreground=c['ink'])
 style.configure('TFrame',background=c['bg']);style.configure('Card.TFrame',background=c['surface'])
 style.configure('TLabel',background=c['bg']);style.configure('Card.TLabel',background=c['surface'])
 style.configure('Muted.TLabel',foreground=c['muted']);style.configure('Heading.TLabel',font=(font,19,'bold'),foreground=c['ink'])
 style.configure('Metric.TLabel',font=(font,24,'bold'),background=c['surface']);style.configure('Caption.TLabel',foreground=c['muted'],background=c['surface'])
 style.configure('TButton',background=c['surface'],foreground=c['ink'],bordercolor=c['line'],lightcolor=c['surface'],darkcolor=c['surface'],padding=(13,9),relief='flat',focusthickness=2,focuscolor=c['blue'])
 style.map('TButton',background=[('active',c['soft']),('disabled','#EDF1F7')],foreground=[('disabled','#99A5B7')])
 style.configure('Primary.TButton',background=c['blue'],foreground='white',bordercolor=c['blue'],padding=(16,10))
 style.map('Primary.TButton',background=[('disabled','#A7BFF5'),('active','#1D4ED8')],foreground=[('disabled','#F3F6FF'),('!disabled','white')])
 for name,bg,fg in [('Nav.TButton',c['surface'],c['muted']),('NavActive.TButton',c['soft'],c['blue'])]:
  style.configure(name,background=bg,foreground=fg,borderwidth=0,anchor='w',padding=(16,13),font=(font,10,'bold'))
  style.map(name,background=[('active',c['soft'])])
 style.configure('TEntry',fieldbackground=c['surface'],bordercolor=c['line'],padding=8)
 style.configure('TCombobox',fieldbackground=c['surface'],bordercolor=c['line'],padding=7)
 style.map('TEntry',bordercolor=[('focus',c['blue'])]);style.map('TCombobox',fieldbackground=[('readonly',c['surface'])])
 style.configure('TLabelframe',background=c['bg'],bordercolor=c['line'],relief='solid',padding=10)
 style.configure('TLabelframe.Label',foreground=c['muted'],font=(font,10,'bold'))
 style.configure('TNotebook',background=c['bg'],borderwidth=0,tabmargins=(0,4,0,0))
 style.configure('TNotebook.Tab',padding=(20,10),background='#E9EDF5',foreground=c['muted'])
 style.map('TNotebook.Tab',background=[('selected',c['surface'])],foreground=[('selected',c['blue'])])
 style.layout('Workspace.TNotebook.Tab',[]);style.configure('Workspace.TNotebook',background=c['bg'],borderwidth=0,bordercolor=c['bg'],lightcolor=c['bg'],darkcolor=c['bg'])
 style.configure('Treeview',rowheight=38,background=c['surface'],fieldbackground=c['surface'],bordercolor=c['line'],borderwidth=0,foreground=c['ink'])
 style.configure('Treeview.Heading',background='#EDF1F8',foreground='#51627A',font=(font,10,'bold'),padding=(8,10),relief='flat')
 style.map('Treeview',background=[('selected',c['soft'])],foreground=[('selected','#173F93')])
 style.configure('Vertical.TScrollbar',background='#D1D9E7',troughcolor=c['bg'],borderwidth=0,arrowsize=12)
 style.configure('Horizontal.TScrollbar',background='#D1D9E7',troughcolor=c['bg'],borderwidth=0,arrowsize=12)
 for widget in ('Text','Listbox'):
  root.option_add('*'+widget+'.font',(font,10))
  root.option_add('*'+widget+'.background',c['surface']);root.option_add('*'+widget+'.foreground',c['ink']);root.option_add('*'+widget+'.selectBackground',c['soft']);root.option_add('*'+widget+'.selectForeground',c['ink'])
 banner=ttk.Frame(root,padding=(24,18));banner.pack(fill='x')
 ttk.Label(banner,text='Ozon 工作台',style='Heading.TLabel').pack(side='left')
 ttk.Label(banner,text='商品制作  /  素材自动化  /  上架审核',style='Muted.TLabel').pack(side='left',padx=22)
 ttk.Label(banner,text='DESKTOP   ·   1.0.50',style='Muted.TLabel').pack(side='right')
 connection=ttk.Label(root,text='正在检查本地连接…',padding=(24,9),wraplength=1360,style='Muted.TLabel');connection.pack(fill='x')
 workspace=ttk.Frame(root);workspace.pack(fill='both',expand=True,padx=16,pady=(8,16))
 rail=ttk.Frame(workspace,style='Card.TFrame',padding=(12,18));rail.pack(side='left',fill='y',padx=(0,16))
 ttk.Label(rail,text='工作空间',style='Caption.TLabel').pack(anchor='w',padx=14,pady=(2,14))
 notebook=ttk.Notebook(workspace,style='Workspace.TNotebook');notebook.pack(side='left',fill='both',expand=True);pages={};buttons={}
 def navigate(key):notebook.select(pages[key])
 for key,title,subtitle in [('product','商品制作','新建商品组与变体'),('tasks','任务中心','制作进度与异常处理'),('settings','设置','连接、托管与定价')]:
  button=ttk.Button(rail,text=title+'  →',style='Nav.TButton',width=16,command=lambda k=key:navigate(k));button.pack(fill='x',pady=4);buttons[key]=button
 ttk.Frame(rail,style='Card.TFrame').pack(fill='both',expand=True)
 ttk.Label(rail,text='本地素材工作流\n预览确认后提交上架',style='Caption.TLabel',justify='left').pack(anchor='w',padx=12,pady=12)
 def scroll_page(title):
  page=ttk.Frame(notebook);notebook.add(page,text=title);page.rowconfigure(0,weight=1);page.columnconfigure(0,weight=1)
  canvas=tk.Canvas(page,highlightthickness=0,background=c['bg']);canvas.grid(row=0,column=0,sticky='nsew');scroll=ttk.Scrollbar(page,orient='vertical',command=canvas.yview);scroll.grid(row=0,column=1,sticky='ns');canvas.configure(yscrollcommand=scroll.set)
  body=ttk.Frame(canvas,padding=(18,12));item=canvas.create_window((0,0),window=body,anchor='nw');body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')));canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width))
  def wheel(e):
   if e.widget.winfo_class() not in ('Treeview','Entry','TEntry','Text','TCombobox','Listbox') and str(e.widget).startswith(str(page)):canvas.yview_scroll(-int(e.delta/120),'units')
  root.bind_all('<MouseWheel>',wheel,add='+');return page,body
 page,body=scroll_page('商品制作');pages.update(product=page,product_body=body)
 ttk.Label(body,text='创建一组商品',style='Heading.TLabel').pack(anchor='w',pady=(4,6))
 ttk.Label(body,text='01  填写变体参数     02  添加原始参考图     03  创建并自动制作',style='Muted.TLabel').pack(anchor='w',pady=(0,18))
 tasks=ttk.Frame(notebook,padding=(18,12));notebook.add(tasks,text='任务中心');pages['tasks']=tasks
 ttk.Label(tasks,text='任务中心',style='Heading.TLabel').pack(anchor='w',pady=(4,5))
 ttk.Label(tasks,text='查看每个变体的进度，选中任务后打开预览或处理异常。',style='Muted.TLabel').pack(anchor='w',pady=(0,16))
 metrics=ttk.Frame(tasks);metrics.pack(fill='x',pady=(0,16));values={}
 for i,(key,label) in enumerate([('total','有效变体'),('queued','等待制作'),('running','制作进行中'),('attention','需要处理')]):
  metrics.columnconfigure(i,weight=1);card=ttk.Frame(metrics,style='Card.TFrame',padding=(18,13));card.grid(row=0,column=i,sticky='ew',padx=(0,10 if i<3 else 0))
  caption=ttk.Label(card,text=label,style='Caption.TLabel',cursor='hand2');caption.pack(anchor='w');value=ttk.Label(card,text='0',style='Metric.TLabel',cursor='hand2');value.pack(anchor='w',pady=(4,0));values[key]=value
  def jump(event=None,k=key):
   search.set('');mode.set({'total':'全部任务','queued':'排队中','running':'制作中','attention':'需处理'}[k])
  for widget in (card,caption,value):widget.bind('<Button-1>',jump)
 pages['metrics']=values
 ttk.Label(tasks,text='“需要处理”表示待核对、待补充或明确异常，不等于上架失败。点击卡片可定位变体，查看“当前阶段 / 原因”。',style='Muted.TLabel',wraplength=1000).pack(anchor='w',pady=(0,12))
 filters=ttk.Frame(tasks);filters.pack(fill='x',pady=(0,12));search=tk.StringVar();mode=tk.StringVar(value='全部任务')
 ttk.Label(filters,text='快速查找',style='Muted.TLabel').pack(side='left',padx=(0,8));entry=ttk.Entry(filters,textvariable=search,width=30);entry.pack(side='left',fill='x',expand=True)
 ttk.Combobox(filters,textvariable=mode,state='readonly',values=['全部任务','排队中','制作中','素材已保存','已上架','需处理'],width=13).pack(side='left',padx=10)
 ttk.Button(filters,text='清除筛选',command=lambda:(search.set(''),mode.set('全部任务'))).pack(side='right')
 result_label=ttk.Label(tasks,text='正在读取任务…',style='Muted.TLabel');result_label.pack(anchor='w',pady=(0,8));pages['task_results']=result_label
 pages['task_search']=search;pages['task_filter']=mode
 root.bind('<Control-f>',lambda e:(navigate('tasks'),entry.focus_set()))
 page,body=scroll_page('设置');pages.update(settings=page,settings_body=body)
 def sync_nav(event=None):
  selected=notebook.select()
  for key,button in buttons.items():button.configure(style='NavActive.TButton' if str(pages[key])==selected else 'Nav.TButton')
 notebook.bind('<<NotebookTabChanged>>',sync_nav);sync_nav()
 for n,key in enumerate(('product','tasks','settings'),1):root.bind('<Control-Key-'+str(n)+'>',lambda e,k=key:navigate(k))
 def fit(event):
  if event.widget is root:connection.configure(wraplength=max(400,event.width-64))
 root.bind('<Configure>',fit,add='+')
 return notebook,pages,connection

def dialog_footer(window,width=850,height=650):
 """Reserve action space before expanding lists/text; fit the visible screen."""
 from tkinter import ttk
 width=min(width,max(320,window.winfo_screenwidth()-60));height=min(height,max(300,window.winfo_screenheight()-100))
 window.geometry(str(width)+'x'+str(height));footer=ttk.Frame(window,padding=(12,8));footer.pack(side='bottom',fill='x');return footer
