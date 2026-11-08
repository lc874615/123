import datetime as dt,io,ssl,tempfile,threading,unittest,urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import secure_http
from pricing_service import PricingService,write,read,FX_URLS
from publication_service import PublicationService,warehouse_label
import test_group_publication as fixtures

class Response(io.BytesIO):
 def __init__(self,raw,url='https://www.cbr.ru/scripts/XML_daily.asp'):super().__init__(raw);self.url=url
 def geturl(self):return self.url

class WarehouseTests(unittest.TestCase):
 def test_unique_blocked_ogl_is_listed_and_applied_to_every_variant(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp,True)
   pub.caller=lambda p,b:{'warehouses':[{'warehouse_id':77,'name':'Synthetic warehouse','warehouse_type':'ogl','status':'blocked','is_rfbs':False}],'has_next':False}
   rows=pub.warehouses();self.assertEqual(len(rows),1);self.assertIn('blocked',warehouse_label(rows[0]));self.assertIn('blocked',pub.warehouse_summary())
   for path in group.paths:
    b=read(path);b.pop('fulfillment',None);write(path,b)
   self.assertTrue(group.use_only_warehouse(rows,'test-shop',group.token()));self.assertTrue(all(b['fulfillment']['warehouse_id']==77 for b in group.load()))
 def test_all_types_statuses_and_pages_are_retained(self):
  with tempfile.TemporaryDirectory() as tmp:
   calls=[]
   def call(path,body):
    calls.append(body)
    return {'warehouses':[{'warehouse_id':'1','status':'blocked','warehouse_type':'ogl','is_karantin':True},{'warehouse_id':2,'status':'disabled','warehouse_type':'fbs'}],'has_next':True,'cursor':'next'} if not body.get('cursor') else {'result':{'warehouses':[{'warehouse_id':3,'status':'created','warehouse_type':'fbo'},{'warehouse_id':'1','status':'blocked','warehouse_type':'ogl'}],'has_next':False}}
   pub=PublicationService(tmp,threading.Lock(),call,lambda:'shop');self.assertEqual([r['warehouse_id'] for r in pub.warehouses()],[1,2,3]);self.assertEqual(calls[1]['cursor'],'next');self.assertEqual(pub.warehouse_diagnostic['listed_count'],3)
 def test_platform_stock_rejection_is_reported_for_listed_blocked_warehouse(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);original=pub.caller
   def call(path,body):
    if path=='/v2/warehouse/list':return {'warehouses':[{'warehouse_id':77,'name':'Synthetic OGL','status':'blocked','warehouse_type':'ogl'}],'has_next':False}
    if path=='/v2/products/stocks':return {'result':[{'offer_id':r['offer_id'],'warehouse_id':77,'updated':False,'errors':[{'code':'WAREHOUSE_BLOCKED','message':'platform declined warehouse'}]} for r in body['stocks']]}
    return original(path,body)
   pub.caller=call;job=pub.begin(group,group.token());result=pub.step(job['id']);item=next(iter(result['items'].values()))
   self.assertEqual(item['stock_state'],'rejected');self.assertEqual(item['errors'][0]['code'],'WAREHOUSE_BLOCKED');self.assertFalse(item.get('on_sale'));self.assertNotEqual(result['state'],'on_sale')
   refreshed=pub.step(job['id']);self.assertEqual(next(iter(refreshed['items'].values()))['stock_errors'][0]['code'],'WAREHOUSE_BLOCKED')

