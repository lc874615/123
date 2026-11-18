"""Presentation helpers: adaptive actions and rounded surfaces; no workflow changes."""
import tkinter as tk
from tkinter import ttk

def section_header(parent,title,subtitle=''):
 header=ttk.Frame(parent,padding=(16,12));header.pack(fill='x')
 ttk.Label(header,text=title,style='SectionTitle.TLabel').pack(anchor='w')
 if subtitle:ttk.Label(header,text=subtitle,style='Muted.TLabel',wraplength=900).pack(anchor='w',pady=(4,0))
 return header

def responsive_actions(parent,actions):
 frame=ttk.Frame(parent);frame.pack(fill='x',pady=(4,8));buttons=[];last=[None]
 for label,command in actions:
  buttons.append(ttk.Button(frame,text=label,command=command))
 def arrange(event=None):
  width=event.width if event else max(320,frame.winfo_width())
  columns=max(1,min(len(buttons),width//175))
  if last[0]==columns:return
  last[0]=columns
  for i in range(len(buttons)):frame.columnconfigure(i,weight=1 if i<columns else 0)
  for i,button in enumerate(buttons):button.grid(row=i//columns,column=i%columns,sticky='ew',padx=3,pady=3)
 frame.bind('<Configure>',arrange);arrange();return frame,buttons

class RoundedCard(tk.Canvas):
 def __init__(self,parent,accent='#5865F2',**kwargs):
  super().__init__(parent,height=112,highlightthickness=0,borderwidth=0,cursor='hand2',background='#F2F5FC',**kwargs)
  self.accent=accent;self.content=ttk.Frame(self,style='Card.TFrame',padding=(18,12));self.item=self.create_window(1,1,anchor='nw',window=self.content)
  self.bind('<Configure>',self._draw)
 def _draw(self,event):
  self.delete('surface');w=event.width-2;h=event.height-2;r=18
  self.create_polygon(r,1,w-r,1,w,1,w,r,w,h-r,w,h,w-r,h,r,h,1,h,1,h-r,1,r,1,1,fill='white',outline='#E2E8F5',smooth=True,splinesteps=24,tags='surface')
  self.tag_lower('surface');self.itemconfigure(self.item,width=max(20,w-22),height=max(20,h-10));self.coords(self.item,10,5)
  self.create_line(26,h-3,w-26,h-3,fill=self.accent,width=3,tags='surface')
