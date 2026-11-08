"""Actual Tk create-button check with synthetic files and no network workers."""
import os,tempfile
from pathlib import Path
from unittest.mock import patch

def main():
 for key in ('OZON_CLIENT_ID','OZON_API_KEY','COS_SECRET_ID','COS_SECRET_KEY'):os.environ.pop(key,None)
 import local_bridge,variants
 from PIL import Image
 original=variants.VariantGrid
 for paused in (False,True):
  with tempfile.TemporaryDirectory() as tmp:
   data=Path(tmp)/'data';ref=Path(tmp)/'reference.png';Image.new('RGB',(120,160),'navy').save(ref);local_bridge.DATA=data;captured=[];errors=[]
   class Grid(original):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);captured.append(self)
   def widgets(parent):
    for w in parent.winfo_children():yield w;yield from widgets(w)
   def ready(root,ui):
    try:
     store=ui['store']
     if paused:store.set_paused(True)
     grid=captured[0];grid.base.set('FIRST');grid.add()
     for row in grid.rows:row['values'].update(name='椅子',color='灰色')
     buttons={str(w.cget('text')):w for w in widgets(root) if w.winfo_class()=='TButton'}
     serial=store.control['serial'];buttons['创建并自动处理'].invoke();assert not store.tasks;assert store.control['serial']==serial and store.control['paused']==paused
     for row in grid.rows:row['refs']=[str(ref)]
     buttons['选择共用详情图参考（全组一次）'].invoke();buttons['创建并自动处理'].invoke()
     assert len(store.tasks)==2;assert not store.control['paused'];assert store.control['serial']==serial+1
     first,second=store.tasks;assert first['sku']=='FIRST(1)' and first['expected_images']==8 and first['detail_references'];assert second['expected_images']==1 and second['gallery_source']==first['sku'];assert all(t['state']=='queued' and t['references'] and t['group_variants'] for t in store.tasks)
    except Exception:
     import traceback
     errors.append(traceback.format_exc())
    finally:ui['close']()
   with patch.object(variants,'VariantGrid',Grid),patch('tkinter.filedialog.askopenfilenames',return_value=(str(ref),)),patch('tkinter.messagebox.showerror'):
    local_bridge.main(test_mode=True,on_ready=lambda root,ui:root.after(0,lambda:ready(root,ui)))
   if errors:raise AssertionError(errors)
 print('PASS first creation: invalid group does not start; complete two-variant group starts from fresh or paused state only after shared references/configuration are saved; no network writes.')
if __name__=='__main__':main()
