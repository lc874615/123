"""Compact remake controls. Generation templates stay internal, never rendered here."""
def build(parent,bundles,store,start,stop,accept=None,current_sku=None):
 import tkinter as tk
 from tkinter import ttk
 from window_registry import lookup,remember
 style=ttk.Style(parent);style.configure('Compact.TButton',padding=(10,6));style.configure('Compact.Primary.TButton',padding=(12,7))
 panel=ttk.Frame(parent,padding=(12,8));panel.pack(fill='both',expand=True)
 selected={};initialized=[False]
 def plan_window():
  from visual_plan_ui import open_plan
  from visual_plans import context,save_group_override
  def owner():
   rows=bundles();sku=current_sku() if current_sku else (rows[0]['sku'] if rows else '')
   return next(t for t in store.tasks if t['sku']==sku)
  return open_plan(panel,lambda:context(store,owner()),lambda v:save_group_override(store,owner()['sku'],v),key='group:'+str(id(panel)))
 plan_button=ttk.Button(panel,text='查看类目方案与8图计划',style='Compact.TButton',command=plan_window);plan_button.pack(fill='x',pady=(0,6))
 shared=ttk.Frame(panel,style='Card.TFrame',padding=(12,10));shared.pack(fill='x',pady=(0,8))
 ttk.Label(shared,text='共用详情',style='CardTitle.TLabel').pack(anchor='w',pady=(0,4))
 ttk.Label(shared,text='重做 7 张 · 自动同步全组',style='CardMuted.TLabel').pack(anchor='w')
 shared_add=tk.Text(shared,height=1,wrap='word',undo=True,background='#F8FAFF',pady=5);shared_add.pack(fill='x',pady=(5,5))
 shared_button=ttk.Button(shared,text='重做详情图',style='Compact.Primary.TButton',command=lambda:start('shared_details',[],shared_add.get('1.0','end-1c')));shared_button.pack(fill='x')
 main=ttk.Frame(panel,style='Card.TFrame',padding=(12,10));main.pack(fill='x',pady=(0,8))
 ttk.Label(main,text='变体主图',style='CardTitle.TLabel').pack(anchor='w',pady=(0,6))
 choice_button=ttk.Button(main,text='选择变体',style='Compact.TButton');choice_button.pack(fill='x')
 main_add=tk.Text(main,height=1,wrap='word',undo=True,background='#F8FAFF',pady=5);main_add.pack(fill='x',pady=(5,5))
 main_button=ttk.Button(main,text='重做选中主图',style='Compact.Primary.TButton',command=lambda:start('variant_main',[sku for sku,var in selected.items() if var.get()],main_add.get('1.0','end-1c')));main_button.pack(fill='x')
 ttk.Label(panel,text='上方可选填补充要求，留空使用默认方案。',style='Muted.TLabel',wraplength=330).pack(anchor='w',pady=(0,4))
 state=ttk.Label(panel,text='本组暂无重做任务',style='Muted.TLabel',wraplength=330);state.pack(fill='x')
 verification=ttk.Label(panel,text='',foreground='#A36536',wraplength=330);verification.pack(fill='x',pady=2)
 tools=ttk.Frame(panel);tools.pack(side='bottom',fill='x',pady=(4,0))
 stop_button=ttk.Button(tools,text='停止重做',command=stop);stop_button.pack(side='right')
 accept_button=ttk.Button(tools,text='沿用现有图片',command=accept) if accept else None
 def summary(*args):
  count=sum(v.get() for v in selected.values());choice_button.configure(text='选择变体 · 已选 '+str(count)+' / '+str(len(selected)))
  main_button.configure(text='重做选中主图'+(' · '+str(count)+' 个' if count else ''),state='normal' if count else 'disabled')
 def picker():
  key=('remake_variant_picker',id(panel));cached=lookup(panel,key)
  if cached is not None:return cached
  window=remember(panel,key,tk.Toplevel(panel));window.title('选择需要重做主图的变体');window.geometry('620x480');window.minsize(440,340)
  footer=ttk.Frame(window,padding=12);footer.pack(side='bottom',fill='x');count=ttk.Label(footer);count.pack(side='left')
  ttk.Button(footer,text='完成选择',style='Primary.TButton',command=window.destroy).pack(side='right')
  query=tk.StringVar();ttk.Entry(window,textvariable=query).pack(fill='x',padx=14,pady=(14,8))
  bar=ttk.Frame(window,padding=(14,0));bar.pack(fill='x')
  holder=ttk.Frame(window,padding=12);holder.pack(fill='both',expand=True);holder.rowconfigure(0,weight=1);holder.columnconfigure(0,weight=1)
  box=ttk.Treeview(holder,columns=('sku','color'),show='tree headings',selectmode='browse');box.heading('#0',text='选择');box.column('#0',width=48,stretch=False);box.heading('sku',text='变体');box.column('sku',width=200);box.heading('color',text='颜色 / 规格');box.column('color',width=200)
  box.grid(row=0,column=0,sticky='nsew');scroll=ttk.Scrollbar(holder,orient='vertical',command=box.yview);scroll.grid(row=0,column=1,sticky='ns');box.configure(yscrollcommand=scroll.set)
  def render(*args):
   box.delete(*box.get_children());needle=query.get().strip().casefold()
   for b in bundles():
    p=b.get('variant_parameters') or {};sku=b['sku'];label=str(p.get('color',''))+' / '+str(p.get('size',''))
    if needle and needle not in (sku+' '+label).casefold():continue
    box.insert('','end',iid=sku,text='☑' if selected[sku].get() else '☐',values=(sku,label))
   count.configure(text='已选 '+str(sum(v.get() for v in selected.values()))+' 个变体');summary()
  def toggle(event):
   item=box.identify_row(event.y)
   if item:selected[item].set(not selected[item].get());render()
  def choose_all(value):
   for sku in box.get_children():selected[sku].set(value)
   render()
  ttk.Button(bar,text='全选当前结果',command=lambda:choose_all(True)).pack(side='left',padx=(0,6));ttk.Button(bar,text='清空当前结果',command=lambda:choose_all(False)).pack(side='left')
  box.bind('<ButtonRelease-1>',toggle);query.trace_add('write',render);render();return window
 choice_button.configure(command=picker)
 def update_ui(*args):
  rows=bundles();first_selection=not selected;target=current_sku() if current_sku else ''
  if not target and rows:target=rows[0]['sku']
  for b in rows:
   if b['sku'] not in selected:
    var=tk.BooleanVar(value=first_selection and b['sku']==target);selected[b['sku']]=var;var.trace_add('write',summary)
  if rows and not initialized[0]:
   initialized[0]=True
   if not shared_add.get('1.0','end-1c'):shared_add.insert('1.0',(rows[0].get('image_regeneration_options') or {}).get('shared_details',''))
  shared_button.configure(state='normal' if rows else 'disabled');summary()
 def select_current(sku):
  if sum(v.get() for v in selected.values())>1:return
  for key,var in selected.items():var.set(key==sku)
  summary()
 def poll():
  if not panel.winfo_exists():return
  rows=bundles();jobs=store.image_jobs.active([b['sku'] for b in rows]);changes=[b for b in rows if (b.get('asset_validation') or {}).get('main_changes') or (b.get('asset_validation') or {}).get('gallery_changes')]
  verification.configure(text=str(len(changes))+' 个变体的图片参数待核对' if changes else '')
  if jobs:
   job=next((j for j in jobs if j.get('state')!='queued'),jobs[0]);name='共用详情' if job.get('kind')=='shared_details' else job['sku']
   state.configure(text=str(len(jobs))+' 个任务 · '+name+' '+str(len(job.get('received_images') or []))+'/'+str(job.get('expected_images',0))+' 图')
  else:state.configure(text='本组暂无重做任务')
  if jobs:stop_button.pack(side='right')
  else:stop_button.pack_forget()
  if accept_button:
   if changes:accept_button.pack(side='left')
   else:accept_button.pack_forget()
  panel.after(1500,poll)
 update_ui();poll()
 return {'frame':panel,'shared_start':shared_button,'main_start':main_button,'shared_add':shared_add,'main_add':main_add,'selected':selected,'refresh':update_ui,'status':state,'select_current':select_current,'picker':picker,'choice':choice_button,'plan':plan_window,'plan_button':plan_button}
