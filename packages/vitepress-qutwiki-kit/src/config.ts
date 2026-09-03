import { extname, join } from 'node:path'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import type { DefaultTheme } from 'vitepress'

export interface ContentTreeOptions {
  root: string
  routeBase: string
  directoryLabels?: Record<string, string>
  sectionOrder?: string[]
  subSectionOrder?: Record<string, string[]>
  collapsed?: boolean
  requireDirectoryLabels?: boolean
}

function frontmatterValue(source: string, key: string): string | undefined {
  const match = source.match(/^---\s*\r?\n([\s\S]*?)\r?\n---/)
  return match?.[1].match(new RegExp(`^${key}:\\s*(.+)$`, 'm'))?.[1].trim().replace(/^['"]|['"]$/g, '')
}

function extractTitle(file: string): string {
  const source = readFileSync(file, 'utf8')
  const title = frontmatterValue(source, 'title')
  if (title) return title
  let fence: string | undefined
  for (const line of source.split(/\r?\n/)) {
    const marker = line.match(/^\s*(`{3,}|~{3,})/)?.[1][0]
    if (marker) {
      fence = fence === marker ? undefined : fence ?? marker
      continue
    }
    if (fence) continue
    const markdown = line.match(/^#(?!#)\s+(.+?)\s*$/)?.[1].replace(/\s+#+\s*$/, '').trim()
    if (markdown) return markdown
    const html = line.match(/<h1[^>]*>(.+?)<\/h1>/i)?.[1].trim()
    if (html) return html
  }
  throw new Error(`Markdown file has no level-one title: ${file}`)
}

function order(file: string): number | undefined {
  const value = frontmatterValue(readFileSync(file, 'utf8'), 'top') ?? frontmatterValue(readFileSync(file, 'utf8'), 'order')
  if (value === undefined) return undefined
  const number = Number(value)
  if (!Number.isInteger(number) || number < 1) throw new Error(`Frontmatter order/top must be a positive integer: ${file}`)
  return number
}

function hasMarkdown(directory: string): boolean {
  return readdirSync(directory).some((name) => {
    const file = join(directory, name)
    return statSync(file).isDirectory() ? hasMarkdown(file) : extname(name) === '.md'
  })
}

export function createContentTree(options: ContentTreeOptions): DefaultTheme.SidebarItem[] {
  const base = `/${options.routeBase.replace(/^\/+|\/+$/g, '')}/`
  const label = (relative: string) => {
    const configured = options.directoryLabels?.[relative]
    if (!configured && options.requireDirectoryLabels) throw new Error(`Missing directory label: ${relative}`)
    return configured ?? relative.split('/').at(-1)!
  }
  const sortFiles = (a: string, b: string) => {
    const first = order(a)
    const second = order(b)
    return (first ?? Number.MAX_SAFE_INTEGER) - (second ?? Number.MAX_SAFE_INTEGER) || a.localeCompare(b)
  }
  const build = (directory: string, relative = ''): DefaultTheme.SidebarItem[] => {
    const entries = readdirSync(directory).map((name) => ({ name, file: join(directory, name), stat: statSync(join(directory, name)) }))
    const files = entries.filter((entry) => entry.stat.isFile() && extname(entry.name) === '.md').sort((a, b) => sortFiles(a.file, b.file))
    const rank = relative ? options.subSectionOrder?.[relative] ?? [] : options.sectionOrder ?? []
    const directories = entries.filter((entry) => entry.stat.isDirectory() && hasMarkdown(entry.file)).sort((a, b) => {
      const aRank = rank.indexOf(a.name)
      const bRank = rank.indexOf(b.name)
      return (aRank < 0 ? rank.length : aRank) - (bRank < 0 ? rank.length : bRank) || a.name.localeCompare(b.name)
    })
    return [
      ...files.map((entry) => ({ text: extractTitle(entry.file), link: `${base}${relative ? `${relative}/` : ''}${entry.name.slice(0, -3)}` })),
      ...directories.map((entry) => {
        const child = relative ? `${relative}/${entry.name}` : entry.name
        return { text: label(child), collapsed: options.collapsed ?? false, items: build(entry.file, child) }
      }),
    ]
  }
  return build(options.root)
}

export function createContentTreeWatcher(root: string, build: () => unknown) {
  return {
    name: 'vitepress-qutwiki-kit-content-tree',
    configureServer(server: any) {
      let signature = JSON.stringify(build())
      let timer: ReturnType<typeof setTimeout> | undefined
      const check = () => {
        clearTimeout(timer)
        timer = setTimeout(() => {
          const next = JSON.stringify(build())
          if (next !== signature) {
            signature = next
            server.restart()
          }
        }, 150)
      }
      server.watcher.add(root)
      for (const event of ['add', 'unlink', 'addDir', 'unlinkDir', 'change']) server.watcher.on(event, check)
    },
  }
}

export function tokenizeChineseSearch(text: string): string[] {
  return (text.match(/[\u4e00-\u9fff]+|[a-zA-Z0-9]+/g) ?? []).flatMap((part) => {
    if (!/^[\u4e00-\u9fff]+$/.test(part)) return [part.toLowerCase()]
    if (part.length === 1) return [part]
    return Array.from({ length: part.length - 1 }, (_, index) => part.slice(index, index + 2))
  })
}

export function sidebarItemToNav(item: DefaultTheme.SidebarItem): DefaultTheme.NavItem {
  return { text: item.text, ...(item.link ? { link: item.link } : {}), ...(item.items ? { items: item.items.map(sidebarItemToNav) } : {}) } as DefaultTheme.NavItem
}
