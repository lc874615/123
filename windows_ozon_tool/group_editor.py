"""Whole-group, API-schema-driven grid with bulk edits and explicit submission."""
import copy,json,os,threading,webbrowser
from pathlib import Path
from attribute_service import field_key,category_key
from group_service import GroupService,revision
from variants import FIELDS,column_updates
from pricing_service import read
from publication_service import TERMINAL

EXCLUDED={8229,21845}
def open_editor(root,folder,service,group_folders,category_callback=None,price_callback=None,connection_callback=None,*,pricing,store,publication):
 import tkinter as tk
 from tkinter import ttk,messagebox
 from tkinter.scrolledtext import ScrolledText
 paths=[Path(p)/'listing_bundle.json' for p in group_folders]
 if not paths:messagebox.showinfo('没有变体','请选择尚未取消的商品组');return
 coordinator=GroupService(paths,service,pricing,store);dialog=tk.Toplevel(root);dialog.title('整组变体预览 · 可编辑与自动上架');dialog.geometry('1280x850');dialog.minsize(950,650)
 busy=False;selected=set(range(len(paths)));focus=['',''];bundles=[];token=None;rendered=None;warehouses={};photos=[];rows={};last_job=None;copy_dirty=False;displayed_copy=None
 ttk.Label(dialog,text='每列一个变体；双击单格修改，点击参数名选中整行后批量修改。仓库必须从当前店铺可用OGL/rFBS仓库中选择。').pack(pady=6)
 status=ttk.Label(dialog,text='正在加载整组预览',wraplength=1200);status.pack(pady=3)
 bar=ttk.Frame(dialog);bar.pack(fill='x',padx=8,pady=3)
 notebook=ttk.Notebook(dialog);notebook.pack(fill='both',expand=True,padx=8,pady=4)
 parameter_tab=ttk.Frame(notebook);copy_tab=ttk.Frame(notebook);media_tab=ttk.Frame(notebook);progress_tab=ttk.Frame(notebook)
 for widget,label in [(parameter_tab,'整组参数与官方必填项'),(copy_tab,'共用俄语文案'),(media_tab,'图片与视频'),(progress_tab,'提交与上架进度')]:notebook.add(widget,text=label)
 search=tk.StringVar();missing=tk.BooleanVar(value=False);filterbar=ttk.Frame(parameter_tab);filterbar.pack(fill='x',pady=4)
 ttk.Label(filterbar,text='参数关键词').pack(side='left');ttk.Entry(filterbar,textvariable=search,width=35).pack(side='left',padx=5);ttk.Checkbutton(filterbar,text='只看缺失必填项',variable=missing).pack(side='left')
 target_label=ttk.Label(filterbar);target_label.pack(side='right',padx=6)
 holder=ttk.Frame(parameter_tab);holder.pack(fill='both',expand=True);holder.rowconfigure(0,weight=1);holder.columnconfigure(0,weight=1)
 columns=[f'v{i}' for i in range(len(paths))];tree=ttk.Treeview(holder,columns=columns,show='tree headings',selectmode='browse')
 tree.heading('#0',text='参数 / 官方必填项 *');tree.column('#0',width=310,minwidth=240,stretch=False,anchor='center')
 for i,col in enumerate(columns):tree.column(col,width=240,minwidth=160,stretch=False,anchor='center')
 tree.grid(row=0,column=0,sticky='nsew');sx=ttk.Scrollbar(holder,orient='horizontal',command=tree.xview);sx.grid(row=1,column=0,sticky='ew');sy=ttk.Scrollbar(holder,orient='vertical',command=tree.yview);sy.grid(row=0,column=1,sticky='ns');tree.configure(xscrollcommand=sx.set,yscrollcommand=sy.set)
 tree.tag_configure('missing',foreground='#a40000');tree.tag_configure('pending',foreground='#9b5e00')
 detail=ttk.Label(parameter_tab,text='选择参数查看填写说明',wraplength=1180);detail.pack(fill='x',pady=5)
 selected_var=tk.StringVar();warehouse_choice=ttk.Combobox(bar,textvariable=selected_var,state='readonly',width=35);warehouse_choice.pack(side='right',padx=4)
 def offers():return [b.get('sku') for b in bundles]
 def active_job():return publication.active(offers()) if bundles else None
 def editable():
  if busy:return False
  if active_job():messagebox.showinfo('正在上架','本组有未完成的冻结提交任务，请先在进度页核对；未改动本地参数。',parent=dialog);return False
  return True
 def run(action,after=None):
  nonlocal busy
  if busy:return
  busy=True;submit_button.configure(state='disabled');status.configure(text='处理中，参数与售价同步后刷新…')
  def finish(error=None,result=None):
   nonlocal busy,rendered
   if not dialog.winfo_exists():return
   busy=False;rendered=None;refresh()
   if error:messagebox.showerror('整组处理未完成',error,parent=dialog)
   elif after:after(result)
  def work():
   try:result=action();root.after(0,lambda:finish(result=result))
   except Exception as exc:root.after(0,lambda text=str(exc):finish(error=text))
  threading.Thread(target=work,daemon=True).start()
 def chosen():return sorted(selected)
 def headings():
  for n,col in enumerate(columns):tree.heading(col,text=('☑ ' if n in selected else '☐ ')+paths[n].parent.name,command=lambda n=n:toggle(n))
  target_label.configure(text=f'批量对象 {len(chosen())}/{len(paths)} 个变体；点击列标题切换')
 def toggle(n):
  if n in selected:selected.remove(n)
  else:selected.add(n)
  headings()
 def value_for(b,row,n):
  kind,key=row
  if kind=='p':return (b.get('variant_parameters') or {}).get(key,'')
  if kind=='a':
   identifier=int(key.rsplit(':',1)[1])
   if identifier==21841:return (b.get('video') or {}).get('https_url') or '8秒视频链接待托管'
   if identifier==21837:return (b.get('copy') or {}).get('title_ru','')
   state=b.get('attribute_draft') or {}
   if not any(field_key(f)==key for f in state.get('fields',[])):return '— 此类目不适用'
   values=(state.get('values') or {}).get(key) or []
   if values:return '；'.join(str(v.get('value') or v.get('dictionary_value_id')) for v in values)
   old=(state.get('migration_pending') or {}).get(key)
   return '待匹配原值：'+'；'.join(v.get('value','') for v in old) if old else ''
  if key=='category':return ((b.get('category') or {}).get('name') or '待选择')+'（'+('已确认' if (b.get('category') or {}).get('confirmed') else '待确认，双击')+'）'
  if key=='price':return b.get('price_cny') or b.get('pricing_status','等待计算')
  if key=='vat':return (b.get('export_settings') or {}).get('vat','')
  if key=='warehouse':
   setting=b.get('fulfillment') or {};return setting.get('warehouse_name','未选择')+' / '+str(setting.get('warehouse_id') or '')
  if key=='currency':return 'CNY（已确认）' if (b.get('export_settings') or {}).get('currency_confirmed') else '待确认CNY'
  if key=='media':return str((b.get('hosting') or {}).get('verified_images',0))+'/8图；'+('视频✓' if (b.get('video_hosting') or {}).get('state')=='done' else '视频待处理')
  if key=='status':return b.get('pricing_status','')
  return ''
 def grid_refresh():
  nonlocal rows
  selected_row=tree.selection();expanded={iid:tree.item(iid,'open') for iid in ('basic','api','listing') if tree.exists(iid)};tree.delete(*tree.get_children());rows={}
  for key,label in [('basic','基础事实、成本与库存'),('api','官方类目参数（* 必填；按API动态调整）'),('listing','类目、自动售价、税率与仓库')]:tree.insert('','end',iid=key,text=label,open=expanded.get(key,True))
  specs=[('basic','p:'+key,('p',key),label,False,None) for key,label,_ in FIELDS]
  union={}
  for b in bundles:
   for field in (b.get('attribute_draft') or {}).get('fields',[]):
    if field['id'] not in EXCLUDED:union.setdefault(field_key(field),field)
  for key,field in union.items():specs.append(('api','a:'+key,('a',key),field.get('name','')+' / '+field.get('name_ru',''),bool(field.get('is_required')),field))
  for key,label in [('category','上架类目 / 商品类型'),('price','自动售价（人民币元）'),('vat','实际增值税率'),('currency','店铺币种'),('warehouse','所选OGL/rFBS仓库'),('media','托管链接进度'),('status','定价状态 / 待处理原因')]:specs.append(('listing','s:'+key,('s',key),label,key in ('category','vat','warehouse'),None))
  for parent,iid,row,label,required,field in specs:
   values=[value_for(b,row,n) for n,b in enumerate(bundles)];empty=any(not v for v in values)
   if search.get().casefold() not in label.casefold():continue
   if missing.get() and (not required or not empty):continue
   rows[iid]=(row,field);tree.insert(parent,'end',iid=iid,text=('* ' if required else '')+label,values=values,tags=('missing',) if required and empty else ('pending',) if any(str(v).startswith('待匹配') for v in values) else ())
  if selected_row and tree.exists(selected_row[0]):tree.selection_set(selected_row[0])
  headings()
 def refresh():
  nonlocal bundles,token,rendered,last_job,displayed_copy
  if not dialog.winfo_exists():return
  try:
   current=coordinator.load();current_token=revision(current)
   if current_token!=rendered:
    bundles=current;token=current_token;rendered=current_token;grid_refresh()
   actual_copy=bundles[0].get('copy') or {}
   if not copy_dirty and actual_copy!=displayed_copy:
    for key,widget in copy_widgets.items():
     widget.delete('1.0','end');widget.insert('1.0','\n'.join(actual_copy.get(key,[])) if key=='tags_ru' else actual_copy.get(key,''));widget.edit_modified(False)
    displayed_copy=copy.deepcopy(actual_copy)
   merchant=os.environ.get('OZON_CLIENT_ID') or '未连接';job=active_job();last_job=job or next((j for j in publication.jobs() if set(offers())&set(j.get('items',{}))),None)
   status.configure(text='店铺Client-Id：'+merchant+' | '+(coordinator.status if busy else '整组 '+str(len(paths))+' 个变体')+' | '+(last_job.get('message','') if last_job else '编辑会同步重算售价；提交前请核对图文与参数'))
   if copy_dirty:status.configure(text=status.cget('text')+' | 共用文案尚未保存')
   submit_button.configure(state='disabled' if busy or job or copy_dirty else 'normal');progress_refresh()
  except (OSError,ValueError):status.configure(text='正在等待草稿保存完成')
 def refilter(*args):
  nonlocal rendered
  rendered=None;refresh()
 search.trace_add('write',refilter);missing.trace_add('write',refilter)
 def text_editor(label,indices,initial,save,multiline=False):
  window=tk.Toplevel(dialog);window.title(label);window.geometry('760x420');ttk.Label(window,text='目标：'+'、'.join(paths[n].parent.name for n in indices),wraplength=720).pack(pady=7)
  text=ScrolledText(window,height=12);text.pack(fill='both',expand=True,padx=8);text.insert('1.0',initial)
  ttk.Label(window,text='一行表示全部目标填相同值；多行按目标顺序逐项填写。集合属性内多个值用中文分号；分隔。').pack(pady=4)
  def apply():
   content=text.get('1.0','end-1c')
   try:values=column_updates(content,len(indices)) if not multiline else [content]
   except ValueError as exc:messagebox.showerror('未修改',str(exc),parent=window);return
   window.destroy();run(lambda:save(values))
  ttk.Button(window,text='保存并同步属性与售价',command=apply).pack(pady=7)
 def edit_row(indices,iid):
  if not editable() or iid not in rows:return
  if not indices:messagebox.showinfo('未选择变体','请至少勾选一个变体列',parent=dialog);return
  row,field=rows[iid];kind,key=row;expected=token
  if kind=='a' and int(key.rsplit(':',1)[1]) in (21841,21837):
   messagebox.showinfo('自动使用生成视频','视频链接自动使用本变体生成的8秒MP4；视频名称沿用共用标题。',parent=dialog);return
  if kind=='s':
   if key=='category':choose_category(indices);return
   if key=='warehouse':choose_warehouse(indices);return
   if key=='price':
    if price_callback:price_callback(indices[0])
    return
   if key=='currency':text_editor('输入CNY确认店铺结算币种',indices,'CNY',lambda values:settings_batch(indices,'currency',values,expected));return
   if key=='vat':text_editor('修改实际税率（0/0.05/0.07/0.1/0.2/0.22）',indices,value_for(bundles[indices[0]],row,indices[0]),lambda values:settings_batch(indices,'vat',values,expected));return
   return
  initial=value_for(bundles[indices[0]],row,indices[0])
  if str(initial).startswith('待匹配原值：'):initial=initial.split('：',1)[1]
  if kind=='p':text_editor('修改 '+iid,indices,str(initial),lambda values:coordinator.set_parameters(indices,key,values,expected));return
  if len(indices)==1 and field.get('dictionary_id'):dictionary_editor(indices[0],key,field,expected);return
  def save(values):
   resolved=[coordinator.resolve_text(n,key,v) for n,v in zip(indices,values)];coordinator.set_attributes(indices,key,resolved,expected)
  text_editor('修改官方属性：'+field.get('name',''),indices,str(initial) if len(indices)==1 else '',save)
 def settings_batch(indices,key,values,expected):
  # Validate all selected tax values before any write; identical values can be applied together.
  if key=='vat' and any(v not in ('0','0.05','0.07','0.1','0.2','0.22') for v in values):raise ValueError('税率值无效，未修改任何变体')
  coordinator.set_settings_many(indices,key,values,expected)
 def double_click(event):
  iid=tree.identify_row(event.y);col=tree.identify_column(event.x)
  if iid in rows and col!='#0':
   index=int(col[1:])-1;focus[:]=[iid,index];edit_row([index],iid)
 def track(event=None):
  if tree.selection() and tree.selection()[0] in rows:
   iid=tree.selection()[0];focus[0]=iid;row,field=rows[iid];detail.configure(text=(field.get('description','') if field else '基础参数以填写单位为准；包装与商品尺寸分别处理。')+' | 当前参数可对选中变体批量修改')
 tree.bind('<Double-1>',double_click);tree.bind('<<TreeviewSelect>>',track)
 def bulk():
  iid=tree.selection()[0] if tree.selection() else focus[0]
  if iid:edit_row(chosen(),iid)
 ttk.Button(bar,text='批量修改当前参数',command=bulk).pack(side='left',padx=3)
 def refresh_all():
  if not editable():return
  run(lambda:coordinator.after_edit(list(range(len(paths)))))
 ttk.Button(bar,text='刷新API参数并重新定价',command=refresh_all).pack(side='left',padx=3)
 if connection_callback:ttk.Button(bar,text='连接Ozon API',command=connection_callback).pack(side='left',padx=3)
 def load_warehouses():
  def action():return publication.warehouses()
  def show(result):
   nonlocal warehouses
   warehouses={str(r['warehouse_id']):r for r in result};warehouse_choice.configure(values=[r['name']+' / '+str(r['warehouse_id']) for r in result]);status.configure(text=f'已读取本店铺可用OGL/rFBS仓库 {len(result)} 个，请选择仓库。')
   if not result:messagebox.showinfo('没有可选择的仓库',publication.warehouse_summary()+'\n可点击“导出仓库诊断”进一步检查。',parent=dialog)
   if len(result)==1:
    selected_var.set(result[0]['name']+' / '+str(result[0]['warehouse_id']))
    if not active_job():
     expected=coordinator.token();merchant=publication.account_getter()
     run(lambda:coordinator.use_only_warehouse(result,merchant,expected))
  run(action,show)
 ttk.Button(bar,text='读取店铺可用仓库',command=load_warehouses).pack(side='right',padx=3)
 def export_warehouse_diagnostic():
  from tkinter import filedialog
  target=filedialog.asksaveasfilename(parent=dialog,title='保存仓库诊断（不含密钥、仓库名称或地址）',defaultextension='.json',initialfile='warehouse_diagnostic.json')
  if target:
   try:
    from pricing_service import write
    write(Path(target),getattr(publication,'warehouse_diagnostic',{'message':'请先读取仓库'}));messagebox.showinfo('已保存','仓库诊断已保存，不含API密钥。',parent=dialog)
   except OSError:messagebox.showerror('保存失败','请选择可写入的文件位置',parent=dialog)
 ttk.Button(bar,text='导出仓库诊断',command=export_warehouse_diagnostic).pack(side='right',padx=3)
 def warehouse_apply(event=None):
  if not editable():return
  if not chosen():messagebox.showinfo('未选择变体','请先勾选目标变体列',parent=dialog);return
  try:wid=selected_var.get().rsplit(' / ',1)[1];record=warehouses[wid];merchant=publication.account_getter()
  except (IndexError,KeyError,ValueError):return
  expected=token;run(lambda:coordinator.set_settings(chosen(),'warehouse',{'warehouse_id':record['warehouse_id'],'warehouse_name':record['name'],'account_id':merchant},expected))
 warehouse_choice.bind('<<ComboboxSelected>>',warehouse_apply)
 def choose_warehouse(indices):
  def show(result):
   window=tk.Toplevel(dialog);window.title('选择本店铺可用OGL/rFBS仓库');ttk.Label(window,text='目标：'+'、'.join(paths[n].parent.name for n in indices)).pack(pady=5);choices=ttk.Combobox(window,state='readonly',values=[r['name']+' / '+str(r['warehouse_id']) for r in result],width=65);choices.pack(padx=10,pady=10)
   def apply():
    if choices.current()<0:return
    record=result[choices.current()];expected=coordinator.token();merchant=publication.account_getter();window.destroy();run(lambda:coordinator.set_settings(indices,'warehouse',{'warehouse_id':record['warehouse_id'],'warehouse_name':record['name'],'account_id':merchant},expected))
   ttk.Button(window,text='应用到所选变体并重算售价',command=apply).pack(pady=8)
  run(publication.warehouses,show)
 def dictionary_editor(index,key,field,expected):
  window=tk.Toplevel(dialog);window.title(paths[index].parent.name+' · 官方字典：'+field.get('name',''));window.geometry('780x500');query=tk.StringVar();ttk.Entry(window,textvariable=query,width=60).pack(pady=6)
  box=tk.Listbox(window,selectmode='extended' if field.get('is_collection') else 'browse',exportselection=False);box.pack(fill='both',expand=True,padx=8);loaded={};visible=[];cursor=[0]
  def filter_values(*args):
   nonlocal visible
   visible=[r for r in loaded.values() if query.get().casefold() in (str(r.get('value') or '')+' '+str(r.get('info') or '')).casefold()];box.delete(0,'end')
   for r in visible:box.insert('end',str(r.get('value') or '')+' '+str(r.get('info') or ''))
  query.trace_add('write',filter_values)
  def fetch(searching=False):
   text=query.get() if searching else ''
   def action():return service.dictionary(coordinator.load()[index],field,text,cursor[0])
   def show(response):
    if not window.winfo_exists():return
    for r in response['result']:loaded[r['id']]=r
    if not searching and response['result']:cursor[0]=response['result'][-1]['id']
    filter_values()
   run(action,show)
  tools=ttk.Frame(window);tools.pack(pady=4);ttk.Button(tools,text='加载中文选项 / 下一页',command=lambda:fetch(False)).pack(side='left',padx=4);ttk.Button(tools,text='官方关键词搜索',command=lambda:fetch(True)).pack(side='left',padx=4)
  def save():
   if not box.curselection():return
   values=[{'dictionary_value_id':visible[n]['id'],'value':visible[n]['value']} for n in box.curselection()];window.destroy();run(lambda:coordinator.set_attributes([index],key,[values],expected))
  ttk.Button(window,text='保存官方选项并重算售价',command=save).pack(pady=7);fetch(False)
 def choose_category(indices):
  # Show the known category immediately. A click no longer fetches both full trees.
  window=tk.Toplevel(dialog);window.title('确认当前类目 / 搜索其他官方类目');window.geometry('1000x600')
  text='\n'.join(paths[n].parent.name+'：'+str((bundles[n].get('category') or {}).get('path') or (bundles[n].get('category') or {}).get('name') or '未匹配')+'（'+('已确认' if (bundles[n].get('category') or {}).get('confirmed') else '待确认')+'）' for n in indices)
  ttk.Label(window,text=text,wraplength=950).pack(pady=8)
  def confirm_current():
   expected=token;window.destroy();run(lambda:coordinator.confirm_current_categories(indices,expected))
  ttk.Button(window,text='确认沿用当前类目（无需重新搜索）',command=confirm_current).pack(pady=5)
  query=tk.StringVar();ttk.Label(window,text='需要换类目时，加载列表后输入中文或俄文关键词。列表缓存24小时。').pack(pady=5);ttk.Entry(window,textvariable=query,width=75).pack()
  box=tk.Listbox(window,exportselection=False);box.pack(fill='both',expand=True,padx=10,pady=5);result=[];matches=[];count=ttk.Label(window,text='当前类目可直接确认；无需等待全量类目列表。');count.pack()
  def filter_categories(*args):
   nonlocal matches
   found=[r for r in result if all(word in (r['zh_path']+' '+r['path']).casefold() for word in query.get().casefold().split())];matches=found[:500];box.delete(0,'end')
   for r in matches:box.insert('end',r['zh_path']+' | '+r['name'])
   count.configure(text=f'匹配 {len(found)} 项，最多显示500项')
  query.trace_add('write',filter_categories)
  def fetch(force=False):
   from category_catalog import load_catalog
   count.configure(text='后台读取官方类目列表…')
   def show(loaded):
    nonlocal result
    if not window.winfo_exists():return
    result=loaded;filter_categories()
   run(lambda:load_catalog(service,publication.account_getter(),force),show)
  toolbar=ttk.Frame(window);toolbar.pack(pady=5)
  ttk.Button(toolbar,text='加载可搜索类目（优先缓存）',command=fetch).pack(side='left',padx=4)
  ttk.Button(toolbar,text='重新获取官方列表',command=lambda:fetch(True)).pack(side='left',padx=4)
  def apply():
   if not box.curselection():return
   category=matches[box.curselection()[0]];expected=token;window.destroy();run(lambda:coordinator.change_category(indices,category,expected))
  ttk.Button(window,text='应用选中类目、迁移参数并重新定价',command=apply).pack(pady=7)
 # Common copy has a separate readable editor, shared by every variant.
 copy_widgets={}
 for key,label,height in [('title_ru','共用俄语标题',2),('description_ru','共用俄语简介',8),('tags_ru','共用标签（每行一个）',4)]:
  ttk.Label(copy_tab,text=label).pack(anchor='w',padx=8,pady=3);widget=ScrolledText(copy_tab,height=height,wrap='word');widget.pack(fill='both',expand=key=='description_ru',padx=8);copy_widgets[key]=widget
 initial=(coordinator.load()[0].get('copy') or {})
 for key,widget in copy_widgets.items():widget.insert('1.0','\n'.join(initial.get(key,[])) if key=='tags_ru' else initial.get(key,''))
 def mark_copy_dirty(event):
  nonlocal copy_dirty
  if event.widget.edit_modified():copy_dirty=True;event.widget.edit_modified(False)
 for widget in copy_widgets.values():widget.edit_modified(False);widget.bind('<<Modified>>',mark_copy_dirty)

 def save_copy():
  if not editable():return
  value={key:w.get('1.0','end-1c').strip() for key,w in copy_widgets.items()};value['tags_ru']=[t.strip() for t in value['tags_ru'].splitlines() if t.strip()];value['missing_facts']=(bundles[0].get('copy') or {}).get('missing_facts',[]);expected=token
  def saved(result):
   nonlocal copy_dirty
   copy_dirty=False;refresh()
  run(lambda:coordinator.set_copy(value,expected),saved)
 ttk.Button(copy_tab,text='保存为整组共用文案并同步属性',command=save_copy).pack(pady=6)
 media_body=ttk.Frame(media_tab);media_body.pack(fill='both',expand=True)
 def media_refresh():
  from PIL import Image,ImageOps,ImageTk
  for child in media_body.winfo_children():child.destroy()
  photos.clear()
  for n,b in enumerate(bundles):
   frame=ttk.LabelFrame(media_body,text=b['sku']);frame.grid(row=n//4,column=n%4,padx=8,pady=8,sticky='n')
   if b.get('images'):
    path=paths[n].parent/b['images'][0]['local_file']
    try:
     with Image.open(path) as image:photo=ImageTk.PhotoImage(ImageOps.contain(image.convert('RGB'),(140,180)))
     photos.append(photo);thumbnail=ttk.Label(frame,image=photo,cursor='hand2');thumbnail.pack(padx=6,pady=6);thumbnail.bind('<Button-1>',lambda e,n=n:show_image(n,0))
    except (OSError,ValueError):ttk.Label(frame,text='主图不可读').pack(pady=20)
   ttk.Button(frame,text='查看8张图片',command=lambda n=n:gallery(n)).pack(pady=3)
   ttk.Button(frame,text='播放本地8秒视频',command=lambda n=n:play_video(n)).pack(pady=3)
 def show_image(index,start):
  from image_viewer import open_viewer
  return open_viewer(dialog,paths[index].parent,bundles[index].get('images') or [],start,bundles[index]['sku']+' · 图片预览')
 def gallery(index):
  window=tk.Toplevel(dialog);window.title(bundles[index]['sku']+' · 01主图 / 02—08详情');images=[]
  from PIL import Image,ImageOps,ImageTk
  for i,row in enumerate(bundles[index].get('images') or []):
   cell=ttk.Frame(window);cell.grid(row=i//4,column=i%4,padx=5,pady=5)
   try:
    with Image.open(paths[index].parent/row['local_file']) as source:photo=ImageTk.PhotoImage(ImageOps.contain(source.convert('RGB'),(150,200)))
    images.append(photo);thumbnail=ttk.Label(cell,image=photo,cursor='hand2');thumbnail.pack();thumbnail.bind('<Button-1>',lambda e,n=index,start=i:show_image(n,start))
   except (OSError,ValueError,KeyError):ttk.Label(cell,text='图片不可读').pack()
   ttk.Label(cell,text=f'{i+1:02d} '+('本变体主图' if i==0 else '共用详情图')).pack()
  window._photos=images
 def play_video(index):
  path=paths[index].parent/'video'/'product_8s.mp4'
  if os.name=='nt' and path.is_file():os.startfile(str(path))
  elif (bundles[index].get('video') or {}).get('https_url'):webbrowser.open(bundles[index]['video']['https_url'])
 ttk.Button(media_tab,text='刷新图文预览',command=media_refresh).pack(pady=5)
 progress=ttk.Treeview(progress_tab,columns=('offer','warehouse','quantity','state','errors'),show='headings',height=12)
 for key,label,width in [('offer','货号',180),('warehouse','目标仓库',200),('quantity','目标库存 / 当前可用',160),('state','上架阶段',250),('errors','平台结果 / 错误',350)]:progress.heading(key,text=label);progress.column(key,width=width,anchor='center')
 progress.pack(fill='both',expand=True,padx=8,pady=8);progress_info=ScrolledText(progress_tab,height=6);progress_info.pack(fill='x',padx=8,pady=5)
 def progress_refresh():
  if not last_job:return
  progress.delete(*progress.get_children())
  for offer,item in last_job.get('items',{}).items():
   setting=last_job['stocks'][offer];progress.insert('','end',values=(offer,setting['warehouse_name'],str(setting['stock'])+' / '+str(item.get('current_free_stock','待查询')),item.get('status',''),json.dumps(item.get('errors') or item.get('platform_status') or {},ensure_ascii=False)))
  text=json.dumps({'任务':last_job['id'],'导入任务ID':last_job.get('task_id'),'状态':last_job['state'],'说明':last_job.get('message')},ensure_ascii=False,indent=2)
  if progress_info.get('1.0','end-1c')!=text:progress_info.delete('1.0','end');progress_info.insert('1.0',text)
 def query_status():
  if last_job:run(lambda:publication.step(last_job['id'],refresh=True))
 ttk.Button(progress_tab,text='立即查询导入、库存及可售状态',command=query_status).pack(pady=4)
 def reconcile_import():
  if not last_job or last_job['state']!='import_uncertain':return
  if not messagebox.askyesno('必须先在Ozon后台核对','提交超时且没有任务ID，程序无法判断是否受理。只有你已在Ozon后台确认此次未受理，才能解除并重新提交。是否已确认未受理？',parent=dialog):return
  run(lambda:publication.resolve_no_import(last_job['id']))
 def retry_stock():
  if not last_job:return
  if not messagebox.askyesno('核对当前与目标库存','仅重设结果不确定的库存项，数量以进度表“目标库存”为准。可能覆盖销售后的可用数量。是否按所示目标数重新设置？',parent=dialog):return
  run(lambda:publication.retry_uncertain_stock(last_job['id']))
 recovery=ttk.Frame(progress_tab);recovery.pack(pady=4)
 ttk.Button(recovery,text='已在后台确认未受理，解除重试',command=reconcile_import).pack(side='left',padx=4)
 ttk.Button(recovery,text='按预览目标重设不确定库存',command=retry_stock).pack(side='left',padx=4)
 def cancel_followup():
  if not last_job:return
  if not messagebox.askyesno('停止后续跟进','停止未来自动写入，已受理的商品导入和已设置库存不会撤销。之后可修改新预览再次提交。是否停止？',parent=dialog):return
  run(lambda:publication.cancel_followup(last_job['id']))
 ttk.Button(recovery,text='停止后续跟进（不撤销已完成操作）',command=cancel_followup).pack(side='left',padx=4)


 def submit():
  if copy_dirty:messagebox.showinfo('文案未保存','请先保存整组共用文案',parent=dialog);notebook.select(copy_tab);return
  if not editable():return
  from category_catalog import setup_errors
  errors=setup_errors(coordinator.load(),os.environ.get('OZON_CLIENT_ID',''))
  if errors:
   messagebox.showinfo('提交前还需设置', '\n\n'.join(errors),parent=dialog);notebook.select(parameter_tab);return
  expected=token
  def submitted(job):
   nonlocal last_job
   last_job=job;notebook.select(progress_tab);refresh()
  run(lambda:publication.begin(coordinator,expected),submitted)
 bottom=ttk.Frame(dialog);bottom.pack(fill='x',padx=8,pady=6)
 ttk.Label(bottom,text='同货号已存在时会更新商品；选择仓库后按各变体目标库存设置。仅设置所选仓库；库存0不售；税率字段不自动增加定价税费。').pack(side='left')
 submit_button=ttk.Button(bottom,text='提交/更新整组并自动上架',command=submit);submit_button.pack(side='right',padx=6)
 def preview_only():
  from listing_preview import export_preview
  def action():
   current=coordinator.load();settings=[b.get('export_settings') or {} for b in current]
   for b,setting in zip(current,settings):
    if not setting.get('currency_confirmed'):raise ValueError('请在币种行确认CNY')
   service.confirm_many(paths,settings[0].get('vat'),True) if len({s.get('vat') for s in settings})==1 else [service.confirm(p,s.get('vat'),True) for p,s in zip(paths,settings)]
   with service.lock:
    for p in paths:
     b=read(p);b['pricing_confirmed_fingerprint']=b.get('pricing_fingerprint');b['pricing_confirmed_price']=b.get('price_cny');from pricing_service import write;write(p,b)
   return export_preview([p.parent for p in paths],Path(folder)/'listing_preview',service.lock)
  def show(report):messagebox.showinfo('本地预览','校验通过，已导出；未提交。' if report['ready'] else '\n'.join(r['offer_id']+'：'+'；'.join(r['missing']) for r in report['items'] if not r['ready']),parent=dialog)
  run(action,show)
 ttk.Button(bottom,text='仅校验 / 导出整组预览',command=preview_only).pack(side='right',padx=5)
 def poll():
  if not dialog.winfo_exists():return
  refresh();dialog.after(1500,poll)
 refresh();media_refresh();poll()
 try:
  publication.account_getter();dialog.after(100,load_warehouses)
 except ValueError:status.configure(text='请先连接Ozon API，再读取店铺可用仓库')
 return dialog
