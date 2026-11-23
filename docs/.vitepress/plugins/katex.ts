import type MarkdownIt from 'markdown-it'
import katex from 'katex'

/**
 * KaTeX 数学公式插件。
 *
 * 支持：
 * - `$...$` 行内公式
 * - `$$...$$` 块级公式（可单行，也可跨多行）
 * - `\$` 转义成普通美元符号（由 markdown-it 的 escape 规则先处理）
 *
 * 说明：没有直接用 `markdown-it-katex`，因为它依赖的 katex 是 0.6.0（随包
 * 嵌套安装），和本站安装的 katex 0.19 在 HTML 结构/CSS 上对不上。这里直接
 * 调用新版 katex，渲染结果与主题引入的 katex.min.css 完全匹配。
 */

export interface KatexPluginOptions {
  /** 公式语法出错时是否中断渲染，默认 false（渲染成红色错误提示，不中断构建） */
  throwOnError?: boolean
  /** KaTeX 严格模式，默认 'ignore'，避免中文/Unicode 公式刷构建日志 */
  strict?: boolean | 'ignore' | 'warn' | 'error'
  /** 自定义宏，如 { '\\R': '\\mathbb{R}' } */
  macros?: Record<string, string>
  /** 额外传给 katex.renderToString 的选项 */
  katexOptions?: Record<string, unknown>
}

type TokenState = {
  src: string
  pos: number
  posMax: number
  pending: string
  push: (type: string, tag: string, nesting: number) => any
}

type BlockState = {
  src: string
  bMarks: number[]
  eMarks: number[]
  tShift: number[]
  blkIndent: number
  line: number
  getLines: (begin: number, end: number, indent: number, keepLastLF: boolean) => string
  push: (type: string, tag: string, nesting: number) => any
}

function isValidDelim(state: TokenState, pos: number) {
  const prevChar = pos > 0 ? state.src.charCodeAt(pos - 1) : -1
  const nextChar = pos + 1 <= state.posMax ? state.src.charCodeAt(pos + 1) : -1

  let canOpen = true
  let canClose = true

  // 前一个字符是空格/制表符，或后面紧跟数字时，不能作为结束符
  if (prevChar === 0x20 || prevChar === 0x09 || (nextChar >= 0x30 && nextChar <= 0x39)) {
    canClose = false
  }
  // 后面紧跟空格/制表符时，不能作为起始符
  if (nextChar === 0x20 || nextChar === 0x09) {
    canOpen = false
  }

  return { canOpen, canClose }
}

/** 行内公式：$...$ */
function mathInline(state: TokenState, silent: boolean) {
  if (state.src[state.pos] !== '$') return false

  const startDelim = isValidDelim(state, state.pos)
  if (!startDelim.canOpen) {
    if (!silent) state.pending += '$'
    state.pos += 1
    return true
  }

  // 从起始符之后找配对的 $，跳过被反斜杠转义的 $
  const start = state.pos + 1
  let match = start
  while ((match = state.src.indexOf('$', match)) !== -1) {
    let pos = match - 1
    while (state.src[pos] === '\\') pos -= 1
    // 反斜杠数量为偶数（含 0）时才是真正的结束符
    if ((match - pos) % 2 === 1) break
    match += 1
  }

  // 没找到结束符，$ 当普通文本输出
  if (match === -1) {
    if (!silent) state.pending += '$'
    state.pos = start
    return true
  }

  // 空公式（$$）不解析
  if (match - start === 0) {
    if (!silent) state.pending += '$$'
    state.pos = start + 1
    return true
  }

  const endDelim = isValidDelim(state, match)
  if (!endDelim.canClose) {
    if (!silent) state.pending += '$'
    state.pos = start
    return true
  }

  if (!silent) {
    const token = state.push('math_inline', 'math', 0)
    token.markup = '$'
    token.content = state.src.slice(start, match)
  }

  state.pos = match + 1
  return true
}

/** 块级公式：$$ ... $$（支持跨行） */
function mathBlock(state: BlockState, start: number, end: number, silent: boolean) {
  let pos = state.bMarks[start] + state.tShift[start]
  let max = state.eMarks[start]

  if (pos + 2 > max) return false
  if (state.src.slice(pos, pos + 2) !== '$$') return false

  pos += 2
  let firstLine = state.src.slice(pos, max)

  if (silent) return true

  let found = false
  let lastLine = ''
  let next = start

  if (firstLine.trim().slice(-2) === '$$') {
    // 单行写法：$$ x = 1 $$
    firstLine = firstLine.trim().slice(0, -2)
    found = true
  }

  for (; !found; ) {
    next += 1
    if (next >= end) break

    pos = state.bMarks[next] + state.tShift[next]
    max = state.eMarks[next]

    if (pos < max && state.tShift[next] < state.blkIndent) break

    if (state.src.slice(pos, max).trim().slice(-2) === '$$') {
      const lastPos = state.src.slice(0, max).lastIndexOf('$$')
      lastLine = state.src.slice(pos, lastPos)
      found = true
    }
  }

  state.line = next + 1

  const token = state.push('math_block', 'math', 0)
  token.block = true
  token.content =
    (firstLine && firstLine.trim() ? firstLine + '\n' : '') +
    state.getLines(start + 1, next, state.tShift[start], true) +
    (lastLine && lastLine.trim() ? lastLine : '')
  token.map = [start, state.line]
  token.markup = '$$'
  return true
}

export function katexPlugin(md: MarkdownIt, options: KatexPluginOptions = {}) {
  const {
    throwOnError = false,
    strict = 'ignore',
    macros,
    katexOptions,
  } = options

  const render = (latex: string, displayMode: boolean) =>
    katex.renderToString(latex, {
      throwOnError,
      strict,
      ...(macros ? { macros } : {}),
      ...katexOptions,
      displayMode,
    })

  const renderInline: any = (tokens: any[], idx: number) => render(tokens[idx].content, false)
  const renderBlock: any = (tokens: any[], idx: number) => {
    return `<div class="katex-block">${render(tokens[idx].content, true)}</div>\n`
  }

  md.inline.ruler.after('escape', 'math_inline', mathInline)
  md.block.ruler.after('blockquote', 'math_block', mathBlock, {
    alt: ['paragraph', 'reference', 'blockquote', 'list'],
  } as any)

  md.renderer.rules.math_inline = renderInline
  md.renderer.rules.math_block = renderBlock
}

export default katexPlugin
