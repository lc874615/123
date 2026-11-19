"""Synthetic Tk reference acceptance; no live API or store credentials."""
import os,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
for k in ('OZON_CLIENT_ID','OZON_API_KEY','COS_SECRET_ID','COS_SECRET_KEY'):os.environ.pop(k,None)
os.environ['OZON_CLIENT_ID']='synthetic-shop'
from unittest.mock import patch
import tkinter as tk
from pricing_service import read,write
from competitor_reference import context
from test_competitor_reference import FIELDS,URL
from test_group_publication import GroupTests
from group_editor import open_editor
from ui_layout import build
from local_bridge import Store
with tempfile.TemporaryDirectory() as tmp,patch('account_context.credentials',return_value=('synthetic-shop','fake-key')):
 group,api,pub=GroupTests().setup_group(tmp);path=group.paths[0];b=read(path);b['variant_parameters']['competitor_url']=URL;b['attribute_draft']['fields'].append(FIELDS[0]);b['competitor_reference']={'state':'ready','url':URL,'message':'模拟竞品参考已读取','fingerprint':context(b,'synthetic-shop')['fingerprint'],'result_hash':'x','suggestions':{'0:901':{'name':'Тип разъема','value':'USB-C'}}};write(path,b)
 store=Store(path.parent.parent.parent)
 root=tk.Tk();build(root);root.withdraw();errors=[];root.report_callback_exception=lambda a,b,c:errors.append(str(b));w=open_editor(root,path.parent,group.attributes,[p.parent for p in group.paths],pricing=group.pricing,store=store,publication=pub);ui=w._ozon_ui
 def widgets(parent):
  for child in parent.winfo_children():yield child;yield from widgets(child)
 def check():
  try:
   tree=ui['tree'];assert tree.exists('a:0:901');assert '竞品待核对' in str(tree.item('a:0:901','values'));tree.selection_set('a:0:901');button=next(x for x in widgets(w) if x.winfo_class()=='TButton' and x.cget('text')=='采用当前行参考');button.invoke();root.after(700,verify)
  except Exception:errors.append(__import__('traceback').format_exc());finish()
 def verify():
  try:
   assert read(path)['attribute_draft']['values']['0:901'][0]['value']=='USB-C'
   button=next(x for x in widgets(w) if x.winfo_class()=='TButton' and x.cget('text')=='重新读取竞品');button.invoke();root.after(700,verify_retry)
  except Exception:errors.append(__import__('traceback').format_exc());finish()
 def verify_retry():
  try:
   saved=read(path);assert 'competitor_reference' not in saved;assert saved['attribute_draft']['values']['0:901'][0]['value']=='USB-C';assert store.competitor_revision>0
   print('PASS: live Tk reference adoption, direct retry clears snapshot and wakes plugin while preserving adopted official values')
  except Exception:errors.append(__import__('traceback').format_exc())
  finish()
 def finish():w.destroy();root.destroy()
 root.after(1000,check);root.after(12000,lambda:(errors.append('timeout'),finish()));root.mainloop();assert not errors,errors
