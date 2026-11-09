"""Offline verification entry point for the user's local Windows installation."""
import sys,unittest
from unittest.mock import patch

def main():
 with patch('urllib.request.urlopen',side_effect=AssertionError('本地验证禁止网络请求，请检查测试隔离')):
  suite=unittest.defaultTestLoader.loadTestsFromNames(['test_attribute_choices','test_attributes','test_group_publication','test_asset_reconcile','test_final_workflow','test_preview_submission','test_copy_pipeline','test_copy_scheduling','test_copy_privacy','test_variants'])
  result=unittest.TextTestRunner(verbosity=2).run(suite)
 if result.wasSuccessful():print('\n本地自动化验证通过：多选、素材、文案去货号、制作同首行及首变体自动调度。\n本次未连接Ozon，不会修改店铺商品或库存。')
 return 0 if result.wasSuccessful() else 1
if __name__=='__main__':sys.exit(main())
