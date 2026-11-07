import unittest
from product_group import configure
class Tests(unittest.TestCase):
 def test_group_plan(self):
  tasks=[{'sku':f'TEST({i})','facts':f'color {i}','base_article':'TEST','variant_index':i,'prompt':'base'} for i in (1,2,3)]
  group=configure(tasks,'TEST');self.assertEqual(len({t['model'] for t in group}),1);self.assertEqual(group[0]['expected_images'],8);self.assertEqual(group[1]['expected_images'],1);self.assertEqual(group[2]['gallery_source'],'TEST(1)');self.assertIn('color 3',group[0]['group_facts'])
if __name__=='__main__':unittest.main()

class SharedCopyTests(unittest.TestCase):
 def test_prompt_and_reuse_all_variants(self):
  import tempfile,json
  from pathlib import Path
  from local_bridge import Store
  from listing_bundle import copy_prompt_for
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp)
   for i,color in [(1,'红色'),(2,'金色')]:
    store.create_set(f'GROUP({i})',f'颜色：{color}；主体材质：聚丙烯')
    task=store.tasks[-1];task.update(base_article='GROUP',variant_index=i,state='saved',video='test.mp4')
    folder=Path(tmp)/'products'/task['sku'];folder.mkdir(parents=True)
    (folder/'listing_bundle.json').write_text(json.dumps({'copy':{},'blockers':['俄文文案待生成']}),encoding='utf-8')
   group=configure(store.tasks,'GROUP')
   prompt=copy_prompt_for(group[0]);self.assertIn('红色',prompt);self.assertIn('金色',prompt);self.assertIn('统一一套',prompt)
   common={'sku':'GROUP(1)','title_ru':'Корзина','description_ru':'Красный или золотистый цвет на выбор.','tags_ru':['#корзина'],'missing_facts':[]}
   leader=Path(tmp)/'products'/'GROUP(1)'/'listing_bundle.json';leader.write_text(json.dumps({'copy':common}),encoding='utf-8')
   self.assertIsNone(store.next_copy())
   follower=json.loads((Path(tmp)/'products'/'GROUP(2)'/'listing_bundle.json').read_text(encoding='utf-8'))
   for key in ('title_ru','description_ru','tags_ru'):self.assertEqual(follower['copy'][key],common[key])
   self.assertEqual(follower['copy_source'],'GROUP(1)')
