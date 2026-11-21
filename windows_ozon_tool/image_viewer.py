"""Resizable local image preview; does not modify generated assets."""
from window_registry import lookup,remember
from pathlib import Path

def open_viewer(parent,folder,rows,start=0,title='商品图片',on_replace=None):
 import tkinter as tk
 from tkinter import ttk
 from PIL import Image,ImageOps,ImageTk
 from preview_images import PreviewImages
 loader=PreviewImages(limit=12)
 rows=list(rows)
 if not rows:return
 cached=lookup(parent,('image_viewer',str(Path(folder).resolve()),start,title))
 if cached is not None:
  reload=getattr(cached,'_ozon_reload',None)
  if callable(reload):reload(rows,start)
  return cached
 window=remember(parent,('image_viewer',str(Path(folder).resolve()),start,title),tk.Toplevel(parent));window.title(title);window.geometry('900x820');window.minsize(400,350)
 toolbar=ttk.Frame(window);toolbar.pack(fill='x',padx=8,pady=6)
 position=tk.StringVar();canvas=tk.Canvas(window,background='#242424',highlightthickness=0);canvas.pack(fill='both',expand=True)
 state={'index':start%len(rows),'source':None,'photo':None,'timer':None,'request':0}
 window.bind('<Destroy>',lambda e:loader.close() if e.widget is window else None,add='+')
 def render():
  state['timer']=None
  if not window.winfo_exists() or state['source'] is None:return
  size=(max(1,canvas.winfo_width()-16),max(1,canvas.winfo_height()-16))
  image=ImageOps.contain(state['source'],size)
  state['photo']=ImageTk.PhotoImage(image,master=window)
  canvas.delete('all');canvas.create_image(canvas.winfo_width()//2,canvas.winfo_height()//2,image=state['photo'])
 def load(index):
  state['index']=index%len(rows)
  state['source']=None;state['request']+=1;request=state['request']
  i=state['index'];position.set(f'{i+1:02d} / {len(rows):02d} · '+('原始参考图' if on_replace else '本变体主图' if i==0 else '共用详情图'))
  canvas.delete('all');canvas.create_text(220,100,text='正在加载图片…',fill='white')
  def ready(image):
   if state['request']!=request:return
   state['source']=image
   if image is not None:render()
   else:
    canvas.delete('all');canvas.create_text(220,100,text='图片不可读，请检查本地素材',fill='white')
  loader.request(canvas,Path(folder)/rows[i].get('local_file',''),(1800,2200),ready)
 def resize(event):
  if state['timer']:window.after_cancel(state['timer'])
  state['timer']=window.after(80,render)
 def close(event=None):
  if state['timer']:window.after_cancel(state['timer'])
  window.destroy()
 if on_replace:
  def replace_current():
   path=on_replace(state['index'])
   if path:rows[state['index']]['local_file']=path;load(state['index'])
  ttk.Button(toolbar,text='更换当前参考图',command=replace_current).pack(side='right',padx=6)
 ttk.Button(toolbar,text='上一张 ←',command=lambda:load(state['index']-1)).pack(side='left')
 ttk.Label(toolbar,textvariable=position,anchor='center').pack(side='left',fill='x',expand=True)
 ttk.Button(toolbar,text='下一张 →',command=lambda:load(state['index']+1)).pack(side='right')
 ttk.Label(window,text='方向键切换图片 · 调整窗口自动缩放 · Esc关闭',anchor='center').pack(fill='x',pady=4)
 canvas.bind('<Configure>',resize);window.bind('<Left>',lambda e:load(state['index']-1));window.bind('<Right>',lambda e:load(state['index']+1));window.bind('<Escape>',close);window.protocol('WM_DELETE_WINDOW',close)
 def reload(new_rows,index):
  rows[:]=list(new_rows);load(index)
 window._ozon_reload=reload
 load(state['index']);window.focus_set()
 return window
