import type MarkdownIt from 'markdown-it'

/**
 * 给正文里的每个块级元素标上源文件行号，生成可以直接跳转的 `#L<行号>` 锚点。
 *
 * 为什么需要：
 * - VitePress 只会给标题生成锚点，站内搜索/RAG 引用只能跳到小节开头；
 * - 这里为段落、列表项、表格、代码块、标题等也补上 `id="L42"`，
 *   外链或前端路由跳 `#L42` 时就能落到具体那一行；
 * - 同时写入 `data-src-line`，跳转后可以用来高亮目标块。
 *
 * 行号与 RAG 语料的 `line_start` 完全一致（1 起算、含 frontmatter 的源文件行号）。
 */

/** 可以直接把 id 写到元素上的块级 token */
const ID_BLOCKS = new Set([
  'paragraph_open',
  'list_item_open',
  'table_open',
  'tr_open',
  'hr',
])

/**
 * 自身不渲染属性或属性会落到子元素上的 token：
 * 在它前面插入一个 0 高度的 span 作为锚点。
 */
const SPAN_BLOCKS = new Set([
  'heading_open',
  'fence',
  'code_block',
  'html_block',
])

/** 与 extract_corpus.py 的 line_offset 保持一致 */
export function frontmatterLineOffset(src: string): number {
  const lines = String(src || '').split('\n')
  if (lines[0]?.trim() !== '---') return 1
  for (let i = 1; i < Math.min(lines.length, 100); i++) {
    if (lines[i].trim() === '---' || lines[i].trim() === '...') return i + 2
  }
  return 1
}

/**
 * FNV-1a 32 位哈希，用来给图片生成稳定的 `img-<hash>` 前缀。
 * Python 端 `extract_corpus.fnv1a32` 使用同一实现，两边必须保持一致。
 */
export function fnv1a32(value: string): string {
  let hash = 0x811c9dc5
  for (let i = 0; i < value.length; i++) {
    hash ^= value.charCodeAt(i)
    hash = Math.imul(hash, 0x01000193)
  }
  return (hash >>> 0).toString(16).padStart(8, '0')
}

/** 匹配 Markdown 图片语法，用来反推图片在源文件中的行号 */
const INLINE_IMAGE_RE = /!\[[^\]]*\]\(([^)\s]+)/g

export function sourceLinesPlugin(md: MarkdownIt) {
  // 包住 md.parse，先算好 frontmatter 占用的行数，再交给 VitePress 自己的
  // frontmatter 插件（它会先剥掉 frontmatter，token.map 因此是正文内行号）。
  const parse = md.parse.bind(md)
  md.parse = ((src: string, env?: Record<string, unknown>) => {
    if (env) {
      const bag = env as Record<string, unknown>
      bag.__srcLineOffset = frontmatterLineOffset(src)
      bag.__imageIds = new Set<string>()
    }
    return parse(src, env as never)
  }) as typeof md.parse

  md.core.ruler.push('source_line_anchors', (state: any) => {
    const offset = Number(state.env?.__srcLineOffset) || 1
    const imageIds: Set<string> = state.env?.__imageIds || new Set<string>()
    const used = new Set<number>()
    const tokens: any[] = []

    for (const token of state.tokens) {
      // inline token 里的图片：按 Markdown 原文反推行号，生成 #img-<hash>-<行号>。
      // 同一图片在页面里出现多次时行号不同，链接不会指错位置。
      if (token.type === 'inline' && token.map && token.children?.some((child: any) => child.type === 'image')) {
        const matches: { src: string, index: number }[] = []
        INLINE_IMAGE_RE.lastIndex = 0
        let matched: RegExpExecArray | null
        while ((matched = INLINE_IMAGE_RE.exec(token.content || ''))) {
          matches.push({ src: matched[1], index: matched.index })
        }
        let imageIndex = 0
        for (const child of token.children) {
          if (child.type !== 'image') continue
          const info = matches[imageIndex++]
          const src = child.attrGet('src') || info?.src || ''
          if (!src) continue
          const before = info ? String(token.content).slice(0, info.index) : ''
          const line = Number(token.map[0]) + offset + (before.match(/\n/g)?.length || 0)
          let id = `img-${fnv1a32(src)}-${line}`
          let suffix = 2
          while (imageIds.has(id)) id = `img-${fnv1a32(src)}-${line}-${suffix++}`
          imageIds.add(id)
          child.attrSet('id', id)
          child.attrSet('data-src-line', String(line))
        }
      }

      const map = token.map
      if (map && map.length) {
        const line = Number(map[0]) + offset
        if (Number.isFinite(line) && line > 0) {
          if (!used.has(line) && ID_BLOCKS.has(token.type)) {
            if (!token.attrGet('id')) token.attrSet('id', `L${line}`)
            token.attrSet('data-src-line', String(line))
            used.add(line)
          } else if (!used.has(line) && SPAN_BLOCKS.has(token.type)) {
            const anchor = new state.Token('html_block', '', 0)
            anchor.content =
              `<span class="line-anchor" id="L${line}" data-src-line="${line}" aria-hidden="true"></span>`
            tokens.push(anchor)
            if (token.type === 'heading_open') token.attrSet('data-src-line', String(line))
            used.add(line)
          } else if (token.type === 'heading_open' || ID_BLOCKS.has(token.type)) {
            // 同一行已经由更合适的元素占用了 id，这里只保留 data 属性
            token.attrSet('data-src-line', String(line))
          }
        }
      }
      tokens.push(token)
    }

    state.tokens = tokens
  })
}
