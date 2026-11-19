import unittest
from visual_plans import STYLES,build,render
from selling_plan import PROFILES,EXTRACTION,VALUE_SELECTION,STORYBOARD,VISUAL_PROOF,selection_for_scope,storyboard_for_scope,MAIN_FOCUS
class SellingPlanTests(unittest.TestCase):
 def test_every_style_has_distinct_buyer_questions_hero_and_detail_story(self):
  self.assertEqual(set(PROFILES),set(STYLES));self.assertEqual(len({p['hero'] for p in PROFILES.values()}),len(STYLES));self.assertEqual(len({p['details'] for p in PROFILES.values()}),len(STYLES))
 def test_initial_and_both_remake_scopes_share_full_extraction_and_value_rules(self):
  for style in STYLES:
   for scope in ('full','main','shared'):
    with self.subTest(style=style,scope=scope):
     text=render(build(override=style),'UNTRUSTED_FACT','UNTRUSTED_GROUP',scope)
     for rule in (EXTRACTION,selection_for_scope(scope),storyboard_for_scope(scope),VISUAL_PROOF):self.assertEqual(text.count(rule),1)
     self.assertIn(PROFILES[style]['hero'],text) if scope!='shared' else self.assertNotIn('【本类主图打法】',text)
     self.assertIn(PROFILES[style]['details'],text) if scope!='main' else self.assertNotIn('【本类详情叙事】',text)
     self.assertNotIn('UNTRUSTED_',text);self.assertLess(len(text),6500)
     self.assertIn('2—4项',text);self.assertIn('不足则减少',text)
 def test_readable_original_claims_are_usable_without_invented_proof_in_every_scope(self):
  from selling_plan import VERSION
  self.assertEqual(VERSION,2)
  old=build(override='digital');old['selling_plan_version']=1
  for style in STYLES:
   for scope in ('full','main','shared'):
    plan=build(override=style);self.assertEqual(plan['selling_plan_version'],2);text=render(plan,scope=scope)
    for phrase in ('原图清晰文字本身就是来源依据','无需另外提供测试报告','不能边读边只保留两三项','无法直接拍出的性能','不升级宣称强度','不要求虚构实验'):
     self.assertIn(phrase,text,(style,scope))
  self.assertIn('原图清晰文字本身就是来源依据',render(old,scope='main'))
 def test_main_does_not_receive_seven_detail_generation_instructions(self):
  main=render(build(override='digital'),scope='main');shared=render(build(override='digital'),scope='shared')
  self.assertIn(MAIN_FOCUS,main);self.assertNotIn(STORYBOARD,main);self.assertNotIn('【按证据分配7张详情】',main);self.assertNotIn('01始终是当前变体主图',shared);self.assertNotIn('【本类主图打法】',shared)
 def test_story_does_not_turn_category_questions_or_visible_features_into_performance(self):
  text=render(build(override='digital'))
  for phrase in ('不是本品已具备的属性','不能推导续航','保留有图证的事实','不得臆造'):
   self.assertIn(phrase,text)
  self.assertIn('英文文件后缀只是关联标识',text);self.assertIn('不能连续',text.replace('不连续','不能连续'))
if __name__=='__main__':unittest.main()
