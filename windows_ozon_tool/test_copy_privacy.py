import copy,tempfile,unittest
from copy_privacy import clean
from listing_bundle import copy_prompt_for
import test_group_publication as fixtures
class CopyPrivacyTests(unittest.TestCase):
 def value(self):return {'sku':'1688-1010(1)','title_ru':'Стул 1688-1010(1)','description_ru':'Артикул: 1688-1010(2) — красный стул.\nРазмер: 40×40×76 см.','tags_ru':['#стул','#1688_1010_1','#стул_1688_1010_2'],'missing_facts':[]}
 def context(self):return {'sku':'1688-1010(1)','base_article':'1688-1010','group_variants':[{'sku':'1688-1010(1)'},{'sku':'1688-1010(2)'}]}
 def test_public_text_and_embedded_tags_are_cleaned_but_metadata_stays(self):
  original=self.value();result=clean(original,self.context());self.assertEqual(result['sku'],original['sku']);self.assertEqual(result['title_ru'],'Стул');self.assertNotIn('1688',result['description_ru']);self.assertNotIn('Артикул',result['description_ru']);self.assertIn('40×40×76',result['description_ru']);self.assertEqual(result['tags_ru'],['#стул']);self.assertEqual(original,self.value())
 def test_model_and_dimensions_are_not_removed_as_substrings(self):
  result=clean({'title_ru':'Стул X1688-1010Z, модель 40','description_ru':'40 см, комплект 2 шт.','tags_ru':[]},{'sku':'40(1)','base_article':'40','group_variants':[]});self.assertIn('модель 40',result['title_ru']);self.assertIn('40 см',result['description_ru']);self.assertIn('X1688-1010Z',result['title_ru'])
 def test_labelled_plain_identifier_is_removed_without_deleting_ordinary_words(self):
  result=clean({'title_ru':'Generic ITEM chair','description_ru':'SKU: ITEM\nA chair.','tags_ru':[]},{'sku':'ITEM'});self.assertEqual(result['title_ru'],'Generic ITEM chair');self.assertEqual(result['description_ru'],'A chair.')
 def test_prompt_uses_option_labels_and_forbids_public_sku(self):
  task={'group_variants':[{'sku':'1688-1010(1)','facts':'灰色椅子'},{'sku':'1688-1010(2)','facts':'红色椅子'}]};prompt=copy_prompt_for(task);self.assertIn('选项1',prompt);self.assertIn('选项2',prompt);self.assertNotIn('1688-1010',prompt);self.assertIn('禁止出现内部货号',prompt)
 def test_existing_group_copy_save_cleans_identifiers_for_every_variant(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp,True);value=copy.deepcopy(group.load()[0]['copy']);value.update(title_ru='Стул, SKU: '+group.load()[0]['sku'],description_ru='Стул. Артикул: '+group.load()[1]['sku']);group.set_copy(value,group.token())
   for b in group.load():self.assertNotIn('SKU:',b['copy']['title_ru']);self.assertNotIn('Артикул:',b['copy']['description_ru']);self.assertEqual(b['copy']['sku'],b['sku'])
 def test_generated_copy_save_removes_customer_identifiers_and_keeps_binding(self):
  from listing_bundle import save_copy
  from pricing_service import read
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);b=group.load()[0];value=copy.deepcopy(b['copy']);value.update(sku=b['sku'],title_ru='Стул SKU: '+b['sku'],description_ru='Стул. Артикул: '+b['sku']);save_copy(group.paths[0].parent,value,replace=True);saved=read(group.paths[0])['copy'];self.assertEqual(saved['sku'],b['sku']);self.assertNotIn('SKU:',saved['title_ru']);self.assertNotIn('Артикул:',saved['description_ru'])
 def test_identifier_only_title_is_rejected_without_overwriting_saved_copy(self):
  from listing_bundle import save_copy
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp);before=group.load()[0];value=copy.deepcopy(before['copy']);value.update(sku=before['sku'],title_ru='SKU: '+before['sku'])
   with self.assertRaises(ValueError):save_copy(group.paths[0].parent,value,replace=True)
   self.assertEqual(group.load()[0],before)
if __name__=='__main__':unittest.main()
