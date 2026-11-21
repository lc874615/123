"""Place red reference badges over individual visible ttk Treeview cells."""
class ReferenceBadges:
 def __init__(self,tree,get_cells,on_click,on_double,native=False):
  self.native=native
  self.tree=tree;self.get_cells=get_cells;self.on_click=on_click;self.on_double=on_double;self.labels=[];self.pending=None;self.pool={}
  if native:
   tree.tag_configure('reference',foreground='#9b5e00');return
  tree.bind('<Configure>',lambda e:self.schedule(),add='+');tree.bind('<MouseWheel>',lambda e:self.schedule(),add='+');tree.bind('<Button-4>',lambda e:self.schedule(),add='+');tree.bind('<Button-5>',lambda e:self.schedule(),add='+');tree.bind('<KeyRelease>',lambda e:self.schedule(),add='+')
 def schedule(self):
  if self.pending is None:self.pending=self.tree.after(32,self.redraw)
 def redraw(self):
  import tkinter as tk
  self.pending=None
  if not self.tree.winfo_exists():return
  if self.native:
   referenced={iid for iid,column,text,index in self.get_cells()}
   for parent in self.tree.get_children():
    for iid in self.tree.get_children(parent):
     tags=[t for t in self.tree.item(iid,'tags') if t!='reference']
     if iid in referenced:tags.append('reference')
     self.tree.item(iid,tags=tags)
   return
  visible=set()
  for iid,column,text,index in self.get_cells():
   if not self.tree.exists(iid):continue
   box=self.tree.bbox(iid,column)
   if not box:continue
   x,y,w,h=box
   # Never cover the fixed parameter column when horizontally scrolled.
   header=self.tree.bbox(iid,'#0');left=header[0]+header[2] if header else 0
   if x<left or x>=self.tree.winfo_width()-2:continue
   key=(iid,column);visible.add(key);label=self.pool.get(key)
   if label is None:
    label=tk.Label(self.tree,background='#ffe1e1',foreground='#b00020',anchor='center',borderwidth=0,cursor='hand2');self.pool[key]=label
    label.bind('<Button-1>',lambda e,iid=iid,index=index:self.on_click(iid,index));label.bind('<Double-1>',lambda e,iid=iid,index=index:self.on_double(iid,index));label.bind('<MouseWheel>',self.wheel)
   if label.cget('text')!=text:label.configure(text=text)
   label.place(x=x,y=y,width=min(w,self.tree.winfo_width()-x-2),height=h)
  for key in set(self.pool)-visible:self.pool.pop(key).destroy()
  self.labels=list(self.pool.values())
 def wheel(self,event):
  self.tree.yview_scroll(-int(event.delta/120),'units');self.schedule()
