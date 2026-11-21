import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from listing_bundle import copy_prompt_for
from reference_prefill import build

class CopyWritingPolicyTests(unittest.TestCase):
 def test_prompt_includes_structure_evidence_search_and_packaging_boundaries(self):
  prompt=copy_prompt_for({'facts':'椅子'})
  for rule in ('先读资料，再写文案','标题 title_ru','简介 description_ru','自然埋词','不写物流包装信息','不删除物流/定价字段','包装信息不列为missing_facts','商品本体尺寸可以保留'):
   self.assertIn(rule,prompt)
 def test_large_group_keeps_shared_detail_in_actual_attachments(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);tasks=[]
   for n in range(12):
    sku='SKU'+str(n);path=root/'products'/sku/'references'/'main.png';path.parent.mkdir(parents=True);Image.new('RGB',(20,20),(n,0,0)).save(path)
    tasks.append({'sku':sku,'copy_leader':'SKU0','set_mode':True,'state':'saved','references':[{'path':str(path),'purpose':'variant_main'}]})
   detail=root/'products'/'SKU0'/'shared_references'/'spec.png';detail.parent.mkdir();Image.new('RGB',(20,30),'blue').save(detail)
   tasks[0]['detail_references']=[{'path':str(detail),'purpose':'shared_information'}]
   store=SimpleNamespace(folder=root,tasks=tasks)
   with patch('reference_prefill.pending_task',return_value=True),patch('reference_prefill.category_context',return_value=([],'')):
    context,attachments=build(store,'SKU0')
   self.assertEqual(len(attachments),8)
   row=next(r for r in context['references'] if r['path']==str(detail))
   self.assertEqual(set(row['skus']),{t['sku'] for t in tasks})

if __name__=='__main__':unittest.main()
