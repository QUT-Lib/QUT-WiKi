import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitepress'
import { createContentTree, createContentTreeWatcher, sidebarItemToNav, tokenizeChineseSearch } from 'vitepress-qutwiki-kit/config'
import { installWikiMarkdown } from 'vitepress-qutwiki-kit/markdown'
import { site } from './site'

const currentDirectory = dirname(fileURLToPath(import.meta.url))
const docsRoot = resolve(currentDirectory, '..')
const guideRoot = resolve(docsRoot, 'guide')
const buildGuide = () => createContentTree({
  root: guideRoot,
  routeBase: '/guide/',
  directoryLabels: site.directoryLabels,
  sectionOrder: site.sectionOrder,
})

export default defineConfig({
  lang: 'zh-CN',
  title: site.title,
  description: site.description,
  cleanUrls: true,
  lastUpdated: true,
  head: [['link', { rel: 'icon', href: '/favicon.svg', type: 'image/svg+xml' }]],
  vite: { plugins: [createContentTreeWatcher(guideRoot, buildGuide)] },
  markdown: { config: (md) => installWikiMarkdown(md) },
  themeConfig: {
    nav: [{ text: '首页', link: '/' }, ...buildGuide().map(sidebarItemToNav)],
    sidebar: { '/guide/': buildGuide() },
    socialLinks: [{ icon: 'github', link: site.repository }],
    search: {
      provider: 'local',
      options: {
        miniSearch: { options: { tokenize: tokenizeChineseSearch, processTerm: (term) => term.toLowerCase() } },
        async _render(source, env, md) {
          if ((env as any).frontmatter?.search === false) return ''
          return md.render(source, env).replace(/<span class="wk-word-count">.*?<\/span>/g, '')
        },
      },
    },
  },
})
