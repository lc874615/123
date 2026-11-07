import hashlib,io,json,tempfile,threading,time,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from hosting_service import HostingService
from cos_host import CosHost,HostingError,authorization
from pricing_service import write,read

class FakeHost:
 def __init__(self,config,credentials):self.config=config;self.uploads=[];self.verified=[];self.fail_number=None;self.on_upload=None
 def upload(self,raw,digest):
  if self.fail_number==len(self.uploads)+1:raise HostingError('网络暂不可用')
  self.uploads.append(digest)
  if self.on_upload:self.on_upload()
  return {'https_url':'https://test-1250000000.cos.ap-hongkong.myqcloud.com/ozon-images/'+digest+'.png','sha256':digest,'size':len(raw),'verified_at':time.time(),'provider':'tencent_cos'}
 def verify(self,url,digest,size):self.verified.append(digest)

class HostingTests(unittest.TestCase):
 def setup_service(self,tmp):
  host=FakeHost({'region':'ap-hongkong','bucket':'test-1250000000'},{});service=HostingService(tmp,threading.Lock(),lambda *args:host)
  service.configure('ap-hongkong','test-1250000000','test-key','test-secret');return service,host
 def seed(self,tmp,article,variant=0):
  folder=Path(tmp)/'products'/article;rows=[];images=[]
  for n in range(1,9):
   image=Image.new('RGB',(600,800),(variant*40+5,10,20) if n==1 else (n*20,40,90))
   raw=io.BytesIO();image.save(raw,format='PNG');path=folder/'images'/f'{n:02d}.png';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw.getvalue())
   row={'order':n,'role':'primary' if n==1 else 'gallery','file':str(path),'sha256':hashlib.sha256(raw.getvalue()).hexdigest()};rows.append(row)
   images.append({'order':n,'role':row['role'],'local_file':'images/'+path.name,'sha256':row['sha256'],'https_url':None})
  write(folder/'image_manifest.json',rows)
  path=folder/'listing_bundle.json';write(path,{'sku':article,'images':images,'price_cny':'123','copy':{'title_ru':'test'},'blockers':['图片HTTPS托管未配置','类目及必填属性待匹配']});return path
 def test_three_variants_share_seven_uploads_with_fixed_primary_and_resume(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,host=self.setup_service(tmp);paths=[self.seed(tmp,'ITEM('+str(i)+')',i) for i in (1,2,3)]
   service.scan_once();self.assertEqual(len(host.uploads),10)
   bundles=[read(p) for p in paths]
   self.assertEqual(len({b['images'][0]['https_url'] for b in bundles}),3)
   for n in range(1,8):self.assertEqual(len({b['images'][n]['https_url'] for b in bundles}),1)
   self.assertTrue(all(b['hosting']['state']=='done' for b in bundles))
   self.assertTrue(all('图片HTTPS托管未配置' not in b['blockers'] for b in bundles))
   self.assertTrue(all('类目及必填属性待匹配' in b['blockers'] for b in bundles))
   service.status='未配置图片托管';service.scan_once();self.assertEqual(len(host.uploads),10);self.assertIn('链接就绪 3',service.status)
 def test_partial_failure_retries_only_unfinished_images(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,host=self.setup_service(tmp);path=self.seed(tmp,'ITEM');host.fail_number=4
   service.scan_once();self.assertEqual(read(path)['hosting']['verified_images'],3)
   host.fail_number=None;service.retry_at.clear();service.scan_once()
   self.assertEqual(len(host.uploads),8);self.assertEqual(read(path)['hosting']['state'],'done')
 def test_concurrent_pricing_and_copy_edits_survive(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,host=self.setup_service(tmp);path=self.seed(tmp,'ITEM')
   def edit():
    data=read(path);data.update(price_cny='999',copy={'title_ru':'new'});write(path,data)
   host.on_upload=edit;service.scan_once()
   self.assertEqual(read(path)['price_cny'],'999');self.assertEqual(read(path)['copy']['title_ru'],'new')
 def test_source_change_during_upload_does_not_attach_old_url(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,host=self.setup_service(tmp);path=self.seed(tmp,'ITEM')
   host.on_upload=lambda:(path.parent/'images'/'01.png').write_bytes(b'changed')
   service.scan_once();self.assertIsNone(read(path)['images'][0]['https_url']);self.assertNotEqual(read(path)['hosting']['state'],'done')
 def test_reference_directory_and_wrong_primary_are_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,host=self.setup_service(tmp);path=self.seed(tmp,'ITEM');data=read(path);data['images'][0]['local_file']='references/01.png';write(path,data)
   service.scan_once();self.assertEqual(host.uploads,[])
 def test_legacy_reference_mixed_into_generated_folder_is_never_uploaded(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,host=self.setup_service(tmp);path=self.seed(tmp,'ITEM')
   reference=path.parent/'references'/'input.png';reference.parent.mkdir();reference.write_bytes((path.parent/'images'/'01.png').read_bytes())
   service.scan_once();self.assertEqual(host.uploads,[]);self.assertIn('参考图',read(path)['hosting']['message'])
 def test_malformed_old_draft_does_not_stop_other_products(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,host=self.setup_service(tmp);bad=Path(tmp)/'products'/'BAD'/'listing_bundle.json';write(bad,None)
   good=self.seed(tmp,'GOOD');service.scan_once()
   self.assertIsNone(read(bad));self.assertEqual(read(good)['hosting']['state'],'done')
 def test_pause_and_no_plaintext_secret(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,host=self.setup_service(tmp);self.seed(tmp,'ITEM');service.set_enabled(False);service.scan_once();self.assertEqual(host.uploads,[])
   self.assertNotIn('test-secret',(Path(tmp)/'hosting'/'config.json').read_text());self.assertFalse((Path(tmp)/'hosting'/'credentials.dpapi').exists())
 def test_missing_price_waits_and_deleted_tasks_are_not_uploaded(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,host=self.setup_service(tmp);path=self.seed(tmp,'ACTIVE');deleted=self.seed(tmp,'DELETED',2)
   service.active_skus=lambda:{'ACTIVE'}
   data=read(path);data['price_cny']=None;write(path,data);service.scan_once()
   self.assertEqual(host.uploads,[]);self.assertEqual(read(path)['hosting']['state'],'waiting')
   data=read(path);data['price_cny']='123';write(path,data);service.retry_at.clear();service.scan_once()
   self.assertEqual(len(host.uploads),8);self.assertIsNone(read(deleted)['images'][0]['https_url'])
 def test_remember_uses_encrypted_file_and_no_plaintext_fallback(self):
  with tempfile.TemporaryDirectory() as tmp:
   service=HostingService(tmp)
   with patch('hosting_credentials.protect',side_effect=ValueError('protect failed')):
    with self.assertRaises(ValueError):service.configure('ap-hongkong','test-1250000000','test-id','test-secret',True)
   self.assertFalse((service.root/'config.json').exists());self.assertFalse((service.root/'credentials.dpapi').exists())
   with patch('hosting_credentials.protect',return_value=b'encrypted-placeholder'):
    service.configure('ap-hongkong','test-1250000000','test-id','test-secret',True)
   self.assertEqual((service.root/'credentials.dpapi').read_bytes(),b'encrypted-placeholder')
   self.assertNotIn('test-secret',(service.root/'config.json').read_text())
   restarted=HostingService(tmp)
   with patch('hosting_credentials.protect',return_value=json.dumps({'secret_id':'test-id','secret_key':'test-secret'}).encode()):
    config,credentials=restarted.settings()
   self.assertTrue(config['enabled']);self.assertEqual(credentials['secret_key'],'test-secret')
 def test_refresh_assets_keeps_links_for_identical_images(self):
  from listing_bundle import refresh_assets
  with tempfile.TemporaryDirectory() as tmp:
   service,host=self.setup_service(tmp);path=self.seed(tmp,'ITEM');service.scan_once();before=read(path)
   refresh_assets(path.parent);self.assertEqual(read(path)['images'],before['images']);self.assertEqual(read(path)['hosting']['state'],'done')
 def test_refresh_assets_invalidates_changed_main_only(self):
  from listing_bundle import refresh_assets
  with tempfile.TemporaryDirectory() as tmp:
   service,host=self.setup_service(tmp);path=self.seed(tmp,'ITEM');service.scan_once()
   raw=io.BytesIO();Image.new('RGB',(600,800),'red').save(raw,format='PNG');(path.parent/'images'/'01.png').write_bytes(raw.getvalue())
   rows=read(path.parent/'image_manifest.json');rows[0]['sha256']=hashlib.sha256(raw.getvalue()).hexdigest();write(path.parent/'image_manifest.json',rows)
   refresh_assets(path.parent);data=read(path);self.assertIsNone(data['images'][0]['https_url']);self.assertTrue(all(r['https_url'] for r in data['images'][1:]));self.assertEqual(data['hosting']['state'],'pending')

class TransportTests(unittest.TestCase):
 def host(self):return CosHost({'region':'ap-hongkong','bucket':'test-1250000000','prefix':'ozon-images'},{'secret_id':'test-id','secret_key':'test-secret'})
 def payload(self):
  raw=io.BytesIO();Image.new('RGB',(600,800),'red').save(raw,format='PNG');return raw.getvalue()
 def test_signature_matches_official_python_sdk_fixture(self):
  # Verified against tencentyun/cos-python-sdk-v5 CosS3Auth using these public test inputs.
  headers={'Host':'test-1250000000.cos.ap-hongkong.myqcloud.com','Content-Type':'image/png','Content-Length':'4','Content-MD5':'jXd/OF09/siBXSD3SWAm3A==','x-cos-storage-class':'STANDARD','x-cos-forbid-overwrite':'true'}
  result=authorization('PUT','/ozon-images/test.png',headers,'test-id','test-key',1700000000)
  self.assertTrue(result.endswith('q-signature=f93a57dd08fbae78fab3f01efdc7a977ff450972'))
 def test_put_signed_then_anonymous_get_and_no_secret_in_link(self):
  raw=self.payload();digest=hashlib.sha256(raw).hexdigest();host=self.host();requests=[]
  class Reply(io.BytesIO):headers={'Content-Type':'image/png'}
  def open_request(request,**kwargs):
   requests.append(request);return Reply(b'' if request.get_method()=='PUT' else raw)
  with patch.object(host.opener,'open',side_effect=open_request):result=host.upload(raw,digest)
  self.assertEqual(result['https_url'],host.base+'/ozon-images/'+digest+'.png')
  self.assertEqual(requests[0].get_method(),'PUT');self.assertIn('q-signature=',requests[0].get_header('Authorization'))
  self.assertNotIn('test-secret',requests[0].get_header('Authorization'));self.assertEqual(requests[0].data,raw)
  self.assertEqual(requests[1].get_method(),'GET');self.assertIsNone(requests[1].get_header('Authorization'));self.assertNotIn('?',result['https_url'])
 def test_anonymous_read_rejects_html_wrong_bytes_and_unsafe_urls(self):
  host=self.host()
  class Reply(io.BytesIO):headers={'Content-Type':'text/html'}
  with patch.object(host.opener,'open',return_value=Reply(b'login')):
   with self.assertRaises(HostingError):host.verify(host.base+'/ozon-images/a.png','x',5)
  class WrongImage(io.BytesIO):headers={'Content-Type':'image/png'}
  with patch.object(host.opener,'open',return_value=WrongImage(b'bad')):
   with self.assertRaises(HostingError):host.verify(host.base+'/ozon-images/a.png','wrong-digest',3)
  for url in ('http://test-1250000000.cos.ap-hongkong.myqcloud.com/ozon-images/a.png','https://elsewhere.invalid/a.png',host.base+'/ozon-images/a.png?token=temporary'):
   with self.assertRaises(HostingError):host.verify(url,'x',1)
 def test_upload_error_does_not_expose_private_response_body(self):
  host=self.host();raw=self.payload();error=urllib.error.HTTPError(host.base,403,'test-secret',{},None)
  with patch.object(host.opener,'open',side_effect=error):
   with self.assertRaises(HostingError) as caught:host.upload(raw,hashlib.sha256(raw).hexdigest())
  self.assertNotIn('test-secret',str(caught.exception))
 def test_existing_object_is_verified_after_conflict(self):
  host=self.host();raw=self.payload();digest=hashlib.sha256(raw).hexdigest();url=host.base+'/ozon-images/'+digest+'.png'
  class Reply(io.BytesIO):headers={'Content-Type':'image/png'}
  with patch.object(host.opener,'open',side_effect=[urllib.error.HTTPError(url,409,'exists',{},None),Reply(raw)]):
   self.assertEqual(host.upload(raw,digest)['https_url'],url)

if __name__=='__main__':unittest.main()
