import { defineConfig } from 'vitepress'
import { installWikiMarkdown } from 'vitepress-qutwiki-kit/markdown'
import { tokenizeChineseSearch } from 'vitepress-qutwiki-kit/config'

export default defineConfig({
  lang: 'zh-CN',
  title: 'VitePress QUTWiKi Kit',
  description: '面向内容型 VitePress 站点的组件、Markdown 扩展与配置工具集',
  cleanUrls: true,
  lastUpdated: true,
  head: [['link', { rel: 'icon', href: '/favicon.svg', type: 'image/svg+xml' }]],
  markdown: {
    config: (md) => installWikiMarkdown(md),
  },
  themeConfig: {
    nav: [
      { text: '介绍', link: '/' },
      { text: '快速开始', link: '/plugin/usage' },
      { text: '示例', link: '/examples/' },
      { text: '模板', link: '/template' },
    ],
    sidebar: {
      '/plugin/': [
        {
          text: '插件文档',
          items: [
            { text: '插件介绍', link: '/plugin/' },
            { text: '安装与配置', link: '/plugin/usage' },
            { text: 'API 与边界', link: '/plugin/migration' },
          ],
        },
      ],
      '/examples/': [
        {
          text: '真实用法示例',
          items: [
            { text: '组件与 Markdown', link: '/examples/' },
            { text: '友链卡片', link: '/examples/flinks' },
          ],
        },
      ],
      '/template': [
        { text: '模板使用', link: '/template' },
      ],
    },
    socialLinks: [],
    outline: { level: [2, 3], label: '本页目录' },
    sidebarMenuLabel: '文档目录',
    returnToTopLabel: '返回顶部',
    docFooter: { prev: '上一页', next: '下一页' },
    lastUpdatedText: '最后更新于',
    search: {
      provider: 'local',
      options: {
        translations: {
          button: { buttonText: '搜索', buttonAriaLabel: '搜索文档' },
          modal: {
            displayDetails: '显示详细列表', resetButtonTitle: '清空搜索', backButtonTitle: '关闭搜索', noResultsText: '没有找到相关结果',
            footer: { selectText: '选择', selectKeyAriaLabel: '回车键', navigateText: '切换', navigateUpKeyAriaLabel: '上方向键', navigateDownKeyAriaLabel: '下方向键', closeText: '关闭', closeKeyAriaLabel: 'Esc 键' },
          },
        },
        miniSearch: { options: { tokenize: tokenizeChineseSearch, processTerm: (term) => term.toLowerCase() } },
        async _render(source, env, md) {
          if ((env as any).frontmatter?.search === false) return ''
          return md.render(source, env).replace(/<span class="wk-word-count">.*?<\/span>/g, '')
        },
      },
    },
  },
})
