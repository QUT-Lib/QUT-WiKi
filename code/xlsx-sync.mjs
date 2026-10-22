import { chmodSync, existsSync, mkdirSync, readFileSync, readdirSync, renameSync, statSync, unlinkSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import chromium from '@sparticuz/chromium'
import puppeteer from 'puppeteer-core'
import XLSX from 'xlsx'

export const CACHE_DIR = process.env.CACHE_DIR || join(tmpdir(), 'qutwiki_xlsx_cache')
export const CACHE_TTL = Number(process.env.CACHE_TTL || 60 * 60 * 1000)
export const MAX_CONCURRENT_SYNCS = Number(process.env.MAX_CONCURRENT_SYNCS || 2)
export const MAX_SYNC_QUEUE = Number(process.env.MAX_SYNC_QUEUE || 10)
const MAX_SHEETS = Number(process.env.MAX_SHEETS || 20)
const MAX_ROWS = Number(process.env.MAX_ROWS || 5000)
const MAX_COLUMNS = Number(process.env.MAX_COLUMNS || 100)
const MAX_CELLS = Number(process.env.MAX_CELLS || 100000)
const MAX_CELL_LENGTH = Number(process.env.MAX_CELL_LENGTH || 10000)
const MAX_XLSX_BYTES = Number(process.env.MAX_XLSX_BYTES || 20 * 1024 * 1024)
const MAX_CACHE_FILES = Number(process.env.MAX_CACHE_FILES || 100)

const syncing = new Map()
const syncQueue = []
let activeSyncs = 0
mkdirSync(CACHE_DIR, { recursive: true, mode: 0o700 })
chmodSync(CACHE_DIR, 0o700)

if (!Number.isInteger(MAX_CONCURRENT_SYNCS) || MAX_CONCURRENT_SYNCS < 1) {
  throw new Error('MAX_CONCURRENT_SYNCS 必须是大于 0 的整数')
}
if (!Number.isInteger(MAX_SYNC_QUEUE) || MAX_SYNC_QUEUE < 0) {
  throw new Error('MAX_SYNC_QUEUE 必须是大于或等于 0 的整数')
}
for (const [name, value] of Object.entries({ MAX_SHEETS, MAX_ROWS, MAX_COLUMNS, MAX_CELLS, MAX_CELL_LENGTH, MAX_XLSX_BYTES, MAX_CACHE_FILES })) {
  if (!Number.isInteger(value) || value < 1) throw new Error(`${name} 必须是大于 0 的整数`)
}

export function ts() {
  return new Date().toLocaleString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' })
}

export function log(...args) {
  console.log(`[${ts()}]`, ...args)
}

export function cacheKey(url) {
  const match = url.match(/docs\.qq\.com\/sheet\/([A-Za-z0-9]+)/)
  return match ? match[1] : Buffer.from(url).toString('base64url').slice(0, 20)
}

export function cacheFile(key) {
  return join(CACHE_DIR, `${key}.xlsx`)
}

export function fromCache(key) {
  const file = cacheFile(key)
  if (!existsSync(file)) return null
  if (Date.now() - statSync(file).mtimeMs > CACHE_TTL) return null
  return readFileSync(file)
}

export function isTencentSheetUrl(url) {
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'https:' &&
      parsed.hostname === 'docs.qq.com' &&
      parsed.port === '' &&
      parsed.username === '' &&
      parsed.password === '' &&
      /^\/sheet\/[A-Za-z0-9]+$/.test(parsed.pathname)
  } catch {
    return false
  }
}

function removeExpiredCacheFiles() {
  const now = Date.now()
  const files = []
  for (const name of readdirSync(CACHE_DIR).filter(name => name.endsWith('.xlsx'))) {
    try {
      const file = join(CACHE_DIR, name)
      const mtimeMs = statSync(file).mtimeMs
      if (now - mtimeMs > CACHE_TTL) unlinkSync(file)
      else files.push({ file, mtimeMs })
    } catch {}
  }
  files.sort((a, b) => b.mtimeMs - a.mtimeMs)
  for (const { file } of files.slice(MAX_CACHE_FILES)) {
    try { unlinkSync(file) } catch {}
  }
}

removeExpiredCacheFiles()
const cleanupTimer = setInterval(removeExpiredCacheFiles, Math.max(CACHE_TTL, 60 * 60 * 1000))
cleanupTimer.unref()

