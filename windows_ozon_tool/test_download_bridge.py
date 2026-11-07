import io,json,tempfile,threading,unittest,urllib.request,urllib.error,zipfile
from pathlib import Path
from PIL import Image
from local_bridge import Store,server
class Tests(unittest.TestCase):
 def test_ticketed_zip_read_is_bound_to_task_and_download_filename(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(Path(tmp)/'data');store.create_set('FILES','generic');task=store.claim();http=server(store,'test-token',0);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
   def post(route,body):
    req=urllib.request.Request(f'http://127.0.0.1:{http.server_port}'+route,data=json.dumps(body).encode(),headers={'Host':'127.0.0.1:0','Origin':'chrome-extension://test','Authorization':'Bearer test-token','Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=5) as response:return json.load(response)
   try:
    grant=post('/download-ticket',{'task_id':task['id'],'extension':'zip'});path=Path(tmp)/'Downloads'/grant['filename'];path.parent.mkdir(parents=True)
    with zipfile.ZipFile(path,'w') as archive:
     for i in range(1,9):
      image=io.BytesIO();Image.new('RGB',(600,800),(i*20,20,80)).save(image,format='PNG');archive.writestr(f'{i:02d}_image.png',image.getvalue())
    result=post('/read-download',{'task_id':task['id'],'ticket':grant['ticket'],'path':str(path)});self.assertEqual(len(result['images']),8)
    self.assertEqual(store.find(task['id'])['received_images'],[])
    with self.assertRaises(urllib.error.HTTPError):post('/read-download',{'task_id':task['id'],'ticket':grant['ticket'],'path':str(path)})
    other=post('/download-ticket',{'task_id':task['id'],'extension':'zip'})
    with self.assertRaises(urllib.error.HTTPError):post('/read-download',{'task_id':task['id'],'ticket':other['ticket'],'path':str(path)})
   finally:http.shutdown();http.server_close();thread.join()
if __name__=='__main__':unittest.main()
