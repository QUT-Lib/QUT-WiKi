import { defineConfig, type DefaultTheme } from 'vitepress'
import { readdirSync, readFileSync, statSync } from 'fs'
import { resolve, extname, dirname, join } from 'path'
import { fileURLToPath } from 'url'
import taskLists from 'markdown-it-task-lists'
import { xlsxTablePlugin } from './plugins/xlsx-table'
import { flinkBlockPlugin } from './plugins/flink-block'

const __dirname = dirname(fileURLToPath(import.meta.url))
const docsRoot = resolve(__dirname, '..')
const startRoot = resolve(docsRoot, 'start')

// ---- 侧边栏自动生成 ----
// 分组名称：文件夹 -> 中文名。缺少映射会在生成时报错，提醒补充。
const directoryLabels: Record<string, string> = {
  preface: '序言',
  newstudent: '新生入学',
  'campus-life': '校园生活',
  'campus-life/study': '学习学业',
  'campus-life/systems': '校园系统',
  'campus-life/daily-life': '生活日常',
  'campus-life/qut-organization': 'QUT-组织',
  'campus-life/competition': '竞赛--战队',
  about: '关于',
}
// 顶层分组的展示顺序，未列出的目录排在最后并按名称排序。
const sectionOrder = ['preface', 'newstudent', 'campus-life', 'about']
// 子目录的展示顺序，未列出的目录排在最后并按名称排序。
const subSectionOrder: Record<string, string[]> = {
  'campus-life': ['systems', 'study', 'daily-life', 'qut-organization', 'competition'],
}

function getDirectoryLabel(relativeDir: string): string {
  const label = directoryLabels[relativeDir]
  if (!label) {
    throw new Error(`文件夹缺少中文名映射：docs/start/${relativeDir}。请在 config.ts 的 directoryLabels 中添加。`)
  }
  if (!/[\u4e00-\u9fff]/.test(label)) {
    throw new Error(`文件夹的中文名映射必须包含中文字符：docs/start/${relativeDir}。请更新 config.ts 中的 directoryLabels。`)
  }
  return label
}

