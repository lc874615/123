"""Explicit official category selection before image generation, scoped to the shop."""
import copy,time

def selection(category,merchant):
 if not isinstance(category,dict) or not merchant:raise ValueError('请先连接店铺并选择官方类目')
 if any(type(category.get(k)) is not int or category[k]<=0 for k in ('description_category_id','type_id')):raise ValueError('请选择官方类目列表中的有效商品类型')
 value={k:copy.deepcopy(category[k]) for k in ('description_category_id','type_id','name','path','zh_path') if k in category}
 return {'account_id':str(merchant),'selected_at':time.time(),'category':{**value,'confirmed':True,'group_confirmed':True,'method':'creation_manual','attributes_revalidation_required':True}}

def apply_task(task,chosen,merchant):
 if not chosen:return
 if not isinstance(chosen,dict) or chosen.get('account_id')!=str(merchant):raise ValueError('店铺已切换，请重新选择创建类目')
 checked=selection(chosen.get('category'),merchant);checked['selected_at']=chosen.get('selected_at',checked['selected_at']);task['category_selection']=checked
 if chosen.get('visual_style_override'):
  from visual_plans import STYLES
  if chosen['visual_style_override'] not in STYLES:raise ValueError('未知作图风格，请重新选择')
  task['visual_style_override']=chosen['visual_style_override'];task['visual_style_account']=str(merchant)
 from visual_plans import build
 task['visual_plan']=build(checked['category'],task.get('variant_parameters'),override=task.get('visual_style_override'))

def category_for_task(task,merchant=None):
 chosen=task.get('category_selection')
 if not isinstance(chosen,dict) or not isinstance(chosen.get('category'),dict):return None
 if merchant is None:
  from account_context import credentials
  merchant=credentials()[0]
 category=copy.deepcopy(chosen['category'])
 if any(type(category.get(k)) is not int or category[k]<=0 for k in ('description_category_id','type_id')):return None
 if not merchant or chosen.get('account_id')!=str(merchant):category.update(confirmed=False,group_confirmed=False,method='creation_manual_other_shop')
 return category

def choose(parent,service,merchant_getter,save):
 import queue,threading,tkinter as tk
 from tkinter import ttk,messagebox
 from category_catalog import load_catalog
 from window_registry import lookup,remember
 cached=lookup(parent,('creation_category_picker',))
 if cached is not None:return cached
 merchant=str(merchant_getter() or '')
 if not merchant:messagebox.showinfo('先连接店铺','请在设置中连接 Ozon API 后选择官方类目。',parent=parent);return
 window=remember(parent,('creation_category_picker',),tk.Toplevel(parent));window.title('选择商品类目');window.geometry('920x600');window.minsize(640,420)
 footer=ttk.Frame(window,padding=12);footer.pack(side='bottom',fill='x');state=ttk.Label(footer,text='正在读取官方类目…',style='Muted.TLabel');state.pack(side='left')
 header=ttk.Frame(window,padding=(14,12));header.pack(fill='x');ttk.Label(header,text='选择商品类目',style='SectionTitle.TLabel').pack(side='left')
 query=tk.StringVar();entry=ttk.Entry(window,textvariable=query);entry.pack(fill='x',padx=14,pady=(0,10))
 body=ttk.Frame(window,padding=(14,0));body.pack(fill='both',expand=True);body.rowconfigure(0,weight=1);body.columnconfigure(0,weight=1)
 tree=ttk.Treeview(body,columns=('name','path'),show='headings',selectmode='browse');tree.heading('name',text='商品类型');tree.column('name',width=230);tree.heading('path',text='官方类目路径');tree.column('path',width=580);tree.grid(row=0,column=0,sticky='nsew');scroll=ttk.Scrollbar(body,orient='vertical',command=tree.yview);scroll.grid(row=0,column=1,sticky='ns');tree.configure(yscrollcommand=scroll.set)
 rows=[];shown={};results=queue.Queue();loading=[False];generation=[0]
 def render(*args):
  tree.delete(*tree.get_children());shown.clear();words=query.get().strip().casefold().split()
  found=[r for r in rows if all(w in (' '.join(str(r.get(k,'')) for k in ('name','path','zh_path'))).casefold() for w in words)]
  for i,r in enumerate(found[:500]):
   shown[str(i)]=r;name=str(r.get('zh_path') or r.get('name','')).split(' / ')[-1];tree.insert('','end',iid=str(i),values=(name+' / '+str(r.get('name','')),r.get('zh_path') or r.get('path','')))
  state.configure(text='匹配 '+str(len(found))+' 项'+(' · 输入关键词缩小范围' if len(found)>500 else ''))
 def load(force=False):
  if loading[0]:return
  loading[0]=True;generation[0]+=1;serial=generation[0];state.configure(text='正在读取官方类目…');reload_button.configure(state='disabled')
  def work():
   try:results.put((serial,load_catalog(service,merchant,force),None))
   except Exception as error:results.put((serial,None,str(error)))
  threading.Thread(target=work,daemon=True).start()
 def poll():
  if not window.winfo_exists():return
  try:
   serial,data,error=results.get_nowait()
   if serial==generation[0]:
    loading[0]=False;reload_button.configure(state='normal')
    if str(merchant_getter() or '')!=merchant:state.configure(text='店铺已切换，请关闭后重新选择')
    elif error:state.configure(text='读取未完成：'+error[:100])
    else:rows[:]=data;render()
  except queue.Empty:pass
  window.after(100,poll)
 def commit(event=None):
  if str(merchant_getter() or '')!=merchant:messagebox.showinfo('店铺已切换','请重新打开类目选择。',parent=window);return
  ids=tree.selection()
  if not ids or ids[0] not in shown:return
  save(selection(shown[ids[0]],merchant));window.destroy()
 reload_button=ttk.Button(header,text='刷新官方类目',command=lambda:load(True));reload_button.pack(side='right')
 ttk.Button(footer,text='使用此类目',style='Primary.TButton',command=commit).pack(side='right');tree.bind('<Double-1>',commit);query.trace_add('write',render);entry.focus_set();load();poll();window._ozon_ui={'tree':tree,'query':query,'select':commit,'status':state};return window
