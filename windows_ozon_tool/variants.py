"""Variant columns: stable natural-number suffixes, explicit units, TSV paste."""
from window_registry import lookup,remember
from decimal import Decimal,InvalidOperation
import re
FIELDS=[('name','商品名称/用途',''),('color','颜色',''),('size','规格/型号',''),('quantity','每套件数','1'),('material','主体材质',''),('accessory_material','配件/内衬材质',''),('length','商品长(cm)',''),('width','商品宽(cm)',''),('height','商品高(cm)',''),('net_weight','商品净重(g)',''),('pack_length','包装长(cm)',''),('pack_width','包装宽(cm)',''),('pack_height','包装高(cm)',''),('pack_weight','包装总重(g)',''),('cost','每套成本含国内运费(元)',''),('margin','目标净利润率(%)','25'),('stock','初始库存（固定1000）','1000'),('origin','产地','中国'),('assembly','组装方式(未知留空)',''),('extra','其他真实参数/卖点',''),('competitor_url','竞品链接','')]
# Compact views cover every business field without changing the stored schema.
SECTIONS={
 '基础信息':('name','color','quantity','competitor_url'),
 '材质功能':('material','accessory_material','assembly','extra'),
 '商品尺寸':('length','width','height','net_weight','size'),
 '包装物流':('pack_length','pack_width','pack_height','pack_weight'),
 '定价其他':('cost','margin','stock','origin'),
 '全部参数':tuple(k for k,_,_ in FIELDS),
}
SHORT_LABELS={'competitor_url':'竞品链接 · 同首行','name':'商品名称 / 用途','color':'颜色 · 多选','size':'规格 / 型号','quantity':'件数','material':'主体材质','accessory_material':'配件 / 内衬','assembly':'组装方式','extra':'更多参数 / 卖点','length':'长 (cm)','width':'宽 (cm)','height':'高 (cm)','net_weight':'净重 (g)','pack_length':'包装长 (cm)','pack_width':'包装宽 (cm)','pack_height':'包装高 (cm)','pack_weight':'总重 (g)','cost':'每套成本 (元)','margin':'净利率 (%)','stock':'初始库存','origin':'产地'}

def paste_fields(section,start,width):
 """Compact paste follows visible fields; wide Excel tables keep full-schema order."""
 fields=SECTIONS.get(section,SECTIONS['全部参数']);all_fields=SECTIONS['全部参数']
 if start not in fields:start=fields[0]
 offset=fields.index(start)
 if width<=len(fields)-offset:return fields[offset:offset+width]
 offset=all_fields.index(start)
 if width>len(all_fields)-offset:raise ValueError('超过参数列数；请勿包含序号、货号、主图列')
 return all_fields[offset:offset+width]

# Creation view only; stored fields and legacy Excel order stay unchanged.
COMPACT_COLUMNS=('name','color','pack_dimensions','pack_weight','cost','quantity','competitor_url')
PACK_KEYS=('pack_length','pack_width','pack_height')
COMPACT_LABELS={'name':'名称 / 用途','color':'颜色','pack_dimensions':'包装长宽高 (cm)','pack_weight':'包装重量 (g)','cost':'成本 (元)','quantity':'件数','competitor_url':'竞品链接 · 同首行'}

def pack_display(values):
 parts=[str(values.get(k,'')).strip() for k in PACK_KEYS]
 return ' × '.join(v or '—' for v in parts) if any(parts) else ''

def cell_values(values,key,value):
 result=dict(values)
 if key!='pack_dimensions':result[key]=str(value).strip();return result
 if isinstance(value,(tuple,list)):parts=[str(v).strip() for v in value]
 elif not str(value).strip():parts=['','','']
 else:parts=re.split(r'\s*[×xX*，,;/／]\s*|\s+',str(value).strip())
 if len(parts)!=3:raise ValueError('包装尺寸请按长、宽、高填写三个数值，例如 35 × 25 × 7，单位cm')
 for part in parts:
  if not part:continue
  try:n=Decimal(part)
  except InvalidOperation:raise ValueError('包装长宽高须为有效数字，单位cm')
  if not n.is_finite() or n<=0:raise ValueError('包装长宽高须大于0，单位cm')
 result.update(zip(PACK_KEYS,parts));return result

