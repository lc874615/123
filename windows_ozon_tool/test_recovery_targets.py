import copy,tempfile,unittest
from pathlib import Path
from pricing_service import write
from recovery_targets import markers
class RecoveryTargetsTests(unittest.TestCase):
 def task(self):return {'id':'CURRENT','sku':'CHAIR(1)','variant_parameters':{'name':'椅子','color':'灰色','quantity':'1'},'group_variants':[{'sku':'CHAIR(1)','variant_parameters':{'color':'灰色'}}]}
 def test_only_matching_sku_and_visual_parameters_supply_old_ids(self):
  with tempfile.TemporaryDirectory() as tmp:
   task=self.task();old=copy.deepcopy(task);old['id']='OLD';write(Path(tmp)/'recovery_backups'/'1'/'task.json',old)
   for i,changes in enumerate([{'id':'OTHER-SKU','sku':'OTHER'},{'id':'OTHER-COLOR','variant_parameters':{'name':'椅子','color':'红色','quantity':'1'}},{'id':'OTHER-GALLERY','group_variants':[{'sku':'CHAIR(1)','variant_parameters':{'color':'红色'}}]}]):write(Path(tmp)/'recovery_backups'/('bad'+str(i))/'task.json',{**old,**changes})
   self.assertEqual(markers(tmp,task),['【OZON_TASK:CURRENT】','【OZON_TASK:OLD】'])
 def test_corrupt_and_unrelated_roles_ignored_and_current_stays_first(self):
  with tempfile.TemporaryDirectory() as tmp:
   task=self.task();old={**task,'id':'OLD','gallery_source':'ANOTHER'};write(Path(tmp)/'auto_recovery'/'1'/'task.json',old)
   path=Path(tmp)/'regeneration_backups'/'bad'/'task.json';path.parent.mkdir(parents=True);path.write_text('{bad')
   self.assertEqual(markers(tmp,task),['【OZON_TASK:CURRENT】'])
if __name__=='__main__':unittest.main()
