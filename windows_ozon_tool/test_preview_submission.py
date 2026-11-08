import copy,io,os,tempfile,threading,time,unittest,urllib.error
from unittest.mock import patch
from pathlib import Path
from assisted_fields import inline_references
from group_service import preview_changes
from listing_preview import attribute_errors,build_item
from pricing_service import read,write
from publication_service import request,Rejected
import test_group_publication as group_fixtures

class PreviewSubmissionTests(unittest.TestCase):
 def test_internal_metadata_is_not_a_visible_change_but_price_is(self):
  b={'sku':'A','price_cny':'10','attribute_draft':{'fields':[],'values':{}},'pricing_fingerprint':'old'};c=copy.deepcopy(b);c['pricing_fingerprint']='new';c['attribute_draft']['source_fingerprint']='new';c['attribute_draft']['fetched_at']=time.time()
  self.assertEqual(preview_changes([b],[c]),[]);c['price_cny']='11';self.assertIn('10 → 11',preview_changes([b],[c])[0])
 def test_live_check_refreshing_fingerprint_without_content_does_not_block_submission(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=group_fixtures.GroupTests().setup_group(tmp);calc=group.pricing.calculate_all
   def refresh():
    calc();b=read(group.paths[0]);b['pricing_fingerprint']='refreshed-internal';write(group.paths[0],b)
   group.pricing.calculate_all=refresh;job=pub.begin(group,group.token());self.assertEqual(job['state'],'importing')
 def test_real_price_change_is_reported_and_never_imported(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=group_fixtures.GroupTests().setup_group(tmp)
   def change():
    b=read(group.paths[0]);b['price_cny']='999';write(group.paths[0],b)
   group.pricing.calculate_all=change
   with self.assertRaisesRegex(ValueError,'售价变化'):pub.begin(group,group.token())
   self.assertFalse(any(p=='/v3/product/import' for p,body in api.calls))
 def test_submit_uses_fresh_attributes_without_reloading_every_variant(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=group_fixtures.GroupTests().setup_group(tmp,True);api.calls=[];stages=[];pub.begin(group,group.token(),on_progress=stages.append)
   self.assertFalse(any(p.endswith('/attribute') for p,body in api.calls));self.assertTrue(any('仓库' in s for s in stages))
 def test_string_task_identifier_is_a_known_receipt(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=group_fixtures.GroupTests().setup_group(tmp);original=pub.caller
   def call(p,b):
    result=original(p,b)
    if p=='/v3/product/import':result['result']['task_id']='501'
    return result
   pub.caller=call;self.assertEqual(pub.begin(group,group.token())['task_id'],501)
 def test_optional_pdf_is_omitted_from_payload_even_if_old_value_exists(self):
  from test_attributes import AttributeTests
  with tempfile.TemporaryDirectory() as tmp:
   path,service=AttributeTests().setup_draft(tmp);state=service.refresh(path);b=read(path);b['attribute_draft']['fields'].append({'id':765,'name_ru':'Документ PDF','type':'string'});b['attribute_draft']['values']['0:765']=[{'value':'https://example.com/old.pdf'}];write(path,b);service.confirm(path,'0',True)
   item,errors=build_item(path.parent,read(path));self.assertEqual(errors,[]);self.assertFalse(any(r['id']==765 for r in item['attributes']))
 def test_required_pdf_remains_explicit_platform_blocker(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=group_fixtures.GroupTests().setup_group(tmp);b=group.load()[0];b['attribute_draft']['fields'].append({'id':765,'name_ru':'Документ PDF','is_required':True})
   self.assertTrue(any('关闭PDF' in x for x in attribute_errors(b)))
 def test_inline_reference_not_submitted_until_confirmed_and_skippable(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=group_fixtures.GroupTests().setup_group(tmp);b=group.load()[0];b['category']['name']='Корзина для хранения';b['attribute_draft']['fields'].extend([{'id':766,'name_ru':'Объем главного отделения, л','type':'Decimal'},{'id':767,'name_ru':'Число секций, шт','type':'Integer'}]);b['variant_parameters'].update(length='44',width='35',height='25');write(group.paths[0],b)
   refs=inline_references(b);self.assertEqual(refs['0:766']['suggested'],'38.5');self.assertEqual(refs['0:767']['suggested'],'1');self.assertNotIn('0:766',b['attribute_draft']['values'])
   group.confirm_references([0],'0:766',group.token());self.assertEqual(group.load()[0]['attribute_draft']['values']['0:766'],[{'value':'38.5'}]);self.assertNotIn('0:766',inline_references(group.load()[0]))
   group.confirm_references([0],'0:767',group.token(),skip=True);self.assertNotIn('0:767',inline_references(group.load()[0]));self.assertNotIn('0:767',group.load()[0]['attribute_draft']['values'])
 def test_400_explains_api_reason_without_exposing_key(self):
  error=urllib.error.HTTPError('https://api-seller.ozon.ru',400,'Bad Request',{},io.BytesIO(b'{"message":"Invalid item secret-test"}'))
  with patch.dict(os.environ,{'OZON_CLIENT_ID':'shop','OZON_API_KEY':'secret-test'}),patch('urllib.request.urlopen',side_effect=error):
   with self.assertRaises(Rejected) as caught:request('/v3/product/import',{'items':[]})
   self.assertIn('Invalid item',str(caught.exception));self.assertNotIn('secret-test',str(caught.exception))

class AutomaticReferenceTests(unittest.TestCase):
 def test_refresh_fills_reference_values_and_manual_override_removes_red_marker(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=group_fixtures.GroupTests().setup_group(tmp);b=group.load()[0];b['category']['name']='Корзина для хранения';b['variant_parameters'].update(length='44',width='35',height='25');write(group.paths[0],b)
   original=api.__call__
   def caller(p,body):
    result=original(p,body)
    if p.endswith('/attribute'):
     fields=[{'id':766,'name':'容积','name_ru':'Объем главного отделения, л','type':'Decimal'},{'id':767,'name':'节数','name_ru':'Число секций, шт','type':'Integer'}]
     if body.get('language')=='RU':
      for f in fields:f['name']=f['name_ru']
     result['result'].extend(fields)
    return result
   group.attributes.caller=caller;state=group.attributes.refresh(group.paths[0]);self.assertEqual(state['values']['0:766'],[{'value':'38.5'}]);self.assertEqual(state['values']['0:767'],[{'value':'1'}]);self.assertIn('0:766',state['auto_reference_keys'])
   group.attributes.save_values(group.paths[0],'0:766',[{'value':'35'}]);state=group.attributes.refresh(group.paths[0]);self.assertEqual(state['values']['0:766'],[{'value':'35'}]);self.assertNotIn('0:766',state['auto_reference_keys'])
 def test_automatic_price_updates_need_no_extra_approval_but_manual_changes_do(self):
  b={'sku':'A','price_cny':'10','attribute_draft':{'fields':[],'values':{}}};c=copy.deepcopy(b);c.update(price_cny='12',auto_pricing={'price_cny':'12'})
  self.assertEqual(preview_changes([b],[c],allow_automatic=True),[]);c['price_cny']='13';self.assertTrue(preview_changes([b],[c],allow_automatic=True))
 def test_visible_snapshot_allows_metadata_refresh_before_button_handler(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=group_fixtures.GroupTests().setup_group(tmp);visible=group.load();token=group.token();b=group.load()[0];b['pricing_fingerprint']='fresh-metadata';write(group.paths[0],b)
   job=pub.begin(group,token,visible_bundles=visible);self.assertEqual(job['state'],'importing')

class AutomaticPriceAdoptionTests(unittest.TestCase):
 def test_estimates_auto_adopt_and_manual_override_is_preserved(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=group_fixtures.GroupTests().setup_group(tmp);b=group.load()[0];self.assertEqual(b['pricing_confirmed_price'],b['price_cny']);self.assertNotIn('售价估算待确认',b.get('blockers',[]))
   group.set_prices([0],['200.00'],group.token());group.pricing.calculate_all();b=group.load()[0];self.assertEqual(b['price_cny'],'200.00');self.assertTrue(b['manual_price'])
   with self.assertRaises(ValueError):group.set_prices([0],['NaN'],group.token())
   group.set_parameters([0],'cost',['40'],group.token());b=group.load()[0];self.assertTrue(b.get('manual_price'));self.assertEqual(b['price_cny'],'200.00');self.assertEqual(b['pricing_confirmed_price'],b['price_cny'])
