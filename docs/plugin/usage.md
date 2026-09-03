# 安装与配置

## 安装

```bash
npm install vitepress-qutwiki-kit
```

VitePress `1.5` 至 `1.x` 和 Vue `3.5+` 是 peer dependencies。只有使用评论组件时才需要额外安装 `twikoo`。

## 注册组件

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

传入 `{ componentPrefix: 'Wiki' }` 可将组件名改为 `WikiGallery`、`WikiAppCards` 等，避免与现有全局组件冲突。

## Markdown 扩展

```ts
import { installWikiMarkdown } from 'vitepress-qutwiki-kit/markdown'

export default defineConfig({
  markdown: {
    config(md) {
      installWikiMarkdown(md, {
        imageCaptions: true,
        flinks: true,
        wordCount: { wordsPerMinute: 350 },
      })
    },
  },
})
```

文章可在 frontmatter 中使用 `wordCount: false` 关闭统计。图片题注默认取 alt 文本。

## 中文搜索

```ts
import { tokenizeChineseSearch } from 'vitepress-qutwiki-kit/config'

themeConfig: {
  search: {
    provider: 'local',
    options: {
      miniSearch: {
        options: {
          tokenize: tokenizeChineseSearch,
          processTerm: (term) => term.toLowerCase(),
        },
      },
    },
  },
}
```

## 自动导航

```ts
import { resolve } from 'node:path'
import { createContentTree, createContentTreeWatcher } from 'vitepress-qutwiki-kit/config'

const root = resolve('docs/guide')
const buildGuide = () => createContentTree({
  root,
  routeBase: '/guide/',
  directoryLabels: { basics: '基础' },
  sectionOrder: ['basics'],
})

export default defineConfig({
  vite: { plugins: [createContentTreeWatcher(root, buildGuide)] },
  themeConfig: { sidebar: { '/guide/': buildGuide() } },
})
```

## 图片查看器

放在自定义布局根部即可覆盖正文图片：

```vue
<script setup>
import DefaultTheme from 'vitepress/theme'
import { ImageViewer } from 'vitepress-qutwiki-kit'
</script>

<template>
  <DefaultTheme.Layout />
  <ImageViewer selector=".vp-doc img" />
</template>
```

为图片添加 `data-no-viewer` 可阻止查看器接管。

## Twikoo

```bash
npm install twikoo
```

```vue
<script setup>
import { TwikooComments } from 'vitepress-qutwiki-kit/twikoo'
</script>

<template>
  <TwikooComments env-id="https://comments.example.com" lang="zh-CN" />
</template>
```
