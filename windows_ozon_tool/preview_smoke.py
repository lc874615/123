"""Offline 20-variant preview check. Requires Tk display. Optional --screenshots. No live API."""
import os,sys,tempfile,shutil
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent))
for k in ('OZON_CLIENT_ID','OZON_API_KEY','COS_SECRET_ID','COS_SECRET_KEY'):os.environ.pop(k,None)
import tkinter as tk
from tkinter import ttk
from PIL import ImageGrab
from pricing_service import read,write
import test_group_publication,local_bridge
from group_editor import open_editor
from ui_layout import build
with tempfile.TemporaryDirectory() as tmp:
 group,api,pub=test_group_publication.GroupTests().setup_group(tmp,True);data=group.paths[0].parent.parent.parent;source=group.paths[0].parent;folders=[];tasks=[]
 for i in range(1,21):
  sku=f'SAMPLE({i})';folder=data/'products'/sku;shutil.copytree(source,folder);b=read(folder/'listing_bundle.json');b.update(sku=sku,base_article='SAMPLE',copy_source='SAMPLE(1)');b['copy']['sku']=sku;b['variant_parameters']['color']=['灰色','米白色','绿色'][i%3];write(folder/'listing_bundle.json',b);folders.append(folder)
  tasks.append({'id':'T'+str(i),'sku':sku,'state':'saved','name':'00_full_set','set_mode':True,'received_images':read(folder/'image_manifest.json'),'video':str(folder/'video'/'product_8s.mp4'),'copy_state':'done','base_article':'SAMPLE','copy_leader':'SAMPLE(1)','variant_index':i,'variant_parameters':b['variant_parameters'],'facts':'合成测试商品','references':[]})
 write(data/'tasks.json',tasks);store=local_bridge.Store(data);errors=[];root=tk.Tk();build(root);root.withdraw();root.report_callback_exception=lambda a,b,c:errors.append(str(b))
 window=open_editor(root,folders[0],group.attributes,folders,pricing=group.pricing,store=store,publication=pub);ui=window._ozon_ui;window.geometry('950x650+10+10')
 def start_checks():
  if len(ui['regeneration']['selected'])<20:root.after(300,start_checks);return
  ui['notebook'].select(2);root.after(300,media_check)
 def media_check():
  try:
   assert ui['media_choice'].get()=='SAMPLE(1)';regen=ui['regeneration']
   for key in ('shared_start','main_start','shared_add','main_add','choice'):
    widget=regen[key];assert widget.winfo_ismapped(),key
    assert widget.winfo_rooty()+widget.winfo_height()<=ui['notebook'].winfo_rooty()+ui['notebook'].winfo_height(),(key,widget.winfo_rooty(),widget.winfo_height())
   assert not any(w.winfo_class()=='Canvas' for w in ui['notebook'].nametowidget(ui['notebook'].select()).winfo_children())
   def text_widgets(w):return [w] if w.winfo_class()=='Text' else [x for c in w.winfo_children() for x in text_widgets(c)]
   assert len(text_widgets(regen['frame']))==2
   picker=regen['picker']();assert regen['picker']() is picker;picker.destroy()
   window.geometry('1280x850+10+10');root.after(300,shots)
  except Exception:errors.append(__import__('traceback').format_exc());finish()
 def screenshot(name):
  if '--screenshots' in sys.argv:ImageGrab.grab(bbox=(window.winfo_rootx(),window.winfo_rooty(),window.winfo_rootx()+window.winfo_width(),window.winfo_rooty()+window.winfo_height())).save(str(Path.cwd()/('Ozon_preview_'+name+'.png')))
 def shots():
  screenshot('图片视频');ui['notebook'].select(1);root.after(200,copy_shot)
 def copy_shot():
  screenshot('共用文案');ui['notebook'].select(0);window.geometry('950x650+10+10');root.after(200,page_check)
 def page_check():
  try:
   tree=ui['tree'];first=tree.cget('displaycolumns')[0];ui['parameter_next'].invoke();root.update_idletasks();shown=tree.cget('displaycolumns');assert shown[0]!=first
   assert tree.xview()[1]>=.999,tree.xview()
   tree.see('p:quantity');root.update_idletasks();bbox=tree.bbox('p:quantity','#1');assert bbox
   x,y=bbox[0]+bbox[2]//2,bbox[1]+bbox[3]//2
   tree.event_generate('<ButtonPress-1>',x=x,y=y,time=1000);tree.event_generate('<ButtonRelease-1>',x=x,y=y,time=1010);tree.event_generate('<ButtonPress-1>',x=x,y=y,time=1100);tree.event_generate('<ButtonRelease-1>',x=x,y=y,time=1110)
   wanted=int(shown[0][1:]);keys=[k for k in root._ozon_windows if k[0]=='parameter_text'];assert keys and keys[-1][-1]==(wanted,),keys
   root._ozon_windows[keys[-1]].destroy();window.geometry('1280x850+10+10');root.after(250,parameter_shot)
  except Exception:errors.append(__import__('traceback').format_exc());finish()
 def parameter_shot():
  screenshot('参数核对');ui['notebook'].select(3);root.after(200,progress_shot)
 def progress_shot():screenshot('上架进度');finish()
 def finish():window.destroy();root.destroy()
 root.after(600,start_checks);root.after(30000,lambda:(errors.append('UI verification timeout'),finish()));root.mainloop();assert not errors,errors
 print('PASS compact 950x650 media actions visible, only optional requirement inputs, 20-variant picker reuse, paginated parameters edit the correct variant, no horizontal drag, four-page screenshots.')
