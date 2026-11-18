"""Reusable compact plan inspector; no long prompt editor or network requests."""
def open_plan(parent,get_plan,save_override=None,key='current'):
 import tkinter as tk
 from tkinter import ttk,messagebox
 from window_registry import lookup,remember
 from visual_plans import STYLES
 cached=lookup(parent,('visual_plan',key))
 if cached is not None:return cached
 window=remember(parent,('visual_plan',key),tk.Toplevel(parent));window.title('作图方案与8图计划');window.geometry('900x600');window.minsize(660,480)
 footer=ttk.Frame(window,padding=12);footer.pack(side='bottom',fill='x');note=ttk.Label(footer,text='只保存下次制作方案，不重做、不删图、不提交上架。',style='Muted.TLabel');note.pack(side='left')
 top=ttk.Frame(window,padding=(14,10));top.pack(fill='x');title=ttk.Label(top,style='SectionTitle.TLabel');title.pack(anchor='w');reason=ttk.Label(top,wraplength=820,style='Muted.TLabel');reason.pack(anchor='w',pady=(4,6))
 choices=['按官方类目自动选择']+[v[0] for v in STYLES.values()];choice=ttk.Combobox(top,values=choices,state='readonly');choice.pack(fill='x')
 body=ttk.Frame(window,padding=(14,0));body.pack(fill='both',expand=True);body.rowconfigure(0,weight=1);body.columnconfigure(0,weight=1)
 tree=ttk.Treeview(body,columns=('number','topic'),show='headings',selectmode='browse');tree.heading('number',text='商品位置');tree.column('number',width=80,stretch=False,anchor='center');tree.heading('topic',text='本张用途（缺少依据时采用明确替代主题）');tree.column('topic',width=680);tree.grid(row=0,column=0,sticky='nsew');sy=ttk.Scrollbar(body,command=tree.yview);sy.grid(row=0,column=1,sticky='ns');tree.configure(yscrollcommand=sy.set)
 def refresh():
  plan=get_plan();title.configure(text=plan['style_name']+' · '+plan['subtype']);reason.configure(text=plan['reason']+'；'+'；'.join(plan.get('warnings',[]))+'；最终画面仍以原始商品图和已填参数为准。');choice.current(0 if plan['source']!='manual' else list(STYLES).index(plan['style'])+1)
  tree.delete(*tree.get_children())
  for p in plan['pages']:tree.insert('','end',values=(str(p['order']).zfill(2),p['title']))
 def save():
  try:
   index=choice.current();save_override(None if index==0 else list(STYLES)[index-1]);refresh()
  except Exception as error:messagebox.showerror('方案未保存',str(error),parent=window)
 ttk.Button(footer,text='刷新方案',command=refresh).pack(side='right',padx=4)
 if save_override:ttk.Button(footer,text='保存选择',style='Primary.TButton',command=save).pack(side='right')
 else:choice.configure(state='disabled')
 refresh();window._ozon_ui={'tree':tree,'choice':choice,'save':save,'refresh':refresh};return window
