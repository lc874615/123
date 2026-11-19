import copy,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from competitor_reference import normalize_url,eligible,context,claim,receive,proposals,match
from pricing_service import read,write
from attribute_service import source_fingerprint
URL='https://www.ozon.ru/product/example-12345/'
FIELDS=[{'id':901,'name':'接口','name_ru':'Тип разъема','type':'String','dictionary_id':3,'is_required':True},{'id':902,'name':'商品长(cm)','name_ru':'Длина, см','type':'Decimal'},{'id':903,'name':'主体材质','name_ru':'Основной материал','type':'String'},{'id':904,'name':'包装长(cm)','name_ru':'Длина упаковки, см','type':'Decimal'},{'id':905,'name':'品牌','name_ru':'Бренд','type':'String'}]
def bundle():return {'sku':'A','status':'draft','category':{'description_category_id':10,'type_id':20,'confirmed':True},'variant_parameters':{'name':'测试','material':'金属','competitor_url':URL},'attribute_draft':{'category_key':[10,20],'schema_hash':'synthetic-schema','fields':copy.deepcopy(FIELDS),'values':{},'manual_keys':[]}}
class CompetitorTests(unittest.TestCase):
 def setUp(self):
  p=patch('account_context.credentials',return_value=('synthetic-shop','synthetic-key'));p.start();self.addCleanup(p.stop)
 def store(self,tmp,count=2):
  store=SimpleNamespace(folder=Path(tmp),tasks=[{'sku':chr(65+n),'state':'done'} for n in range(count)])
  for t in store.tasks:b=bundle();b['sku']=t['sku'];write(store.folder/'products'/t['sku']/'listing_bundle.json',b)
  return store
 def test_urls(self):
  self.assertEqual(normalize_url(URL+'?x=tracking#foo'),URL)
  for v in ['http://www.ozon.ru/product/123/','https://www.ozon.ru.attacker.com/product/123/','https://127.0.0.1/product/123/','https://name@www.ozon.ru/product/123/','https://www.ozon.ru:99/product/123/','https://www.ozon.ru/my/order','https://www.ozon.ru/product/../123/']:
   with self.subTest(v=v),self.assertRaises(ValueError):normalize_url(v)
 def test_local_collector_reads_only_exact_official_labels_without_browser(self):
  import threading
  from competitor_local import LocalCompetitorService,extract
  markup='''<script type="application/ld+json">{"name":"ignored"}</script><script>{"characteristics":[{"name":"Тип разъема","value":"USB-C"},{"name":"Основной материал","value":"Пластик"},{"name":"Длина упаковки, см","value":"99"}]}</script>'''
  rows=extract(markup,FIELDS);self.assertEqual({r['name'] for r in rows},{'Тип разъема','Основной материал','Длина упаковки, см'})
  with tempfile.TemporaryDirectory() as tmp:
   store=self.store(tmp,1);store.lock=threading.RLock();store.save=lambda:None
   with patch('competitor_local._direct_read',return_value=markup):self.assertTrue(LocalCompetitorService(store).run_once())
   saved=read(store.folder/'products'/'A'/'listing_bundle.json');self.assertEqual(saved['competitor_reference']['state'],'ready');self.assertIn('0:901',saved['competitor_reference']['suggestions']);self.assertNotIn('0:904',saved['competitor_reference']['suggestions'])
 def test_local_empty_result_is_terminal_not_a_browser_retry(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=self.store(tmp,1);job=claim(store)['job'];receive(store,{'token':job['token'],'error':'本地公开页未找到字段','error_code':'empty'})
   saved=read(store.folder/'products'/'A'/'listing_bundle.json')['competitor_reference'];self.assertEqual(saved['error_code'],'empty');self.assertFalse(saved['retryable'])
 def test_append_same_first_and_no_prompt_leak(self):
  from variants import FIELDS as vf,same_first,facts
  self.assertEqual(vf[-2][0],'extra');self.assertEqual(vf[-1][0],'competitor_url');rows=[{'values':{'competitor_url':URL}},{'values':{}}];self.assertEqual(same_first(rows,'competitor_url'),1);self.assertEqual(rows[1]['values']['competitor_url'],URL)
  self.assertNotIn('ozon.ru',facts({'name':'测试','competitor_url':URL}));b=bundle();fp=source_fingerprint(b);b['variant_parameters']['competitor_url']='';self.assertEqual(source_fingerprint(b),fp)
 def test_exact_schema_units_conflicts_and_exclusions(self):
  rows=[{'name':'Тип разъема','value':'USB-C'},{'name':'Длина, см','value':'32 см'},{'name':'Длина упаковки, см','value':'999'},{'name':'Бренд','value':'Other'},{'name':'Unknown','value':'invented'}];r=match(FIELDS,rows);self.assertEqual(set(r),{'0:901','0:902'});self.assertEqual(r['0:902']['value'],'32')
  self.assertEqual(match(FIELDS,[{'name':'Длина, см','value':'320 мм'}]),{});self.assertEqual(match(FIELDS,[{'name':'Тип разъема','value':'USB-C'},{'name':'Тип разъема','value':'Lightning'}]),{})
  for name in ['Вес с упаковкой, г','认证','商标品牌','Гарантия','Страна производства','Срок службы','Нужен код маркировки']:self.assertFalse(eligible({'id':999,'name':name,'type':'String'}),name)
 def test_shared_lease_fanout_and_own_value_protection(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=self.store(tmp);job=claim(store)['job'];self.assertIsNone(claim(store)['job']);self.assertEqual(receive(store,{'token':job['token'],'url':URL,'rows':[{'name':'Тип разъема','value':'USB-C'},{'name':'Основной материал','value':'Пластик'}]})['matched'],2)
   for t in store.tasks:
    b=read(store.folder/'products'/t['sku']/'listing_bundle.json');self.assertEqual(b['attribute_draft']['values'],{});self.assertIn('0:901',proposals(b));self.assertNotIn('0:903',proposals(b));b['attribute_draft']['values']['0:901']=[{'value':'Own'}];self.assertNotIn('0:901',proposals(b));b['attribute_draft']['values']={};b['attribute_draft']['manual_keys']=['0:901'];self.assertNotIn('0:901',proposals(b))
   self.assertIsNone(claim(store)['job'])
 def test_new_variant_joins_existing_lease_and_required_suggestion_can_be_ignored(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=self.store(tmp,1);job=claim(store)['job'];b=bundle();b['sku']='B';store.tasks.append({'sku':'B','state':'done'});path=store.folder/'products'/'B'/'listing_bundle.json';write(path,b);self.assertIsNone(claim(store)['job']);self.assertEqual(read(path)['competitor_reference']['token'],job['token']);receive(store,{'token':job['token'],'url':URL,'rows':[{'name':'Тип разъема','value':'USB-C'}]});self.assertEqual(read(path)['competitor_reference']['state'],'ready')
  import test_group_publication as fixture
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixture.GroupTests().setup_group(tmp);b=read(group.paths[0]);b['variant_parameters']['competitor_url']=URL;b['attribute_draft']['fields'].append(FIELDS[0]);b['competitor_reference']={'state':'ready','url':URL,'fingerprint':context(b,'synthetic-shop')['fingerprint'],'result_hash':'abc','suggestions':{'0:901':{'name':'Тип разъема','value':'USB-C'}}};write(group.paths[0],b);group.confirm_references([0],'0:901',group.token(),skip=True);saved=read(group.paths[0]);self.assertNotIn('0:901',proposals(saved));self.assertNotIn('0:901',saved['attribute_draft']['values'])
 def test_transient_errors_retry_bounded_and_old_daily_failure_recovers(self):
  with tempfile.TemporaryDirectory() as tmp,patch('competitor_reference.time.time',return_value=100):
   store=self.store(tmp,1);path=store.folder/'products'/'A'/'listing_bundle.json'
   b=read(path);b['competitor_reference']={'fingerprint':context(b,'synthetic-shop')['fingerprint'],'state':'failed','retry_at':999999};write(path,b)
   for attempt in range(1,4):
    with patch('competitor_reference.time.time',return_value=100+attempt*30):
     job=claim(store)['job'];self.assertIsNotNone(job);receive(store,{'token':job['token'],'error':'temporary no parameters'})
     state=read(path)['competitor_reference'];self.assertEqual(state['attempts'],attempt);self.assertEqual(state['retryable'],attempt<3);self.assertIsNone(claim(store)['job'])
   with patch('competitor_reference.time.time',return_value=9999999):self.assertIsNone(claim(store)['job'])
 def test_manual_restart_scopes_variant_and_invalidates_old_shared_lease(self):
  import threading
  from unittest.mock import Mock
  from competitor_reference import restart
  with tempfile.TemporaryDirectory() as tmp:
   store=self.store(tmp);store.lock=threading.RLock();store.save=Mock();old=claim(store)['job'];other=read(store.folder/'products'/'B'/'listing_bundle.json')
   path=store.folder/'products'/'A'/'listing_bundle.json';b=read(path);b['attribute_draft']['values']['0:901']=[{'value':'Own'}];write(path,b)
   result=restart(store,['A']);self.assertEqual(result['restarted'],['A']);self.assertEqual(read(store.folder/'products'/'B'/'listing_bundle.json'),other)
   self.assertEqual(read(path)['attribute_draft']['values']['0:901'][0]['value'],'Own');fresh=claim(store)['job'];self.assertNotEqual(fresh['token'],old['token']);self.assertNotEqual(fresh['fingerprint'],old['fingerprint'])
   receive(store,{'token':old['token'],'url':URL,'rows':[{'name':'Тип разъема','value':'Old'}]});self.assertEqual(read(path)['competitor_reference']['token'],fresh['token'])
   restart(store,['A','B']);a=read(path);b=read(store.folder/'products'/'B'/'listing_bundle.json');self.assertEqual(a['competitor_refresh_revision'],b['competitor_refresh_revision']);self.assertIsNotNone(claim(store)['job'])
 def test_verification_never_auto_retries_or_fills_values(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=self.store(tmp,1);job=claim(store)['job'];receive(store,{'token':job['token'],'error':'captcha','error_code':'verification'})
   self.assertIsNone(claim(store)['job']);b=read(store.folder/'products'/'A'/'listing_bundle.json');self.assertEqual(b['attribute_draft']['values'],{});self.assertFalse(b['competitor_reference']['retryable'])
 def test_stale_result_after_url_schema_or_shop_change(self):
  for change in ('url','account','schema'):
   with self.subTest(change=change),tempfile.TemporaryDirectory() as tmp:
    store=self.store(tmp,1);job=claim(store)['job'];path=store.folder/'products'/'A'/'listing_bundle.json';b=read(path)
    if change=='url':b['variant_parameters']['competitor_url']=URL.replace('12345','99999')
    if change=='schema':b['attribute_draft']['fields'][0]['dictionary_id']=999
    write(path,b)
    with patch('account_context.credentials',return_value=('other-shop' if change=='account' else 'synthetic-shop','fake')):self.assertTrue(receive(store,{'token':job['token'],'url':URL,'rows':[]})['stale'])
 def test_same_official_schema_reuses_reference_after_category_change(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=self.store(tmp,1);job=claim(store)['job'];path=store.folder/'products'/'A'/'listing_bundle.json';b=read(path)
   b['category']['type_id']=21;b['attribute_draft']['category_key']=[10,21]
   # The category changes, but the freshly returned official fields are exactly
   # the same, so a completed public-reference read stays safe to reuse.
   write(path,b)
   result=receive(store,{'token':job['token'],'url':URL,'rows':[{'name':'Тип разъема','value':'USB-C'}]})
   self.assertFalse(result.get('stale'));self.assertIn('0:901',read(path)['competitor_reference']['suggestions'])
 def test_missing_schema_waits_failure_does_not_block_queue(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=self.store(tmp,1);path=store.folder/'products'/'A'/'listing_bundle.json';b=read(path);b['attribute_draft']['fields']=[];write(path,b);self.assertIsNone(claim(store)['job']);write(path,bundle());job=claim(store)['job'];before=copy.deepcopy(store.tasks);receive(store,{'token':job['token'],'error':'需要验证'});self.assertEqual(store.tasks,before);self.assertEqual(read(path)['competitor_reference']['state'],'failed');self.assertIsNone(claim(store)['job'])
 def test_explicit_accept_resolves_official_dictionary(self):
  import test_group_publication as fixture
  from assisted_fields import inline_references
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixture.GroupTests().setup_group(tmp);b=read(group.paths[0]);b['variant_parameters']['competitor_url']=URL;b['attribute_draft']['fields'].append(FIELDS[0]);b['competitor_reference']={'state':'ready','url':URL,'fingerprint':context(b,'synthetic-shop')['fingerprint'],'result_hash':'abc','suggestions':{'0:901':{'name':'Тип разъема','value':'USB-C'}}};write(group.paths[0],b);self.assertIn('0:901',inline_references(b));self.assertNotIn('0:901',b['attribute_draft']['values']);group.confirm_references([0],'0:901',group.token());saved=read(group.paths[0]);self.assertEqual(saved['attribute_draft']['values']['0:901'][0]['value'],'USB-C');self.assertTrue(saved['attribute_draft']['values']['0:901'][0]['dictionary_value_id']);self.assertIn('0:901',saved['attribute_draft']['manual_keys']);self.assertNotIn('0:901',inline_references(saved))
 def test_refresh_never_auto_adopts_competitor(self):
  from test_attributes import AttributeTests
  with tempfile.TemporaryDirectory() as tmp:
   path,service=AttributeTests().setup_draft(tmp);original=service.caller
   def api(p,body):
    result=original(p,body)
    if p.endswith('/attribute'):result['result'].append(FIELDS[0])
    return result
   service.caller=api;service.refresh(path);b=read(path);b['variant_parameters']['competitor_url']=URL;b['competitor_reference']={'state':'ready','url':URL,'fingerprint':context(b,'synthetic-shop')['fingerprint'],'result_hash':'x','suggestions':{'0:901':{'name':'Тип разъема','value':'USB-C'}}};write(path,b);self.assertIn('0:901',proposals(b));state=service.refresh(path,force=False);self.assertNotIn('0:901',state['values']);self.assertIn('0:901',proposals(read(path)))
if __name__=='__main__':unittest.main()
