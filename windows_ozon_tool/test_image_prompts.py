import unittest
from image_prompts import ROLES,generation_prompt,shared_prompt,VISUAL_STYLE,MAIN_STYLE,EVIDENCE_STYLE,POSTER_RULE,DETAIL_STYLE,MAIN_DETAIL_INFO,SEQUENTIAL_DELIVERY
class PromptStyleTests(unittest.TestCase):
 def test_original_eight_roles_keep_shared_seven_positions(self):
  self.assertEqual([name for name,brief in ROLES],['01_main','02_dimensions','03_scene','04_scene','05_material','06_structure','07_details','08_contents'])
  for (name,brief),prefix in zip(ROLES[1:],['商品尺寸图','真实使用场景一','真实使用场景二','材质细节','结构展示','重要细节和变体选择','套装实际内容']):self.assertTrue(brief.startswith(prefix),(name,brief))
 def test_full_set_keeps_eight_ordered_final_filenames_and_styles(self):
  text=generation_prompt('本变体真实参数','全部变体参数');positions=[text.index(name+'.jpg') for name,brief in ROLES];self.assertEqual(positions,sorted(positions));self.assertIn('不要多出第9张',text);self.assertIn(MAIN_STYLE,text);self.assertIn(DETAIL_STYLE,text);self.assertIn('允许真实坐姿等必要局部遮挡',text)
 def test_single_main_keeps_own_reference_and_does_not_include_other_variants(self):
  text=generation_prompt('本变体灰色绒面椅，1件','OTHER_GREEN_CORDUROY_STYLE_ONLY',1);self.assertNotIn('OTHER_GREEN_CORDUROY_STYLE_ONLY',text);self.assertIn('文件名固定01_main.jpg',text);self.assertIn('2—4',text);self.assertIn('约三分之二',text);self.assertIn('原商品是平绒就不能变成条绒',text)
 def test_seven_regeneration_uses_same_role_mapping_and_no_main_file(self):
  text=shared_prompt('真实全组参数');files=['01_dimensions.jpg','02_scene.jpg','03_scene.jpg','04_material.jpg','05_structure.jpg','06_details.jpg','07_contents.jpg'];positions=[text.index(name) for name in files];self.assertEqual(positions,sorted(positions));self.assertNotIn('01_main.jpg',text);self.assertIn('分别对应商品详情位置02—08',text);self.assertIn('用途和顺序固定',text);self.assertNotIn(MAIN_STYLE,text)
 def test_design_reference_cannot_invent_product_features_or_brand(self):
  for text in [generation_prompt('真实参数'),generation_prompt('真实参数',expected=1),shared_prompt('全组真实参数')]:
   self.assertIn(EVIDENCE_STYLE,text);self.assertIn('无品牌商品不加品牌标',text);self.assertIn('不固定绿色',text);self.assertIn('货号、SKU、任务编号',text);self.assertIn('不得添加未证实',text)
 def test_single_poster_may_use_detail_cards_without_collapsing_delivery(self):
  for text in [generation_prompt('真实参数'),shared_prompt('真实参数')]:self.assertIn(POSTER_RULE,text);self.assertIn('允许一张独立海报内使用局部特写',text);self.assertTrue('不要打包' in text or '不提供ZIP' in text)
 def test_main_template_is_scoped_original_and_adaptive(self):
  for expected in (1,8):
   text=generation_prompt('真实商品参数',expected=expected)
   for rule in ('仅作用于01主图','只选择一种合适的构图','核心商品名称最大','不复刻样例','数字带准确单位','无品牌不加品牌/官方店标','主体结构仍可辨认'):
    self.assertIn(rule,text)
  self.assertNotIn('只选择一种合适的构图',shared_prompt('真实商品参数'))
 def test_detail_template_applies_to_full_set_and_shared_regeneration_only(self):
  self.assertIn(DETAIL_STYLE,generation_prompt('参数',expected=8))
  self.assertIn(DETAIL_STYLE,shared_prompt('参数'))
  self.assertNotIn(DETAIL_STYLE,generation_prompt('参数',expected=1))
 def test_main_contract_stays_one_image_and_preserves_fidelity(self):
  text=generation_prompt('固定本品参数',expected=1)
  self.assertIn('文件名固定01_main.jpg',text);self.assertIn('抠图合成',text);self.assertNotIn(DETAIL_STYLE,text)
 def test_detail_template_original_scenes_facts_and_variant_limits(self):
  text=shared_prompt('全组参数')
  for rule in ('每张只讲一个既定主题','不复刻示例','1—3厘米误差','没有清晰细节照片就不臆造','不能据此虚构内部层数','共同事实才写成全组选项通用','不能只换上一张背景色','具体商品单位'):
   self.assertIn(rule,text)
  self.assertEqual(sum(text.count(name) for name in ('01_dimensions.jpg','02_scene.jpg','03_scene.jpg','04_material.jpg','05_structure.jpg','06_details.jpg','07_contents.jpg')),7)
 def test_main_uses_shared_information_without_adopting_variant_appearance(self):
  from image_prompts import main_detail_references,reference_contract
  tasks=[{'sku':'A','detail_references':[{'path':'shared.png','purpose':'shared_gallery'}]}, {'sku':'B','copy_leader':'A','references':[{'path':'own.png','purpose':'variant_main'}]}]
  refs=main_detail_references(tasks[1],tasks)
  self.assertEqual([r['path'] for r in refs],['own.png','shared.png']);self.assertEqual(refs[1]['purpose'],'shared_information');self.assertEqual(refs[1]['sku'],'A')
  task=dict(tasks[1],references=refs)
  self.assertEqual(main_detail_references(task,tasks),refs)
  self.assertIn('不作为本变体外观依据',reference_contract(task))
  self.assertIn(MAIN_DETAIL_INFO,generation_prompt('参数',expected=1));self.assertNotIn(MAIN_DETAIL_INFO,shared_prompt('参数'))
 def test_photo_direction_precedes_contract_and_does_not_use_card_style(self):
  for text in (generation_prompt('参数'),shared_prompt('参数')):
   self.assertTrue(text.startswith(SEQUENTIAL_DELIVERY+'\n'+DETAIL_STYLE));self.assertEqual(text.count(DETAIL_STYLE),1)
   self.assertNotIn(VISUAL_STYLE,text)
   self.assertIn('不得用Python/PIL/SVG',text);self.assertIn('65%—85%',text);self.assertIn('两张场景图必须出现人物实际使用',text)
  self.assertNotIn(DETAIL_STYLE,generation_prompt('参数',expected=1))
 def test_clear_background_and_one_original_per_generation(self):
  for text in (shared_prompt('参数'),generation_prompt('参数')):
   self.assertIn('按本任务编号输出独立3:4高清图片',text)
   self.assertIn('不要浅景深',text);self.assertIn('中后景家具陈设均清晰可辨',text)
   self.assertIn('不编造链接',text)
