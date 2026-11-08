"""Resizable local image preview; does not modify generated assets."""
from pathlib import Path

def open_viewer(parent,folder,rows,start=0,title='商品图片'):
 import tkinter as tk
 from tkinter import ttk
 from PIL import Image,ImageOps,ImageTk
 rows=list(rows)
 if not rows:return
 window=tk.Toplevel(parent);window.title(title);window.geometry('900x820');window.minsize(400,350)
 toolbar=ttk.Frame(window);toolbar.pack(fill='x',padx=8,pady=6)
 position=tk.StringVar();canvas=tk.Canvas(window,background='#242424',highlightthickness=0);canvas.pack(fill='both',expand=True)
 state={'index':start%len(rows),'source':None,'photo':None,'timer':None}
 def render():
  state['timer']=None
  if not window.winfo_exists() or state['source'] is None:return
  size=(max(1,canvas.winfo_width()-16),max(1,canvas.winfo_height()-16))
  image=ImageOps.contain(state['source'],size)
  state['photo']=ImageTk.PhotoImage(image,master=window)
  canvas.delete('all');canvas.create_image(canvas.winfo_width()//2,canvas.winfo_height()//2,image=state['photo'])
 def load(index):
  state['index']=index%len(rows)
  if state['source'] is not None:state['source'].close();state['source']=None
  i=state['index'];position.set(f'{i+1:02d} / {len(rows):02d} · '+('本变体主图' if i==0 else '共用详情图'))
  try:
   with Image.open(Path(folder)/rows[i]['local_file']) as source:state['source']=ImageOps.exif_transpose(source).convert('RGB')
   render()
  except (OSError,ValueError,KeyError):
   canvas.delete('all');canvas.create_text(max(180,canvas.winfo_width()//2),max(100,canvas.winfo_height()//2),text='图片不可读，请检查本地素材',fill='white')
 def resize(event):
  if state['timer']:window.after_cancel(state['timer'])
  state['timer']=window.after(80,render)
 def close(event=None):
  if state['timer']:window.after_cancel(state['timer'])
  if state['source'] is not None:state['source'].close()
  window.destroy()
 ttk.Button(toolbar,text='上一张 ←',command=lambda:load(state['index']-1)).pack(side='left')
 ttk.Label(toolbar,textvariable=position,anchor='center').pack(side='left',fill='x',expand=True)
 ttk.Button(toolbar,text='下一张 →',command=lambda:load(state['index']+1)).pack(side='right')
 ttk.Label(window,text='方向键切换图片 · 调整窗口自动缩放 · Esc关闭',anchor='center').pack(fill='x',pady=4)
 canvas.bind('<Configure>',resize);window.bind('<Left>',lambda e:load(state['index']-1));window.bind('<Right>',lambda e:load(state['index']+1));window.bind('<Escape>',close);window.protocol('WM_DELETE_WINDOW',close)
 load(state['index']);window.focus_set()
 return window