export class SyncQueueFullError extends Error {
  constructor() {
    super('同步任务繁忙，请稍后重试')
    this.name = 'SyncQueueFullError'
  }
}

async function acquireSyncSlot() {
  if (activeSyncs < MAX_CONCURRENT_SYNCS) {
    activeSyncs++
    return
  }
  if (syncQueue.length >= MAX_SYNC_QUEUE) throw new SyncQueueFullError()

  log(`  → 达到并发上限，进入队列（${syncQueue.length + 1}/${MAX_SYNC_QUEUE}）`)
  await new Promise(resolve => syncQueue.push(resolve))
}

function releaseSyncSlot() {
  const next = syncQueue.shift()
  if (next) next()
  else activeSyncs--
}

async function syncWithLimit(url, syncTimeout) {
  await acquireSyncSlot()
  const syncTask = syncSheets(url).finally(releaseSyncSlot)
  let timeoutId

  try {
    return await Promise.race([
      syncTask,
      new Promise((_, reject) => {
        timeoutId = setTimeout(
          () => reject(new Error(`同步超时（${syncTimeout / 60000} 分钟），已放弃本次任务`)),
          syncTimeout,
        )
      }),
    ])
  } finally {
    clearTimeout(timeoutId)
  }
}

// 腾讯文档页面的 DOMContentLoaded 有时迟迟不触发（页面本身已经可用），
// 因此导航超时不应中断同步，转而依赖后续的工作表等待。
async function navigateToDoc(page, url) {
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 })
  } catch (error) {
    const message = error?.message || ''
    if (/frame.*detached|detached.*frame/i.test(message)) {
      log('  → 页面接管了导航，继续等待工作表加载')
      return
    }
    if (/Navigation timeout/i.test(message)) {
      log('  → DOMContentLoaded 未在 15s 内触发，继续等待工作表加载')
      return
    }
    throw error
  }
}

// 等待期间页面可能仍在导航，执行上下文被销毁时重试。
async function waitForWorkbook(page, predicate, arg, timeout) {
  const deadline = Date.now() + timeout
  for (;;) {
    const left = deadline - Date.now()
    if (left <= 0) throw new Error('等待工作表加载超时')
    try {
      return await page.waitForFunction(predicate, { timeout: Math.min(left, 20000), polling: 500 }, arg)
    } catch (error) {
      const message = error?.message || ''
      if (!/Execution context was destroyed|Cannot find context|detached|Target closed|Navigating frame/i.test(message)) throw error
      log('  → 页面仍在导航，重试等待工作表')
      await new Promise(resolve => setTimeout(resolve, 1000))
    }
  }
}

