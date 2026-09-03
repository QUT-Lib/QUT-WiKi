import type MarkdownIt from 'markdown-it'
import type StateCore from 'markdown-it/lib/rules_core/state_core.mjs'
import { safeLink } from './link.ts'

export interface FlinkItem {
  name: string
  link: string
  avatar?: string
  siteshot?: string
  desc?: string
}

export interface WordCountOptions {
  enabled?: boolean
  frontmatterKey?: string
  wordsPerMinute?: number
  format?: (count: number, minutes: number) => string
}

export interface WikiMarkdownOptions {
  imageCaptions?: boolean
  flinks?: boolean
  wordCount?: boolean | WordCountOptions
}

const FLINK_OPEN = /^<flink(\s[^>]*)?>\s*$/
const FLINK_CLOSE = /^<\/flink\s*>\s*$/
const FLINK_ITEM = /^-\s+([\w-]+)\s*:\s*(.*)$/
const FLINK_VALUE = /^([\w-]+)\s*:\s*(.*)$/

function parseFlinks(block: string): FlinkItem[] {
  const inner = block.replace(/^<flink(\s[^>]*)?>\s*\r?\n/, '').replace(/\r?\n\s*<\/flink\s*>\s*$/, '')
  const items: Record<string, string>[] = []
  let current: Record<string, string> | undefined
  for (const raw of inner.split(/\r?\n/)) {
    const line = raw.trim()
    if (!line) continue
    const item = line.match(FLINK_ITEM)
    if (item) {
      current = { [item[1]]: item[2] }
      items.push(current)
      continue
    }
    const value = line.match(FLINK_VALUE)
    if (value && current) current[value[1]] = value[2]
  }
  return items.filter((item) => item.name && safeLink(item.link)).map((item) => ({
    name: item.name,
    link: item.link,
    avatar: item.avatar,
    siteshot: item.siteshot,
    desc: item.desc ?? item.descr,
  }))
}

export function flinkBlockPlugin(md: MarkdownIt) {
  md.block.ruler.before('html_block', 'wiki_kit_flink_block', (state, startLine, endLine, silent) => {
    const start = state.bMarks[startLine] + state.tShift[startLine]
    if (!FLINK_OPEN.test(state.src.slice(start, state.eMarks[startLine]))) return false
    let end = startLine + 1
    while (end < endLine) {
      const pos = state.bMarks[end] + state.tShift[end]
      if (FLINK_CLOSE.test(state.src.slice(pos, state.eMarks[end]))) break
      end++
    }
    if (end === endLine) return false
    if (silent) return true
    let block = ''
    for (let line = startLine; line <= end; line++) block += `${state.src.slice(state.bMarks[line], state.eMarks[line])}\n`
    const items = parseFlinks(block)
    if (!items.length) return false
    const json = JSON.stringify(items).replace(/&/g, '\\u0026').replace(/</g, '\\u003c').replace(/'/g, '\\u0027')
    const token = state.push('html_block', '', 0)
    token.map = [startLine, end + 1]
    token.content = `<Flinks :links='${json}' />`
    state.line = end + 1
    return true
  })
}

export function imageCaptionPlugin(md: MarkdownIt) {
  const renderImage = md.renderer.rules.image ?? ((tokens, index, options, _env, self) => self.renderToken(tokens, index, options))
  md.renderer.rules.image = (tokens, index, options, env, self) => {
    const alt = tokens[index].content || tokens[index].attrGet('alt') || ''
    const image = renderImage(tokens, index, options, env, self)
    return alt ? `${image}<span class="wk-img-caption">${md.utils.escapeHtml(alt)}</span>` : image
  }
}

export function wordCountPlugin(md: MarkdownIt, options: WordCountOptions = {}) {
  const key = options.frontmatterKey ?? 'wordCount'
  const speed = options.wordsPerMinute ?? 350
  const format = options.format ?? ((count, minutes) => `${count}字 / ${minutes < 1 ? '不到1分钟' : `约${Math.ceil(minutes)}分钟`}`)
  md.core.ruler.push('wiki_kit_word_count', (state: StateCore) => {
    if ((state.env as any).frontmatter?.[key] === false) return
    const count = (state.src.match(/[\u4e00-\u9fff]/g) ?? []).length
    if (!count) return
    const heading = state.tokens.findIndex((token) => token.type === 'heading_open' && token.tag === 'h1')
    const close = state.tokens.findIndex((token, index) => index > heading && token.type === 'heading_close' && token.tag === 'h1')
    if (heading < 0 || close < 0) return
    const token = new state.Token('html_inline', '', 0)
    token.content = `<span class="wk-word-count">${md.utils.escapeHtml(format(count, count / speed))}</span>`
    state.tokens.splice(close, 0, token)
  })
}

export function installWikiMarkdown(md: MarkdownIt, options: WikiMarkdownOptions = {}) {
  if (options.flinks !== false) md.use(flinkBlockPlugin)
  if (options.imageCaptions !== false) md.use(imageCaptionPlugin)
  if (options.wordCount !== false) md.use(wordCountPlugin, typeof options.wordCount === 'object' ? options.wordCount : {})
}
