// 图床资源批量抓取 / 精确替换工具
//
// 设计目标：适用于任意 VitePress（及一般 Markdown）文档仓库，
// 换一个站只需要改下面的 SRC_HOSTS 即可，无需其它适配。
//
// 用法（也可用等价的 npm 脚本 images:download / images:rewrite / images:check）：
//   node docs/scripts/images.mjs download [--dry] [--concurrency 8]
//   node docs/scripts/images.mjs rewrite  [--dry]
//   node docs/scripts/images.mjs check    [--concurrency 8]
//
// 依赖：Node 18+（内置 fetch），无第三方依赖。
// 详细说明见 docs/start/about/features.md 第九节。

import { mkdir, readFile, writeFile, readdir } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { existsSync } from 'node:fs'
import { dirname, join, resolve, extname } from 'node:path'
import { fileURLToPath } from 'node:url'

// ──────────────────────────────────────────────────────────────
// 配置区：迁移到别的仓库时，通常只需要改这一段
// ──────────────────────────────────────────────────────────────

// 站点根目录（docs 的上一级）
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')

// 扫描的文档目录
const SCAN_DIRS = ['docs']

// 需要抓取的图床域名（可写多个）。只处理这些域名的图片。
const SRC_HOSTS = ['pic1.imgdb.cn', 'pic.imgdb.cn']

// 下载后本地存放目录，会被原样复制进构建产物
const ASSET_DIR = join(ROOT, 'docs', 'public', 'images')

// 替换后使用的 URL 前缀。本地镜像的公开访问路径。
// 用根路径前缀（/images）可以让换域名/换仓库时完全不用改内容。
const DEST_PREFIX = '/images'

// 只匹配带这些扩展名的链接
const IMAGE_EXT = '(?:png|jpe?g|gif|webp|svg|bmp|avif|ico|tiff?)'

// 匹配 Markdown/HTML 中任意绝对图片 URL
const URL_RE = new RegExp(`https?://[^\\s"'\\)<>\\]]+\\.${IMAGE_EXT}(?:\\?[^\\s"'\\)<>\\]]*)?`, 'gi')

// ──────────────────────────────────────────────────────────────
// 通用工具
// ──────────────────────────────────────────────────────────────

const args = process.argv.slice(2)
const command = args[0]
const DRY = args.includes('--dry')
const CONCURRENCY = Number(getArg('--concurrency')) || 8

function getArg(name) {
  const i = args.indexOf(name)
  return i !== -1 ? args[i + 1] : undefined
}

function log(...a) {
  console.log('[images]', ...a)
}

async function walk(dir, out = []) {
  let entries
  try {
    entries = await readdir(dir, { withFileTypes: true })
  } catch {
    return out
  }
  for (const e of entries) {
    if (e.isDirectory()) {
      // 跳过依赖 / 版本库 / 构建产物与缓存，避免重复处理
      if (['node_modules', 'dist', 'cache', 'vendor'].includes(e.name) || e.name.startsWith('.git')) continue
      await walk(join(dir, e.name), out)
    } else if (/\.(md|markdown|vue|html|ts|js|mjs|json|ya?ml)$/i.test(e.name)) {
      out.push(join(dir, e.name))
    }
  }
  return out
}

// 收集全仓库的图片 URL -> 出现位置
async function collect() {
  const files = []
  for (const d of SCAN_DIRS) files.push(...await walk(join(ROOT, d)))

  const hits = new Map()
  for (const file of files) {
    const src = await readFile(file, 'utf8')
    const urls = src.match(URL_RE) || []
    for (const url of urls) {
      const host = new URL(url).host
      if (!SRC_HOSTS.includes(host)) continue
      if (!hits.has(url)) hits.set(url, [])
      hits.get(url).push(file)
    }
  }
  return hits
}

// URL -> 相对存储路径：host/去重后的路径，保留文件名与扩展名
function urlToRelPath(url) {
  const u = new URL(url)
  const ext = extname(u.pathname).toLowerCase() || '.bin'
  // 路径形如 /i/0349E4NqLje1oLHNowvJ4R.png → 取 basename 作文件名
  const base = decodeURIComponent(u.pathname.split('/').filter(Boolean).pop() || '')
  const safe = base.replace(/[^\w.-]+/g, '_') || createHash('md5').update(url).digest('hex') + ext
  return join(u.host, safe)
}

