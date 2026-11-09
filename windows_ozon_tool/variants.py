"""Variant columns: stable natural-number suffixes, explicit units, TSV paste."""
from decimal import Decimal,InvalidOperation
import re
FIELDS=[('name','商品名称/用途',''),('color','颜色',''),('size','规格/型号',''),('quantity','每套件数','1'),('material','主体材质',''),('accessory_material','配件/内衬材质',''),('length','商品长(cm)',''),('width','商品宽(cm)',''),('height','商品高(cm)',''),('net_weight','商品净重(g)',''),('pack_length','包装长(cm)',''),('pack_width','包装宽(cm)',''),('pack_height','包装高(cm)',''),('pack_weight','包装总重(g)',''),('cost','每套成本含国内运费(元)',''),('margin','目标净利润率(%)','25'),('stock','初始库存（固定1000）','1000'),('origin','产地','中国'),('assembly','组装方式(未知留空)',''),('extra','其他真实参数/卖点','')]
def valid_article(value):return bool(re.fullmatch(r'[\w-]+(?:\([1-9][0-9]*\))?',value)) and len(value)<=80

def article(base,index):
 if not re.fullmatch(r'[\w-]{1,68}',base):raise ValueError('基础货号只能含字母、数字、下划线、短横线，最多68字符')
 if not isinstance(index,int) or index<1:raise ValueError('变体序号无效')
 value=f'{base}({index})'
 if not valid_article(value):raise ValueError('变体货号过长')
 return value

def facts(values):
 parts=[]
 for key,label,default in FIELDS:
  value=str(values.get(key,'')).strip()
  if not value:continue
  if key in ('quantity','stock'):
   if not value.isdigit() or (key=='quantity' and int(value)<1):raise ValueError(label+'须为整数')
  if key in ('length','width','height','net_weight','pack_length','pack_width','pack_height','pack_weight','cost','margin'):
   try:n=Decimal(value)
   except InvalidOperation:raise ValueError(label+'须为数字')
   if not n.is_finite() or n<0 or (key not in ('cost','margin') and n==0) or (key=='margin' and n>=100):raise ValueError(label+'数值无效')
  parts.append(label+'：'+value)
 if not values.get('name','').strip():raise ValueError('请填写商品名称/用途')
 return '；'.join(parts)+'；品牌：无品牌'

def column_updates(text,count):
 if count<1:raise ValueError('请先增加或选中变体')
 if '\t' in text:raise ValueError('此窗口只填写一列，请勿粘贴多列数据')
 values=text.split('\n')
 values=[v.rstrip('\r').strip() for v in values]
 if len(values)==1:return values*count
 if len(values)!=count:raise ValueError(f'输入{len(values)}行，但目标有{count}个变体；未修改任何数据')
 return values

def same_first(rows,key):
 allowed={k for k,_,_ in FIELDS}-{'stock'}
 if key not in allowed:raise ValueError('此列不支持同首行')
 if not rows:return 0
 value=str(rows[0]['values'].get(key,'')).strip()
 if not value:return 0
 changed=0
 for row in rows[1:]:
  if row['values'].get(key)!=value:row['values'][key]=value;changed+=1
 return changed

