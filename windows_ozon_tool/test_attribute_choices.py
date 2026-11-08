import copy,tempfile,unittest
from pathlib import Path
from attribute_service import AttributeService,field_key
from attribute_choices import OfficialChoices
from pricing_service import read,write
import test_group_publication as fixtures
FIELD={'id':999,'name':'官方多选参数','type':'String','dictionary_id':9,'is_collection':True,'max_value_count':3}
def bundle(sku='A',type_id=20,field=None,values=None):
 f=copy.deepcopy(field or FIELD)
 return {'sku':sku,'category':{'description_category_id':10,'type_id':type_id},'attribute_draft':{'category_key':[10,type_id],'fields':[f],'values':{field_key(f):values or []}}}
class ChoiceTests(unittest.TestCase):
 def service(self,tmp):
  calls=[]
  def api(path,body):
   calls.append((path,copy.deepcopy(body)))
   if body.get('value'):return {'result':[{'id':3,'value':'официальный поиск'}],'has_next':False}
   if body.get('last_value_id'):return {'result':[{'id':3,'value':'Три'}],'has_next':False}
   return {'result':[{'id':1 if body['type_id']==20 else 4,'value':'Один'},{'id':2,'value':'Два'}],'has_next':True}
  return AttributeService(tmp,caller=api),calls
 def test_click_multi_search_and_page_preserve_selection(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,calls=self.service(tmp);model=OfficialChoices(service,[bundle()],'0:999');model.load();model.toggle(1);model.toggle(2);model.load(next_page=True);model.toggle(3);self.assertEqual(len(model.values()[0]),3);model.load('关键词');self.assertEqual([r['id'] for r in model.visible],[3]);self.assertEqual(list(model.selected),[1,2,3]);model.toggle(2);self.assertEqual(list(model.selected),[1,3]);self.assertTrue(any(p.endswith('/search') for p,b in calls))
 def test_same_category_bulk_reads_once_and_returns_values_for_each_variant(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,calls=self.service(tmp);model=OfficialChoices(service,[bundle('A'),bundle('B')],'0:999');model.load();model.toggle(1);model.toggle(2);self.assertEqual(len(calls),1);values=model.values();self.assertEqual(len(values),2);self.assertEqual(values[0],values[1]);self.assertEqual([r['dictionary_value_id'] for r in values[0]],[1,2])
 def test_different_categories_only_offer_common_verified_ids(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,calls=self.service(tmp);model=OfficialChoices(service,[bundle('A'),bundle('B',30)],'0:999');model.load();self.assertEqual([r['id'] for r in model.visible],[2]);self.assertEqual(len(calls),2)
   with self.assertRaises(ValueError):model.toggle(1)
   model.toggle(2);self.assertEqual(len(model.values()),2)
 def test_single_select_and_stricter_target_limit_are_respected(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,calls=self.service(tmp);single={**FIELD,'is_collection':False};model=OfficialChoices(service,[bundle(),bundle('B',field=single)],'0:999');self.assertFalse(model.multiple);model.load();model.toggle(1);model.toggle(2);self.assertEqual(list(model.selected),[2])
 def test_collection_maximum_does_not_silently_truncate(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,calls=self.service(tmp);f={**FIELD,'max_value_count':2};model=OfficialChoices(service,[bundle(field=f)],'0:999');model.load();model.load(next_page=True);model.toggle(1);model.toggle(2)
   with self.assertRaises(ValueError):model.toggle(3)
   self.assertEqual(list(model.selected),[1,2])
 def test_bulk_initial_selection_is_common_values_and_can_be_cleared(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,calls=self.service(tmp);v=lambda n:{'dictionary_value_id':n,'value':str(n)};model=OfficialChoices(service,[bundle(values=[v(1),v(2)]),bundle('B',values=[v(2)])],'0:999');self.assertEqual(list(model.selected),[2]);model.load();model.clear();self.assertEqual(model.values(),[[],[]])
 def test_group_bulk_save_verifies_ids_for_each_target_atomically(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp,True)
   for p in group.paths:
    b=read(p);b['attribute_draft']['fields'].append(copy.deepcopy(FIELD));write(p,b)
   original=group.attributes.caller
   def api_choices(path,body):
    if '/attribute/values' in path and body['attribute_id']==999:return {'result':[{'id':901,'value':'Первое'},{'id':902,'value':'Второе'}],'has_next':False}
    return original(path,body)
   group.attributes.caller=api_choices;model=OfficialChoices(group.attributes,group.load(),'0:999');model.load();model.toggle(901);model.toggle(902);group.set_attributes([0,1],'0:999',model.values(),group.token());self.assertTrue(all(len(b['attribute_draft']['values']['0:999'])==2 for b in group.load()))
   before=group.load()
   with self.assertRaises(ValueError):group.set_attributes([0,1],'0:999',[[{'dictionary_value_id':901}],[{'dictionary_value_id':99999}]],group.token())
   self.assertEqual(group.load(),before)
 def test_missing_official_field_in_one_target_is_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,calls=self.service(tmp);other=bundle('B');other['attribute_draft']['fields']=[]
   with self.assertRaises(ValueError):OfficialChoices(service,[bundle(),other],'0:999')
if __name__=='__main__':unittest.main()