async function downloadOne(url, rel) {
  const dest = join(ASSET_DIR, rel)
  if (existsSync(dest)) return { url, rel, skipped: true }

  await mkdir(dirname(dest), { recursive: true })
  const res = await fetch(url, {
    headers: { 'User-Agent': 'Mozilla/5.0 (compatible; doc-image-mirror/1.0)' },
    redirect: 'follow',
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const buf = Buffer.from(await res.arrayBuffer())
  if (DRY) return { url, rel, bytes: buf.length, dry: true }
  await writeFile(dest, buf)
  return { url, rel, bytes: buf.length }
}

async function pool(items, limit, fn) {
  const results = []
  let i = 0
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (i < items.length) {
      const idx = i++
      try {
        results[idx] = await fn(items[idx], idx)
      } catch (e) {
        results[idx] = { error: e.message, url: items[idx] }
      }
    }
  })
  await Promise.all(workers)
  return results
}

// ──────────────────────────────────────────────────────────────
// 命令实现
// ──────────────────────────────────────────────────────────────

async function cmdDownload() {
  const hits = await collect()
  const urls = [...hits.keys()]
  log(`发现 ${urls.length} 个图床链接，来自 ${new Set([...hits.values()].flat()).size} 个文件`)
  if (!urls.length) return

  const results = await pool(urls, CONCURRENCY, (url) => downloadOne(url, urlToRelPath(url)))

  let ok = 0, skip = 0, fail = 0, bytes = 0
  for (const r of results) {
    if (!r) continue
    if (r.error) { fail++; log('失败:', r.url, r.error); continue }
    if (r.skipped) { skip++; continue }
    ok++; bytes += r.bytes || 0
  }
  log(`完成：新下载 ${ok}，已存在 ${skip}，失败 ${fail}，共 ${(bytes / 1024 / 1024).toFixed(2)} MB`)
  log(`本地目录：${ASSET_DIR}`)
}

async function cmdRewrite() {
  const hits = await collect()
  const files = [...new Set([...hits.values()].flat())]
  let changed = 0, total = 0

  for (const file of files) {
    const src = await readFile(file, 'utf8')
    let replaced = src.replace(URL_RE, (url) => {
      const host = new URL(url).host
      if (!SRC_HOSTS.includes(host)) return url
      total++
      // urlToRelPath 用 path.join，Windows 下是反斜杠，转为 URL 斜杠
      const rel = urlToRelPath(url).split(/[\\/]/).join('/')
      return DEST_PREFIX + '/' + rel
    })
    // 删除指向源图床的 dns-prefetch / preconnect 提示（图片已本地化，无需预连接远端）
    for (const host of SRC_HOSTS) {
      const h = host.replace(/\./g, '\\.')
      const hint = new RegExp(`^\\s*\\[['"]link['"],\\s*\\{[^}]*rel:\\s*['"](?:dns-prefetch|preconnect)['"][^}]*${h}[^}]*\\}\\],?\\s*\\r?\\n`, 'gm')
      const count = (replaced.match(hint) || []).length
      if (count) {
        total += count
        replaced = replaced.replace(hint, '')
      }
    }
    if (replaced !== src) {
      changed++
      if (!DRY) await writeFile(file, replaced)
    }
  }
  log(`${DRY ? '[dry] ' : ''}涉及 ${total} 处链接，修改 ${changed} 个文件`)
  if (DRY) log('（未写入，去掉 --dry 实际执行）')
}

async function cmdCheck() {
  const hits = await collect()
  const urls = [...hits.keys()]
  const results = await pool(urls, CONCURRENCY, async (url) => {
    try {
      const res = await fetch(url, { method: 'HEAD', redirect: 'follow' })
      return { url, status: res.status }
    } catch (e) {
      return { url, status: 0, error: e.message }
    }
  })
  const bad = results.filter((r) => !r || r.status !== 200)
  log(`检查 ${urls.length} 个链接，异常 ${bad.length} 个`)
  for (const r of bad) log('  异常:', r?.url, r?.status, r?.error || '')
}

// ──────────────────────────────────────────────────────────────

const commands = { download: cmdDownload, rewrite: cmdRewrite, check: cmdCheck }

if (!commands[command]) {
  console.error('用法: node docs/scripts/images.mjs <download|rewrite|check> [--dry] [--concurrency N]')
  process.exit(1)
}

commands[command]().catch((e) => {
  console.error('[images] 失败:', e)
  process.exit(1)
})
