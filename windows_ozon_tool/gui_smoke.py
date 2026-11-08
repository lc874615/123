"""Synthetic Tk smoke check. No HTTP server, workers, credentials or store writes.
Run from a machine with Tk and a display: python windows_ozon_tool/gui_smoke.py
"""
import os,tempfile
from pathlib import Path

def main():
 for key in ('OZON_CLIENT_ID','OZON_API_KEY','COS_SECRET_ID','COS_SECRET_KEY'):
  os.environ.pop(key,None)
 import local_bridge
 import test_group_publication as fixtures
 from pricing_service import read,write
 with tempfile.TemporaryDirectory() as tmp:
  group,api,pub=fixtures.GroupTests().setup_group(tmp,True)
  data=group.paths[0].parent.parent.parent;local_bridge.DATA=data;tasks=[];errors=[]
  for n,path in enumerate(group.paths):
   b=read(path);tasks.append({'id':'T'+str(n),'sku':b['sku'],'state':'saved','name':'00_full_set','set_mode':True,'received_images':read(path.parent/'image_manifest.json'),'video':str(path.parent/'video'/'product_8s.mp4'),'copy_state':'done','base_article':'SAMPLE','copy_leader':group.paths[0].parent.name,'variant_index':n+1,'variant_parameters':b['variant_parameters'],'facts':'资料','references':[]})
  write(data/'tasks.json',tasks)
  def ready(root,ui):
   root.report_callback_exception=lambda a,b,c:errors.append(str(b))
   root.geometry('1100x760+15+15');root.update()
   try:
    assert [ui['notebook'].tab(t,'text') for t in ui['notebook'].tabs()]==['商品制作','任务中心','设置']
    assert len(ui['view'].get_children())==1
    ui['view'].selection_set(ui['view'].get_children()[0]);preview=ui['open_preview']();preview.geometry('1000x700+20+20');preview.update();widgets=preview._ozon_ui
    assert len(widgets['notebook'].tabs())==4
    button=widgets['submit'];assert button.winfo_rooty()+button.winfo_height()<=preview.winfo_rooty()+preview.winfo_height()
    for key in ('price_max','price_old','price_min','price_cost'):
     assert widgets['tree'].exists('s:'+key),key
    widgets['notebook'].select(1);root.update();text=widgets['copy_widgets']['description_ru'];text.delete('1.0','end');text.insert('1.0','Общее описание: металлическая корзина с картонной вставкой.');text.edit_modified(True)
   except Exception as error:
    errors.append(str(error));ui['close']();return
   def check():
    try:
     assert all(read(p)['copy']['description_ru']=='Общее описание: металлическая корзина с картонной вставкой.' for p in group.paths)
    except Exception as error:errors.append(str(error))
    preview.destroy();ui['close']()
   root.after(3500,check)
  local_bridge.main(test_mode=True,on_ready=ready)
  if errors:raise AssertionError(errors)
 print('PASS Tk: three main tabs, grouped tasks, four preview tabs, visible footer, four prices and shared-copy autosave for every variant.')

if __name__=='__main__':main()
