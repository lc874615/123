"""Temporary localhost fixture for browser_recollection_group.cjs; never uses shop credentials."""
import json,socket,sys,tempfile,threading
from pathlib import Path
from local_bridge import Store,server
from product_group import configure
from pricing_service import write

def main():
 with tempfile.TemporaryDirectory(prefix='ozon-recollection-fixture-') as tmp:
  store=Store(tmp)
  for i in range(1,8):
   store.create_set('FIXTURE('+str(i)+')','synthetic chair')
   t=store.tasks[-1];t.update(base_article='FIXTURE',variant_index=i,state='needs_attention',variant_parameters={'name':'椅子','material':'金属'},copy_state='done')
  configure(store.tasks,'FIXTURE')
  for t in store.tasks:
   p=Path(tmp)/'products'/t['sku'];p.mkdir(parents=True,exist_ok=True)
   bundle={'sku':t['sku'],'offer_id':t['sku'],'copy':{'sku':t['sku'],'title_ru':'Стул','description_ru':'Стул из металла','tags_ru':['#стул'],'missing_facts':[]},'copy_source':'FIXTURE(1)','variant_parameters':t['variant_parameters'],'category':{'confirmed':True},'price_cny':'200','images':[],'blockers':[]}
   write(p/'recovery_backups'/'old'/'listing_bundle.json',bundle)
   if t['variant_index']!=1:write(p/'listing_bundle.json',bundle);t.update(recollection_requested=True,resume_mode='inspect_only')
  store.render_video=lambda sku:None
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  http=server(store,'fixture-token',port);threading.Thread(target=http.serve_forever,daemon=True).start()
  print(json.dumps({'port':port,'tasks':[{'id':t['id'],'sku':t['sku'],'expected':t['expected_images']} for t in store.tasks]}),flush=True)
  for command in sys.stdin:
   if command.strip()=='backup':
    with store.lock:store.set_paused(True);stamp=store.recollect(store.tasks[0]['id'])
    print(json.dumps({'backed_up':stamp}),flush=True)
   elif command.strip()=='verify':
    from pricing_service import read
    rows=[]
    for t in store.tasks:
     bundle=read(Path(tmp)/'products'/t['sku']/'listing_bundle.json');rows.append({'sku':t['sku'],'state':t['state'],'count':len(t.get('received_images',[])),'digests':[r['sha256'] for r in t.get('received_images',[])],'title':bundle['copy']['title_ru'],'price':bundle['price_cny']})
    print(json.dumps({'rows':rows}),flush=True)
   elif command.strip()=='quit':break
  http.shutdown();http.server_close()
if __name__=='__main__':main()
