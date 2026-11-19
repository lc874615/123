"""Actual Tk compact grid interactions with synthetic values; no network."""
import sys,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
for k in ('OZON_CLIENT_ID','OZON_API_KEY','COS_SECRET_ID','COS_SECRET_KEY'):os.environ.pop(k,None)
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
from variants import VariantGrid,COMPACT_COLUMNS,PACK_KEYS
from ui_layout import build
root=tk.Tk();build(root);root.withdraw();window=tk.Toplevel(root);window.geometry('980x560+10+10');g=VariantGrid(window,tk.StringVar(value='DEMO'));errors=[];root.report_callback_exception=lambda a,b,c:errors.append(str(b))
for i in range(19):g.add()
for row in g.rows:row['values'].update(name='三折叠理发镜',color='черный',pack_weight='1600',cost='29',quantity='1')
g.refresh();g.tree.see('1');g.frozen.see('1')
def check():
 try:
  assert g.tree.winfo_height()>300;assert tuple(g.tree.cget('displaycolumns'))==COMPACT_COLUMNS;assert not g.section_buttons;assert g.tree.xview()[1]>=.999
  for key in ('pack_dimensions','pack_weight','cost','quantity'):assert g.tree.column(key,'width')<g.tree.column('name','width')
  box=g.tree.bbox('1','pack_dimensions');g.edit(SimpleNamespace(x=box[0]+10,y=box[1]+10));assert g.editor and g.editor[2]=='pack_dimensions';entries=[x for x in g.editor[0].winfo_children() if isinstance(x,ttk.Entry)];assert len(entries)==3
  for entry,value in zip(entries,('35','25','7')):entry.delete(0,'end');entry.insert(0,value)
  entries[1].focus_set();root.update();assert g.editor;assert g.commit();g.bulk_column('pack_dimensions');assert all(tuple(r['values'][k] for k in PACK_KEYS)==('35','25','7') for r in g.rows)
  g.rows[0]['values']['competitor_url']='https://www.ozon.ru/product/example-12345/';g.bulk_column('competitor_url');assert all(r['values']['competitor_url'].endswith('12345/') for r in g.rows)
  assert g.competitor_links() is g.competitor_links();g.competitor_links().destroy()
  g.focus=(1,0);g.focus_key='name';root.clipboard_clear();root.clipboard_append('镜子A\t黑色\t40x25x8\t1700\t30\t1\n镜子B\t白色\t41x26x9\t1800\t31\t2');g.paste();assert g.rows[1]['values']['pack_height']=='9';assert g.rows[1]['values']['quantity']=='2'
  window.geometry('760x560+10+10');root.update();assert g.tree.xview()[1]>=.999
  window.geometry('1100x560+10+10');root.update()
  if '--screenshot' in sys.argv:
   from PIL import ImageGrab
   ImageGrab.grab(bbox=(window.winfo_rootx(),window.winfo_rooty(),window.winfo_rootx()+window.winfo_width(),window.winfo_rooty()+window.winfo_height())).save('/tmp/ozon165-compact.png')
  print('PASS: seven columns including inline competitor link, no tabs, 20 variants, three-value editor, same-first, six-column Excel paste, reusable competitor window, 760px no horizontal scroll')
 except Exception:errors.append(__import__('traceback').format_exc())
 root.destroy()
root.after(400,check);root.mainloop();assert not errors,errors
