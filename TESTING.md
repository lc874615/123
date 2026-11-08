# v1.0.0 最终版验证

2026-11-08，本次发布在合成商品与模拟 API 上验证，未对真实 Ozon 店铺或 COS 执行操作。

## 结果

- Python：231 项通过，覆盖采集、图序恢复、视频、托管、类目/属性、定价、整组编辑、上架状态、重启与店铺隔离。
- JavaScript：24 项通过，覆盖图片/文案解析、上传控件、配对、暂停和安全恢复。
- Chromium：7 个独立页面场景通过。包含隐藏图库、延迟加载、用户参考图排除、八个独立文件直接下载、文件链接、无原生上传控件的粘贴路径及精简插件界面。
- Tk：真实窗口验证三页主界面、按组显示、四页预览、1000×700 下提交区可见、四项价格行存在，编辑共用文案后两个变体自动保存。
- Python 编译与插件版本/文件引用检查通过。

## 本版重点回归

物理参数修改只标记素材待更新、手动更新先备份；人工售价保留并重新测算费用；WEBP 转 JPG；配对持久保存；重启仅恢复已发送结果读取；删除前暂停并核对；按店铺隔离写入及回执；长等待提示；清空本地进度不删除平台商品。

整组标题、简介和标签落盘到所有变体，包括尚无素材/草稿的变体。后续建立草稿时自动继承，每个变体保留自己的货号。

四项价格：最高价 2P、划线价 4P、促销最低限制 P、成本使用输入值对应官方 net_price。价格 API 在创建后、库存设置前调用，成功后不重复写；失败显示具体回执并间隔重试，不误报完成。

## 复现

```sh
python -m unittest discover -s windows_ozon_tool -q
node --test edge_extension/test_*.cjs
python -m compileall -q windows_ozon_tool
```

浏览器测试需另行安装 Node Playwright 与 Chromium（不是日常工具运行依赖）。OZON_TEST_CHROMIUM 可指定浏览器路径。每个脚本使用合成页面或拦截路由，不访问真实 ChatGPT 对话：

```sh
node edge_extension/browser_regression.cjs
node edge_extension/browser_upload_regression.cjs
node edge_extension/browser_gallery_regression.cjs
node edge_extension/browser_structural_gallery.cjs
node edge_extension/browser_file_links.cjs
node edge_extension/browser_direct_download.cjs
node edge_extension/browser_popup_final.cjs
```

有图形显示的环境运行 `python windows_ozon_tool/gui_smoke.py`。Linux 可使用 Xvfb 与系统 Tk；测试使用临时 data、模拟 API，并关闭 HTTP 服务和后台自动任务。

Windows DPAPI、Edge 安装权限及真实平台审核未在该 Linux 环境验证。实际平台状态以店铺回执为准；不把模拟测试写成真实上架成功。

历史记录见 TESTING_HISTORY.md。