class VariantGrid:
 def __init__(self,parent,base):
  import tkinter as tk
  from tkinter import ttk
  self.tk=tk;self.ttk=ttk;self.base=base;self.rows=[];self.next_index=1;self.focus=(1,0);self.editor=None;self.photos={}
  self.frame=ttk.Frame(parent);self.frame.pack(fill='both',padx=12,pady=8)
  bar=ttk.Frame(self.frame);bar.pack(fill='x',pady=4)
  for label,cmd in [('增加变体',self.add),('删除选中变体',self.remove),('选择主图参考',self.choose),('当前参数同首行',self.fill_row),('粘贴Excel表格',self.paste)]:ttk.Button(bar,text=label,command=cmd).pack(side='left',padx=3)
  self.hint=ttk.Label(self.frame,text='每行一个变体；双击编辑。点击参数列标题“同首行”，将首行该参数复制到其余全部变体。');self.hint.pack(anchor='w')
  holder=ttk.Frame(self.frame);holder.pack(fill='both',expand=True);holder.rowconfigure(0,weight=1);holder.columnconfigure(0,weight=1)
  self.tree=ttk.Treeview(holder,columns=('index','article','refs')+tuple(k for k,_,_ in FIELDS),show='tree headings',height=6,selectmode='extended')
  self.tree.heading('#0',text='主图');self.tree.column('#0',width=85,stretch=False,anchor='center')
  from tkinter import font as tkfont
  heading_font=tkfont.nametofont('TkDefaultFont');copy_keys={k for k,_,_ in FIELDS}-{'stock'}
  for key,title,width in [('index','序号',55),('article','货号',160),('refs','主图参考',95)]+[(k,label,170 if k in ('name','extra') else 125) for k,label,_ in FIELDS]:
   heading=title+(' · 同首行' if key in copy_keys else '')
   self.tree.heading(key,text=heading,anchor='center',command=(lambda k=key:self.bulk_column(k)) if key in copy_keys else (lambda:None));self.tree.column(key,width=max(width,heading_font.measure(heading)+24),stretch=False,anchor='center')
  self.tree.grid(row=0,column=0,sticky='nsew');sx=ttk.Scrollbar(holder,orient='horizontal',command=self.tree.xview);sx.grid(row=1,column=0,sticky='ew');sy=ttk.Scrollbar(holder,orient='vertical',command=self.tree.yview);sy.grid(row=0,column=1,sticky='ns');self.tree.configure(xscrollcommand=sx.set,yscrollcommand=sy.set)
  ttk.Style().configure('Variants.Treeview',rowheight=58);self.tree.configure(style='Variants.Treeview')
  self.tree.bind('<Button-1>',self.image_click);self.tree.bind('<Double-1>',self.edit);self.tree.bind('<ButtonRelease-1>',self.track);self.tree.bind('<Control-v>',lambda e:self.paste());self.base.trace_add('write',lambda *_:self.refresh());self.add()
 def commit(self):
  if self.editor:
   widget,row,key=self.editor;row['values'][key]=widget.get().strip();self.editor=None;widget.destroy();self.refresh()
 def refresh(self):
  selected=self.tree.selection()
  for item in self.tree.get_children():self.tree.delete(item)
  for row in self.rows:
   row['values']['stock']='1000'
   try:code=article(self.base.get().strip(),row['index'])
   except ValueError:code='待填基础货号'
   self.tree.insert('', 'end',iid=str(row['index']),image=self.photos.get(row['index'],''),values=(row['index'],code,f"{len(row['refs'])} 张")+tuple(row['values'][k] for k,_,_ in FIELDS))
  selected=[i for i in selected if self.tree.exists(i)]
  if selected:self.tree.selection_set(selected)
 def add(self):
  self.commit();self.rows.append({'index':self.next_index,'refs':[],'values':{k:d for k,_,d in FIELDS}});self.next_index+=1;self.refresh()
 def selected(self):
  return [r for r in self.rows if str(r['index']) in self.tree.selection()]
 def remove(self):
  self.commit();ids={r['index'] for r in self.selected()};self.rows=[r for r in self.rows if r['index'] not in ids];self.refresh()
 def image_click(self,event):
  item=self.tree.identify_row(event.y);column=self.tree.identify_column(event.x)
  if item and column=='#0':
   self.tree.selection_set(item)
   row=next(r for r in self.rows if str(r['index'])==item)
   self.tree.after(10,lambda:self.manage_images(row) if row['refs'] else self.choose())
   return 'break'
 def thumbnail(self,row):
  from PIL import Image,ImageOps,ImageTk
  if row['refs']:
   with Image.open(row['refs'][0]) as im:self.photos[row['index']]=ImageTk.PhotoImage(ImageOps.contain(im.convert('RGB'),(64,52)))
  else:self.photos.pop(row['index'],None)
  self.refresh()
 def choose(self):
  from tkinter import filedialog,messagebox
  rows=self.selected()
  if len(rows)!=1:messagebox.showinfo('选择变体','请选中一行变体再上传主图参考');return
  paths=list(filedialog.askopenfilenames(filetypes=[('Images','*.png *.jpg *.jpeg *.webp')]))
  if not paths:return
  try:
   from PIL import Image
   for path in paths:
    with Image.open(path) as im:im.verify()
   rows[0]['refs']=list(dict.fromkeys(rows[0]['refs']+paths));self.thumbnail(rows[0])
  except Exception as e:messagebox.showerror('图片无法读取',str(e))
 def manage_images(self,row):
  from PIL import Image,ImageOps,ImageTk
  dialog=self.tk.Toplevel(self.frame);dialog.title('主图参考：点击图片选中后删除');dialog.geometry('640x420')
  body=self.ttk.Frame(dialog);body.pack(fill='both',expand=True)
  selected=set();photos=[]
  def render():
   for child in body.winfo_children():child.destroy()
   photos.clear()
   for i,path in enumerate(row['refs']):
    try:
     with Image.open(path) as im:photo=ImageTk.PhotoImage(ImageOps.contain(im.convert('RGB'),(110,100)))
     photos.append(photo)
     def select(p=path):
      if p in selected:selected.remove(p)
      else:selected.add(p)
      render()
     button=self.tk.Button(body,image=photo,text=('✓ ' if path in selected else '')+__import__('os').path.basename(path),compound='top',command=select,relief='sunken' if path in selected else 'raised');button.grid(row=i//4,column=i%4,padx=5,pady=5)
    except Exception:self.ttk.Label(body,text='图片不可读').grid(row=i//4,column=i%4)
  def delete():
   row['refs']=[p for p in row['refs'] if p not in selected];selected.clear();self.thumbnail(row);render()
  self.ttk.Button(dialog,text='删除选中参考（不删除原文件）',command=delete).pack(side='bottom',pady=8)
  render()
 def track(self,event):
  item=self.tree.identify_row(event.y);column=self.tree.identify_column(event.x)
  if item and column.startswith('#') and int(column[1:])>=4:self.focus=(int(item),int(column[1:])-4)
 def edit(self,event):
  self.commit();self.track(event);item=self.tree.identify_row(event.y);column=self.tree.identify_column(event.x)
  if not item or not column.startswith('#') or int(column[1:])<4:return
  key=FIELDS[int(column[1:])-4][0]
  if key=='stock':return
  row=next(r for r in self.rows if str(r['index'])==item);box=self.tree.bbox(item,column)
  if not box:return
  entry=self.ttk.Entry(self.tree,justify='center');entry.insert(0,row['values'][key]);entry.place(x=box[0],y=box[1],width=box[2],height=box[3]);entry.focus_set();entry.selection_range(0,'end');self.editor=(entry,row,key)
  entry.bind('<Return>',lambda e:self.commit());entry.bind('<FocusOut>',lambda e:self.commit())
 def fill_row(self):
  self.bulk_column(FIELDS[self.focus[1]][0])
 def bulk_column(self,key):
  self.commit()
  if key=='stock':return
  try:
   count=same_first(self.rows,key);label=next(title for k,title,_ in FIELDS if k==key)
   self.focus=(self.rows[0]['index'] if self.rows else 1,next(n for n,f in enumerate(FIELDS) if f[0]==key));self.refresh()
   self.hint.configure(text=(label+'：已同首行，更新'+str(count)+'个变体') if self.rows and str(self.rows[0]['values'].get(key,'')).strip() else label+'：首行为空，请先填写首行；未覆盖其余变体')
  except ValueError as exc:self.hint.configure(text=str(exc))
 def paste(self):
  from tkinter import messagebox
  self.commit()
  try:
   matrix=[line.split('\t') for line in self.frame.clipboard_get().rstrip('\r\n').splitlines()]
   if not matrix:return
   index,col=self.focus;start=next((i for i,r in enumerate(self.rows) if r['index']==index),0)
   if col+max(map(len,matrix))>len(FIELDS):raise ValueError('超过参数列数；请勿包含序号、货号、主图列')
   while len(self.rows)<start+len(matrix):self.add()
   for y,line in enumerate(matrix):
    for x,value in enumerate(line):self.rows[start+y]['values'][FIELDS[col+x][0]]=value
   self.refresh()
  except Exception as e:messagebox.showerror('无法粘贴',str(e))
 def records(self):
  self.commit()
  if not self.rows:raise ValueError('请至少增加一个变体')
  for row in self.rows:row['values']['stock']='1000'
  return [{'article':article(self.base.get().strip(),r['index']),'index':r['index'],'base_article':self.base.get().strip(),'values':dict(r['values']),'facts':facts(r['values']),'references':list(r['refs'])} for r in self.rows]
