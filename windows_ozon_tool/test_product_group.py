import unittest
from product_group import configure
class Tests(unittest.TestCase):
 def test_group_plan(self):
  tasks=[{'sku':f'TEST({i})','facts':f'color {i}','base_article':'TEST','variant_index':i,'prompt':'base'} for i in (1,2,3)]
  group=configure(tasks,'TEST');self.assertEqual(len({t['model'] for t in group}),1);self.assertEqual(group[0]['expected_images'],8);self.assertEqual(group[1]['expected_images'],1);self.assertEqual(group[2]['gallery_source'],'TEST(1)');self.assertIn('color 3',group[0]['group_facts'])
if __name__=='__main__':unittest.main()
