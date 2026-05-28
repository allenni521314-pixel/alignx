# AlignX Local Amazon Capture

本地体验版 Chrome 插件，用于读取用户当前已经打开的 Amazon 商品页，并把页面证据交给 AlignX 本品诊断页解析。

## 安装

1. 打开 Chrome：`chrome://extensions`
2. 右上角打开“开发者模式”
3. 点击“加载已解压的扩展程序”
4. 选择本文件夹：`app/chrome-extension-alignx-local-capture`

## 使用

1. 用 Chrome 打开 Amazon 商品详情页
2. 点击浏览器右上角的 AlignX Capture 插件
3. 点击“采集当前 Amazon 页面”
4. 点击“打开 AlignX 本品诊断”
5. AlignX 会自动识别为 `local_browser_capture`，显示证据完整性闸门

## 边界

- 只读取当前已打开页面，不自动批量访问 Amazon。
- 不绕过验证码、登录墙或访问限制。
- 缺字段时由 AlignX 完整性闸门提示，不让 AI 猜空字段。