class SecureHttpTests(unittest.TestCase):
 def contexts(self):return [ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT),ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)]
 def test_chain_failure_retries_with_verified_native_context(self):
  contexts=self.contexts();error=urllib.error.URLError(ssl.SSLCertVerificationError(1,'unable to get local issuer certificate'))
  with patch.object(secure_http,'contexts',return_value=contexts),patch.object(secure_http.urllib.request,'urlopen',side_effect=[error,Response(b'validated')]) as opened:
   self.assertEqual(secure_http.read('https://www.cbr.ru/scripts/XML_daily.asp',100),b'validated');self.assertEqual(opened.call_count,2)
   self.assertIs(opened.call_args.kwargs['context'],contexts[1]);self.assertTrue(all(c.check_hostname and c.verify_mode==ssl.CERT_REQUIRED for c in contexts))
 def test_verification_failure_never_returns_unverified_data(self):
  with patch.object(secure_http,'contexts',return_value=self.contexts()),patch.object(secure_http.urllib.request,'urlopen',side_effect=urllib.error.URLError(ssl.SSLCertVerificationError(1,'bad chain'))) as opened:
   with self.assertRaisesRegex(ValueError,'证书链校验失败'):secure_http.read('https://www.cbr.ru/scripts/XML_daily.asp',100)
   self.assertEqual(opened.call_count,2)
 def test_plain_http_and_http_redirect_are_rejected(self):
  with patch.object(secure_http.urllib.request,'urlopen') as opened:
   with self.assertRaisesRegex(ValueError,'HTTPS'):secure_http.read('http://www.cbr.ru/scripts/XML_daily.asp',100)
   opened.assert_not_called()
  with patch.object(secure_http,'contexts',return_value=self.contexts()),patch.object(secure_http.urllib.request,'urlopen',return_value=Response(b'bad','http://www.cbr.ru/')):
   with self.assertRaisesRegex(ValueError,'非HTTPS'):secure_http.read('https://www.cbr.ru/scripts/XML_daily.asp',100)
 def test_noncertificate_error_is_not_hidden_by_tls_retry(self):
  with patch.object(secure_http,'contexts',return_value=self.contexts()),patch.object(secure_http.urllib.request,'urlopen',side_effect=urllib.error.URLError('connection refused')) as opened:
   with self.assertRaises(urllib.error.URLError):secure_http.read('https://www.cbr.ru/',100)
   self.assertEqual(opened.call_count,1)
 def test_response_size_limit_remains_enforced(self):
  with patch.object(secure_http,'contexts',return_value=self.contexts()),patch.object(secure_http.urllib.request,'urlopen',return_value=Response(b'1234')):
   with self.assertRaisesRegex(ValueError,'大小限制'):secure_http.read('https://www.cbr.ru/',3)
 def test_windows_uses_system_mozilla_and_native_trust_without_disabling_checks(self):
  system=SimpleNamespace(load_verify_locations=lambda **kwargs:calls.append(kwargs),check_hostname=True,verify_mode=ssl.CERT_REQUIRED);native=SimpleNamespace();calls=[]
  with patch.object(secure_http.sys,'platform','win32'),patch.object(secure_http.ssl,'create_default_context',return_value=system),patch.dict('sys.modules',{'certifi':SimpleNamespace(where=lambda:'test-ca.pem'),'truststore':SimpleNamespace(SSLContext=lambda protocol:native)}):
   result=secure_http.contexts();self.assertEqual(result,[system,native]);self.assertEqual(calls,[{'cafile':'test-ca.pem'}]);self.assertTrue(native.check_hostname);self.assertEqual(native.verify_mode,ssl.CERT_REQUIRED)

class FxRecoveryTests(unittest.TestCase):
 def raw(self):
  date=dt.datetime.now(dt.timezone.utc).strftime('%d.%m.%Y');return ('<ValCurs Date="'+date+'"><Valute><CharCode>CNY</CharCode><Nominal>10</Nominal><Value>120,0000</Value></Valute></ValCurs>').encode()
 def test_alternate_official_url_is_recorded_with_nominal_and_date(self):
  with tempfile.TemporaryDirectory() as tmp,patch('pricing_service.fetch',side_effect=[ValueError('certificate chain'),self.raw()]) as fetch:
   service=PricingService(tmp);value=service.update_fx();self.assertEqual(value['rub_per_cny'],'12.0000');self.assertEqual(value['url'],FX_URLS[1]);self.assertEqual(read(service.root/'fx.json'),value);self.assertEqual(fetch.call_count,2)
 def test_all_failed_attempts_preserve_existing_fx(self):
  with tempfile.TemporaryDirectory() as tmp,patch('pricing_service.fetch',side_effect=ValueError('HTTPS证书链校验失败')):
   service=PricingService(tmp);old={'rub_per_cny':'12','date':'2026-11-07'};write(service.root/'fx.json',old)
   with self.assertRaisesRegex(ValueError,'已有汇率未覆盖'):service.update_fx()
   self.assertEqual(read(service.root/'fx.json'),old)
