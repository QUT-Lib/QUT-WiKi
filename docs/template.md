# 模板使用

`template/wiki/` 是完整可运行的 VitePress 项目，适合直接复制后开始编写内容。它已经组合了自动导航、中文搜索、Markdown 扩展、组件注册和图片查看器。

```bash
cd template/wiki
npm install
npm run dev
```

复制到独立仓库后，修改以下位置：

- `docs/.vitepress/site.ts`：站名、描述、仓库地址和目录名称
- `docs/index.md`：首页文案
- `docs/guide/`：示例文章和真实内容
- `docs/.vitepress/theme/style.css`：品牌色及少量展示样式

模板示例同样参考 [wiki.quters.top](https://wiki.quters.top/) 中已经实际运行的组件组合，但不包含其校园正文、地图、组织数据、品牌资源或服务端代码。
