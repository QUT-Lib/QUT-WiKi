# API 与边界

## 导出 API

| 名称 | 说明 |
| --- | --- |
| `installWikiComponents(app, options)` | 注册全部核心 Vue 组件 |
| `createWikiKit(options)` | 返回可供 `app.use()` 使用的 Vue plugin |
| `installWikiMarkdown(md, options)` | 安装 Markdown 扩展集合 |
| `wordCountPlugin` | 只安装字数和阅读时间 |
| `imageCaptionPlugin` | 只安装图片题注 |
| `flinkBlockPlugin` | 只安装友链容器语法 |
| `createContentTree(options)` | 从文件系统生成 sidebar 数据 |
| `createContentTreeWatcher(root, build)` | 内容结构变化时重启开发服务 |
| `sidebarItemToNav(item)` | 将 sidebar 节点转换为 nav 节点 |
| `tokenizeChineseSearch(text)` | 中文双字搜索分词 |

## 不包含的能力

- 不提供地图 SDK、校园点位或定位服务。
- 不提供 XLSX 解析、在线表格同步或浏览器后端。
- 不提供站点 Logo、主题色、统计脚本、域名和部署平台配置。
- 不自动读取 Git 贡献者，避免要求第三方构建环境必须具有完整 Git 历史。
- 不修改 VitePress 默认主题内部 DOM，侧栏抽屉等强主题能力应由站点自行实现。

## 兼容范围

首个版本面向 VitePress `>=1.5 <2` 和 Vue `>=3.5`。组件使用 VitePress CSS variables，但不导入默认主题内部组件或虚拟模块。

## 排序规则

自动内容树依次比较 frontmatter `top`、`order` 和文件名。它不会使用文件创建时间，因为创建时间在 Git clone、压缩包和 CI 环境中并不稳定。

```yaml
---
title: 快速开始
order: 1
---
```
