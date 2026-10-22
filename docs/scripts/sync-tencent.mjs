#!/usr/bin/env node
/**
 * 在 CI（或本地）里直接把腾讯文档导出成 xlsx，写入 docs/.http_cache/<docId>.xlsx。
 *
 * 构建阶段的 xlsxTablePlugin 会优先读取这个缓存（1 小时 TTL），
 * 因此只要在 build 之前跑一遍本脚本，就不必再依赖自建的同步服务。
 *
 * 用法：
 *   node docs/scripts/sync-tencent.mjs            # 自动扫描 docs 下所有腾讯文档链接
 *   node docs/scripts/sync-tencent.mjs --url ...  # 只同步指定文档
 */
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'
import XLSX from 'xlsx'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const DOCS = join(ROOT, 'docs')
const CACHE_DIR = join(DOCS, '.http_cache')
const MAX_SHEETS = 20
const MAX_ROWS = 5000
const MAX_COLUMNS = 100
const MAX_CELLS = 100000
const MAX_CELL_LENGTH = 10000
const NAV_TIMEOUT = Number(process.env.QUTWIKI_SYNC_NAV_TIMEOUT || 60000)
const SHEET_TIMEOUT = Number(process.env.QUTWIKI_SYNC_SHEET_TIMEOUT || 60000)

const TEN_DOC_RE = /https:\/\/docs\.qq\.com\/sheet\/([A-Za-z0-9]+)/g

function log(...args) {
  console.log(`[sync-tencent]`, ...args)
}

function findDocUrls() {
  const urls = new Map()
  const files = readdirSync(DOCS, { recursive: true })
    .filter(file => typeof file === 'string' && file.endsWith('.md'))
  for (const rel of files) {
    const full = join(DOCS, rel)
    if (!existsSync(full) || !statSync(full).isFile()) continue
    const text = readFileSync(full, 'utf8')
    for (const match of text.matchAll(TEN_DOC_RE)) {
      urls.set(match[1], `https://docs.qq.com/sheet/${match[1]}`)
    }
  }
  return [...urls.values()]
}

// 腾讯文档页面的 DOMContentLoaded 经常迟迟不触发（页面其实已经可用），
// 所以用 commit 等待导航提交，再等 SpreadsheetApp 就绪。
async function openDoc(page, url) {
  try {
    await page.goto(url, { waitUntil: 'commit', timeout: NAV_TIMEOUT })
  } catch (error) {
    const message = error?.message || ''
    if (!/timeout/i.test(message)) throw error
    log(`  导航未在 ${NAV_TIMEOUT}ms 内提交，继续等待页面初始化`)
  }
}

async function waitFor(page, fn, arg, timeout) {
  const deadline = Date.now() + timeout
  for (;;) {
    const left = deadline - Date.now()
    if (left <= 0) throw new Error('等待工作表加载超时')
    try {
      return await page.waitForFunction(fn, arg, { timeout: Math.min(left, 20000), polling: 500 })
    } catch (error) {
      const message = error?.message || ''
      if (!/Execution context was destroyed|Cannot find context|navigat|detached|Target closed/i.test(message)) throw error
      await new Promise(r => setTimeout(r, 1000))
    }
  }
}

