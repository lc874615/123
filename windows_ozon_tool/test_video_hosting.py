import hashlib,io,struct,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import test_hosting as fixtures
from pricing_service import read,write
from video_hosting import VideoHostingService
from video_inspect import inspect_mp4
from listing_bundle import refresh_assets

def box(kind,payload):return struct.pack('>I4s',len(payload)+8,kind)+payload
def mp4(duration=8000,extra=b''):
 return box(b'ftyp',b'isom'+b'\0'*4+b'isomavc1')+box(b'moov',box(b'mvhd',b'\0'*12+struct.pack('>II',1000,duration)+b'\0'*12)+box(b'trak',b'avc1'+extra))+box(b'mdat',b'data'+extra)
class MediaHost(fixtures.FakeHost):
 def __init__(self,*a):super().__init__(*a);self.video_uploads=[]
 def upload_video(self,raw,digest):
  inspect_mp4(raw);self.video_uploads.append(digest)
  return {'https_url':'https://test-1250000000.cos.ap-hongkong.myqcloud.com/ozon-images/videos/'+digest+'.mp4','sha256':digest,'size':len(raw),'verified_at':time.time()}
 def verify_video(self,*a):pass
class VideoTests(unittest.TestCase):
 def setup_media(self,tmp):
  helper=fixtures.HostingTests();source,_=helper.setup_service(tmp);path=helper.seed(tmp,'ITEM');source.scan_once()
  host=MediaHost({},{});source.host_factory=lambda *a:host;video=path.parent/'video'/'product_8s.mp4';video.parent.mkdir();video.write_bytes(mp4())
  return source,path,host,video
 def test_existing_eight_second_mp4_uploads_without_rebuilding_or_image_reupload(self):
  with tempfile.TemporaryDirectory() as tmp:
   source,path,host,video=self.setup_media(tmp);before=video.read_bytes();service=VideoHostingService(source);service.scan_once()
   data=read(path);self.assertEqual(data['video_hosting']['state'],'done');self.assertEqual(data['video']['duration_seconds'],8);self.assertEqual(video.read_bytes(),before);self.assertEqual(len(host.video_uploads),1)
   service.scan_once();self.assertEqual(len(host.video_uploads),1)
   self.assertEqual(data['video']['image_hashes'],[r['sha256'] for r in data['images']])
 def test_refresh_same_images_and_video_preserves_video_link(self):
  with tempfile.TemporaryDirectory() as tmp:
   source,path,host,video=self.setup_media(tmp);VideoHostingService(source).scan_once();before=read(path)['video'];refresh_assets(path.parent);self.assertEqual(read(path)['video'],before)
 def test_cos_video_put_and_anonymous_get_use_existing_prefix_and_original_bytes(self):
  host=fixtures.TransportTests().host();raw=mp4();digest=hashlib.sha256(raw).hexdigest();requests=[]
  class Reply(io.BytesIO):headers={'Content-Type':'video/mp4'}
  def respond(request,**kwargs):requests.append(request);return Reply(b'' if request.get_method()=='PUT' else raw)
  with patch.object(host.opener,'open',side_effect=respond):value=host.upload_video(raw,digest)
  self.assertIn('/ozon-images/videos/',value['https_url']);self.assertEqual(requests[0].data,raw);self.assertIsNone(requests[1].get_header('Authorization'))
 def test_wrong_duration_or_non_mp4_is_rejected(self):
  for raw in (b'<html>not video',mp4(7000),mp4(9000)):
   with self.assertRaises(ValueError):inspect_mp4(raw)
 def test_missing_video_waits_without_damaging_image_links(self):
  with tempfile.TemporaryDirectory() as tmp:
   source,path,host,video=self.setup_media(tmp);video.unlink();VideoHostingService(source).scan_once();data=read(path)
   self.assertEqual(data['video_hosting']['state'],'waiting');self.assertEqual(data['hosting']['state'],'done');self.assertEqual(host.video_uploads,[])

if __name__=='__main__':unittest.main()
