"""Run offline alert tests; --demo opens a local simulated alert without business writes."""
import argparse,sys,unittest
from unittest.mock import patch

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--demo',action='store_true');args=parser.parse_args()
 with patch('urllib.request.urlopen',side_effect=AssertionError('离线验证禁止联网')):
  result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_task_alerts'))
 if not result.wasSuccessful():return 1
 print('异常提醒离线检查通过；没有连接店铺或修改商品。')
 if args.demo:
  import tempfile,tkinter as tk
  from tkinter import ttk
  from pathlib import Path
  from task_alerts import AlertPopup,issue
  with tempfile.TemporaryDirectory() as tmp:
   root=tk.Tk();root.title('异常弹窗本机演示（不会操作真实任务）');root.geometry('660x130');ttk.Label(root,text='这是离线演示。弹窗仅展示模拟异常；关闭此窗口即可退出。',wraplength=620).pack(padx=10,pady=15);ttk.Button(root,text='退出演示',command=root.destroy).pack()
   popup=AlertPopup(root,Path(tmp)/'demo-alert.json',lambda:None);rows=[issue('示例货号(1)','图片采集','未找到原始作图标记'),issue('示例货号(2)','提交与上架','导入请求结果不确定，response lost')];root.after(300,lambda:popup.update(rows));root.after(2000,lambda:popup.update(rows));root.mainloop()
 return 0
if __name__=='__main__':sys.exit(main())
