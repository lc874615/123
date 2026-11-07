import json,tempfile,unittest
from pathlib import Path
from material_guard import validate
from listing_bundle import save_copy
class Tests(unittest.TestCase):
 def data(self,**kwargs):
  return dict(sku='TEST(1)',facts='主体材质：聚丙烯；配件/内衬材质：纸板',variant_parameters={'material':'聚丙烯','accessory_material':'纸板'},copy={},blockers=[],**kwargs)
 def test_body_and_lining_are_both_valid(self):
  validate(self.data(),{'title_ru':'Корзина из полипропилена','description_ru':'Корпус — полипропилен. Вставка — картон.'})
 def test_mixed_unscoped_materials_are_valid(self):
  validate(self.data(),{'title_ru':'Корзина','description_ru':'Материалы: полипропилен, картон.'})
 def test_wrong_body_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'主体材质'):validate(self.data(),{'title_ru':'Корзина','description_ru':'Корпус изготовлен из картона.'})
 def test_wrong_lining_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'内衬'):validate(self.data(),{'description_ru':'Подкладка — полипропилен.'})
 def test_legacy_labelled_facts(self):
  data=self.data();data.pop('variant_parameters');validate(data,{'description_ru':'Полипропилен и картон.'})
 def test_lining_does_not_become_body(self):
  data={'facts':'主体材质：纸板；配件/内衬材质：聚丙烯'}
  validate(data,{'description_ru':'Корпус — картон. Подкладка — полипропилен.'})
  with self.assertRaises(ValueError):validate(data,{'description_ru':'Корпус — полипропилен.'})
 def test_saved_bundle_with_lining_can_be_saved_again(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);target=folder/'listing_bundle.json';target.write_text(json.dumps(self.data()),encoding='utf-8')
   value={'sku':'TEST(1)','title_ru':'Корзина','description_ru':'Корпус — полипропилен. Вставка — картон.','tags_ru':[],'missing_facts':[]}
   self.assertTrue(save_copy(folder,value)['saved']);self.assertTrue(save_copy(folder,value)['saved'])
   self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['variant_parameters']['accessory_material'],'纸板')
if __name__=='__main__':unittest.main()
