"""Offline settings geometry check with temporary data; never invokes a real API."""
import os,tempfile
from pathlib import Path
for k in ('OZON_CLIENT_ID','OZON_API_KEY','COS_SECRET_ID','COS_SECRET_KEY'):os.environ.pop(k,None)
import local_bridge
with tempfile.TemporaryDirectory() as tmp:
 local_bridge.DATA=Path(tmp);errors=[]
 def descendants(w):
  for c in w.winfo_children():yield c;yield from descendants(c)
 def ready(root,ui):root.after(300,lambda:check(root,ui))
 def check(root,ui):
  try:
   button=next(w for w in descendants(root) if w.winfo_class()=='TButton' and w.cget('text')=='自动定价设置 / 运费表 / 央行汇率');button.invoke();root.update()
   window=next(w for w in root.winfo_children() if w.winfo_class()=='Toplevel');button.invoke();root.update();assert len([w for w in root.winfo_children() if w.winfo_class()=='Toplevel'])==1
   buttons=[w for w in descendants(window) if w.winfo_class()=='TButton'];assert len(buttons)==6
   for b in buttons:
    assert b.winfo_ismapped();assert b.winfo_rooty()+b.winfo_height()<=window.winfo_rooty()+window.winfo_height()
   assert any('下载最新版佣金表' in b.cget('text') for b in buttons)
   print('PASS: six pricing controls visible, shop sync and corrected export available, reused settings window')
  except Exception:errors.append(__import__('traceback').format_exc())
  ui['close']()
 local_bridge.main(test_mode=True,on_ready=ready)
 if errors:raise AssertionError('\n'.join(errors))
