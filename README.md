# VitePress QUTWiKi Kit

面向第三方 VitePress 站点的 Wiki 工具包，提供两个可独立使用的版本：

- **插件版**：`packages/vitepress-qutwiki-kit/`，接入已有 VitePress 1.x 项目。
- **模板版**：`template/wiki/`，复制后直接建立新的内容型 Wiki。

仓库不包含任何学校正文、地图点位、组织名单、品牌资源或业务后端。组件用法参考了已在线运行的 [wiki.quters.top 功能说明](https://wiki.quters.top/start/about/features)，并保留线上页面链接作为真实案例。

## 插件能力

- 自动扫描 Markdown 并生成 sidebar/nav
- 开发模式监听内容结构变化
- 中文本地搜索双字分词
- 中文字数与阅读时间
- Markdown 图片题注
- Gallery 自适应画廊
- AppCards 应用与资源卡片
- Flink/Flinks 友链卡片和 `<flink>` 容器语法
- ImageViewer 图片缩放与拖动
- 独立入口中的可选 Twikoo 评论组件

## 快速开始

运行插件文档站：

```bash
npm ci
npm run dev
```

构建文档站和模板：

```bash
npm run check
```

## 安装插件

```bash
npm install vitepress-qutwiki-kit
```

主题入口：

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

VitePress 配置：

```ts
import { defineConfig } from 'vitepress'
import { installWikiMarkdown } from 'vitepress-qutwiki-kit/markdown'
import { tokenizeChineseSearch } from 'vitepress-qutwiki-kit/config'

export default defineConfig({
  markdown: { config: installWikiMarkdown },
  themeConfig: {
    search: {
      provider: 'local',
      options: { miniSearch: { options: { tokenize: tokenizeChineseSearch } } },
    },
  },
})
```

## 使用模板

```bash
cd template/wiki
npm install
npm run dev
```

复制模板到独立仓库后，修改：

- `docs/.vitepress/site.ts`：站名、描述、仓库链接和目录名称
- `docs/index.md`：首页
- `docs/guide/`：内容
- `docs/.vitepress/theme/style.css`：品牌色

模板当前通过 `file:../../packages/vitepress-qutwiki-kit` 引用本仓库插件。独立使用时将其改为 npm 版本。

## 文档

- [插件介绍](docs/plugin/index.md)
- [安装与配置](docs/plugin/usage.md)
- [API 与边界](docs/plugin/migration.md)
- [真实用法示例](docs/examples/index.md)
- [模板说明](docs/template.md)

## 真实案例

- [线上功能说明](https://wiki.quters.top/start/about/features)
- [Gallery 实际使用页面](https://wiki.quters.top/start/newstudent/campus-network)
- [AppCards 实际使用页面](https://wiki.quters.top/start/campus-life/systems/software)
- [Flink 实际使用页面](https://wiki.quters.top/flink)

## 许可

源代码和本仓库插件文档使用 [MIT License](LICENSE)。外部案例页面的内容及许可由其原站负责，本仓库不复制其校园业务正文。
