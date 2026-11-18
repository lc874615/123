"""Offline actual-Tk style routing/override UI check with temporary synthetic data."""
import os,tempfile,sys
from pathlib import Path
for k in ('OZON_CLIENT_ID','OZON_API_KEY','COS_SECRET_ID','COS_SECRET_KEY'):os.environ.pop(k,None)
import local_bridge
from visual_plans import STYLES
from creation_category import selection
with tempfile.TemporaryDirectory() as tmp:
 local_bridge.DATA=Path(tmp);errors=[]
 def ready(root,ui):
  root.geometry('1080x700');ui['notebook'].select(ui['pages']['product']);root.after(300,lambda:check(root,ui))
 def check(root,ui):
  try:
   ui['category_selection'].update(selection({'description_category_id':10,'type_id':20,'name':'Наушники'},'mock-shop'))
   ui['creation_grid'].rows[0]['values'].update(name='耳机',length='3')
   window=ui['visual_plan']();assert window is ui['visual_plan']();root.update();widgets=window._ozon_ui
   assert len(widgets['tree'].get_children())==8
   widgets['choice'].current(list(STYLES).index('textile')+1);widgets['save']();assert ui['category_selection']['visual_style_override']=='textile'
   widgets['choice'].current(0);widgets['save']();assert 'visual_style_override' not in ui['category_selection']
   window.destroy();root.update();assert ui['creation_grid'].tree.winfo_height()>70
   print('PASS Tk: category-selected plan inspector reused, 8 pages visible, manual override and automatic reset, 1080x700 compact creation remains usable')
  except Exception:errors.append(__import__('traceback').format_exc())
  ui['close']()
 local_bridge.main(test_mode=True,on_ready=ready)
 if errors:raise AssertionError('\n'.join(errors))
