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

class AttentionConsistencyTests(unittest.TestCase):
 def test_published_receipt_does_not_count_stale_local_failure(self):
  from pipeline_status import stage
  task={'id':'old','sku':'A','state':'saved','copy_state':'needs_attention','message':'历史文案异常'}
  receipts=[{'state':'done','items':{'A':{'on_sale':True}}}];display={'old':stage(task,{},receipts)}
  self.assertEqual(display['old'],'已上架');self.assertEqual(task_summary([task],stages=display)['attention'],0)
  self.assertFalse(matches(task,mode='需处理',stages=display));self.assertTrue(matches(task,mode='已上架',stages=display));self.assertEqual(task['copy_state'],'needs_attention')
 def test_new_regeneration_failure_remains_actionable_after_previous_publication(self):
  from pipeline_status import stage
  task={'id':'old','sku':'A','state':'saved'};jobs=[{'state':'needs_attention','kind':'variant_main','targets':[{'sku':'A'}],'message':'生成工具失败'}];receipts=[{'state':'done','items':{'A':{'on_sale':True}}}]
  display={'old':stage(task,{},receipts,jobs)}
  self.assertIn('主图重做',display['old']);self.assertIn('生成工具失败',display['old']);self.assertEqual(task_summary([task],jobs,display)['attention'],1);self.assertTrue(matches(task,mode='需处理',jobs=jobs,stages=display))
 def test_copy_attention_has_a_visible_reason(self):
  from pipeline_status import stage
  task={'id':'copy-owner','sku':'A','state':'saved','copy_state':'needs_attention','message':'需要核对JSON'}
  self.assertIn('需要核对JSON',stage(task,{},[]))

if __name__=='__main__':unittest.main()
