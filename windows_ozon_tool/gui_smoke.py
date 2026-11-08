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
  import publication_service
  original_begin=publication_service.PublicationService.begin;submission_calls=[]
  def unexpected_submission(*args,**kwargs):submission_calls.append(True);raise AssertionError('local preview update attempted platform submission')
  publication_service.PublicationService.begin=unexpected_submission
  def ready(root,ui):
   root.report_callback_exception=lambda a,b,c:errors.append(str(b))
   root.geometry('1100x760+15+15');root.update()
   try:
    assert [ui['notebook'].tab(t,'text') for t in ui['notebook'].tabs()]==['商品制作','任务中心','设置']
    assert len(ui['view'].get_children())==1
    ui['view'].selection_set(ui['view'].get_children()[0]);preview=ui['open_preview']();preview.geometry('1000x700+20+20');preview.update();widgets=preview._ozon_ui
    assert len(widgets['notebook'].tabs())==4
    assert widgets['submit'].cget('text')=='提交上架'
    assert widgets['update_preview'].cget('text')=='更新整组预览'
    assert widgets['update_preview'].winfo_rootx()<widgets['submit'].winfo_rootx()
    button=widgets['submit'];assert button.winfo_rooty()+button.winfo_height()<=preview.winfo_rooty()+preview.winfo_height()
    for key in ('price_max','price_old','price_min','price_cost'):
     assert widgets['tree'].exists('s:'+key),key
    widgets['notebook'].select(1);root.update();text=widgets['copy_widgets']['description_ru'];text.delete('1.0','end');text.insert('1.0','Общее описание: металлическая корзина с картонной вставкой.');text.edit_modified(True)
   except Exception as error:
    errors.append(__import__('traceback').format_exc());ui['close']();return
   def check():
    try:
     assert all(read(p)['copy']['description_ru']=='Общее описание: металлическая корзина с картонной вставкой.' for p in group.paths)
    except Exception as error:errors.append(__import__('traceback').format_exc())
    if errors:preview.destroy();ui['close']();return
    widgets['update_preview'].invoke()
    def updated():
     try:
      assert '未提交至Ozon' in widgets['footer_note'].cget('text')
      assert not submission_calls
      assert widgets['submit'].cget('state')!='disabled'
      assert widgets['update_preview'].winfo_rooty()+widgets['update_preview'].winfo_height()<=preview.winfo_rooty()+preview.winfo_height()
     except Exception as error:errors.append(__import__('traceback').format_exc())
     if errors:preview.destroy();ui['close']();return
     controls=widgets['regeneration'];widgets['notebook'].select(2);calls=[]
     ui['store'].image_jobs.create=lambda sku,kind,selected,addition:(calls.append((sku,kind,selected,addition)) or ['fixture-job'])
     controls['shared_add'].insert('1.0','场景加入人物');controls['shared_start'].invoke()
     def shared_queued():
      try:
       assert calls[-1][1:] == ('shared_details',[],'场景加入人物')
       for var in controls['selected'].values():var.set(True)
       controls['main_add'].insert('1.0','保留原商品腿部造型');controls['main_start'].invoke()
      except Exception as error:errors.append(__import__('traceback').format_exc());preview.destroy();ui['close']();return
      def main_queued():
       try:
        assert calls[-1][1]=='variant_main' and set(calls[-1][2])=={read(p)['sku'] for p in group.paths}
        assert calls[-1][3]=='保留原商品腿部造型'
        assert not submission_calls
        assert controls['shared_add'].get('1.0','end-1c')=='场景加入人物'
       except Exception as error:errors.append(__import__('traceback').format_exc())
       preview.destroy();ui['close']()
      root.after(1000,main_queued)
     root.after(1000,shared_queued)
    root.after(2500,updated)
   root.after(3500,check)
  try:local_bridge.main(test_mode=True,on_ready=ready)
  finally:publication_service.PublicationService.begin=original_begin
  if errors:raise AssertionError(errors)
 print('PASS Tk: three main tabs, grouped tasks, four preview tabs, visible footer, four prices, shared-copy autosave, and separate local-update/submit buttons; local update never submits; media regeneration controls queue shared details and selected main jobs.')

if __name__=='__main__':main()