function readSheetRows(page, sheetId) {
  return page.evaluate(({ sheetId, limits }) => {
    const sheet = window.SpreadsheetApp.workbook.worksheetManager.getSheetBySheetId(sheetId)
    if (!sheet) return { rows: [], rowCount: 0, colCount: 0 }
    const grid = sheet.cellDataGrid
    const rowCount = sheet.getRowCount()
    const colCount = sheet.getColCount()
    if (rowCount > limits.maxRows) throw new Error(`行数超过限制（${limits.maxRows}）`)
    if (colCount > limits.maxColumns) throw new Error(`列数超过限制（${limits.maxColumns}）`)
    if (rowCount * colCount > limits.maxCells) throw new Error(`单元格数量超过限制（${limits.maxCells}）`)

    function textOf(cell) {
      if (!cell) return ''
      if (cell.formattedValue && typeof cell.formattedValue.value === 'string') return cell.formattedValue.value
      if (typeof cell.value === 'string' || typeof cell.value === 'number') return String(cell.value)
      if (cell.value?.r) return cell.value.r.map(run => run.t || '').join('')
      return ''
    }

    const data = []
    let trailingEmptyRows = 0
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
    return { rows: data.map(row => row.slice(0, usedColumns)), rowCount, colCount }
  }, { sheetId, limits: { maxRows: MAX_ROWS, maxColumns: MAX_COLUMNS, maxCells: MAX_CELLS, maxCellLength: MAX_CELL_LENGTH } })
}

async function syncDoc(browser, docUrl) {
  const docId = docUrl.match(/docs\.qq\.com\/sheet\/([A-Za-z0-9]+)/)?.[1]
  if (!docId) throw new Error(`无法识别文档 ID：${docUrl}`)

  const page = await browser.newPage()
  try {
    log(`打开文档 ${docId}`)
    await openDoc(page, docUrl)
    await waitFor(page, () => {
      const manager = window.SpreadsheetApp?.workbook?.worksheetManager
      return manager?.getSheetList?.().length > 0
    }, undefined, NAV_TIMEOUT)

    const sheetInfo = await page.evaluate(() => {
      const manager = window.SpreadsheetApp.workbook.worksheetManager
      return manager.getSheetList().map(sheet => ({ id: sheet.getSheetId(), name: sheet.getSheetName() }))
    })
    if (sheetInfo.length > MAX_SHEETS) throw new Error(`工作表数量超过限制（${MAX_SHEETS}）`)
    log(`  发现 ${sheetInfo.length} 个工作表：${sheetInfo.map(s => s.name).join('、')}`)

    const workbook = XLSX.utils.book_new()
    for (const { id, name } of sheetInfo) {
      const url = new URL(docUrl)
      url.searchParams.set('tab', id)
      await openDoc(page, url.href)
      await waitFor(page, (sheetId) => {
        const wb = window.SpreadsheetApp?.workbook
        return wb?.worksheetManager?.getSheetBySheetId?.(sheetId)?.cellDataGrid
      }, id, SHEET_TIMEOUT)
      await page.waitForTimeout(2000)

      const { rows } = await readSheetRows(page, id)
      const sheetName = String(name).slice(0, 31).replace(/[:\\/?*[\]]/g, '_') || `Sheet${workbook.SheetNames.length + 1}`
      XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet(rows), sheetName)
      log(`  「${name}」 ${rows.length} 行 × ${rows[0]?.length ?? 0} 列`)
    }

    const buffer = XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' })
    mkdirSync(CACHE_DIR, { recursive: true })
    const file = join(CACHE_DIR, `${docId}.xlsx`)
    writeFileSync(file, buffer)
    log(`已写入 ${file}（${buffer.length} 字节）`)
  } finally {
    await page.close()
  }
}

async function main() {
  const args = process.argv.slice(2)
  const urls = []
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--url' && args[i + 1]) urls.push(args[++i])
  }
  const targets = urls.length > 0 ? urls : findDocUrls()
  if (targets.length === 0) {
    log('没有找到需要同步的腾讯文档链接')
    return
  }

  log(`待同步文档 ${targets.length} 个`)
  const browser = await chromium.launch({ args: ['--no-sandbox', '--disable-setuid-sandbox'] })
  try {
    for (const url of targets) {
      try {
        await syncDoc(browser, url)
      } catch (error) {
        log(`失败：${url} -> ${error.message}`)
        process.exitCode = 1
      }
    }
  } finally {
    await browser.close()
  }
}

main().catch(error => {
  console.error('[sync-tencent] 未捕获错误：', error)
  process.exit(1)
})
