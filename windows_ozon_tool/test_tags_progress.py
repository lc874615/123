import copy,tempfile,unittest
from pathlib import Path
from tag_rules import normalize_tags
from attribute_service import AttributeService,suggested_value
from pricing_service import read,write
import test_attributes as attr_fixtures
import test_group_publication as group_fixtures
from publication_service import PublicationService

class TagsProgressTests(unittest.TestCase):
 def test_real_series_id_is_not_hashtags(self):
  b={'copy':{'title_ru':'Title','tags_ru':['#дом','хранение вещей']}}
  self.assertEqual(suggested_value({'id':22390,'name_ru':'Объединить в похожие товары'},b),'1')
  self.assertEqual(suggested_value({'id':23171,'name_ru':'#Хештеги'},b),'#дом #хранение_вещей')
  self.assertEqual(suggested_value({'id':4180,'name_ru':'Название'},b),'Title')
 def test_hashtags_only_valid_characters_prefix_lengths_and_count(self):
  tags=normalize_tags(['хранение вещей','#дом, #Дом; #красный-цвет 😀','x'*90]+['item'+str(i) for i in range(40)])
  self.assertEqual(tags[:3],['#хранение_вещей','#дом','#красный_цвет']);self.assertEqual(len(tags),30)
  self.assertTrue(all(t.startswith('#') and len(t)<=30 and all(c.isalpha() or c.isdecimal() or c=='_' for c in t[1:]) for t in tags))
 def test_existing_bad_mappings_are_repaired_without_regenerating_copy(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,service=attr_fixtures.AttributeTests().setup_draft(tmp);original=service.caller
   def caller(endpoint,body):
    result=original(endpoint,body)
    if endpoint.endswith('/attribute'):result['result'].append({'id':22390,'name':'Объединить в похожие товары','type':'string'})
    return result
   service.caller=caller;service.refresh(path);b=read(path);b['copy']['tags_ru']=['хранение вещей','#дом!'];b['attribute_draft']['autofill_version']=4;b['attribute_draft']['values']['0:22390']=[{'value':'old'*200}];b['attribute_draft']['manual_keys'].append('0:22390');write(path,b)
   state=service.refresh(path);b=read(path);self.assertEqual(state['values']['0:22390'],[{'value':'1'}]);self.assertEqual(state['values']['0:23171'],[{'value':'#хранение_вещей'},{'value':'#дом'}]);self.assertEqual(b['copy']['tags_ru'],['#хранение_вещей','#дом'])
 def test_pending_import_card_errors_are_not_displayed_as_endless_creation(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=group_fixtures.GroupTests().setup_group(tmp);api.import_pending=True;original=pub.caller
   def caller(p,b):
    result=original(p,b)
    if p=='/v3/product/info/list':
     for row in result['items']:row['errors']=[{'level':'ERROR_LEVEL_ERROR','attribute_id':22390,'texts':{'message':'Series too long'}}]
    return result
   pub.caller=caller;job=pub.begin(group,group.token());result=pub.step(job['id']);self.assertEqual(result['state'],'validation_failed');self.assertIsNone(pub.active([group.load()[0]['sku']]));item=next(iter(result['items'].values()));self.assertTrue(item['card_exists']);self.assertTrue(item['validation_blocked']);self.assertEqual(item['errors'][0]['attribute_id'],22390)
   self.assertFalse(any(p=='/v2/products/stocks' for p,b in api.calls))
 def test_warning_alone_does_not_fail_product(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=group_fixtures.GroupTests().setup_group(tmp);original=pub.caller
   def caller(p,b):
    result=original(p,b)
    if p=='/v3/product/info/list':
     for row in result['items']:row['errors']=[{'level':'ERROR_LEVEL_WARNING','code':'minor'}]
    return result
   pub.caller=caller;job=pub.begin(group,group.token());pub.step(job['id']);self.assertEqual(pub.step(job['id'])['state'],'on_sale')
 def test_skipped_import_with_product_id_is_followed(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=group_fixtures.GroupTests().setup_group(tmp);original=pub.caller
   def caller(p,b):
    result=original(p,b)
    if p=='/v1/product/import/info':
     for row in result['result']['items']:row['status']='skipped'
    return result
   pub.caller=caller;job=pub.begin(group,group.token());pub.step(job['id']);self.assertEqual(pub.step(job['id'])['state'],'on_sale')
 def test_clear_local_progress_preserves_assets_and_does_not_delete_platform(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=group_fixtures.GroupTests().setup_group(tmp);job=pub.begin(group,group.token());api.calls=[];offer=group.load()[0]['sku'];self.assertEqual(pub.clear_group([offer]),1)
   self.assertEqual(pub.jobs(),[]);self.assertIsNone(pub.active([offer]));self.assertTrue((pub.root/'cleared'/(job['id']+'.json')).is_file());self.assertTrue(group.paths[0].is_file());self.assertEqual(api.calls,[])
   restarted=PublicationService(pub.data,pub.lock,api,lambda:'test-shop');self.assertEqual(restarted.jobs(),[])
 def test_clear_only_the_selected_group(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=group_fixtures.GroupTests().setup_group(tmp);job=pub.begin(group,group.token());other=copy.deepcopy(job);other['id']='other';other['items']={'DIFFERENT':{}};write(pub.root/'other.json',other)
   pub.clear_group([group.load()[0]['sku']]);self.assertEqual([j['id'] for j in pub.jobs()],['other'])
