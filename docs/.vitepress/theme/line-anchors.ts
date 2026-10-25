/**
 * 源文件行锚点 / 图片锚点的前端解析与高亮。
 *
 * 页面里的锚点由 `plugins/source-lines.ts` 生成：
 * - `#L42`   正文第 42 行的块（段落、列表项、表格、代码块、标题……）
 * - `#img-…` 某张图片
 */

const LINE_HASH = /^L(\d+)$/

/** 找到 hash 对应的元素；`#L42` 找不到时退回到它前面最近的一个块 */
export function resolveHashElement(hash: string): HTMLElement | null {
  let id = String(hash || '')
  if (id.startsWith('#')) id = id.slice(1)
  try {
    id = decodeURIComponent(id)
  } catch {}
  if (!id) return null

  const direct = document.getElementById(id)
  if (direct) return direct

  const matched = LINE_HASH.exec(id)
  if (!matched) return null

  const targetLine = Number(matched[1])
  let best: HTMLElement | null = null
  let bestLine = -1
  document.querySelectorAll<HTMLElement>('[data-src-line]').forEach((el) => {
    const line = Number(el.dataset.srcLine)
    if (!Number.isFinite(line) || line > targetLine) return
    if (line > bestLine) {
      best = el
      bestLine = line
    }
  })
  return best
}

/** 行锚点可能是 0 高度的 span，高亮/定位时换成它后面的块元素 */
function visualTarget(element: HTMLElement): HTMLElement {
  if (!element.classList.contains('line-anchor')) return element
  const next = element.nextElementSibling
  return next instanceof HTMLElement ? next : element
}

function isVisible(element: HTMLElement): boolean {
  const rect = element.getBoundingClientRect()
  return rect.bottom > 0 && rect.top < window.innerHeight
}

/** 跳到锚点并短暂高亮目标，用于 RAG 引用 / 外部行号链接 */
export function flashAnchor(hash: string, options: { scroll?: boolean, timeout?: number } = {}) {
  const { scroll = true, timeout = 3600 } = options
  let tries = 0

  const apply = (target: HTMLElement) => {
    target.classList.remove('line-target-flash')
    // 强制重启动画，连续点同一引用也能看到反馈
    void target.offsetWidth
    target.classList.add('line-target-flash')
    window.setTimeout(() => target.classList.remove('line-target-flash'), timeout)
  }

  const tick = () => {
    const element = resolveHashElement(hash)
    if (!element) {
      if (tries++ < 30) window.setTimeout(tick, 60)
      return
    }

    const target = visualTarget(element)
    if (scroll && !isVisible(target)) {
      target.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }
    apply(target)

    // 首次打开页面时 Vue hydration 可能替换节点，稍后再补一次高亮
    window.setTimeout(() => {
      const again = resolveHashElement(hash)
      if (again) apply(visualTarget(again))
    }, 700)
  }

  window.setTimeout(tick, 0)
}
