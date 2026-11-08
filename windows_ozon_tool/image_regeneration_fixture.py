"""Temporary partial-regeneration browser fixture; no real GPT, shop, COS or FFmpeg calls."""
import json,socket,sys,tempfile,threading
from local_bridge import server
from test_image_regeneration import ImageRegenerationTests
from prefill_rules import basis,VERSION

def main():
 with tempfile.TemporaryDirectory(prefix='ozon-image-regeneration-') as tmp:
  store=ImageRegenerationTests().setup(tmp);store.render_video=lambda sku:None
  for task in store.tasks:task['attribute_attempt']={'version':VERSION,'basis':basis(task['variant_parameters'])}
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  http=server(store,'fixture-token',port);threading.Thread(target=http.serve_forever,daemon=True).start();print(json.dumps({'port':port}),flush=True)
  for command in sys.stdin:
   if command.strip()=='start':
    with store.lock:
     a=store.image_jobs.create('CHAIR(1)','shared_details',[],'新增人物使用场景');b=store.image_jobs.create('CHAIR(1)','variant_main',['CHAIR(1)','CHAIR(3)'],'保留原椅腿造型，醒目大标题')
    print(json.dumps({'jobs':a+b}),flush=True)
   elif command.strip()=='verify':
    from pricing_service import read
    print(json.dumps({'jobs':[{'id':j['id'],'kind':j['kind'],'state':j['state'],'expected':j['expected_images']} for j in store.image_jobs.jobs],'products':[{'sku':t['sku'],'images':len(t['received_images']),'hashes':[r['sha256'] for r in t['received_images']],'copy':read(store.folder/'products'/t['sku']/'listing_bundle.json')['copy']['title_ru']} for t in store.tasks]}),flush=True)
   elif command.strip()=='quit':break
  http.shutdown();http.server_close()
if __name__=='__main__':main()
