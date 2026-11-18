"""Synthetic creation UI check; uses a fake category API and temporary files only."""
import sys,os,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
for k in ('OZON_CLIENT_ID','OZON_API_KEY','COS_SECRET_ID','COS_SECRET_KEY'):os.environ.pop(k,None)
from unittest.mock import patch
from PIL import Image
import local_bridge
from creation_category import selection,choose
from types import SimpleNamespace
with tempfile.TemporaryDirectory() as tmp:
 local_bridge.DATA=__import__('pathlib').Path(tmp);pic=local_bridge.DATA/'sample.png';Image.new('RGB',(600,800),'navy').save(pic);errors=[]
 def ready(root,ui):
  root.geometry('1080x700');ui['notebook'].select(ui['pages']['product']);root.after(400,lambda:check(root,ui))
 def check(root,ui):
  try:
   import tkinter as tk
   ui['notebook'].select(ui['pages']['product']);root.update();g=ui['creation_grid'];assert g.tree.winfo_height()>70
   assert not any(isinstance(x,tk.Canvas) for x in ui['pages']['product'].winfo_children())
   with patch('tkinter.filedialog.askopenfilenames',return_value=[str(pic)]):ui['shared_choose']()
   a=ui['shared_preview']();assert a is ui['shared_preview']();a.destroy()
   os.environ['OZON_CLIENT_ID']='mock-shop'
   service=SimpleNamespace(root=local_bridge.DATA,caller=lambda *a:{'result':[{'description_category_id':10,'category_name':'家具','children':[{'type_id':20,'type_name':'椅子','children':[]}]}]})
   values=[];window=choose(root,service,lambda:'mock-shop',values.append)
   assert window is choose(root,service,lambda:'mock-shop',values.append)
   def finish():
    try:
     tree=window._ozon_ui['tree'];assert len(tree.get_children())==1;tree.selection_set(tree.get_children()[0]);window._ozon_ui['select']();assert values[0]['category']['confirmed']
     ui['category_selection'].update(values[0]);g.base.set('CHECK');g.rows[0]['values']['name']='测试椅子';g.rows[0]['refs']=[str(pic)];g.refresh();ui['create']();task=next(t for t in ui['store'].tasks if t['sku']=='CHECK(1)');assert task['category_selection']['category']['confirmed'];assert not ui['store'].control['paused']
     print('PASS: compact 1080x700 creation, reusable image/category windows, official API fixture, category persistence, queue start')
    except Exception:errors.append(__import__('traceback').format_exc())
    ui['close']()
   root.after(800,finish)
  except Exception:errors.append(__import__('traceback').format_exc());ui['close']()
 with patch('tkinter.messagebox.showerror',side_effect=lambda *a,**k:errors.append(str(a))),patch('tkinter.messagebox.showinfo'):
  local_bridge.main(test_mode=True,on_ready=ready)
 if errors:raise AssertionError('\n'.join(errors))
