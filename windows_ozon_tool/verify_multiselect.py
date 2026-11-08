"""Offline verification entry point for the user's local Windows installation."""
import sys,unittest
from unittest.mock import patch

def main():
 with patch('urllib.request.urlopen',side_effect=AssertionError('本地验证禁止网络请求，请检查测试隔离')):
  suite=unittest.defaultTestLoader.loadTestsFromNames(['test_attribute_choices','test_attributes','test_group_publication'])
  result=unittest.TextTestRunner(verbosity=2).run(suite)
 if result.wasSuccessful():print('\n本地多选验证通过：官方选项模拟、分页保留、多选数量限制、批量字典校验及整组保存。\n本次未连接Ozon，不会修改店铺商品或库存。')
 return 0 if result.wasSuccessful() else 1
if __name__=='__main__':sys.exit(main())
