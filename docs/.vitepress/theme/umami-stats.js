/** 站内统计（Umami 公开分享接口）的共享逻辑：只读，不涉及密钥 */
const SHARE_ID = 'iib1PnzFrZEe9dVR'
const UMAMI_ORIGIN = 'https://umami.lris625.top'
const CACHE_TTL = 10 * 60 * 1000

const SITE_KEY = 'qutwiki:site-stats'
const PAGE_KEY = 'qutwiki:page-stats'

export function formatNumber(value) {
  const n = Number(value) || 0
  if (n >= 10000) return `${(n / 1000).toFixed(1)}K`
  return n.toLocaleString('zh-CN')
}

/** 与 Umami 记录的 url_path 对齐：去掉查询串、hash 和结尾斜杠 */
export function normPath(path) {
  let p = String(path || '/').split(/[?#]/)[0]
  if (p.length > 1) p = p.replace(/\/+$/, '')
  return p || '/'
}

function readCache(key) {
  try {
    const raw = sessionStorage.getItem(key)
    if (!raw) return null
    const cached = JSON.parse(raw)
    if (!cached || Date.now() - cached.at > CACHE_TTL) return null
    return cached
  } catch {
    return null
  }
}

function writeCache(key, data) {
  try {
    sessionStorage.setItem(key, JSON.stringify({ at: Date.now(), ...data }))
  } catch {}
}

let sharePromise = null
function getShare() {
  if (!sharePromise) {
    sharePromise = fetch(`${UMAMI_ORIGIN}/api/share/${SHARE_ID}`).then((r) => r.json())
  }
  return sharePromise
}

/** path 为空取全站统计，传入 path 取该页统计 */
async function fetchStats(path) {
  const share = await getShare()
  const headers = {
    'x-umami-share-token': share.token,
    'x-umami-share-context': '1',
  }
  const url = new URL(`${UMAMI_ORIGIN}/api/websites/${share.websiteId}/stats`)
  url.searchParams.set('startAt', '0')
  url.searchParams.set('endAt', String(Date.now()))
  if (path) url.searchParams.set('path', path)
  const res = await fetch(url, { headers })
  if (!res.ok) throw new Error(`umami stats ${res.status}`)
  return res.json()
}

/** 全站访客与浏览量（10 分钟内复用 sessionStorage） */
export async function getSiteStats() {
  const cached = readCache(SITE_KEY)
  if (cached) return { pageviews: cached.pageviews, visitors: cached.visitors }

  const stats = await fetchStats()
  const data = { pageviews: stats.pageviews, visitors: stats.visitors }
  writeCache(SITE_KEY, data)
  return data
}

/** 单页浏览量 */
export async function getPageStats(path) {
  const key = `${PAGE_KEY}:${path}`
  const cached = readCache(key)
  if (cached) return cached.pageviews

  const stats = await fetchStats(path)
  const pageviews = Number(stats.pageviews) || 0
  writeCache(key, { pageviews })
  return pageviews
}
