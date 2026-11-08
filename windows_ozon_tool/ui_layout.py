"""Compact three-page desktop shell with responsive scrolling."""
import os

def build(root):
 import tkinter as tk
 from tkinter import ttk
 root.title('Ozon 商品自动化 · 1.0.12');root.geometry('1280x880');root.minsize(1000,680)
 style=ttk.Style(root);style.theme_use('clam')
 font='Microsoft YaHei UI' if os.name=='nt' else 'Noto Sans CJK SC'
 style.configure('.',font=(font,10));style.configure('TButton',padding=(12,7));style.configure('TNotebook.Tab',padding=(24,10));style.configure('Treeview',rowheight=32);style.configure('Treeview.Heading',font=(font,10,'bold'));style.configure('Primary.TButton',foreground='white',background='#2167b7');style.map('Primary.TButton',background=[('active','#18518f')])
 banner=ttk.Frame(root,padding=(16,10));banner.pack(fill='x');ttk.Label(banner,text='Ozon 商品自动化',font=(font,17,'bold')).pack(side='left');ttk.Label(banner,text='本地制作 → 整组预览 → 提交上架',foreground='#526174').pack(side='left',padx=25)
 connection=ttk.Label(root,text='等待插件连接',padding=(16,4),wraplength=1200);connection.pack(fill='x')
 notebook=ttk.Notebook(root);notebook.pack(fill='both',expand=True,padx=12,pady=(4,12));pages={}
 def scroll_page(title):
  page=ttk.Frame(notebook);notebook.add(page,text=title);page.rowconfigure(0,weight=1);page.columnconfigure(0,weight=1)
  canvas=tk.Canvas(page,highlightthickness=0,background='#f5f7fa');canvas.grid(row=0,column=0,sticky='nsew');scroll=ttk.Scrollbar(page,orient='vertical',command=canvas.yview);scroll.grid(row=0,column=1,sticky='ns');canvas.configure(yscrollcommand=scroll.set)
  body=ttk.Frame(canvas,padding=12);item=canvas.create_window((0,0),window=body,anchor='nw');body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')));canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width))
  def wheel(e):
   if e.widget.winfo_class() not in ('Treeview','Entry','TEntry','Text','TCombobox') and str(e.widget).startswith(str(page)):canvas.yview_scroll(-int(e.delta/120),'units')
  root.bind_all('<MouseWheel>',wheel,add='+');return page,body
 page,body=scroll_page('商品制作');pages['product']=page;pages['product_body']=body
 tasks=ttk.Frame(notebook,padding=12);notebook.add(tasks,text='任务中心');pages['tasks']=tasks
 page,body=scroll_page('设置');pages['settings']=page;pages['settings_body']=body
 return notebook,pages,connection
