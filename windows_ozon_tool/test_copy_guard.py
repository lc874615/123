import json,tempfile,unittest
from pathlib import Path
from listing_bundle import save_copy
class Tests(unittest.TestCase):
 def test_sku_material_and_backup(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);f=p/'listing_bundle.json';old={'title_ru':'Корзина','description_ru':'Материал — картон'}
   f.write_text(json.dumps({'sku':'TEST','facts':'材质：聚丙烯','copy':old,'blockers':[]}),encoding='utf-8')
   value={'sku':'OTHER','title_ru':'Корзина','description_ru':'Полипропилен','tags_ru':[],'missing_facts':['Бренд']}
   with self.assertRaisesRegex(ValueError,'SKU'):save_copy(p,value)
   value['sku']='TEST';value['description_ru']='Картон'
   with self.assertRaisesRegex(ValueError,'材质冲突'):save_copy(p,value)
   value['description_ru']='Полипропилен';save_copy(p,value)
   self.assertEqual(json.loads(f.read_text(encoding='utf-8'))['copy']['missing_facts'],[])
   self.assertTrue((p/'copy_before_material_fix.json').exists())
   with self.assertRaisesRegex(ValueError,'不自动覆盖'):save_copy(p,value)
if __name__=='__main__':unittest.main()
