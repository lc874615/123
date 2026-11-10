"""Shared multi-color editor; official IDs remain category-validated separately."""
from prefill_rules import COLORS,split

def is_color_field(field,include_name=True):
 from prefill_rules import name
 return name(field) in ('цвет','цвет товара','颜色','商品颜色')+ (('название цвета','颜色名称') if include_name else ())

def choose(parent,initial,save,title='选择颜色（可多选）',close_on_save=True):
 import tkinter as tk
 from tkinter import ttk,messagebox
 from ui_layout import dialog_footer
 window=tk.Toplevel(parent);window.title(title);footer=dialog_footer(window,660,490)
 ttk.Label(window,text='勾选商品实际包含的全部颜色；不会增加商品变体。保存后同步基础参数与对应官方颜色。',wraplength=610).pack(fill='x',padx=10,pady=8)
 current=split(initial);selected={};options=list(dict.fromkeys(COLORS))
 # Avoid showing both synonymous choices; retain unknown/custom labels verbatim.
 canonical={ru:zh for zh,ru in reversed(list(COLORS.items()))}
 current=[canonical.get(v,v) for v in current]
 options=list(dict.fromkeys([*options,*current]));body=ttk.Frame(window);body.pack(fill='both',expand=True,padx=10)
 for i,label in enumerate(options):
  var=tk.BooleanVar(value=label in current);selected[label]=var
  ttk.Checkbutton(body,text=label,variable=var).grid(row=i//4,column=i%4,sticky='w',padx=8,pady=5)
 ttk.Label(footer,text='其他颜色（用逗号或分号分隔；未知颜色不猜测）').pack(anchor='w')
 extra=ttk.Entry(footer);extra.pack(fill='x',pady=4)
 def apply():
  values=list(dict.fromkeys([k for k,v in selected.items() if v.get()]+split(extra.get())))
  try:save('；'.join(values))
  except ValueError as error:messagebox.showerror('未保存',str(error),parent=window);return
  if close_on_save:window.destroy()
 ttk.Button(footer,text='保存所选颜色并同步',command=apply).pack(side='right',padx=5,pady=4)
 ttk.Button(footer,text='取消',command=window.destroy).pack(side='right',padx=5,pady=4)
 return window