// 读取 Markdown 的一级标题，跳过代码块内的伪标题。
// 优先使用 frontmatter 中的 title，其次 # 标题，最后 <h1> 标签
function extractTitle(file: string): string {
  const raw = readFileSync(file, 'utf-8')

  // 检查 frontmatter title
  const fmMatch = raw.match(/^---\s*\n([\s\S]*?)\n---/)
  if (fmMatch) {
    const titleMatch = fmMatch[1].match(/^title:\s*(.+)$/m)
    if (titleMatch) return titleMatch[1].trim().replace(/^["'](.+)["']$/, '$1')
  }

  const lines = raw.split(/\r?\n/)
  let fence: string | null = null
  for (const line of lines) {
    const fenceMatch = line.match(/^\s*(`{3,}|~{3,})/)
    if (fenceMatch) {
      const marker = fenceMatch[1][0]
      if (fence === null) fence = marker
      else if (fence === marker) fence = null
      continue
    }
    if (fence === null) {
      const heading = line.match(/^#(?!#)\s+(.+?)\s*$/)
      if (heading) return heading[1].replace(/\s+#+\s*$/, '').trim()
      const h1 = line.match(/<h1[^>]*>(.+?)<\/h1>/i)
      if (h1) return h1[1].trim()
    }
  }
  throw new Error(`Markdown 文件缺少一级标题：${file}`)
}

function extractTop(file: string): number | null {
  const raw = readFileSync(file, 'utf-8')
  const fmMatch = raw.match(/^---\s*\n([\s\S]*?)\n---/)
  if (!fmMatch) return null

  const topMatch = fmMatch[1].match(/^top:\s*(.+)$/m)
  if (!topMatch) return null

  const value = Number(topMatch[1].trim().replace(/^["'](.+)["']$/, '$1'))
  if (!Number.isInteger(value) || value < 1) {
    throw new Error(`Markdown 文件的 top 必须是从 1 开始的整数：${file}`)
  }
  return value
}

function sortMarkdownFiles<T extends { name: string, full: string, stat: ReturnType<typeof statSync> }>(a: T, b: T): number {
  const topA = extractTop(a.full)
  const topB = extractTop(b.full)
  if (topA !== null || topB !== null) {
    if (topA === null) return 1
    if (topB === null) return -1
    return topA - topB || a.stat.birthtimeMs - b.stat.birthtimeMs || a.name.localeCompare(b.name)
  }
  return a.stat.birthtimeMs - b.stat.birthtimeMs || a.name.localeCompare(b.name)
}

function hasMarkdown(dir: string): boolean {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name)
    const stat = statSync(full)
    if (stat.isDirectory()) {
      if (hasMarkdown(full)) return true
    } else if (extname(name) === '.md') {
      return true
    }
  }
  return false
}

// 目录内的条目：文件可用 frontmatter top 置顶排序，否则按创建时间从早到晚排序；子目录按名称排序并递归成组。
function buildItems(dir: string, relativeDir: string): DefaultTheme.SidebarItem[] {
  const entries = readdirSync(dir).map((name) => {
    const full = join(dir, name)
    return { name, full, stat: statSync(full) }
  })

  const items: DefaultTheme.SidebarItem[] = []

  const files = entries
    .filter((e) => e.stat.isFile() && extname(e.name) === '.md')
    .sort(sortMarkdownFiles)
  for (const file of files) {
    const base = file.name.replace(/\.md$/, '')
    const link = relativeDir ? `/start/${relativeDir}/${base}` : `/start/${base}`
    items.push({ text: extractTitle(file.full), link })
  }

  const order = subSectionOrder[relativeDir] || []
  const dirs = entries
    .filter((e) => e.stat.isDirectory() && hasMarkdown(e.full))
    .sort((a, b) => {
      const rankA = order.indexOf(a.name)
      const rankB = order.indexOf(b.name)
      const orderA = rankA === -1 ? order.length : rankA
      const orderB = rankB === -1 ? order.length : rankB
      return orderA - orderB || a.name.localeCompare(b.name)
    })
  for (const child of dirs) {
    const childRelative = relativeDir ? `${relativeDir}/${child.name}` : child.name
    items.push({
      text: getDirectoryLabel(childRelative),
      collapsed: false,
      items: buildItems(child.full, childRelative),
    })
  }

  return items
}

// 顶层：根目录 .md 作为独立条目，各文件夹按 sectionOrder 成组。
function buildStartSidebar(): DefaultTheme.SidebarItem[] {
  const entries = readdirSync(startRoot).map((name) => {
    const full = join(startRoot, name)
    return { name, full, stat: statSync(full) }
  })

  const groups: DefaultTheme.SidebarItem[] = []

  const rootFiles = entries
    .filter((e) => e.stat.isFile() && extname(e.name) === '.md')
    .sort(sortMarkdownFiles)
  for (const file of rootFiles) {
    groups.push({ text: extractTitle(file.full), link: `/start/${file.name.replace(/\.md$/, '')}` })
  }

  const dirs = entries
    .filter((e) => e.stat.isDirectory() && hasMarkdown(e.full))
    .sort((a, b) => {
      const rankA = sectionOrder.indexOf(a.name)
      const rankB = sectionOrder.indexOf(b.name)
      const orderA = rankA === -1 ? sectionOrder.length : rankA
      const orderB = rankB === -1 ? sectionOrder.length : rankB
      return orderA - orderB || a.name.localeCompare(b.name)
    })
  for (const dir of dirs) {
    groups.push({
      text: getDirectoryLabel(dir.name),
      collapsed: false,
      items: buildItems(dir.full, dir.name),
    })
  }

  return groups
}

// 顶栏三大板块：复用侧边栏自动生成的数据，与侧边栏保持同步。
function sidebarGroupToNav(group: DefaultTheme.SidebarItem): DefaultTheme.NavItem {
  const item: any = { text: group.text }
  if (group.link) item.link = group.link
  if (group.items) item.items = group.items.map(sidebarGroupToNav)
  return item
}

const majorSections = buildStartSidebar()
  .filter((g) => ['新生入学', '校园生活', '关于'].includes(g.text))
  .map(sidebarGroupToNav)

// dev 模式下监听 docs/start：仅当生成结果（结构/标题/顺序）变化时重启，
// 普通正文编辑保持 VitePress 原生 HMR，不触发重启。
function sidebarWatchPlugin() {
  const signature = () => {
    try {
      return JSON.stringify(buildStartSidebar())
    } catch (err) {
      return `ERROR:${(err as Error).message}`
    }
  }
  return {
    name: 'qutwiki-sidebar-watch',
    configureServer(server: any) {
      let last = signature()
      let timer: ReturnType<typeof setTimeout> | null = null
      const check = () => {
        if (timer) clearTimeout(timer)
        timer = setTimeout(() => {
          const next = signature()
          if (next !== last) {
            last = next
            server.restart()
          }
        }, 150)
      }
      server.watcher.add(startRoot)
      server.watcher.on('add', check)
      server.watcher.on('unlink', check)
      server.watcher.on('addDir', check)
      server.watcher.on('unlinkDir', check)
      server.watcher.on('change', check)
    },
  }
}

function countChineseChars(dir: string): number {
  let total = 0
  const entries = readdirSync(dir)
  for (const entry of entries) {
    const full = resolve(dir, entry)
    const stat = statSync(full)
    if (stat.isDirectory()) {
      if (entry === 'node_modules' || entry === '.vitepress' || entry.startsWith('.')) continue
      total += countChineseChars(full)
    } else if (extname(entry) === '.md') {
      try {
        const content = readFileSync(full, 'utf-8')
        const chinese = content.replace(/[^\u4e00-\u9fff]/g, '')
        total += chinese.length
      } catch {}
    }
  }
  return total
}

const totalK = (countChineseChars(docsRoot) / 1000).toFixed(1)

function tokenizeSearchText(text: string) {
  const tokens: string[] = []
  const parts = text.match(/[\u4e00-\u9fff]+|[a-zA-Z0-9]+/g) || []

  for (const part of parts) {
    if (/^[\u4e00-\u9fff]+$/.test(part)) {
      if (part.length === 1) {
        tokens.push(part)
        continue
      }
      for (let i = 0; i < part.length - 1; i++) {
        tokens.push(part.slice(i, i + 2))
      }
    } else {
      tokens.push(part.toLowerCase())
    }
  }

  return tokens
}

export default defineConfig({
  lang: 'zh-CN',
  title: 'QUTWiKi',
  description: '青岛理工大学 Wiki 知识库',
  lastUpdated: true,
  cleanUrls: true,
  vite: {
    envDir: resolve(docsRoot, '..'),
    plugins: [sidebarWatchPlugin()],
    build: {
      chunkSizeWarningLimit: 1100,
    },
  },
  markdown: {
    config: (md) => {
      md.use(taskLists)
      md.use(xlsxTablePlugin, docsRoot)
      md.use(flinkBlockPlugin)
      md.core.ruler.push('word_count', (state) => {
        if ((state.env as any).frontmatter?.wordCount === false) return
        const text = state.src.replace(/[^\u4e00-\u9fff]/g, '')
        const count = text.length
        if (count === 0) return
        const minutes = count < 150 ? '不到1分钟' : `约${Math.ceil(count / 350)}分钟`
        const tokens = state.tokens
        for (let i = 0; i < tokens.length; i++) {
          if (tokens[i].type === 'heading_open' && tokens[i].tag === 'h1') {
            const closeIdx = tokens.findIndex((t, j) => j > i && t.type === 'heading_close' && t.tag === 'h1')
            if (closeIdx !== -1) {
              const span = new state.Token('html_inline', '', 0)
              span.content = `<span class="word-count">${count}字 / ${minutes}</span>`
              tokens.splice(closeIdx, 0, span)
            }
            break
          }
        }
      })
      const origImg = md.renderer.rules.image || ((tokens: any, idx: any, options: any, _env: any, self: any) => self.renderToken(tokens, idx, options))
      md.renderer.rules.image = (tokens, idx, options, env, self) => {
        const token = tokens[idx]
        const alt = token.content || token.attrGet('alt') || ''
        let html = origImg(tokens, idx, options, env, self)
        if (alt) html += `<span class="img-caption">${md.utils.escapeHtml(alt)}</span>`
        return html
      }
    },
  },
  head: [
    ['link', { rel: 'icon', href: 'https://pic1.imgdb.cn/i/0349E4NqLje1oLHNowvJ4R.png' }],
    ['link', { rel: 'dns-prefetch', href: 'https://pic1.imgdb.cn' }],
    ['link', { rel: 'preconnect', href: 'https://pic1.imgdb.cn', crossorigin: '' }],
    ['script', { src: 'https://umami.lris625.top/script.js', 'data-website-id': '1f32faca-51d3-4c90-a8b0-581e3c649c92', defer: '' }],
  ],
  themeConfig: {
    nav: [
      { text: '首页', link: '/' },
      ...majorSections,
      { text: '学校地图', link: '/map' },
      { text: '友情链接', link: '/flink' }
    ],
    sidebar: {
      '/start/': buildStartSidebar(),
      '/': [
        {
          text: '站点',
          collapsed: false,
          items: [
            { text: '首页', link: '/' },
          ]
        }
      ]
    },
    socialLinks: [
      { icon: 'github', link: 'https://github.com/QUT-Lib/QUT-WiKi' }
    ],
    footer: {
      message: `基于 VitePress 构建  ·  全站共计 <span style="color:rgb(1,93,149)">${totalK}K</span> 字`,
      copyright: 'Copyright © 2026 <a href="https://github.com/QUT-Lib/QUT-WiKi" style="color:inherit;">QUTWiKi</a><br>本站内容采用 <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh-hans" style="color:inherit;">CC BY-NC-SA 4.0</a> 声明'
    },
    outline: { level: [2, 3], label: '本页导航' },
    sidebarMenuLabel: '本站目录',
    returnToTopLabel: '返回顶部',
    docFooter: { prev: '上一篇', next: '下一篇' },
    lastUpdatedText: '最后更新于',
    search: {
      provider: 'local',
      options: {
        translations: {
          button: {
            buttonText: '搜索',
            buttonAriaLabel: '搜索文档'
          },
          modal: {
            displayDetails: '显示详细列表',
            resetButtonTitle: '清空搜索',
            backButtonTitle: '关闭搜索',
            noResultsText: '没有找到相关结果',
            footer: {
              selectText: '选择',
              selectKeyAriaLabel: '回车键',
              navigateText: '切换',
              navigateUpKeyAriaLabel: '上方向键',
              navigateDownKeyAriaLabel: '下方向键',
              closeText: '关闭',
              closeKeyAriaLabel: 'Esc 键'
            }
          }
        },
        miniSearch: {
          options: {
            tokenize: tokenizeSearchText,
            processTerm: (term) => term.toLowerCase()
          }
        },
        async _render(src, env, md) {
          const html = md.render(src, env)
          if ((env as any).frontmatter?.search === false) return ''
          return html
            .replace(/<span class="word-count">.*?<\/span>/g, '')
            .replace(/<(strong|b|em|i|code)(\s[^>]*)?>/g, ' $&')
            .replace(/<\/(strong|b|em|i|code)>/g, '$& ')
        }
      }
    }
  }
})
