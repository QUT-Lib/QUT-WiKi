# My VitePress Wiki

这是一个可直接复制的通用 VitePress Wiki 模板。

```bash
npm install
npm run dev
```

开始使用前修改：

- `docs/.vitepress/site.ts`：站名、描述、仓库链接和目录名称
- `docs/index.md`：首页文案
- `docs/guide/`：删除示例文章并加入自己的 Markdown

模板当前默认引用仓库内的 `file:../../packages/vitepress-qutwiki-kit`。单独复制模板后，将依赖改为已发布的 `vitepress-qutwiki-kit` 版本，或改为插件包在新项目中的实际相对路径。
