# 插件介绍

`vitepress-qutwiki-kit` 是一套面向知识库、手册和内容站的 VitePress 1.x 扩展。它把经真实 Wiki 长期使用的功能整理成独立 npm 包，让已有 VitePress 项目无需复制整套主题，也能按需获得自动导航、中文搜索、Markdown 增强和内容组件。

## 它解决什么问题

VitePress 提供了可靠的文档基础，但内容规模增长后，维护者通常还需要手工维护侧边栏、补充中文搜索策略、实现图片画廊、链接卡片、题注和阅读时间。各站点重复实现这些功能，容易造成配置臃肿、代码与内容耦合，也让升级变得困难。

Wiki Kit 将这些能力拆成三个入口：

| 入口 | 职责 |
| --- | --- |
| `vitepress-qutwiki-kit` | Vue 组件及全局组件安装器 |
| `vitepress-qutwiki-kit/markdown` | 字数、阅读时间、图片题注和友链容器 |
| `vitepress-qutwiki-kit/config` | 自动内容树、开发监听器和中文搜索 tokenizer |

Twikoo 评论单独位于 `vitepress-qutwiki-kit/twikoo`，不使用评论时不会进入核心模块图。

## 核心能力

### 自动内容树

扫描指定 Markdown 目录，从 frontmatter `title`、一级标题和目录映射生成 VitePress sidebar。排序依次使用 `top`、`order` 和文件名，因此在本机、CI 与重新 clone 后保持一致。

### 中文搜索优化

将连续中文切分为双字 token，同时保留英文和数字词，直接接入 VitePress 本地搜索的 MiniSearch 配置。它不替换搜索引擎，只改善中文内容的召回方式。

### Markdown 增强

- 在一级标题旁显示中文字符数和预计阅读时间
- 使用图片 alt 文本生成安全转义的题注
- 将 `<flink>` 列表语法转换为友链卡片
- 通过 `wordCount: false` 或 `search: false` 控制单页行为

### 内容组件

<div class="example-panel">

- `Gallery`：按图片宽高比生成杂志式自适应画廊
- `AppCards`：适合软件、资源和入口导航的响应式卡片
- `Flink` / `Flinks`：带站点截图、头像和描述的友链卡片
- `ImageViewer`：点击正文图片后缩放、拖动和全屏查看
- `TwikooComments`：SSR 安全的可选评论组件

</div>

## 适用场景

- 团队知识库和内部手册
- 学校、社区与开源项目 Wiki
- 产品帮助中心和长期维护的教程站
- 已有 VitePress 站点，只想接入一两个内容组件

## 快速接入

```bash
npm install vitepress-qutwiki-kit
```

在主题入口注册组件：

```ts
import DefaultTheme from 'vitepress/theme'
import { installWikiComponents } from 'vitepress-qutwiki-kit'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    installWikiComponents(app)
  },
}
```

在 VitePress 配置中启用 Markdown 扩展：

```ts
import { defineConfig } from 'vitepress'
import { installWikiMarkdown } from 'vitepress-qutwiki-kit/markdown'

export default defineConfig({
  markdown: { config: installWikiMarkdown },
})
```

下一步阅读[安装与配置](/plugin/usage)，或直接查看从真实线上 Wiki 用法整理的[示例](/examples/)。

## 真实使用参考

这些功能来自实际内容站的长期使用与迭代。可在 [wiki.quters.top 的功能说明](https://wiki.quters.top/start/about/features) 查看原始线上效果，也可查看其[应用卡片页面](https://wiki.quters.top/start/campus-life/systems/software)和[友链页面](https://wiki.quters.top/flink)。本仓库只保留通用实现与最小示例，不包含该站的校园资料、地图数据或服务端业务。

## 设计原则

- **按需使用**：组件、Markdown 和配置 helper 互不强绑。
- **不接管主题**：延续 VitePress 默认主题变量，可嵌入已有主题。
- **稳定优先**：公开 API 不依赖 VitePress 默认主题的私有模块路径。
- **安全默认**：卡片链接只接受 HTTP(S) 与安全相对路径，题注进行 HTML 转义。
- **业务无关**：包内不含学校、组织、域名、统计 ID、地图点位或后端接口。
