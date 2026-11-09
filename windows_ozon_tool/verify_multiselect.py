"""Offline verification entry point for the user's local Windows installation."""
import sys,unittest
from unittest.mock import patch

def main():
 with patch('urllib.request.urlopen',side_effect=AssertionError('本地验证禁止网络请求，请检查测试隔离')):
  suite=unittest.defaultTestLoader.loadTestsFromNames(['test_attribute_choices','test_attributes','test_group_publication','test_asset_reconcile','test_final_workflow','test_preview_submission','test_copy_pipeline'])
  result=unittest.TextTestRunner(verbosity=2).run(suite)
 if result.wasSuccessful():print('\n本地多选与素材状态验证通过：官方选项、批量保存、参数等价判断及沿用素材流程。\n本次未连接Ozon，不会修改店铺商品或库存。')
 return 0 if result.wasSuccessful() else 1
if __name__=='__main__':sys.exit(main())
