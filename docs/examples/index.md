# 组件与 Markdown 示例

本页从 [wiki.quters.top 的线上功能说明](https://wiki.quters.top/start/about/features)中选取真实用法，再将内容替换为通用占位数据。示例展示的组件结构与线上站点一致，但不携带其校园业务内容。

## Gallery 图片画廊

```md
<Gallery :row-height="220" :gap="8">

![图片说明](https://vitepress.dev/vitepress-logo-large.webp)

![图片说明](https://vuejs.org/images/logo.png)

</Gallery>
```

<Gallery :row-height="180" :gap="8">

![VitePress](https://vitepress.dev/vitepress-logo-large.webp)

![Vue](https://vuejs.org/images/logo.png)

</Gallery>

## AppCards 应用卡片

线上参考：[常用软件页面](https://wiki.quters.top/start/campus-life/systems/software)。该页面用卡片划分生活、学习、校务和工具类软件，适合验证大量卡片的响应式布局。

```md
<AppCards width="12em" :desc-lines="2" :links="[
  { text: 'VitePress', icon: 'https://vitepress.dev/vitepress-logo-mini.svg', desc: '静态站点生成器', link: 'https://vitepress.dev/' },
  { text: 'Vue', icon: 'https://vuejs.org/images/logo.png', desc: '渐进式 JavaScript 框架', link: 'https://vuejs.org/' }
]" />
```

<AppCards width="12em" :desc-lines="2" :links="[
  { text: 'VitePress', icon: 'https://vitepress.dev/vitepress-logo-mini.svg', desc: '静态站点生成器', link: 'https://vitepress.dev/' },
  { text: 'Vue', icon: 'https://vuejs.org/images/logo.png', desc: '渐进式 JavaScript 框架', link: 'https://vuejs.org/' }
]" />

## 图片题注和字数

页面标题后的字数与阅读时间、图片下方题注都由 Markdown 插件自动生成。任意图片 alt 都会成为题注；本页标题旁的统计则是字数插件的直接效果。
