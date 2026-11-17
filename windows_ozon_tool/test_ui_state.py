import unittest
from ui_state import task_bucket,task_summary,matches
class DashboardTests(unittest.TestCase):
 def test_summary_counts_active_regeneration_and_excludes_cancelled(self):
  tasks=[{'sku':'A','state':'saved'},{'sku':'B','state':'queued'},{'sku':'C','state':'needs_attention'},{'sku':'D','state':'cancelled'}]
  jobs=[{'state':'waiting','targets':[{'sku':'A'}]}]
  self.assertEqual(task_summary(tasks,jobs),{'total':3,'queued':1,'running':1,'attention':1})
 def test_search_and_phase_filter_do_not_mutate_queue(self):
  row={'sku':'CHAIR(2)','base_article':'CHAIR','state':'saved','variant_parameters':{'color':'灰色'}}
  self.assertTrue(matches(row,'chair 灰色'));self.assertFalse(matches(row,'RED'));self.assertTrue(matches(row,mode='素材已保存'));self.assertFalse(matches(row,mode='制作中'));self.assertEqual(row['state'],'saved')
 def test_copy_and_image_failure_take_priority_over_saved_product(self):
  self.assertEqual(task_bucket({'sku':'A','state':'saved','copy_state':'running'}),'制作中')
  self.assertEqual(task_bucket({'sku':'A','state':'saved'},[{'state':'needs_attention','targets':[{'sku':'A'}]}]),'需处理')
if __name__=='__main__':unittest.main()
