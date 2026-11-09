import unittest
from image_prompts import ROLES,generation_prompt,shared_prompt,VISUAL_STYLE,MAIN_STYLE,EVIDENCE_STYLE,POSTER_RULE
class PromptStyleTests(unittest.TestCase):
 def test_original_eight_roles_keep_shared_seven_positions(self):
  self.assertEqual([name for name,brief in ROLES],['01_main','02_dimensions','03_scene','04_scene','05_material','06_structure','07_details','08_contents'])
  for (name,brief),prefix in zip(ROLES[1:],['商品尺寸图','真实使用场景一','真实使用场景二','材质细节','结构展示','重要细节和变体选择','套装实际内容']):self.assertTrue(brief.startswith(prefix),(name,brief))
 def test_full_set_keeps_eight_ordered_final_filenames_and_styles(self):
  text=generation_prompt('本变体真实参数','全部变体参数');positions=[text.index(name+'.jpg') for name,brief in ROLES];self.assertEqual(positions,sorted(positions));self.assertIn('不要多出第9张',text);self.assertIn(MAIN_STYLE,text);self.assertIn(VISUAL_STYLE,text);self.assertIn('允许真实坐姿等必要局部遮挡',text)
 def test_single_main_keeps_own_reference_and_does_not_include_other_variants(self):
  text=generation_prompt('本变体灰色绒面椅，1件','OTHER_GREEN_CORDUROY_STYLE_ONLY',1);self.assertNotIn('OTHER_GREEN_CORDUROY_STYLE_ONLY',text);self.assertIn('文件名固定01_main.jpg',text);self.assertIn('2—4',text);self.assertIn('约三分之二',text);self.assertIn('原商品是平绒就不能变成条绒',text)
 def test_seven_regeneration_uses_same_role_mapping_and_no_main_file(self):
  text=shared_prompt('真实全组参数');files=['01_dimensions.jpg','02_scene.jpg','03_scene.jpg','04_material.jpg','05_structure.jpg','06_details.jpg','07_contents.jpg'];positions=[text.index(name) for name in files];self.assertEqual(positions,sorted(positions));self.assertNotIn('01_main.jpg',text);self.assertIn('分别对应商品详情位置02—08',text);self.assertIn('用途和顺序固定',text);self.assertNotIn(MAIN_STYLE,text)
 def test_design_reference_cannot_invent_product_features_or_brand(self):
  for text in [generation_prompt('真实参数'),generation_prompt('真实参数',expected=1),shared_prompt('全组真实参数')]:
   self.assertIn(EVIDENCE_STYLE,text);self.assertIn('无品牌商品不加品牌标',text);self.assertIn('不固定绿色',text);self.assertIn('货号、SKU、任务编号',text);self.assertIn('旋转、透气、承重、护脊',text)
 def test_single_poster_may_use_detail_cards_without_collapsing_delivery(self):
  for text in [generation_prompt('真实参数'),shared_prompt('真实参数')]:self.assertIn(POSTER_RULE,text);self.assertIn('允许一张独立海报内使用局部特写',text);self.assertTrue('不要打包' in text or '不提供ZIP' in text)
 def test_main_template_is_scoped_original_and_adaptive(self):
  for expected in (1,8):
   text=generation_prompt('真实商品参数',expected=expected)
   for rule in ('仅作用于01主图','只选择一种合适的构图','核心商品名称最大','不复刻样例','数字带准确单位','无品牌不加品牌/官方店标','主体结构仍可辨认'):
    self.assertIn(rule,text)
  self.assertNotIn('只选择一种合适的构图',shared_prompt('真实商品参数'))
if __name__=='__main__':unittest.main()
