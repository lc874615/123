# v1.0.2 最终版验证

2026-11-08，本次发布在合成商品与模拟 API 上验证，未对真实 Ozon 店铺或 COS 执行操作。

## 结果

- Python：243 项通过，覆盖采集、图序恢复、视频、托管、类目/属性、定价、整组编辑、上架状态、重启与店铺隔离。
- JavaScript：26 项通过，覆盖图片/文案解析、上传控件、配对、暂停和安全恢复。
- Chromium：8 个独立页面场景通过。包含隐藏图库、延迟加载、用户参考图排除、八个独立文件直接下载、文件链接、无原生上传控件的粘贴路径及精简插件界面。
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
node edge_extension/browser_final_delivery.cjs
```

有图形显示的环境运行 `python windows_ozon_tool/gui_smoke.py`。Linux 可使用 Xvfb 与系统 Tk；测试使用临时 data、模拟 API，并关闭 HTTP 服务和后台自动任务。

Windows DPAPI、Edge 安装权限及真实平台审核未在该 Linux 环境验证。实际平台状态以店铺回执为准；不把模拟测试写成真实上架成功。

历史记录见 TESTING_HISTORY.md。


## v1.0.1 新增回归

复现“先凑到8张、继续生成12张过程图、最后交付折叠的8个文件”：过程中不保存，最终卡片优先于早期链接，自动展开并按编号下载，不打开预览、不下载压缩包。9个编号文件不会截断成8个，结束后的静默核对时间随回复变化重新计时。测试同时运行实际 content.js 恢复循环。

图片完成后自动启动整组文案，不等待视频；生成中的页面不会提前创建文案发送任务或关闭自动化。已采错完整8张可核对最终文件后备份替换，其他变体主图保持、7张详情及视频更新，移除旧格式的活跃文件，旧视频先备份避免上传旧成品。已知未发送的文案可恢复，结果不确定的文案不重发。


## v1.0.2 安装验证

新增7项启动器测试：首选镜像/同一虚拟环境解释器、镜像失败回退、超时切源、旧新版pip选项兼容、安装失败保留数据、离线wheel优先/不完整时联网补齐、全部Windows安装/修复入口统一bootstrap。依赖已齐时不调用pip或下载源，仍禁止修改系统Python。

通过阿里云HTTPS镜像实际下载Windows x64/Python3.12对应的Pillow 12.3.0（7.2MB）、imageio-ffmpeg 0.8.1（38.9MB）、openpyxl 3.1.5和et-xmlfile 2.0.0，四个wheel下载成功。测试环境视频依赖显示9.8MB/s、约4秒；这不是对用户本地带宽的保证。未执行这些Windows二进制文件，也未向真实店铺写入。

本次修改只优化安装，前版运行协议1.0.1保持兼容。插件版本/诊断和弹窗回归通过，采集流程仍包含1.0.1全部修复。