if __name__=='__main__':unittest.main()

class MainDimensionPreservationTests(unittest.TestCase):
 def test_initial_and_regenerated_mains_must_keep_original_dimension_labels(self):
  from image_prompts import generation_prompt,MAIN_DIMENSIONS
  for expected in (1,8):
   prompt=generation_prompt('当前变体真实尺寸',expected=expected)
   self.assertIn(MAIN_DIMENSIONS,prompt);self.assertIn('不能以“详情图已有尺寸”',prompt);self.assertIn('不得挪用其他变体',prompt)
 def test_leader_keeps_secondary_original_dimension_reference(self):
  import tempfile
  from pathlib import Path
  from local_bridge import Store
  from PIL import Image
  with tempfile.TemporaryDirectory() as tmp:
   refs=[]
   for n in range(2):
    p=Path(tmp)/('original'+str(n)+'.png');Image.new('RGB',(600,800),(n*120,60,80)).save(p);refs.append(str(p))
   store=Store(tmp);store.create_set('DIM(1)','真实商品',refs);store.tasks[0]['main_references']=list(store.tasks[0]['references']);task=store.claim()
   paths={r['path'] for r in store.tasks[0]['main_references']};self.assertTrue(paths<={r['path'] for r in store.tasks[0]['references']});self.assertIn('本变体原图内清晰商品尺寸必须保留到01主图',task['prompt'])


class CompactExecutionTests(unittest.TestCase):
 def test_scoped_sequential_calls_and_commercial_rules_stay_compact(self):
  from image_prompts import photo_facts,FIDELITY
  data={'name':'无线耳机','color':'白色','quantity':'1','length':'3','extra':'蓝牙6.0','cost':'PRIVATE_COST_29','margin':'PRIVATE_MARGIN_25','stock':'PRIVATE_STOCK_1000','pack_weight':'PRIVATE_PACKAGE_1600'}
  facts=photo_facts(data);text=generation_prompt(facts,facts)
  for token in ('PRIVATE_COST','PRIVATE_MARGIN','PRIVATE_STOCK','PRIVATE_PACKAGE'):self.assertNotIn(token,text)
  self.assertIn('每次图像生成/编辑工具调用只制作当前编号的一张完整海报',text);self.assertIn('不要求插件逐张发送请求',text);self.assertIn('不能替代图片内容合格',text)
  self.assertEqual(text.count(FIDELITY),1);self.assertNotIn('扶手有无',text);self.assertIn('商品长(cm)：3',text);self.assertLess(len(text),4500)
  self.assertEqual(generation_prompt('UNIQUE_OWN_FACT',expected=1).count('UNIQUE_OWN_FACT'),1)
 def test_initial_claim_and_both_remake_scopes_filter_business_parameters(self):
  import tempfile
  from unittest.mock import patch
  from pathlib import Path
  from local_bridge import Store
  from variants import facts as all_facts
  from product_group import configure
  from test_image_regeneration import picture,ImageRegenerationTests
  params={'name':'耳机','color':'白色','quantity':'1','length':'3','cost':'29','margin':'25','stock':'1000','pack_weight':'1600','pack_length':'35','pack_width':'25','pack_height':'7'}
  with tempfile.TemporaryDirectory() as tmp,patch('image_regeneration.threading.Thread'):
   store=Store(tmp)
   for i in (1,2):
    ref=Path(tmp)/(str(i)+'.png');ref.write_bytes(picture(i));store.create_set('A('+str(i)+')',all_facts(params),[ref]);store.tasks[-1].update(base_article='A',variant_index=i,variant_parameters=dict(params))
   configure(store.tasks,'A');prompt=store.claim()['prompt']
   for token in ('每套成本含国内运费(元)：','目标净利润率(%)：','初始库存（固定1000）：','包装总重(g)：','包装长(cm)：'):self.assertNotIn(token,prompt)
   self.assertIn('A(1)',prompt);self.assertIn('A(2)',prompt)
  with tempfile.TemporaryDirectory() as tmp:
   store=ImageRegenerationTests().setup(tmp)
   for kind in ('variant_main','shared_details'):
    prompt=store.image_jobs.prompt(store.tasks[0]['sku'],kind)
    self.assertNotIn('pack_weight',prompt);self.assertNotIn('各变体最新参数：[',prompt)
