"""Variant columns: stable natural-number suffixes, explicit units, TSV paste."""
from decimal import Decimal,InvalidOperation
import re
FIELDS=[('name','商品名称/用途',''),('color','颜色',''),('size','规格/型号',''),('quantity','每套件数','1'),('material','主体材质',''),('accessory_material','配件/内衬材质',''),('length','商品长(cm)',''),('width','商品宽(cm)',''),('height','商品高(cm)',''),('net_weight','商品净重(g)',''),('pack_length','包装长(cm)',''),('pack_width','包装宽(cm)',''),('pack_height','包装高(cm)',''),('pack_weight','包装总重(g)',''),('cost','每套成本含国内运费(元)',''),('margin','目标净利润率(%)','25'),('stock','库存(套/件)','1000'),('origin','产地',''),('assembly','组装方式(未知留空)',''),('extra','其他真实参数/卖点','')]
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

class VariantGrid:
 def __init__(self,parent,base):
  import tkinter as tk
  from tkinter import ttk,filedialog,messagebox
  self.tk=tk;self.ttk=ttk;self.base=base;self.columns=[];self.next_index=1;self.focus=(0,0)
  self.frame=ttk.Frame(parent);self.frame.pack(fill='both',expand=False,padx=12)
  toolbar=ttk.Frame(self.frame);toolbar.pack(fill='x')
  ttk.Button(toolbar,text='增加变体',command=self.add).pack(side='left')
  ttk.Button(toolbar,text='当前格值填充整行',command=self.fill_row).pack(side='left',padx=4)
  ttk.Button(toolbar,text='粘贴Excel表格到当前格',command=self.paste).pack(side='left')
  ttk.Label(toolbar,text='支持从Excel复制多行多列；各变体独立选择主图参考').pack(side='left',padx=5)
  canvas=tk.Canvas(self.frame,height=290);canvas.pack(fill='both',expand=True)
  sx=ttk.Scrollbar(self.frame,orient='horizontal',command=canvas.xview);sx.pack(fill='x');sy=ttk.Scrollbar(self.frame,orient='vertical',command=canvas.yview);sy.pack(side='right',fill='y')
  canvas.configure(xscrollcommand=sx.set,yscrollcommand=sy.set)
  self.body=ttk.Frame(canvas);canvas.create_window((0,0),window=self.body,anchor='nw');self.body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
  for r,(_,label,_) in enumerate(FIELDS,1):ttk.Label(self.body,text=label,width=29).grid(row=r,column=0,sticky='w',padx=4,pady=2)
  self.base.trace_add('write',lambda *_:self.headers());self.add()
 def headers(self):
  for col in self.columns:
   try:text=article(self.base.get().strip(),col['index'])
   except ValueError:text='待填基础货号'
   col['header'].configure(text=f"变体{col['index']}\n{text}")
 def add(self):
  c=len(self.columns)+1;col={'index':self.next_index,'cells':[],'refs':[]};self.next_index+=1
  col['header']=self.ttk.Label(self.body,width=27);col['header'].grid(row=0,column=c)
  for r,(_,_,default) in enumerate(FIELDS,1):
   var=self.tk.StringVar(value=default);entry=self.ttk.Entry(self.body,textvariable=var,width=27);entry.grid(row=r,column=c,padx=3,pady=2);entry.bind('<FocusIn>',lambda e,r=r-1,c=c-1:setattr(self,'focus',(r,c)));col['cells'].append(var)
  def choose():
   from tkinter import filedialog
   refs=list(filedialog.askopenfilenames(filetypes=[('Images','*.png *.jpg *.jpeg *.webp')]))
   if refs:col['refs']=refs;col['refs_label'].configure(text=f'已选{len(refs)}张原图')
  self.ttk.Button(self.body,text='选择本变体主图参考',command=choose).grid(row=len(FIELDS)+1,column=c)
  col['refs_label']=self.ttk.Label(self.body,text='未选主图参考');col['refs_label'].grid(row=len(FIELDS)+2,column=c)
  self.columns.append(col);self.headers()
 def fill_row(self):
  r,c=self.focus;value=self.columns[c]['cells'][r].get()
  for col in self.columns:col['cells'][r].set(value)
 def paste(self):
  from tkinter import messagebox
  try:
   rows=self.frame.clipboard_get().rstrip('\r\n').splitlines();r,c=self.focus
   if r+len(rows)>len(FIELDS):raise ValueError('粘贴数据超过参数行数')
   needed=c+max(len(x.split('\t')) for x in rows)
   while len(self.columns)<needed:self.add()
   for y,line in enumerate(rows):
    for x,value in enumerate(line.split('\t')):self.columns[c+x]['cells'][r+y].set(value)
  except Exception as e:messagebox.showerror('无法粘贴',str(e))
 def records(self):
  result=[]
  for col in self.columns:
   values={key:v.get().strip() for (key,_,_),v in zip(FIELDS,col['cells'])}
   result.append({'article':article(self.base.get().strip(),col['index']),'index':col['index'],'base_article':self.base.get().strip(),'values':values,'facts':facts(values),'references':col['refs']})
  return result
