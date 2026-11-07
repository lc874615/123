"""Local attribute review and export UI. This module never submits products."""
from pathlib import Path
import json,os,threading
from attribute_service import field_key
from pricing_service import read

def open_editor(root,folder,service,group_folders,category_callback=None,price_callback=None,connection_callback=None):
 import tkinter as tk
 from tkinter import ttk,messagebox
 from tkinter.scrolledtext import ScrolledText
 folder=Path(folder);path=folder/'listing_bundle.json';dialog=tk.Toplevel(root);dialog.title(folder.name+' · 上架草稿与必填属性');dialog.geometry('1100x740')
 ttk.Label(dialog,text='读取官方类目属性 → 核对缺失项 → 确认真实税率与CNY币种 → 导出整组提交预览。此窗口不会提交商品或设置库存。').pack(pady=7)
 status=ttk.Label(dialog,text='等待读取属性',wraplength=1050);status.pack(pady=4)
 bar=ttk.Frame(dialog);bar.pack(pady=4)
 def work(action):
  status.configure(text='正在处理，请稍候…')
  def run():
   try:action();root.after(0,refresh)
   except Exception as exc:root.after(0,lambda text=str(exc):messagebox.showerror('草稿待处理',text,parent=dialog))
  threading.Thread(target=run,daemon=True).start()
 ttk.Button(bar,text='读取 / 刷新官方必填属性',command=lambda:work(lambda:service.refresh(path))).pack(side='left',padx=5)
 if connection_callback:ttk.Button(bar,text='连接Ozon API',command=connection_callback).pack(side='left',padx=5)
 if category_callback:ttk.Button(bar,text='确认 / 修改类目',command=category_callback).pack(side='left',padx=5)
 if price_callback:ttk.Button(bar,text='查看 / 确认售价',command=price_callback).pack(side='left',padx=5)
 filter_bar=ttk.Frame(dialog);filter_bar.pack(fill='x',padx=10)
 search=tk.StringVar();only_missing=tk.BooleanVar(value=False)
 ttk.Label(filter_bar,text='搜索属性').pack(side='left');ttk.Entry(filter_bar,textvariable=search,width=45).pack(side='left',padx=5)
 ttk.Checkbutton(filter_bar,text='只看缺失的必填项',variable=only_missing).pack(side='left')
 frame=ttk.Frame(dialog);frame.pack(fill='both',expand=True,padx=10)
 columns=('name','ru','required','kind','value');tree=ttk.Treeview(frame,columns=columns,show='headings',selectmode='browse')
 for key,title,width in [('name','中文属性',250),('ru','俄文原名',260),('required','必填',60),('kind','填写方式',100),('value','当前值（双击编辑）',330)]:tree.heading(key,text=title);tree.column(key,width=width,anchor='center')
 scroll=ttk.Scrollbar(frame,orient='vertical',command=tree.yview);scroll.pack(side='right',fill='y');tree.configure(yscrollcommand=scroll.set);tree.pack(fill='both',expand=True)
 info=ScrolledText(dialog,height=5,wrap='word');info.pack(fill='x',padx=10,pady=4)
 bundle=read(path);fields={};rendered=None
 vat=tk.StringVar(value=(bundle.get('export_settings') or {}).get('vat',''));currency=tk.BooleanVar(value=(bundle.get('export_settings') or {}).get('currency_confirmed',False))
 bottom=ttk.Frame(dialog);bottom.pack(pady=5)
 ttk.Label(bottom,text='实际增值税率（必选）').pack(side='left');ttk.Combobox(bottom,textvariable=vat,values=['0','0.05','0.07','0.1','0.2','0.22'],state='readonly',width=9).pack(side='left',padx=7)
 ttk.Checkbutton(bottom,text='已确认店铺币种为人民币CNY',variable=currency).pack(side='left')
 ttk.Label(dialog,text='税率是平台申报字段；当前定价公式不会据此自动增加税费扣减，请按实际税费成本核对售价。').pack(pady=2)
 def refresh():
  nonlocal bundle,fields,rendered
  if not dialog.winfo_exists():return
  try:
   bundle=read(path);state=bundle.get('attribute_draft') or {};status.configure(text='类目：'+bundle.get('category_match_status','待确认')+' | 属性：'+('已确认' if state.get('confirmed') else '待读取或核对')+' | 属性读取：'+service.status+' | 视频：'+(bundle.get('video_hosting') or {}).get('message','待COS托管'))
   if state!=rendered:
    rendered=state;selected=tree.selection();tree.delete(*tree.get_children());fields={field_key(f):f for f in state.get('fields',[]) if f['id'] not in (8229,21841,21837,21845)}
    for key,field in fields.items():
     values=(state.get('values') or {}).get(key) or []
     if search.get().casefold() not in (field.get('name','')+' '+field.get('name_ru','')).casefold():continue
     if only_missing.get() and (not field.get('is_required') or values):continue
     text='；'.join(str(v.get('value') or v.get('dictionary_value_id')) for v in values)
     tree.insert('','end',iid=key,values=(field.get('name'),field.get('name_ru'), '是' if field.get('is_required') else '否','官方字典' if field.get('dictionary_id') else '文本/数值',text or '未填写'))
    if selected and tree.exists(selected[0]):tree.selection_set(selected[0])
  except (OSError,ValueError):status.configure(text='草稿暂不可读，请等待保存完成')
 def filter_changed(*args):
  nonlocal rendered
  rendered=None;refresh()
 search.trace_add('write',filter_changed);only_missing.trace_add('write',filter_changed)
 def edit(event=None):
  selected=tree.selection()
  if not selected:return
  key=selected[0];field=fields[key];state=bundle.get('attribute_draft') or {};window=tk.Toplevel(dialog);window.title(field.get('name','属性')+' · '+field.get('name_ru',''));window.geometry('850x530')
  ttk.Label(window,text=field.get('description',''),wraplength=800).pack(pady=6)
  current=(state.get('values') or {}).get(key) or []
  if not field.get('dictionary_id'):
   text=ScrolledText(window,height=15,wrap='word');text.pack(fill='both',expand=True,padx=10)
   text.insert('1.0','\n'.join(v.get('value','') for v in current));ttk.Label(window,text='多值字段每行一项；非多值字段整段作为一个值。不确定的信息请留空核对。').pack()
   def save():
    value=text.get('1.0','end-1c').strip();values=[{'value':v.strip()} for v in value.splitlines() if v.strip()] if field.get('is_collection') else [{'value':value}]
    try:service.save_values(path,key,values);window.destroy();refresh()
    except ValueError as exc:messagebox.showerror('未保存',str(exc),parent=window)
   ttk.Button(window,text='保存此属性',command=save).pack(pady=7)
  else:
   query=tk.StringVar();ttk.Label(window,text='中文筛选已加载选项；官方服务器搜索支持至少2字符，俄文关键词更精确。').pack()
   ttk.Entry(window,textvariable=query,width=60).pack(pady=4);options=tk.Listbox(window,selectmode='extended' if field.get('is_collection') else 'browse',exportselection=False);options.pack(fill='both',expand=True,padx=10)
   loaded={};visible=[];cursor=0;has_next=True;count=ttk.Label(window);count.pack()
   def filter_local(*args):
    nonlocal visible
    visible=[r for r in loaded.values() if query.get().casefold() in ((r.get('value') or '')+' '+(r.get('info') or '')).casefold()];options.delete(0,'end')
    for row in visible:options.insert('end',(row.get('value') or '')+' '+(row.get('info') or ''))
    count.configure(text=f'已加载 {len(loaded)} 项，筛选结果 {len(visible)} 项')
   query.trace_add('write',filter_local)
   def fetch(search=False):
    if not search and not has_next:return
    def action():
     response=service.dictionary(read(path),field,query.get() if search else '',cursor if not search else 0)
     def show():
      nonlocal cursor,has_next
      for row in response['result']:loaded[str(row['id'])]=row
      if not search:
       has_next=response.get('has_next',False)
       if response['result']:cursor=response['result'][-1]['id']
      filter_local()
     root.after(0,show)
    work(action)
   buttons=ttk.Frame(window);buttons.pack(pady=4)
   ttk.Button(buttons,text='加载官方中文选项 / 下一页',command=lambda:fetch(False)).pack(side='left',padx=5)
   ttk.Button(buttons,text='按关键词查官方字典',command=lambda:fetch(True)).pack(side='left',padx=5)
   def save():
    selected=options.curselection();values=[{'dictionary_value_id':visible[n]['id'],'value':visible[n]['value']} for n in selected]
    try:service.save_values(path,key,values);window.destroy();refresh()
    except ValueError as exc:messagebox.showerror('未保存',str(exc),parent=window)
   ttk.Button(window,text='保存已选官方值',command=save).pack(pady=7);fetch(False)
 tree.bind('<Double-1>',edit)
 def show_help(event=None):
  if not tree.selection():return
  field=fields[tree.selection()[0]];info.delete('1.0','end');info.insert('1.0',field.get('description','')+'\n建议值：'+str((bundle.get('attribute_draft') or {}).get('suggestions',{}).get(field_key(field),'')))
 tree.bind('<<TreeviewSelect>>',show_help)
 def confirm():
  try:service.confirm(path,vat.get(),currency.get());refresh();messagebox.showinfo('已保存','属性、税率和币种已确认；修改属性或类目后需重新核对。',parent=dialog)
  except ValueError as exc:messagebox.showerror('仍有待填信息',str(exc),parent=dialog)
 ttk.Button(dialog,text='确认本变体属性、税率和币种',command=confirm).pack(pady=4)
 def group_review():
  from attribute_service import review_hash
  snapshots={};details=[]
  with service.lock:
   for directory in group_folders:
    target=Path(directory)/'listing_bundle.json';data=read(target);state=data.get('attribute_draft') or {};snapshots[str(target)]=review_hash(state)
    details.append({'货号':data.get('offer_id',data.get('sku')),'属性':[{'名称':f.get('name'),'俄文原名':f.get('name_ru'),'必填':bool(f.get('is_required')),'值':(state.get('values') or {}).get(field_key(f),[])} for f in state.get('fields',[]) if f['id'] not in (8229,21841,21837,21845)]})
  preview=tk.Toplevel(dialog);preview.title('整组属性核对 · 确认后仍不提交');preview.geometry('950x700');text=ScrolledText(preview,wrap='word');text.pack(fill='both',expand=True)
  text.insert('1.0',json.dumps({'本组税率':vat.get(),'店铺币种CNY已确认':currency.get(),'各变体属性':details},ensure_ascii=False,indent=2));text.configure(state='disabled')
  chosen_vat=vat.get();chosen_currency=currency.get()
  def apply():
   try:
    service.confirm_many([Path(p)/'listing_bundle.json' for p in group_folders],chosen_vat,chosen_currency,snapshots);preview.destroy();refresh();messagebox.showinfo('整组已确认','已保存本组属性、税率和币种；可以继续导出提交预览。',parent=dialog)
   except ValueError as exc:messagebox.showerror('整组仍有待处理项目',str(exc),parent=preview)
  ttk.Button(preview,text='确认以上整组属性与税率（不提交商品）',command=apply).pack(pady=8)
 ttk.Button(dialog,text='查看并确认整组属性、税率和币种',command=group_review).pack(pady=4)

 def export():
  from listing_preview import export_preview
  def action():
   output=folder/'listing_preview';report=export_preview(group_folders,output,service.lock)
   def show():
    preview=tk.Toplevel(dialog);preview.title('整组上架提交预览 · 未提交');preview.geometry('900x650');text=ScrolledText(preview,wrap='word');text.pack(fill='both',expand=True)
    target=output/('ozon_import_preview.json' if report['ready'] else 'review_report.json');text.insert('1.0',target.read_text(encoding='utf-8'));text.configure(state='disabled')
    ttk.Label(preview,text='预览通过，尚未提交商品。' if report['ready'] else '存在待处理项目；未生成可提交的载荷。').pack(pady=5)
    if os.name=='nt':ttk.Button(preview,text='打开本地预览文件夹',command=lambda:os.startfile(str(output))).pack(pady=5)
   root.after(0,show)
  work(action)
 ttk.Button(dialog,text='校验并导出整组上架预览（不提交）',command=export).pack(pady=5)
 def poll():
  if not dialog.winfo_exists():return
  refresh();dialog.after(1500,poll)
 poll();return dialog