export async function syncSheets(docUrl) {
  log('启动 Chromium...')
  const browser = await puppeteer.launch({
    args: [...chromium.args, '--no-sandbox', '--disable-setuid-sandbox'],
    defaultViewport: chromium.defaultViewport,
    executablePath: await chromium.executablePath(),
    headless: chromium.headless,
  })

  try {
    const page = await browser.newPage()
    log(`打开腾讯文档：${docUrl}`)
    await navigateToDoc(page, docUrl)
    await waitForWorkbook(page, () => {
      const manager = window.SpreadsheetApp?.workbook?.worksheetManager
      return manager?.getSheetList?.().length > 0
    }, undefined, 60000)

    const sheetInfo = await page.evaluate(() => {
      const manager = window.SpreadsheetApp.workbook.worksheetManager
      return manager.getSheetList().map(sheet => ({
        id: sheet.getSheetId(),
        name: sheet.getSheetName(),
      }))
    })
    if (sheetInfo.length > MAX_SHEETS) throw new Error(`工作表数量超过限制（${MAX_SHEETS}）`)
    log(`发现 ${sheetInfo.length} 个工作表：${sheetInfo.map(sheet => sheet.name).join('、')}`)

    const workbook = XLSX.utils.book_new()
    for (const { id, name } of sheetInfo) {
      log(`读取工作表「${name}」...`)
      const sheetUrl = new URL(docUrl)
      sheetUrl.searchParams.set('tab', id)
      await navigateToDoc(page, sheetUrl.href)
      await waitForWorkbook(page, (sheetId) => {
        const workbook = window.SpreadsheetApp?.workbook
        return workbook?.worksheetManager?.getSheetBySheetId?.(sheetId)?.cellDataGrid
      }, id, 60000)
      await new Promise(resolve => setTimeout(resolve, 2000))

      const rows = await page.evaluate((sheetId, limits) => {
        const sheet = window.SpreadsheetApp.workbook.worksheetManager.getSheetBySheetId(sheetId)
        if (!sheet) return []
        const grid = sheet.cellDataGrid
        const rowCount = sheet.getRowCount()
        const colCount = sheet.getColCount()
        if (rowCount > limits.maxRows) throw new Error(`行数超过限制（${limits.maxRows}）`)
        if (colCount > limits.maxColumns) throw new Error(`列数超过限制（${limits.maxColumns}）`)
        if (rowCount * colCount > limits.maxCells) throw new Error(`单元格数量超过限制（${limits.maxCells}）`)
        const data = []
        let trailingEmptyRows = 0

        function textOf(cell) {
          if (!cell) return ''
          if (cell.formattedValue && typeof cell.formattedValue.value === 'string') return cell.formattedValue.value
          if (typeof cell.value === 'string' || typeof cell.value === 'number') return String(cell.value)
          if (cell.value?.r) return cell.value.r.map(run => run.t || '').join('')
          return ''
        }

        for (let rowIndex = 0; rowIndex < rowCount; rowIndex++) {
          const row = []
          let hasData = false
          for (let colIndex = 0; colIndex < colCount; colIndex++) {
            const text = textOf(grid.getCellData(rowIndex, colIndex)).slice(0, limits.maxCellLength)
            row.push(text)
            if (text) hasData = true
          }

          if (hasData) {
            trailingEmptyRows = 0
            data.push(row)
          } else if (data.length > 0 && ++trailingEmptyRows >= 10) {
            break
          }
        }
        const usedColumns = data.reduce((max, row) => {
          for (let index = row.length - 1; index >= 0; index--) {
            if (row[index]) return Math.max(max, index + 1)
          }
          return max
        }, 0)
        return data.map(row => row.slice(0, usedColumns))
      }, id, {
        maxRows: MAX_ROWS,
        maxColumns: MAX_COLUMNS,
        maxCells: MAX_CELLS,
        maxCellLength: MAX_CELL_LENGTH,
      })

      if (rows.length === 0) {
        log('  → 空表，跳过')
        continue
      }

      log(`  → ${rows.length} 行数据`)
      XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet(rows), name)
    }

    if (workbook.SheetNames.length === 0) throw new Error('腾讯文档中没有可读取的工作表')
    const buffer = XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' })
    if (buffer.length > MAX_XLSX_BYTES) throw new Error(`XLSX 大小超过限制（${MAX_XLSX_BYTES} 字节）`)
    return buffer
  } finally {
    try {
      await Promise.race([
        browser.close(),
        new Promise((_, reject) => setTimeout(() => reject(new Error('Chromium 关闭超时')), 10000)),
      ])
      log('Chromium 已关闭')
    } catch (error) {
      log(`${error.message}，强制结束 Chromium`)
      browser.process()?.kill('SIGKILL')
    }
  }
}

export function syncOnce(key, url) {
  if (syncing.has(key)) {
    log(`  → 文档正在同步，等待已有任务：${key}`)
    return syncing.get(key)
  }

  // 看门狗：同步任务卡死时强制放弃并释放锁，避免后续请求无限等待
  const syncTimeout = Number(process.env.SYNC_TIMEOUT || 5 * 60 * 1000)
  const task = syncWithLimit(url, syncTimeout).finally(() => syncing.delete(key))
  syncing.set(key, task)
  return task
}

export async function refreshCache(docUrl) {
  const key = cacheKey(docUrl)
  const buffer = await syncOnce(key, docUrl)
  if (buffer.length > MAX_XLSX_BYTES) throw new Error(`XLSX 大小超过限制（${MAX_XLSX_BYTES} 字节）`)
  const file = cacheFile(key)
  const tempFile = `${file}.${process.pid}.${Date.now()}.tmp`
  try {
    writeFileSync(tempFile, buffer, { mode: 0o600, flag: 'wx' })
    renameSync(tempFile, file)
  } finally {
    try { unlinkSync(tempFile) } catch {}
  }
  removeExpiredCacheFiles()
  return { buffer, file, key }
}
