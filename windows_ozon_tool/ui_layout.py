"""Unified light workspace, persistent navigation and responsive task controls."""
import os

PALETTE={'bg':'#F2F5FC','surface':'#FFFFFF','ink':'#17243B','muted':'#64748B','line':'#E2E8F2','blue':'#5865F2','soft':'#ECEEFF','green':'#16785B','red':'#B74347'}
def build(root):
 import tkinter as tk
 from tkinter import ttk
 from ui_components import RoundedCard
 c=PALETTE;root.title('Ozon 商品自动化 · 1.0.65');root.geometry('1440x900');root.minsize(1080,700);root.configure(background=c['bg'])
 style=ttk.Style(root);style.theme_use('clam')
 font='Microsoft YaHei UI' if os.name=='nt' else 'Noto Sans CJK SC'
 style.configure('.',font=(font,10),background=c['bg'],foreground=c['ink'])
 style.configure('Rail.TFrame',background='#121E38');style.configure('Rail.TLabel',background='#121E38',foreground='#99ABC9');style.configure('RailTitle.TLabel',background='#121E38',foreground='#FFFFFF',font=(font,16,'bold'))
 style.configure('SectionTitle.TLabel',font=(font,13,'bold'));style.configure('Chip.TLabel',background='#ECEEFF',foreground='#5865F2',padding=(10,5));style.configure('Status.TLabel',background='#FFFFFF',foreground='#566782',padding=(14,10))
 style.configure('Surface.TLabelframe',background=c['surface'],bordercolor=c['line'],relief='solid',padding=16);style.configure('Surface.TLabelframe.Label',background=c['bg'],foreground=c['muted'],font=(font,10,'bold'))
 style.configure('CardTitle.TLabel',background=c['surface'],font=(font,13,'bold'));style.configure('CardMuted.TLabel',background=c['surface'],foreground=c['muted'])
 style.configure('TCheckbutton',padding=(8,6));style.configure('TRadiobutton',padding=(8,6));style.configure('TMenubutton',padding=(13,9),background=c['surface'],foreground=c['ink'],bordercolor=c['line'])
 style.configure('TFrame',background=c['bg']);style.configure('Card.TFrame',background=c['surface'])
 style.configure('TLabel',background=c['bg']);style.configure('Card.TLabel',background=c['surface'])
 style.configure('Muted.TLabel',foreground=c['muted']);style.configure('Heading.TLabel',font=(font,19,'bold'),foreground=c['ink'])
 style.configure('Metric.TLabel',font=(font,24,'bold'),background=c['surface']);style.configure('Caption.TLabel',foreground=c['muted'],background=c['surface'])
 style.configure('TButton',background=c['surface'],foreground=c['ink'],bordercolor=c['line'],lightcolor=c['surface'],darkcolor=c['surface'],padding=(13,9),relief='flat',focusthickness=2,focuscolor=c['blue'])
 style.map('TButton',background=[('active',c['soft']),('disabled','#EDF1F7')],foreground=[('disabled','#99A5B7')])
 style.configure('Compact.TButton',padding=(6,4))
 style.configure('Primary.TButton',background=c['blue'],foreground='white',bordercolor=c['blue'],padding=(16,10))
 style.map('Primary.TButton',background=[('disabled','#A7BFF5'),('active','#1D4ED8')],foreground=[('disabled','#F3F6FF'),('!disabled','white')])
 for name,bg,fg in [('Nav.TButton','#121E38','#B5C4DD'),('NavActive.TButton','#2A385D','#FFFFFF')]:
  style.configure(name,background=bg,foreground=fg,borderwidth=0,anchor='w',padding=(16,13),font=(font,10,'bold'))
  style.map(name,background=[('active','#253456')],foreground=[('active','#FFFFFF')])
 style.configure('Segment.TButton',background='#E9EDF8',foreground='#687C9D',padding=(8,9),borderwidth=0)
 style.configure('SegmentActive.TButton',background='#FFFFFF',foreground=c['blue'],padding=(8,9),bordercolor='#CBD3FA')
 style.map('Segment.TButton',background=[('active','#E2E7FC')]);style.map('SegmentActive.TButton',background=[('active','#ECEEFF')])
 style.configure('TEntry',fieldbackground=c['surface'],bordercolor=c['line'],padding=8)
 style.configure('TCombobox',fieldbackground=c['surface'],bordercolor=c['line'],padding=7)
 style.map('TEntry',bordercolor=[('focus',c['blue'])]);style.map('TCombobox',fieldbackground=[('readonly',c['surface'])])
 style.configure('TLabelframe',background=c['bg'],bordercolor=c['line'],relief='solid',padding=10)
 style.configure('TLabelframe.Label',foreground=c['muted'],font=(font,10,'bold'))
 style.configure('TNotebook',background=c['bg'],borderwidth=0,tabmargins=(0,4,0,0))
 style.configure('TNotebook.Tab',padding=(23,12),background='#E8EDFA',foreground=c['muted'])
 style.map('TNotebook.Tab',background=[('selected',c['soft']),('active','#F1F3FF')],foreground=[('selected',c['blue'])])
 style.layout('Workspace.TNotebook.Tab',[]);style.configure('Workspace.TNotebook',background=c['bg'],borderwidth=0,bordercolor=c['bg'],lightcolor=c['bg'],darkcolor=c['bg'])
 style.configure('Treeview',rowheight=44,background=c['surface'],fieldbackground=c['surface'],bordercolor=c['line'],borderwidth=0,foreground=c['ink'])
 style.configure('Treeview.Heading',background='#EDF1F8',foreground='#51627A',font=(font,10,'bold'),padding=(8,10),relief='flat')
 style.map('Treeview',background=[('selected',c['soft'])],foreground=[('selected','#173F93')])
 style.configure('Vertical.TScrollbar',background='#D1D9E7',troughcolor=c['bg'],borderwidth=0,arrowsize=12)
 style.configure('Horizontal.TScrollbar',background='#D1D9E7',troughcolor=c['bg'],borderwidth=0,arrowsize=12)
 for widget in ('Text','Listbox'):
  root.option_add('*'+widget+'.font',(font,10));root.option_add('*'+widget+'.borderWidth',0);root.option_add('*'+widget+'.highlightThickness',1);root.option_add('*'+widget+'.highlightBackground',c['line'])
  if widget=='Text':root.option_add('*Text.padX',12);root.option_add('*Text.padY',10)
  root.option_add('*'+widget+'.background',c['surface']);root.option_add('*'+widget+'.foreground',c['ink']);root.option_add('*'+widget+'.selectBackground',c['soft']);root.option_add('*'+widget+'.selectForeground',c['ink'])
 banner=ttk.Frame(root,padding=(24,12));banner.pack(fill='x')
 ttk.Label(banner,text='Ozon 工作台',style='Heading.TLabel').pack(side='left')
 ttk.Label(banner,text='商品与素材自动化工作空间',style='Muted.TLabel').pack(side='left',padx=22)
 ttk.Label(banner,text='DESKTOP   ·   1.0.65',style='Chip.TLabel').pack(side='right')
 connection=ttk.Label(root,text='正在检查本地连接…',padding=(24,6),wraplength=1360,style='Status.TLabel');connection.pack(fill='x',padx=24,pady=(0,4))
 workspace=ttk.Frame(root);workspace.pack(fill='both',expand=True,padx=16,pady=(8,16))
 rail=ttk.Frame(workspace,style='Rail.TFrame',padding=(12,20));rail.pack(side='left',fill='y',padx=(0,16))
 ttk.Label(rail,text='OZON / STUDIO',style='RailTitle.TLabel').pack(anchor='w',padx=14,pady=(2,14))
 notebook=ttk.Notebook(workspace,style='Workspace.TNotebook');notebook.pack(side='left',fill='both',expand=True);pages={};buttons={}
 def navigate(key):notebook.select(pages[key])
 for key,title,subtitle in [('product','商品制作','新建商品组与变体'),('tasks','任务中心','制作进度与异常处理'),('settings','设置','连接、托管与定价')]:
  button=ttk.Button(rail,text={'product':'01   商品制作','tasks':'02   任务中心','settings':'03   偏好设置'}[key],style='Nav.TButton',width=16,command=lambda k=key:navigate(k));button.pack(fill='x',pady=4);buttons[key]=button
 ttk.Frame(rail,style='Rail.TFrame').pack(fill='both',expand=True)
 ttk.Label(rail,text='AUTOMATION WORKSPACE\n本地制作 · 预览后提交\n\nCtrl 1 / 2 / 3  切换模块\nCtrl F  查找任务',style='Rail.TLabel',justify='left').pack(anchor='w',padx=12,pady=12)
 def scroll_page(title):
  page=ttk.Frame(notebook);notebook.add(page,text=title);page.rowconfigure(0,weight=1);page.columnconfigure(0,weight=1)
  canvas=tk.Canvas(page,highlightthickness=0,background=c['bg']);canvas.grid(row=0,column=0,sticky='nsew');scroll=ttk.Scrollbar(page,orient='vertical',command=canvas.yview);scroll.grid(row=0,column=1,sticky='ns');canvas.configure(yscrollcommand=scroll.set)
  body=ttk.Frame(canvas,padding=(18,12));item=canvas.create_window((0,0),window=body,anchor='nw');body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')));canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width))
  def wheel(e):
   if e.widget.winfo_class() not in ('Treeview','Entry','TEntry','Text','TCombobox','Listbox') and str(e.widget).startswith(str(page)):canvas.yview_scroll(-int(e.delta/120),'units')
  root.bind_all('<MouseWheel>',wheel,add='+');return page,body
 page=ttk.Frame(notebook);notebook.add(page,text='商品制作');page.rowconfigure(0,weight=1);page.columnconfigure(0,weight=1)
 body=ttk.Frame(page,padding=(18,12));body.grid(row=0,column=0,sticky='nsew');pages.update(product=page,product_body=body)
 ttk.Label(body,text='创建商品组',style='SectionTitle.TLabel').pack(anchor='w',pady=(0,4))
 tasks=ttk.Frame(notebook,padding=(18,12));notebook.add(tasks,text='任务中心');pages['tasks']=tasks
 ttk.Label(tasks,text='任务中心',style='Heading.TLabel').pack(anchor='w',pady=(4,5))

 metrics=ttk.Frame(tasks);metrics.pack(fill='x',pady=(8,12));values={}
 for i,(key,label) in enumerate([('total','有效变体'),('queued','等待制作'),('running','制作进行中'),('attention','需要处理')]):
  metrics.columnconfigure(i,weight=1);card=RoundedCard(metrics,height=88,accent=['#5865F2','#17A5BC','#7856D9','#D8813B'][i]);card.grid(row=0,column=i,sticky='ew',padx=(0,10 if i<3 else 0))
  caption=ttk.Label(card.content,text=label,style='Caption.TLabel',cursor='hand2');caption.pack(side='left');value=ttk.Label(card.content,text='0',style='Metric.TLabel',cursor='hand2');value.pack(side='right');values[key]=value
  def jump(event=None,k=key):
   search.set('');mode.set({'total':'全部任务','queued':'排队中','running':'制作中','attention':'需处理'}[k])
  for widget in (card,card.content,caption,value):widget.bind('<Button-1>',jump)
 pages['metrics']=values

 filters=ttk.Frame(tasks);filters.pack(fill='x',pady=(0,12));search=tk.StringVar();mode=tk.StringVar(value='全部任务')
 ttk.Label(filters,text='快速查找',style='Muted.TLabel').pack(side='left',padx=(0,8));entry=ttk.Entry(filters,textvariable=search,width=30);entry.pack(side='left',fill='x',expand=True)
 ttk.Combobox(filters,textvariable=mode,state='readonly',values=['全部任务','排队中','制作中','素材已保存','已上架','需处理'],width=13).pack(side='left',padx=10)
 ttk.Button(filters,text='清除筛选',command=lambda:(search.set(''),mode.set('全部任务'))).pack(side='right')
 result_label=ttk.Label(tasks,text='正在读取任务…',style='Muted.TLabel');result_label.pack(anchor='w',pady=(0,8));pages['task_results']=result_label
 pages['task_search']=search;pages['task_filter']=mode
 root.bind('<Control-f>',lambda e:(navigate('tasks'),entry.focus_set()))
 page,body=scroll_page('设置');pages.update(settings=page,settings_body=body)
 ttk.Label(body,text='连接你的工作空间',style='Heading.TLabel').pack(anchor='w',pady=(4,6))
 ttk.Label(body,text='管理配对、定价来源与素材托管；配置状态随任务实时更新。',style='Muted.TLabel').pack(anchor='w',pady=(0,18))
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
