import copy,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,Mock
from competitor_reference import context,claim,receive,proposals,match,eligible
from competitor_flow import describe,group_label,before_copy,accepted_records,copy_prompt,copy_signature
from pricing_service import read,write
import test_competitor_reference as fixtures
class CompetitorFlowTests(unittest.TestCase):
 def test_blank_link_skips_gate_and_clears_old_wait_without_credentials(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,path=self.setup_store(tmp);owner=store.tasks[0]
   owner['variant_parameters']={'competitor_url':fixtures.URL};owner['competitor_wait']={'state':'waiting'}
   bundle=read(path);bundle['variant_parameters']['competitor_url']='  ';write(path,bundle)
   with patch('account_context.credentials',side_effect=ValueError('not connected')):
    self.assertTrue(before_copy(store,owner));self.assertEqual(describe(bundle,owner)['state'],'none')
   self.assertNotIn('competitor_wait',owner);store.attributes.wake.set.assert_not_called()
 def test_missing_bundle_without_link_does_not_wait(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,path=self.setup_store(tmp);path.unlink()
   with patch('account_context.credentials',side_effect=ValueError('not connected')):self.assertTrue(before_copy(store,store.tasks[0]))
 def test_mixed_group_only_waits_for_configured_variant(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,path=self.setup_store(tmp);owner=store.tasks[0]
   store.tasks.append({'sku':'B','state':'saved','copy_leader':'A'})
   blank=fixtures.bundle();blank['sku']='B';blank['variant_parameters']['competitor_url']=''
   write(store.folder/'products'/'B'/'listing_bundle.json',blank)
   self.assertFalse(before_copy(store,owner));self.collect(store)
   self.assertTrue(before_copy(store,owner));self.assertNotIn('competitor_wait',owner)
 def setUp(self):
  p=patch('account_context.credentials',return_value=('synthetic-shop','fake'));p.start();self.addCleanup(p.stop)
 def setup_store(self,tmp):
  store=SimpleNamespace(folder=Path(tmp),tasks=[{'sku':'A','state':'saved','set_mode':True}],save=Mock(),attributes=SimpleNamespace(wake=Mock()))
  path=store.folder/'products'/'A'/'listing_bundle.json';write(path,fixtures.bundle());return store,path
 def collect(self,store,rows=None):
  job=claim(store)['job'];return receive(store,{'token':job['token'],'url':fixtures.URL,'rows':rows if rows is not None else [{'name':'Тип разъема','value':'USB-C'}]})
 def test_status_distinguishes_no_link_schema_wait_reading_reference_prefill_and_adoption(self):
  b=fixtures.bundle();b['variant_parameters']['competitor_url']='';self.assertEqual(describe(b)['state'],'none');b=fixtures.bundle();b['attribute_draft']['fields']=[];self.assertEqual(describe(b)['state'],'schema')
  with tempfile.TemporaryDirectory() as tmp:
   store,path=self.setup_store(tmp);self.assertEqual(describe(read(path))['state'],'queued');job=claim(store)['job'];self.assertEqual(describe(read(path))['state'],'reading');receive(store,{'token':job['token'],'url':fixtures.URL,'rows':[{'name':'Тип разъема','value':'USB-C'}]});b=read(path);r=describe(b);self.assertEqual((r['matched'],r['prefilled'],r['applied']),(1,1,0));self.assertIn('预填1',r['label']);self.assertEqual(b['attribute_draft']['values'],{})
   b['attribute_draft']['values']['0:901']=[{'dictionary_value_id':101,'value':'USB-C'}];values=copy.deepcopy(b['attribute_draft']['values']['0:901']);b['reference_decisions']={'0:901':{'source':b['competitor_reference']['fingerprint']+':'+b['competitor_reference']['result_hash'],'action':'accepted','accepted_values':values}};write(path,b);self.assertEqual(describe(b)['applied'],1);self.assertEqual(describe(b)['prefilled'],0);self.assertIn('已读1/1',group_label([describe(b)]))
 def test_creation_prefetch_is_visible_before_images_create_a_bundle(self):
  task={'variant_parameters':{'competitor_url':fixtures.URL},'category_selection':{'attribute_preload':{'fields':copy.deepcopy(fixtures.FIELDS),'category_key':[10,20],'schema_hash':'synthetic-schema'}}}
  result=describe({},task)
  self.assertEqual(result['state'],'preloaded');self.assertIn('官方字段已读',result['label']);self.assertIn('不会再次等待官方字段接口',result['detail'])
 def test_copy_waits_for_schema_and_capture_but_failed_or_empty_match_finishes(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,path=self.setup_store(tmp);owner=store.tasks[0];self.assertFalse(before_copy(store,owner,now=100));store.attributes.wake.set.assert_called();self.assertNotIn('copy_state',owner);self.collect(store);self.assertTrue(before_copy(store,owner,now=101));self.assertNotIn('competitor_wait',owner)
   b=read(path);b.pop('competitor_reference');write(path,b);self.assertFalse(before_copy(store,owner,now=102));job=claim(store)['job'];receive(store,{'token':job['token'],'error':'需要验证码','error_code':'verification'});self.assertTrue(before_copy(store,owner,now=103));self.assertEqual(describe(read(path))['state'],'verification')
 def test_copy_gate_keeps_waiting_during_transient_retry_then_allows_success(self):
  with tempfile.TemporaryDirectory() as tmp,patch('competitor_reference.time.time',return_value=100):
   store,path=self.setup_store(tmp);owner=store.tasks[0];job=claim(store)['job'];receive(store,{'token':job['token'],'error':'temporary'})
   self.assertFalse(before_copy(store,owner,now=100));self.assertEqual(describe(read(path))['state'],'retrying')
   with patch('competitor_reference.time.time',return_value=106):self.collect(store)
   self.assertTrue(before_copy(store,owner,now=107));self.assertEqual(describe(read(path))['matched'],1)
 def test_pre_copy_timeout_is_bounded_and_url_change_starts_new_wait(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,path=self.setup_store(tmp);owner=store.tasks[0];self.assertFalse(before_copy(store,owner,now=100));self.assertTrue(before_copy(store,owner,now=251));self.assertEqual(owner['competitor_wait']['state'],'timeout');self.assertEqual(describe(read(path),owner)['state'],'timeout');b=read(path);b['variant_parameters']['competitor_url']=fixtures.URL.replace('12345','67890');write(path,b);self.assertFalse(before_copy(store,owner,now=252))
 def test_successful_page_with_zero_official_matches_does_not_fill_arbitrary_fields(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,path=self.setup_store(tmp);self.collect(store,[{'name':'Unofficial invented field','value':'123'}]);b=read(path);self.assertEqual(b['competitor_reference']['state'],'ready');self.assertEqual(describe(b)['matched'],0);self.assertEqual(proposals(b),{});self.assertTrue(before_copy(store,store.tasks[0]))
 def test_pending_values_are_only_verification_questions_not_trusted_copy_claims(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,path=self.setup_store(tmp);self.collect(store);b=read(path);self.assertEqual(accepted_records(b),[]);self.assertEqual(copy_signature([b]),'');text=copy_prompt([b]);self.assertIn('待核验候选，不是商品事实',text);self.assertIn('USB-C',text);self.assertIn('独立证据',text);self.assertNotIn('用户已核对采用',text);self.assertNotIn(fixtures.URL,text)
 def test_adopted_values_are_provided_to_copy_and_edits_or_shop_changes_invalidate_them(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,path=self.setup_store(tmp);self.collect(store);b=read(path);value=[{'dictionary_value_id':101,'value':'USB-C'}];b['attribute_draft']['values']['0:901']=value;b['reference_decisions']={'0:901':{'source':b['competitor_reference']['fingerprint']+':'+b['competitor_reference']['result_hash'],'action':'accepted','accepted_values':copy.deepcopy(value)}}
   self.assertTrue(copy_signature([b]));self.assertIn('用户已核对采用',copy_prompt([b]));self.assertEqual(accepted_records(b)[0]['values'],['USB-C'])
   with patch('account_context.credentials',return_value=('other-shop','fake')):self.assertEqual(accepted_records(b),[])
   b['attribute_draft']['values']['0:901'][0]['value']='USB-A';self.assertEqual(accepted_records(b),[])
 def test_official_collection_fields_and_channel_count_are_supported_as_reference_only(self):
  field={'id':999,'name_ru':'Особенности','name':'特点','type':'String','is_collection':True,'max_value_count':2};result=match([field],[{'name':'Особенности','value':'A B','values':['A','B']}]);self.assertEqual(result['0:999']['value'],'A；B');self.assertTrue(eligible({'id':998,'name_ru':'Количество каналов','type':'Integer'}));self.assertTrue(eligible({'id':997,'name_ru':'Совместимость','type':'String'}));self.assertEqual(match([field],[{'name':'Особенности','value':'A B C','values':['A','B','C']}]),{})
 def test_direct_copy_generation_endpoint_cannot_skip_pending_reference_gate(self):
  import test_image_regeneration as image_fixtures
  from copy_pipeline import prepare
  with tempfile.TemporaryDirectory() as tmp:
   store=image_fixtures.ImageRegenerationTests().setup(tmp);task=store.tasks[0];path=store.folder/'products'/task['sku']/'listing_bundle.json';b=read(path);b['variant_parameters']['competitor_url']=fixtures.URL;b['copy']={};write(path,b);task.pop('resume_mode',None);task.pop('copy_phase',None);task.pop('copy_mode',None);result=prepare(store,{'sku':task['sku']});self.assertTrue(result['waiting_for_competitor']);self.assertNotEqual(task.get('copy_phase'),'generating')
if __name__=='__main__':unittest.main()
