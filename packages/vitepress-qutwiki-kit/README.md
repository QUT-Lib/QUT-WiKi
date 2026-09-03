# vitepress-qutwiki-kit

为 VitePress 1.x 提供自动导航、中文搜索、Markdown 增强和可复用内容组件。

```bash
npm install vitepress-qutwiki-kit
```

## 入口

- `vitepress-qutwiki-kit`：Gallery、AppCards、Flink/Flinks、ImageViewer 和组件安装器
- `vitepress-qutwiki-kit/markdown`：字数、阅读时间、图片题注和友链容器
- `vitepress-qutwiki-kit/config`：内容树、开发监听器和中文搜索 tokenizer
- `vitepress-qutwiki-kit/twikoo`：可选 Twikoo 评论组件

```ts
import { installWikiComponents } from 'vitepress-qutwiki-kit'
import { installWikiMarkdown } from 'vitepress-qutwiki-kit/markdown'
```

完整说明见仓库文档站。线上真实用法可参考 [wiki.quters.top 的功能说明](https://wiki.quters.top/start/about/features)。
