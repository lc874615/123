"""Whole-group, API-schema-driven grid with bulk edits and explicit submission."""
import copy,json,os,threading,time,webbrowser
from pathlib import Path
from attribute_service import field_key,category_key
from group_service import GroupService,revision
from variants import FIELDS,column_updates
from pricing_service import read
from publication_service import TERMINAL,warehouse_label

EXCLUDED={8229,21845}
def open_editor(root,folder,service,group_folders,category_callback=None,price_callback=None,connection_callback=None,*,pricing,store,publication,hosting=None):
 import tkinter as tk
 from tkinter import ttk,messagebox
 from tkinter.scrolledtext import ScrolledText
 paths=[Path(p)/'listing_bundle.json' for p in group_folders]
 if not paths:messagebox.showinfo('没有变体','请选择尚未取消的商品组');return
 coordinator=GroupService(paths,service,pricing,store)
 coordinator.ensure_fixed_vat()
 if publication.initial_stock is not None and not publication.active([p.parent.name for p in paths]):coordinator.ensure_initial_stock(publication.initial_stock)
 dialog=tk.Toplevel(root);dialog.title('整组预览 · Ozon 商品自动化 1.0.15');dialog.geometry('1280x850');dialog.minsize(950,650)
 busy=False;selected=set(range(len(paths)));focus=['',''];bundles=[];token=None;rendered=None;warehouses={};photos=[];rows={};last_job=None;copy_dirty=False;displayed_copy=None;copy_timer=None;busy_since=0;operation_error='';operation_name=''
 ttk.Label(dialog,text='每列一个变体；双击单格修改，点击参数名选中整行后批量修改。仓库显示当前店铺全部类型和状态。',wraplength=900).pack(pady=6)
 status=ttk.Label(dialog,text='正在加载整组预览',wraplength=1200);status.pack(pady=3)
 bar=ttk.Frame(dialog);bar.pack(fill='x',padx=8,pady=3);more_menu=tk.Menu(dialog,tearoff=False);ttk.Menubutton(bar,text='更多',menu=more_menu).pack(side='right',padx=4)
 footer=ttk.Frame(dialog,padding=(8,5));footer.pack(side='bottom',fill='x');blocker=ttk.Label(footer,text='',wraplength=900,foreground='#b00020');blocker.pack(fill='x');asset_actions=ttk.Frame(footer);asset_actions.pack(fill='x');bottom=ttk.Frame(footer);bottom.pack(fill='x',pady=4)
 notebook=ttk.Notebook(dialog);notebook.pack(fill='both',expand=True,padx=8,pady=4)
 parameter_tab=ttk.Frame(notebook);copy_tab=ttk.Frame(notebook);media_tab=ttk.Frame(notebook);progress_tab=ttk.Frame(notebook)
 for widget,label in [(parameter_tab,'参数'),(copy_tab,'共用文案'),(media_tab,'图片视频'),(progress_tab,'上架进度')]:notebook.add(widget,text=label)
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
  if active_job():notebook.select(progress_tab);messagebox.showinfo('已有提交任务','已打开上架进度页。请查看逐变体状态；资料已变化可停止旧任务跟进后重新编辑，结果未知的写入需要先核对。',parent=dialog);return False
  return True
 def run(action,after=None,label='同步参数与售价'):
  nonlocal busy,busy_since,operation_error,operation_name
  if busy:return
  busy=True;busy_since=time.monotonic();operation_error='';operation_name=label;coordinator.status=label;submit_button.configure(state='disabled');update_button.configure(state='disabled');status.configure(text='处理中，参数与售价同步后刷新…')
  def finish(error=None,result=None):
   nonlocal busy,rendered,operation_error
   if not dialog.winfo_exists():return
   busy=False;rendered=None;operation_error=error or '';refresh()
   if error:
    notebook.select(progress_tab);progress_info.delete('1.0','end');progress_info.insert('1.0','提交/处理未完成：\n'+error+'\n\n若提示预览内容变化，核对所列字段后再提交。若有结果不确定的导入任务，请先核对平台回执。');messagebox.showerror('整组处理未完成',error,parent=dialog)
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
   from assisted_fields import inline_references
   reference=inline_references(b).get(key)
   if reference:return reference['display']+'（参考）'
   old=(state.get('migration_pending') or {}).get(key)
   return '待匹配原值：'+'；'.join(v.get('value','') for v in old) if old else ''
  if key=='category':return ((b.get('category') or {}).get('name') or '待选择')+'（'+('已确认' if (b.get('category') or {}).get('confirmed') else '待确认，双击')+'）'
  if key=='price':return b.get('price_cny') or b.get('pricing_status','等待计算')
  if key in ('price_max','price_old','price_min','price_cost'):
   from listing_prices import listing_prices
   try:return listing_prices(b)[{'price_max':'price','price_old':'old_price','price_min':'min_price','price_cost':'net_price'}[key]]
   except Exception:return '等待有效售价和成本'
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
  specs=[('basic','p:'+key,('p',key),('初始库存（固定1000）' if key=='stock' and publication.initial_stock==1000 else label),False,None) for key,label,_ in FIELDS]
  union={}
  for b in bundles:
   for field in (b.get('attribute_draft') or {}).get('fields',[]):
    from assisted_fields import is_pdf
    if field['id'] not in EXCLUDED and not is_pdf(field):union.setdefault(field_key(field),field)
  for key,field in union.items():specs.append(('api','a:'+key,('a',key),field.get('name','')+' / '+field.get('name_ru',''),bool(field.get('is_required')),field))
  for key,label in [('category','上架类目 / 商品类型'),('price','计算售价 / 促销底价基准（人民币元）'),('price_max','最高价格（基准×2）'),('price_old','划线价（基准×4）'),('price_min','促销最低限制（基准×1）'),('price_cost','平台成本（所填成本）'),('vat','实际增值税率'),('currency','店铺币种'),('warehouse','所选店铺仓库'),('media','托管链接进度'),('status','定价状态 / 待处理原因')]:specs.append(('listing','s:'+key,('s',key),label,key in ('category','vat','warehouse'),None))
  for parent,iid,row,label,required,field in specs:
   values=[value_for(b,row,n) for n,b in enumerate(bundles)];empty=any(not v for v in values)
   if search.get().casefold() not in label.casefold():continue
   if missing.get() and (not required or not empty):continue
   rows[iid]=(row,field);tree.insert(parent,'end',iid=iid,text=('* ' if required else '')+label,values=values,tags=('missing',) if required and empty else ('pending',) if any(str(v).startswith('待匹配') for v in values) else ())
  if selected_row and tree.exists(selected_row[0]):tree.selection_set(selected_row[0])
  headings();badges.schedule()
 def refresh():
  nonlocal bundles,token,rendered,last_job,displayed_copy
  if not dialog.winfo_exists():return
  try:
   current=coordinator.load();current_token=revision(current)
   if current_token!=rendered:
    media_changed=[[r.get('sha256') for r in b.get('images') or []] for b in bundles]!=[[r.get('sha256') for r in b.get('images') or []] for b in current]
    bundles=current;token=current_token;rendered=current_token;grid_refresh();regen_ui['refresh']()
    if media_changed:media_refresh()
   actual_copy=bundles[0].get('copy') or {}
   if not copy_dirty and actual_copy!=displayed_copy:
    for key,widget in copy_widgets.items():
     widget.delete('1.0','end');widget.insert('1.0','\n'.join(actual_copy.get(key,[])) if key=='tags_ru' else actual_copy.get(key,''));widget.edit_modified(False)
    displayed_copy=copy.deepcopy(actual_copy)
   merchant=os.environ.get('OZON_CLIENT_ID') or '未连接';job=active_job();last_job=job or next((j for j in publication.jobs() if j.get('account_id')==os.environ.get('OZON_CLIENT_ID') and set(offers())&set(j.get('items',{}))),None)
   status.configure(text='店铺Client-Id：'+merchant+' | '+(coordinator.status if busy else '整组 '+str(len(paths))+' 个变体')+' | '+(last_job.get('message','') if last_job else '编辑会同步重算售价；提交前请核对图文与参数'))
   if busy:status.configure(text=status.cget('text')+' | 正在'+coordinator.status+'（已用'+str(int(time.monotonic()-busy_since))+'秒）'+(' | '+service.status if '官方属性' in coordinator.status else ''))
   if operation_error:status.configure(text='处理未完成：'+operation_error[:220]+' | 详见提交与上架进度页')
   from asset_state import pending
   changed=[b['sku'] for b in bundles if b.get('regeneration_pending') or any((b.get('asset_review') or {}).get(k) for k in ('main','gallery'))]
   if any(b.get('image_regeneration_jobs') for b in bundles):status.configure(text='图片重做已排队或正在采集；进度见图片视频页，无需重新提交上架。')
   elif changed:status.configure(text='图片待核对：'+str(len(changed))+'个变体；变化项见图片视频页。图片无误请点击底部“图片无误，沿用本组”。')
   elif any((b.get('asset_review') or {}).get('copy') for b in bundles):status.configure(text='图片已校验，整组文案自动采集或补全后同步全部变体。')
   if changed and not any(b.get('image_regeneration_jobs') for b in bundles):
    if not accept_button.winfo_manager():accept_button.pack(side='right',padx=4,pady=3)
    accept_button.configure(state='disabled' if busy or job else 'normal')
   else:accept_button.pack_forget()
   if copy_dirty:status.configure(text=status.cget('text')+' | 共用文案尚未保存')
   submit_button.configure(state='disabled' if busy else 'normal',text='查看当前提交进度' if job else '提交上架');update_button.configure(state='disabled' if busy or job else 'normal');progress_refresh()
   blocker.configure(text=('当前按钮暂不可用：'+coordinator.status+'，已用'+str(int(time.monotonic()-busy_since))+'秒' if busy else '共用文案尚未保存' if copy_dirty else '已有上架任务：点击右侧按钮查看进度，系统不会重复提交' if job else operation_error or ''))
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
  from rich_content import is_rich_field
  if kind=='a' and is_rich_field(field):
   window=tk.Toplevel(dialog);window.title('自动富内容JSON · '+paths[indices[0]].parent.name);window.geometry('850x600');text=ScrolledText(window,wrap='word');text.pack(fill='both',expand=True,padx=8,pady=8)
   value=value_for(bundles[indices[0]],row,indices[0])
   try:value=json.dumps(json.loads(value),ensure_ascii=False,indent=2)
   except (ValueError,TypeError):value='等待对应变体8张图片托管完成后生成'
   text.insert('1.0',value);text.configure(state='disabled');ttk.Label(window,text='自动使用本变体01主图和02—08详情；图片更新后自动重建。').pack(pady=5);return
  if kind=='a' and int(key.rsplit(':',1)[1]) in (21841,21837):
   messagebox.showinfo('自动使用生成视频','视频链接自动使用本变体生成的8秒MP4；视频名称沿用共用标题。',parent=dialog);return
  if kind=='s':
   if key=='category':choose_category(indices);return
   if key=='warehouse':choose_warehouse(indices);return
   if key=='price':
    text_editor('修改售价（人民币元；手动修改后优先采用）',indices,str(bundles[indices[0]].get('price_cny') or ''),lambda values:coordinator.set_prices(indices,values,expected));return
   if key=='currency':text_editor('输入CNY确认店铺结算币种',indices,'CNY',lambda values:settings_batch(indices,'currency',values,expected));return
   if key=='vat':detail.configure(text='实际增值税率按你的固定规则自动填写0。');return
   return
  initial=value_for(bundles[indices[0]],row,indices[0])
  if kind=='a':
   from assisted_fields import inline_references
   reference=inline_references(bundles[indices[0]]).get(key)
   if reference:initial=reference['suggested']
  if str(initial).startswith('待匹配原值：'):initial=initial.split('：',1)[1]
  if kind=='p' and key=='stock' and publication.initial_stock is not None:
   messagebox.showinfo('统一初始库存','新商品初始库存固定为'+str(publication.initial_stock)+'，销售后正常扣减，不自动重置。',parent=dialog);return
  if kind=='p':text_editor('修改 '+iid,indices,str(initial),lambda values:coordinator.set_parameters(indices,key,values,expected));return
  if field.get('dictionary_id'):dictionary_editor(indices,key,field,expected);return
  def save(values):
   resolved=[coordinator.resolve_text(n,key,v) for n,v in zip(indices,values)];coordinator.set_attributes(indices,key,resolved,expected)
  text_editor('修改官方属性：'+field.get('name',''),indices,str(initial) if len(indices)==1 else '',save)
 def settings_batch(indices,key,values,expected):
  # Validate all selected tax values before any write; identical values can be applied together.
  if key=='vat' and any(v!='0' for v in values):raise ValueError('实际增值税率固定为0')
  coordinator.set_settings_many(indices,key,values,expected)
 def double_click(event):
  iid=tree.identify_row(event.y);col=tree.identify_column(event.x)
  if iid in rows and col!='#0':
   index=int(col[1:])-1;focus[:]=[iid,index];edit_row([index],iid)
 def track(event=None):
  if tree.selection() and tree.selection()[0] in rows:
   iid=tree.selection()[0];focus[0]=iid;row,field=rows[iid];detail.configure(text=(field.get('description','') if field else '基础参数以填写单位为准；包装与商品尺寸分别处理。')+' | 当前参数可对选中变体批量修改')
   if row[0]=='a':
    from assisted_fields import inline_references
    n=focus[1] if isinstance(focus[1],int) else 0
    reference=((bundles[n].get('attribute_draft') or {}).get('auto_references') or {}).get(row[1]) or inline_references(bundles[n]).get(row[1])
    note=((bundles[n].get('attribute_draft') or {}).get('prefill_notes') or {}).get(row[1])
    if note:detail.configure(text=note+'；请手动选择符合实际的官方选项')
    if reference:detail.configure(text='已自动采用的参考：'+reference['confidence']+'；'+reference['evidence']+'；'+reference['note'])
 tree.bind('<Double-1>',double_click);tree.bind('<<TreeviewSelect>>',track)
 def bulk():
  iid=tree.selection()[0] if tree.selection() else focus[0]
  if iid:edit_row(chosen(),iid)
 ttk.Button(bar,text='批量修改当前参数',command=bulk).pack(side='left',padx=3)
 def refresh_all():
  if not editable():return
  run(lambda:coordinator.after_edit(list(range(len(paths))),force=True))
 more_menu.add_command(label='刷新官方属性并重新定价',command=refresh_all)
 if connection_callback:more_menu.add_command(label='连接 / 切换Ozon店铺',command=connection_callback)
 def load_warehouses():
  def action():return publication.warehouses()
  def show(result):
   nonlocal warehouses
   warehouses={str(r['warehouse_id']):r for r in result};warehouse_choice.configure(values=[warehouse_label(r) for r in result]);status.configure(text=f'已读取本店铺全部仓库 {len(result)} 个，保留平台原始状态。')
   if not result:messagebox.showinfo('没有可选择的仓库',publication.warehouse_summary()+'\n可点击“导出仓库诊断”进一步检查。',parent=dialog)
   if len(result)==1:
    selected_var.set(warehouse_label(result[0]))
    if not active_job():
     expected=coordinator.token();merchant=publication.account_getter()
     run(lambda:coordinator.use_only_warehouse(result,merchant,expected))
  run(action,show)
 ttk.Button(bar,text='刷新仓库',command=load_warehouses).pack(side='right',padx=3)
 def export_warehouse_diagnostic():
  from tkinter import filedialog
  target=filedialog.asksaveasfilename(parent=dialog,title='保存仓库诊断（不含密钥、仓库名称或地址）',defaultextension='.json',initialfile='warehouse_diagnostic.json')
  if target:
   try:
    from pricing_service import write
    write(Path(target),getattr(publication,'warehouse_diagnostic',{'message':'请先读取仓库'}));messagebox.showinfo('已保存','仓库诊断已保存，不含API密钥。',parent=dialog)
   except OSError:messagebox.showerror('保存失败','请选择可写入的文件位置',parent=dialog)
 more_menu.add_command(label='导出仓库诊断',command=export_warehouse_diagnostic)
 def warehouse_apply(event=None):
  if not editable():return
  if not chosen():messagebox.showinfo('未选择变体','请先勾选目标变体列',parent=dialog);return
  try:wid=selected_var.get().rsplit(' / ',1)[1];record=warehouses[wid];merchant=publication.account_getter()
  except (IndexError,KeyError,ValueError):return
  expected=token;run(lambda:coordinator.set_settings(chosen(),'warehouse',{'warehouse_id':record['warehouse_id'],'warehouse_name':record['name'],'account_id':merchant},expected))
 warehouse_choice.bind('<<ComboboxSelected>>',warehouse_apply)
 def choose_warehouse(indices):
  def show(result):
   window=tk.Toplevel(dialog);window.title('选择店铺仓库（全部类型和状态）');ttk.Label(window,text='目标：'+'、'.join(paths[n].parent.name for n in indices)).pack(pady=5);choices=ttk.Combobox(window,state='readonly',values=[warehouse_label(r) for r in result],width=65);choices.pack(padx=10,pady=10)
   def apply():
    if choices.current()<0:return
    record=result[choices.current()];expected=coordinator.token();merchant=publication.account_getter();window.destroy();run(lambda:coordinator.set_settings(indices,'warehouse',{'warehouse_id':record['warehouse_id'],'warehouse_name':record['name'],'account_id':merchant},expected))
   ttk.Button(window,text='应用到所选变体并重算售价',command=apply).pack(pady=8)
  run(publication.warehouses,show)
 def open_reference(index):
  from image_viewer import open_viewer
  b=coordinator.load()[index];refs=b.get('main_references') or b.get('references') or []
  # Reference locations differ across older bundles; consult the original task too.
  if not refs and store:
   task=next((t for t in store.tasks if t.get('sku')==b.get('sku')),{});refs=task.get('main_references') or task.get('reference_images') or task.get('references') or []
  rows=[{'local_file':r if isinstance(r,str) else r.get('local_file') or r.get('path','')} for r in refs]
  if not rows:messagebox.showinfo('未找到原始参考图','当前草稿未记录参考图片位置，请用你保留的原图或实物核对。生成图不能作为隔层结构的可靠依据。',parent=dialog);return
  open_viewer(dialog,paths[index].parent,rows,0,b['sku']+' · 原始参考图')
 refbar=ttk.Frame(parameter_tab);refbar.pack(fill='x',pady=3)
 ttk.Label(refbar,text='红色=已自动采用的参考值；售价也自动采用，无需另行确认。有问题直接双击修改。',foreground='#b00020').pack(side='left',padx=5)
 if price_callback:more_menu.add_command(label='查看当前变体售价明细',command=lambda:price_callback(focus[1] if isinstance(focus[1],int) else 0))
 more_menu.add_command(label='查看当前变体原始参考图',command=lambda:open_reference(focus[1] if isinstance(focus[1],int) else 0))
 def reference_cells():
  for n,b in enumerate(bundles):
   state=b.get('attribute_draft') or {}
   for key,reference in (state.get('auto_references') or {}).items():
    text='；'.join(str(v.get('value') or '') for v in (state.get('values') or {}).get(key,[]))
    if text:yield 'a:'+key,'v'+str(n),text,n
   estimate=(b.get('auto_pricing') or {}).get('price_cny')
   if not b.get('manual_price') and estimate is not None and str(estimate)==str(b.get('price_cny')):yield 's:price','v'+str(n),str(b['price_cny']),n
 def select_cell(iid,index):
  focus[:]=[iid,index];tree.selection_set(iid);track()
 from cell_references import ReferenceBadges
 badges=ReferenceBadges(tree,reference_cells,select_cell,lambda iid,n:(select_cell(iid,n),edit_row([n],iid)))
 old_x=tree.xview;old_y=tree.yview
 def scroll_x(*args):old_x(*args);badges.schedule()
 def scroll_y(*args):old_y(*args);badges.schedule()
 sx.configure(command=scroll_x);sy.configure(command=scroll_y)
 def report_x(first,last):sx.set(first,last);badges.schedule()
 def report_y(first,last):sy.set(first,last);badges.schedule()
 tree.configure(xscrollcommand=report_x,yscrollcommand=report_y)
 def dictionary_editor(indices,key,field,expected):
  from attribute_choices import OfficialChoices
  try:
   snapshot=coordinator.load();model=OfficialChoices(service,[snapshot[n] for n in indices],key)
  except ValueError as exc:messagebox.showerror('无法选择',str(exc),parent=dialog);return
  window=tk.Toplevel(dialog);window.title(('批量' if len(indices)>1 else paths[indices[0]].parent.name)+' · 官方选项：'+field.get('name',''));window.geometry('850x650')
  ttk.Label(window,text='目标：'+'、'.join(paths[n].parent.name for n in indices),wraplength=810).pack(pady=5)
  ttk.Label(window,text=('点击勾选，可多选，最多'+str(model.maximum)+'项' if model.multiple else '此参数按API规则只能单选')+('；批量显示所有目标类目共有的官方选项，保存后统一替换本参数' if len(indices)>1 else '') ,wraplength=810).pack(pady=4)
  query=tk.StringVar();ttk.Entry(window,textvariable=query,width=65).pack(pady=5)
  holder=ttk.Frame(window);holder.pack(fill='both',expand=True,padx=8);holder.rowconfigure(0,weight=1);holder.columnconfigure(0,weight=1)
  box=ttk.Treeview(holder,columns=('label',),show='tree headings',selectmode='browse',height=10);box.heading('#0',text='勾选');box.column('#0',width=60,stretch=False);box.heading('label',text='API官方选项 / 说明');box.column('label',width=660);box.grid(row=0,column=0,sticky='nsew');scroll=ttk.Scrollbar(holder,orient='vertical',command=box.yview);scroll.grid(row=0,column=1,sticky='ns');box.configure(yscrollcommand=scroll.set)
  count=ttk.Label(window);count.pack(pady=3);selected_box=tk.Listbox(window,height=4,selectmode='multiple',exportselection=False);selected_box.pack(fill='x',padx=8);loading=[False]
  def render(*args):
   if not window.winfo_exists():return
   box.delete(*box.get_children());needle=query.get().strip().casefold()
   for r in model.visible:
    label=str(r.get('value') or '')+' '+str(r.get('info') or '')
    if not needle or needle==str(model.query or '').casefold() or needle in label.casefold():box.insert('','end',iid=str(r['id']),text='☑' if r['id'] in model.selected else '☐',values=(label,))
   selected_box.delete(0,'end')
   for v in model.selected.values():selected_box.insert('end',v.get('value') or str(v['dictionary_value_id']))
   count.configure(text='已选 '+str(len(model.selected))+' / '+str(model.maximum)+' 项；搜索、翻页保留已选内容')
  def toggle(event):
   if loading[0]:return
   iid=box.identify_row(event.y)
   if not iid:return
   try:model.toggle(int(iid));render()
   except ValueError as exc:messagebox.showerror('无法选择',str(exc),parent=window)
  box.bind('<ButtonRelease-1>',toggle);query.trace_add('write',render)
  tools=ttk.Frame(window);tools.pack(pady=4)
  def fetch(next_page=False,force=False):
   if loading[0]:return
   loading[0]=True;save_button.configure(state='disabled');count.configure(text='正在读取所选变体的API官方选项…')
   def show(error):
    loading[0]=False
    if not window.winfo_exists():return
    save_button.configure(state='disabled' if error else 'normal');next_button.configure(state='normal' if model.has_more else 'disabled');render()
    if error:messagebox.showerror('官方选项读取失败',error,parent=window)
   # Capture Tk text in the UI thread before the worker starts.
   search_text=query.get() if not next_page else model.query or ''
   def load_action():
    try:model.load(search_text,next_page=next_page,force=force)
    except Exception as exc:return str(exc)
    return None
   run(load_action,show)
  ttk.Button(tools,text='官方关键词搜索',command=lambda:fetch()).pack(side='left',padx=4)
  next_button=ttk.Button(tools,text='加载下一页',command=lambda:fetch(True));next_button.pack(side='left',padx=4)
  ttk.Button(tools,text='刷新API选项',command=lambda:fetch(force=True)).pack(side='left',padx=4)
  def remove():
   ids=list(model.selected)
   for n in selected_box.curselection():model.selected.pop(ids[n],None)
   render()
  ttk.Button(tools,text='移除下方选中项',command=remove).pack(side='left',padx=4);ttk.Button(tools,text='清空已选',command=lambda:(model.clear(),render())).pack(side='left',padx=4)
  def save():
   if loading[0]:return
   try:values=model.values()
   except ValueError as exc:messagebox.showerror('未保存',str(exc),parent=window);return
   window.destroy();run(lambda:coordinator.set_attributes(indices,key,values,expected))
  save_button=ttk.Button(window,text='保存所选官方选项并重算售价',command=save);save_button.pack(pady=7);render();fetch()
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
  nonlocal copy_dirty,copy_timer
  if event.widget.edit_modified():
   copy_dirty=True;event.widget.edit_modified(False)
   if copy_timer:dialog.after_cancel(copy_timer)
   copy_timer=dialog.after(800,autosave_copy)
 def autosave_copy():
  nonlocal copy_timer
  copy_timer=None
  if not dialog.winfo_exists() or not copy_dirty:return
  if busy:
   copy_timer=dialog.after(800,autosave_copy);return
  if active_job():return
  if not copy_widgets['title_ru'].get('1.0','end-1c').strip() or not copy_widgets['description_ru'].get('1.0','end-1c').strip():return
  save_copy()
 for widget in copy_widgets.values():widget.edit_modified(False);widget.bind('<<Modified>>',mark_copy_dirty)

 def save_copy(after=None):
  if not editable():return
  value={key:w.get('1.0','end-1c').strip() for key,w in copy_widgets.items()};value['tags_ru']=[t.strip() for t in value['tags_ru'].splitlines() if t.strip()];value['missing_facts']=(bundles[0].get('copy') or {}).get('missing_facts',[]);expected=token
  def saved(result):
   nonlocal copy_dirty
   copy_dirty=False;refresh()
   if after:after()
  run(lambda:coordinator.set_copy(value,expected),saved,label='自动保存整组共用文案')
 ttk.Label(copy_tab,text='自动保存并同步全组。标题和简介不能为空；标签会自动规范格式。').pack(pady=6)
 media_canvas=tk.Canvas(media_tab,highlightthickness=0);media_canvas.pack(side='left',fill='both',expand=True);media_scroll=ttk.Scrollbar(media_tab,orient='vertical',command=media_canvas.yview);media_scroll.pack(side='right',fill='y');media_canvas.configure(yscrollcommand=media_scroll.set);media_body=ttk.Frame(media_canvas);media_id=media_canvas.create_window((0,0),window=media_body,anchor='nw');media_body.bind('<Configure>',lambda e:media_canvas.configure(scrollregion=media_canvas.bbox('all')));media_canvas.bind('<Configure>',lambda e:media_canvas.itemconfigure(media_id,width=e.width))
 media_cards=ttk.Frame(media_body);media_cards.pack(fill='x')
 def media_wheel(event):
  if str(event.widget).startswith(str(media_tab)) and event.widget.winfo_class()!='Text':media_canvas.yview_scroll(-int(event.delta/120),'units')
 dialog.bind_all('<MouseWheel>',media_wheel,add='+')
 def media_refresh():
  from PIL import Image,ImageOps,ImageTk
  for child in media_cards.winfo_children():child.destroy()
  photos.clear()
  for n,b in enumerate(bundles):
   frame=ttk.LabelFrame(media_cards,text=b['sku']);frame.grid(row=n//4,column=n%4,padx=8,pady=8,sticky='n')
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
 def queue_images(kind,skus,addition):
  if copy_dirty:
   if not busy:save_copy(after=lambda:queue_images(kind,skus,addition))
   return
  if not editable():return
  def action():
   with store.lock:return store.image_jobs.create(bundles[0]['sku'],kind,skus,addition)
  def queued(result):
   footer_note.configure(text='已备份并加入 '+str(len(result))+' 个图片任务；插件自动生成、采集并替换，进度见本页下方。')
   regen_ui['refresh']()
  run(action,queued,label='备份并创建图片重做任务')
 def stop_images():
  if busy:return
  targets=offers()
  with store.lock:store.set_paused(True)
  def action():
   deadline=time.time()+75
   while True:
    with store.lock:
     jobs=store.image_jobs.active(targets);waiting=any(j.get('pause_requested') and not j.get('pause_ack') for j in jobs)
     if not waiting:return store.image_jobs.cancel(targets)
    if time.time()>deadline:raise ValueError('插件停止回执尚未到达，备份与当前图片保留，请保持插件连接')
    time.sleep(.5)
  run(action,lambda count:footer_note.configure(text='已停止 '+str(count)+' 个图片重做任务；原图与备份保留。'),label='停止本组图片重做')
 def accept_images():
  if copy_dirty:
   if not busy:save_copy(after=accept_images)
   return
  if not editable():return
  def action():
   from asset_reconcile import reconcile
   with store.lock:
    owner=next(t for t in store.tasks if t['sku']==bundles[0]['sku']);count=reconcile(store,accept_group=owner.get('copy_leader',owner['sku']));store.set_paused(False);return count
  run(action,lambda count:footer_note.configure(text='已沿用本组校验图片，自动继续文案和素材处理；未提交上架。'),label='沿用已检查的整组图片')
 from media_regeneration_ui import build as build_regeneration
 regen_ui=build_regeneration(media_body,lambda:bundles,store,queue_images,stop_images,accept_images)
 more_menu.add_command(label='刷新图片视频预览',command=media_refresh)
 progress=ttk.Treeview(progress_tab,columns=('offer','warehouse','quantity','state','barcodes','errors'),show='headings',height=12)
 for key,label,width in [('offer','货号',180),('warehouse','目标仓库',200),('quantity','目标库存 / 当前可用',160),('state','上架阶段',250),('barcodes','条形码',200),('errors','平台结果 / 错误',350)]:progress.heading(key,text=label);progress.column(key,width=width,anchor='center')
 progress.pack(fill='both',expand=True,padx=8,pady=8);progress_info=ScrolledText(progress_tab,height=6);progress_info.pack(fill='x',padx=8,pady=5)
 def progress_refresh():
  progress.delete(*progress.get_children())
  if not last_job:
   if not operation_error:progress_info.delete('1.0','end');progress_info.insert('1.0','本组暂无本地上架记录。')
   return
  for offer,item in last_job.get('items',{}).items():
   setting=last_job['stocks'][offer];progress.insert('','end',values=(offer,setting['warehouse_name'],str(setting['stock'])+' / '+str(item.get('current_free_stock','待查询')),item.get('status',''),' / '.join(item.get('barcodes') or []) or item.get('barcode_status','等待商品创建'),item.get('error_summary') or json.dumps(item.get('barcode_errors') or item.get('price_errors') or item.get('stock_errors') or item.get('errors') or item.get('platform_errors') or item.get('platform_status') or {},ensure_ascii=False)))
  from pipeline_status import wait_details
  text=json.dumps({'等待':wait_details(last_job),'需处理':bool(last_job.get('needs_attention')),'任务':last_job['id'],'导入任务ID':last_job.get('task_id'),'状态':last_job['state'],'说明':last_job.get('message'),'最近处理错误':operation_error or None},ensure_ascii=False,indent=2)
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
 more_menu.add_separator()
 more_menu.add_command(label='已在后台确认未受理，解除重试',command=reconcile_import)
 more_menu.add_command(label='按预览目标重设不确定库存',command=retry_stock)
 def cancel_followup():
  if not last_job:return
  if not messagebox.askyesno('停止后续跟进','停止未来自动写入，已受理的商品导入和已设置库存不会撤销。之后可修改新预览再次提交。是否停止？',parent=dialog):return
  run(lambda:publication.cancel_followup(last_job['id']))
 more_menu.add_command(label='停止后续跟进（不撤销已完成操作）',command=cancel_followup)
 def clear_progress():
  if busy:return
  targets=offers()
  def done(count):
   nonlocal operation_error
   operation_error='';refresh();progress_refresh();messagebox.showinfo('本地进度已清空','已清理 '+str(count)+' 条记录，素材和回执备份保留。平台商品未删除；可在后台处理后再提交。',parent=dialog)
  run(lambda:publication.clear_group(targets),done,label='清空本组本地上架进度')
 ttk.Button(progress_tab,text='清空本组上架进度（保留素材）',command=clear_progress).pack(pady=4)



 def submit():
  if copy_dirty:
   if not busy:save_copy(after=submit)
   return
  if busy:return
  if active_job():notebook.select(progress_tab);return
  if store.image_jobs.active(offers()):notebook.select(media_tab);footer_note.configure(text='图片重做尚未结束，请等待新图、视频及托管完成后再提交上架。');return
  if not editable():return
  from asset_state import pending,blocking_reason
  if any(pending(b) for b in coordinator.load()):
   def check_assets():
    coordinator.reconcile_assets();return coordinator.load()
   def checked_assets(current):
    unresolved=[b for b in current if pending(b)]
    if not unresolved:submit();return
    pictures=any(b.get('regeneration_pending') or any((b.get('asset_review') or {}).get(k) for k in ('main','gallery')) for b in unresolved)
    notebook.select(media_tab if pictures else copy_tab)
    footer_note.configure(text=blocking_reason(unresolved[0]))
   run(check_assets,checked_assets,label='核对图片与文案状态');return
  from category_catalog import setup_errors
  errors=setup_errors(coordinator.load(),os.environ.get('OZON_CLIENT_ID',''))
  if errors:
   messagebox.showinfo('提交前还需设置', '\n\n'.join(errors),parent=dialog);notebook.select(parameter_tab);return
  expected=token
  def submitted(job):
   nonlocal last_job
   last_job=job;notebook.select(progress_tab);refresh()
  notebook.select(progress_tab)
  visible=copy.deepcopy(bundles)
  def stage(message):coordinator.status=message
  run(lambda:publication.begin(coordinator,expected,on_progress=stage,visible_bundles=visible),submitted,label='提交前校验')
 def update_preview():
  if copy_dirty:
   if not busy:save_copy(after=update_preview)
   return
  if not editable():return
  def updated(message):
   media_refresh()
   footer_note.configure(text=('部分属性未同步：请查看参数提示。' if str(message).startswith('部分属性未同步') else '整组本地预览已更新。')+'未提交至Ozon；点击“提交上架”才同步。')
  run(coordinator.refresh_preview,updated,label='更新整组本地预览（不提交）')
 footer_note=ttk.Label(bottom,text='更新整组预览只保存本地；提交上架才同步Ozon。初始库存1000，销售后不重置。',wraplength=500)
 submit_button=ttk.Button(bottom,text='提交上架',style='Primary.TButton',command=submit);submit_button.pack(side='right',padx=6)
 update_button=ttk.Button(bottom,text='更新整组预览',command=update_preview);update_button.pack(side='right',padx=6);footer_note.pack(side='left',fill='x',expand=True)
 accept_button=ttk.Button(asset_actions,text='图片无误，沿用本组',command=accept_images)
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
 more_menu.add_command(label='校验 / 导出整组载荷',command=preview_only)
 def poll():
  if not dialog.winfo_exists():return
  refresh();dialog.after(1500,poll)
 refresh();poll()
 try:
  publication.account_getter();dialog.after(100,load_warehouses)
 except ValueError:status.configure(text='请先连接Ozon API，再读取店铺全部仓库')
 dialog._ozon_ui={'notebook':notebook,'copy_widgets':copy_widgets,'tree':tree,'more':more_menu,'submit':submit_button,'update_preview':update_button,'accept_images':accept_button,'footer_note':footer_note,'regeneration':regen_ui,'refresh':refresh}
 return dialog