def compact_paste_keys(start,width):
 if start not in COMPACT_COLUMNS:start='name'
 offset=COMPACT_COLUMNS.index(start)
 if width<=len(COMPACT_COLUMNS)-offset:return COMPACT_COLUMNS[offset:offset+width]
 # Older full-schema Excel input still uses the original field order.
 return paste_fields('全部参数','pack_length' if start=='pack_dimensions' else start,width)

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
  if key=='competitor_url':
   from competitor_reference import normalize_url
   normalize_url(value);continue
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
  self.frame=ttk.Frame(parent);self.frame.pack(fill='both',expand=True,padx=12,pady=8)
  from ui_components import responsive_actions
  bar,self.action_buttons=responsive_actions(self.frame,[('＋ 增加变体',self.add),('删除选中变体',self.remove),('添加主图参考',self.choose),('管理主图参考',self.manage_selected),('当前参数同首行',self.fill_row),('粘贴Excel表格',self.paste)],min_width=110,button_style='Compact.TButton')
  self.section='简洁录入';self.section_buttons={};self.focus_key='name'
  self.hint=ttk.Label(self.frame,text='双击编辑，点击列标题同首行；包装尺寸单位cm。',style='Muted.TLabel',wraplength=950);self.hint.pack_forget()
  holder=ttk.Frame(self.frame);holder.pack(fill='both',expand=True);holder.rowconfigure(0,weight=1);holder.columnconfigure(1,weight=1)
  self.frozen=ttk.Treeview(holder,columns=('index',),show='tree headings',height=6,selectmode='extended')
  self.frozen.heading('#0',text='主图参考');self.frozen.column('#0',width=84,stretch=False,anchor='center')
  self.frozen.heading('index',text='序号');self.frozen.column('index',width=40,stretch=False,anchor='center')
  self.frozen.grid(row=0,column=0,sticky='ns')
  self.tree=ttk.Treeview(holder,columns=('index','article','refs')+tuple(k for k,_,_ in FIELDS)+('pack_dimensions',),displaycolumns=COMPACT_COLUMNS,show='headings',height=6,selectmode='extended')
  self.tree.heading('#0',text='主图');self.tree.column('#0',width=85,stretch=False,anchor='center')
  from tkinter import font as tkfont
  heading_font=tkfont.nametofont('TkDefaultFont');copy_keys={k for k,_,_ in FIELDS}-{'stock'}
  for key,title,width in [('index','序号',55),('article','货号',160),('refs','主图参考',95)]+[(k,label,170 if k in ('name','extra') else 125) for k,label,_ in FIELDS]:
   if key=='color':title='颜色（可多选）'
   heading=title+(' · 同首行' if key in copy_keys else '')
   self.tree.heading(key,text=heading,anchor='center',command=(lambda k=key:self.bulk_column(k)) if key in copy_keys else (lambda:None));self.tree.column(key,width=max(width,heading_font.measure(heading)+24),stretch=False,anchor='center')
  self.tree.heading('pack_dimensions',text=COMPACT_LABELS['pack_dimensions'],command=lambda:self.bulk_column('pack_dimensions'))
  self.tree.grid(row=0,column=1,sticky='nsew')
  def horizontal(*args):self.commit();self.tree.xview(*args)
  sx=ttk.Scrollbar(holder,orient='horizontal',command=horizontal);sx.grid(row=1,column=1,sticky='ew');self.horizontal_scroll=sx
  def vertical(*args):self.frozen.yview(*args);self.tree.yview(*args)
  sy=ttk.Scrollbar(holder,orient='vertical',command=vertical);sy.grid(row=0,column=2,sticky='ns')
  def report(source,other,first,last):
   sy.set(first,last)
   if abs(other.yview()[0]-float(first))>.000001:other.yview_moveto(first)
  self.tree.configure(xscrollcommand=sx.set,yscrollcommand=lambda a,b:report(self.tree,self.frozen,a,b))
  self.frozen.configure(yscrollcommand=lambda a,b:report(self.frozen,self.tree,a,b))
  def selection(source,other):
   ids=source.selection()
   if ids:
    focused=source.focus();self.focus=(int(focused if focused in ids else ids[0]),self.focus[1])
   if set(ids)!=set(other.selection()):other.selection_set([i for i in ids if other.exists(i)])
   self.update_summary()
  for widget in (self.tree,self.frozen):
   widget.tag_configure('row_even',background='#FFFFFF');widget.tag_configure('row_odd',background='#F6F8FD')
  self.tree.bind('<<TreeviewSelect>>',lambda e:selection(self.tree,self.frozen))
  self.frozen.bind('<<TreeviewSelect>>',lambda e:selection(self.frozen,self.tree))
  self.frozen.bind('<Button-1>',self.image_click)
  self.frozen.bind('<Control-v>',lambda e:self.paste())
  ttk.Style().configure('Variants.Treeview',rowheight=58);self.tree.configure(style='Variants.Treeview',height=8);self.frozen.configure(style='Variants.Treeview',height=8)
  foot=ttk.Frame(self.frame);foot.pack(side='bottom',before=holder,fill='x',pady=(6,0))
  self.summary=ttk.Label(foot,style='Muted.TLabel');self.summary.pack(side='left')
  self.tree.bind('<Double-1>',self.edit);self.tree.bind('<ButtonRelease-1>',self.track);self.tree.bind('<Control-v>',lambda e:self.paste());self.base.trace_add('write',lambda *_:self.refresh());self.tree.bind('<Configure>',lambda e:self.fit_columns(e.width));self.set_section();self.add()
 def set_section(self,name=None):
  # Compatibility entry point: creation now has one view, no category tabs.
  self.commit();self.horizontal_scroll.grid_remove();self.tree.configure(displaycolumns=COMPACT_COLUMNS)
  for key in COMPACT_COLUMNS:self.tree.heading(key,text=COMPACT_LABELS[key],command=lambda k=key:self.bulk_column(k))
  self.fit_columns(self.tree.winfo_width());self.update_summary()
 def update_summary(self):
  if hasattr(self,'summary'):self.summary.configure(text='共 '+str(len(self.rows))+' 个变体 · 已选 '+str(len(self.tree.selection()))+' 个 · 主图与序号固定')
 def fit_columns(self,width):
  if width<100:return
  # Give spare room to the product name; numeric columns remain compact.
  sizes={'color':105,'pack_dimensions':164,'pack_weight':102,'cost':82,'quantity':56}
  if width<850:
   sizes={'color':75,'pack_dimensions':134,'pack_weight':86,'cost':68,'quantity':44}
  sizes['competitor_url']=max(110,min(220,int(width*.22)))
  sizes['name']=max(80,width-4-sum(sizes.values()))
  for key in COMPACT_COLUMNS:self.tree.column(key,width=sizes[key],minwidth=35,stretch=(key=='name'))
 def commit(self):
  if not self.editor:return True
  if getattr(self,'committing',False):return False
  widget,row,key=self.editor
  try:values=cell_values(row['values'],key,widget.get())
  except ValueError as exc:
   from tkinter import messagebox
   self.committing=True
   try:messagebox.showerror('包装尺寸无效',str(exc),parent=self.frame)
   finally:self.committing=False
   return False
  self.editor=None;row['values']=values;widget.destroy();self.refresh();return True
 def commit_outside(self):
  if not self.editor:return
  widget=self.editor[0];focused=widget.focus_get()
  if focused is not None and (focused is widget or str(focused).startswith(str(widget)+'.')):return
  self.commit()
 def refresh(self):
  selected=self.tree.selection();xpos=self.tree.xview()[0];ypos=self.tree.yview()[0]
  for widget in (self.tree,self.frozen):
   for item in widget.get_children():widget.delete(item)
  for n,row in enumerate(self.rows):
   tags=('row_even' if n%2==0 else 'row_odd',)
   row['values']['stock']='1000'
   try:code=article(self.base.get().strip(),row['index'])
   except ValueError:code='待填基础货号'
   self.frozen.insert('','end',iid=str(row['index']),text=str(len(row['refs']))+' 图' if row['refs'] else '未选图',values=(row['index'],),image=self.photos.get(row['index'],''),tags=tags)
   self.tree.insert('', 'end',iid=str(row['index']),image=self.photos.get(row['index'],''),values=(row['index'],code,f"{len(row['refs'])} 张")+tuple(row['values'][k] for k,_,_ in FIELDS)+(pack_display(row['values']),),tags=tags)
  selected=[i for i in selected if self.tree.exists(i)]
  if selected:self.tree.selection_set(selected);self.frozen.selection_set(selected)
  self.tree.xview_moveto(xpos);self.tree.yview_moveto(ypos);self.frozen.yview_moveto(ypos);self.update_summary()
 def add(self):
  if self.commit() is False:return
  self.rows.append({'index':self.next_index,'refs':[],'values':{k:d for k,_,d in FIELDS}});self.next_index+=1;self.refresh();item=str(self.rows[-1]['index']);self.tree.selection_set(item);self.frozen.selection_set(item);self.tree.see(item);self.frozen.see(item)
 def selected(self):
  return [r for r in self.rows if str(r['index']) in self.tree.selection()]
 def remove(self):
  if self.commit() is False:return
  ids={r['index'] for r in self.selected()};self.rows=[r for r in self.rows if r['index'] not in ids];self.refresh()
 def image_click(self,event):
  item=self.frozen.identify_row(event.y);column=self.frozen.identify_column(event.x)
  if item and column=='#0':
   self.tree.selection_set(item)
   row=next(r for r in self.rows if str(r['index'])==item)
   self.tree.after(10,lambda:self.preview_reference(row) if row['refs'] else self.choose())
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
 def manage_selected(self):
  from tkinter import messagebox
  rows=self.selected()
  if len(rows)!=1:messagebox.showinfo('选择变体','请选中一个变体再管理主图参考');return
  self.manage_images(rows[0])
 def preview_reference(self,row,start=0):
  from image_viewer import open_viewer
  return open_viewer(self.frame,'',[{'local_file':p} for p in row['refs']],start,title='原始主图参考 · '+str(row['index']),on_replace=lambda index:self.replace_reference(row,index))
 def replace_reference(self,row,index=0):
  from tkinter import filedialog,messagebox
  from PIL import Image
  path=filedialog.askopenfilename(filetypes=[('Images','*.png *.jpg *.jpeg *.webp')])
  if not path:return None
  try:
   with Image.open(path) as image:image.verify()
   if path in row['refs'] and row['refs'].index(path)!=index:raise ValueError('这张图片已在本变体参考中，请选择另一张图片')
   row['refs'][index]=path;self.thumbnail(row);return path
  except (OSError,ValueError) as error:messagebox.showerror('未更换图片',str(error));return None
 def manage_images(self,row):
  from PIL import Image,ImageOps,ImageTk
  cached=lookup(self.frame,('original_reference_manager',id(self),row['index']))
  if cached is not None:return cached
  dialog=remember(self.frame,('original_reference_manager',id(self),row['index']),self.tk.Toplevel(self.frame));dialog.title('主图参考：点击图片选中后删除');dialog.geometry('640x420')
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
  if not item or not column:return
  key=self.tree.column(column,'id')
  if key in COMPACT_COLUMNS:
   self.focus_key=key;self.focus=(int(item),next(i for i,f in enumerate(FIELDS) if f[0]==('pack_length' if key=='pack_dimensions' else key)))
 def edit(self,event):
  if self.commit() is False:return
  self.track(event);item=self.tree.identify_row(event.y);column=self.tree.identify_column(event.x)
  if not item or not column:return
  key=self.tree.column(column,'id')
  if key not in COMPACT_COLUMNS:return
  if key=='stock':return
  row=next(r for r in self.rows if str(r['index'])==item);box=self.tree.bbox(item,column)
  if not box:return
  if key=='pack_dimensions':
   frame=self.ttk.Frame(self.tree);frame.place(x=box[0],y=box[1]+(box[3]-30)//2,width=box[2],height=30);entries=[]
   for i,k in enumerate(PACK_KEYS):
    frame.columnconfigure(i*2,weight=1)
    entry=self.ttk.Entry(frame,width=4,justify='center');entry.insert(0,row['values'].get(k,''));entry.grid(row=0,column=i*2,sticky='ew');entries.append(entry)
    if i<2:self.ttk.Label(frame,text='×').grid(row=0,column=i*2+1)
    entry.bind('<Return>',lambda e:self.commit());entry.bind('<FocusOut>',lambda e:self.tree.after_idle(self.commit_outside))
   frame.get=lambda:tuple(e.get() for e in entries);self.editor=(frame,row,key);entries[0].focus_set();entries[0].selection_range(0,'end');return
  if key=='color':
   from color_selection import choose
   def save_color(value):row['values']['color']=value;self.refresh()
   choose(self.frame,row['values'][key],save_color,window_key=('create',id(self),row['index']),service=getattr(self,'color_service',None));return
  entry=self.ttk.Entry(self.tree,justify='center');entry.insert(0,row['values'][key]);entry.place(x=box[0],y=box[1],width=box[2],height=box[3]);entry.focus_set();entry.selection_range(0,'end');self.editor=(entry,row,key)
  entry.bind('<Return>',lambda e:self.commit());entry.bind('<FocusOut>',lambda e:self.commit())
 def fill_row(self):
  self.bulk_column(getattr(self,'focus_key',FIELDS[self.focus[1]][0]))
 def bulk_column(self,key):
  if self.commit() is False:return
  if key=='stock':return
  try:
   if key=='pack_dimensions':
    parts=[self.rows[0]['values'].get(k,'') for k in PACK_KEYS] if self.rows else []
    count=0
    if parts and all(str(v).strip() for v in parts):
     prepared=cell_values(self.rows[0]['values'],key,parts)
     for row in self.rows[1:]:
      if any(row['values'].get(k)!=prepared[k] for k in PACK_KEYS):row['values'].update({k:prepared[k] for k in PACK_KEYS});count+=1
    label='包装长宽高'
   else:count=same_first(self.rows,key);label=next(title for k,title,_ in FIELDS if k==key)
   self.focus_key=key
   self.focus=(self.rows[0]['index'] if self.rows else 1,next(n for n,f in enumerate(FIELDS) if f[0]==('pack_length' if key=='pack_dimensions' else key)));self.refresh()
   self.hint.configure(text=(label+'：已同首行，更新'+str(count)+'个变体') if self.rows and (pack_display(self.rows[0]['values']) if key=='pack_dimensions' else str(self.rows[0]['values'].get(key,'')).strip()) else label+'：首行为空，请先填写首行；未覆盖其余变体')
  except ValueError as exc:self.hint.configure(text=str(exc))
 def competitor_links(self):
  from tkinter import messagebox
  if self.commit() is False:return
  cached=lookup(self.frame,('creation_competitor_links',id(self)))
  if cached is not None:return cached
  row_ids=tuple(r['index'] for r in self.rows)
  dialog=remember(self.frame,('creation_competitor_links',id(self)),self.tk.Toplevel(self.frame));dialog.title('竞品链接');dialog.geometry('680x380')
  self.ttk.Label(dialog,text='按变体顺序每行一个链接；只填一行会应用到全部变体。',style='Muted.TLabel').pack(fill='x',padx=16,pady=12)
  text=self.tk.Text(dialog,height=9,wrap='none');text.pack(fill='both',expand=True,padx=16);text.insert('1.0','\n'.join(r['values'].get('competitor_url','') for r in self.rows))
  bar=self.ttk.Frame(dialog);bar.pack(fill='x',padx=16,pady=12)
  def copy_first():
   lines=text.get('1.0','end-1c').splitlines();first=lines[0].strip() if lines else ''
   if first:text.delete('1.0','end');text.insert('1.0','\n'.join([first]*len(self.rows)))
  def save():
   try:
    from competitor_reference import normalize_url
    if tuple(r['index'] for r in self.rows)!=row_ids:raise ValueError('变体已增删，请关闭并重新打开链接窗口后填写')
    values=column_updates(text.get('1.0','end-1c'),len(self.rows));checked=[normalize_url(v) for v in values]
    for row,value in zip(self.rows,checked):row['values']['competitor_url']=value
    self.refresh();dialog.destroy()
   except ValueError as exc:messagebox.showerror('链接未保存',str(exc),parent=dialog)
  self.ttk.Button(bar,text='同首行',command=copy_first).pack(side='left');self.ttk.Button(bar,text='保存链接',command=save,style='Primary.TButton').pack(side='right')
  return dialog
 def paste(self):
  from tkinter import messagebox
  if self.commit() is False:return
  try:
   matrix=[line.split('\t') for line in self.frame.clipboard_get().rstrip('\r\n').splitlines()]
   if not matrix:return
   index,col=self.focus;start=next((i for i,r in enumerate(self.rows) if r['index']==index),0)
   keys=compact_paste_keys(getattr(self,'focus_key',FIELDS[col][0]),max(map(len,matrix)))
   prepared=[]
   for y,line in enumerate(matrix):
    values=dict(self.rows[start+y]['values']) if start+y<len(self.rows) else {k:d for k,_,d in FIELDS}
    for key,value in zip(keys,line):values=cell_values(values,key,value)
    prepared.append(values)
   while len(self.rows)<start+len(matrix):self.add()
   for y,values in enumerate(prepared):self.rows[start+y]['values']=values
   self.refresh()
  except Exception as e:messagebox.showerror('无法粘贴',str(e))
 def records(self):
  if self.commit() is False:raise ValueError('请先修正包装尺寸')
  if not self.rows:raise ValueError('请至少增加一个变体')
  for row in self.rows:row['values']['stock']='1000'
  return [{'article':article(self.base.get().strip(),r['index']),'index':r['index'],'base_article':self.base.get().strip(),'values':dict(r['values']),'facts':facts(r['values']),'references':list(r['refs'])} for r in self.rows]
