"""Place red reference badges over individual visible ttk Treeview cells."""
class ReferenceBadges:
 def __init__(self,tree,get_cells,on_click,on_double):
  self.tree=tree;self.get_cells=get_cells;self.on_click=on_click;self.on_double=on_double;self.labels=[];self.pending=None
  tree.bind('<Configure>',lambda e:self.schedule(),add='+');tree.bind('<MouseWheel>',lambda e:self.schedule(),add='+');tree.bind('<Button-4>',lambda e:self.schedule(),add='+');tree.bind('<Button-5>',lambda e:self.schedule(),add='+');tree.bind('<KeyRelease>',lambda e:self.schedule(),add='+')
 def schedule(self):
  if self.pending is None:self.pending=self.tree.after_idle(self.redraw)
 def redraw(self):
  import tkinter as tk
  self.pending=None
  for label in self.labels:label.destroy()
  self.labels=[]
  if not self.tree.winfo_exists():return
  for iid,column,text,index in self.get_cells():
   if not self.tree.exists(iid):continue
   box=self.tree.bbox(iid,column)
   if not box:continue
   x,y,w,h=box
   # Never cover the fixed parameter column when horizontally scrolled.
   header=self.tree.bbox(iid,'#0');left=header[0]+header[2] if header else 0
   if x<left or x>=self.tree.winfo_width()-2:continue
   label=tk.Label(self.tree,text=text,background='#ffe1e1',foreground='#b00020',anchor='center',borderwidth=0,cursor='hand2')
   label.place(x=x,y=y,width=min(w,self.tree.winfo_width()-x-2),height=h);label.bind('<Button-1>',lambda e,iid=iid,index=index:self.on_click(iid,index));label.bind('<Double-1>',lambda e,iid=iid,index=index:self.on_double(iid,index));label.bind('<MouseWheel>',lambda e:self.wheel(e));self.labels.append(label)
 def wheel(self,event):
  self.tree.yview_scroll(-int(event.delta/120),'units');self.schedule()
