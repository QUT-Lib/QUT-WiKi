import { reactive } from 'vue'

export const twikooEnvId = import.meta.env.VITE_TWIKOO_ENV_ID || ''

const RATING_RE = /\[rating:([1-5])\]/
const PAGE_SIZE = 100
const MAX_PAGES = 5

/* 每条美食的评分聚合：{ [id]: { sum, count, avg, loaded, loading } } */
export const ratingState = reactive({})

/* 当前访客自己打过的分（本地记录，用于回显与防重复提交） */
export const myRatings = reactive(readStoredRatings())

function readStoredRatings() {
  const result = {}
  if (typeof window === 'undefined') return result
  try {
    const raw = window.localStorage.getItem('qutwiki:food-ratings')
    if (raw) Object.assign(result, JSON.parse(raw))
  } catch {}
  return result
}

export function setMyRating(id, value) {
  const rating = Number(value) || 0
  if (rating > 0) myRatings[id] = rating
  else delete myRatings[id]
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem('qutwiki:food-ratings', JSON.stringify(myRatings))
  } catch {}
}

/* 每条美食在 Twikoo 中占用的页面路径，作为评论与评分的唯一标识 */
export function foodUrl(id) {
  return `/food/${id}`
}

function idFromUrl(url) {
  const match = String(url || '').match(/\/food\/([^/?#]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

export function parseRating(text) {
  const match = String(text || '').match(RATING_RE)
  return match ? Number(match[1]) : null
}

export function avgText(state) {
  if (!state || !state.count) return ''
  return state.avg.toFixed(1)
}

function applyStats(id, stats) {
  const state = ratingState[id] || (ratingState[id] = { sum: 0, count: 0, avg: 0, loaded: false, loading: false })
  state.sum = stats.sum
  state.count = stats.count
  state.avg = stats.count ? stats.sum / stats.count : 0
  state.loaded = true
  state.loading = false
  return state
}

let twikooModule = null

export async function getTwikoo() {
  if (!twikooModule) twikooModule = await import('twikoo')
  return twikooModule
}

function chunk(list, size) {
  const chunks = []
  for (let index = 0; index < list.length; index += size) {
    chunks.push(list.slice(index, index + size))
  }
  return chunks
}

async function loadChunk(ids) {
  const urls = ids.map(foodUrl)
  const totals = new Map(ids.map((id) => [id, { sum: 0, count: 0 }]))
  const seen = new Set()

  const twikoo = await getTwikoo()
  for (let page = 1; page <= MAX_PAGES; page++) {
    const list = await twikoo.getRecentComments({
      envId: twikooEnvId,
      urls,
      pageSize: PAGE_SIZE,
      includeReply: false,
      page,
    })
    if (!Array.isArray(list) || !list.length) break

    let added = 0
    for (const item of list) {
      if (!item || seen.has(item.id)) continue
      seen.add(item.id)
      added++
      const id = idFromUrl(item.url)
      if (!id || !totals.has(id)) continue
      const rating = parseRating(item.commentText || item.comment)
      if (!rating) continue
      const total = totals.get(id)
      total.sum += rating
      total.count++
    }

    if (list.length < PAGE_SIZE || added === 0) break
  }

  for (const [id, stats] of totals) applyStats(id, stats)
}

/**
 * 拉取指定美食的评分聚合。
 * 首次调用会标记 loaded；force 为 true 时始终重新请求（用于弹窗内刷新）。
 */
export async function loadRatings(ids, { force = false } = {}) {
  if (!twikooEnvId) return
  const pending = [...new Set(ids)].filter((id) => id && (force || !ratingState[id]?.loaded))
  if (!pending.length) return

  for (const id of pending) {
    const state = ratingState[id] || (ratingState[id] = { sum: 0, count: 0, avg: 0, loaded: false, loading: false })
    state.loading = true
  }

  try {
    for (const group of chunk(pending, 40)) {
      await loadChunk(group)
    }
  } catch (error) {
    console.error('美食评分加载失败：', error)
    for (const id of pending) {
      const state = ratingState[id]
      if (state) {
        state.loading = false
        if (!state.loaded) state.loaded = true
      }
    }
  }
}

/* ============ Twikoo 实例增强 ============ */

export function findVueRoot(element) {
  if (!element) return null
  if (element.__vue__) return element.__vue__
  for (const node of element.querySelectorAll('*')) {
    if (node.__vue__) return node.__vue__
  }
  return null
}

function findComponent(root, predicate) {
  if (!root) return null
  const stack = [root]
  const seen = new Set()
  while (stack.length) {
    const component = stack.pop()
    if (!component || seen.has(component)) continue
    seen.add(component)
    if (predicate(component)) return component
    if (Array.isArray(component.$children)) stack.push(...component.$children)
  }
  return null
}

function findSubmitComponent(element) {
  const root = findVueRoot(element)
  return findComponent(root, (component) =>
    typeof component.send === 'function' && typeof component.comment === 'string'
  )
}

/**
 * 在提交前把 [rating:n] 拼进评论内容，交由 Twikoo 正常渲染与存储。
 * 仅对主评论生效，回复不重复打分。
 */
export function injectRating(element, getRating) {
  const submit = findSubmitComponent(element)
  if (!submit || submit.__qutFoodPatched) return false

  // 注意：Vue 已在初始化时把 methods 绑定到实例，这里替换后的函数拿不到 this，
  // 必须通过闭包里的组件实例读写状态。
  const component = submit
  const original = component.send.bind(component)
  component.send = async function patchedSend() {
    const rating = getRating()
    const raw = String(component.comment || '').trim()
    if (rating > 0 && raw && !component.replyId && !RATING_RE.test(raw)) {
      component.comment = `[rating:${rating}] ${raw}`
    }
    return original()
  }
  component.__qutFoodPatched = true
  return true
}

/**
 * 只提交评分，不携带文字评论。
 * 仍调用 Twikoo 自己的 send 方法，因此昵称、邮箱、验证码和反垃圾配置继续生效。
 */
export async function submitRatingOnly(element, getRating) {
  const submit = findSubmitComponent(element)
  if (!submit) return { ok: false, reason: 'unavailable' }
  if (submit.isSending) return { ok: false, reason: 'sending' }
  if (submit.replyId) return { ok: false, reason: 'reply' }
  if (!submit.isMetaValid) return { ok: false, reason: 'meta' }

  const rating = Number(getRating())
  if (rating < 1 || rating > 5) return { ok: false, reason: 'rating' }

  const draft = String(submit.comment || '')
  if (draft.trim()) return { ok: false, reason: 'comment' }

  const original = submit.send.bind(submit)
  submit.comment = `[rating:${rating}]`
  submit.errorMessage = ''
  try {
    await original()
    if (submit.errorMessage) return { ok: false, reason: 'submit', message: submit.errorMessage }
    return { ok: true }
  } finally {
    // Rating-only submission should not leave the internal marker in the editor.
    submit.comment = draft
  }
}

/**
 * 把渲染出来的 [rating:n] 文本替换成星级徽章，避免原始标记影响阅读。
 */
export function decorateRatings(element) {
  if (!element || typeof document === 'undefined') return
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT)
  const targets = []
  while (walker.nextNode()) {
    const node = walker.currentNode
    if (!node.nodeValue || !RATING_RE.test(node.nodeValue)) continue
    if (node.parentElement?.classList.contains('qut-food-rating-badge')) continue
    targets.push(node)
  }

  for (const node of targets) {
    const match = node.nodeValue.match(RATING_RE)
    if (!match) continue
    const value = Number(match[1])
    const index = node.nodeValue.indexOf(match[0])
    const rest = node.nodeValue.slice(0, index) + node.nodeValue.slice(index + match[0].length)

    const badge = document.createElement('span')
    badge.className = 'qut-food-rating-badge'
    badge.title = `评分 ${value} / 5`
    badge.textContent = '★'.repeat(value) + '☆'.repeat(5 - value)

    const parent = node.parentNode
    if (!parent) continue
    if (rest.trim()) {
      parent.insertBefore(document.createTextNode(rest), node)
    }
    parent.insertBefore(badge, node)
    parent.removeChild(node)
  }
}

export function destroyTwikoo(element) {
  if (!element) return
  const root = findVueRoot(element)
  if (root && typeof root.$destroy === 'function') {
    try { root.$destroy() } catch {}
  }
  element.innerHTML = ''
}

export function shortDate(timestamp) {
  if (!timestamp) return ''
  const date = new Date(Number(timestamp))
  if (Number.isNaN(date.getTime())) return ''
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}
