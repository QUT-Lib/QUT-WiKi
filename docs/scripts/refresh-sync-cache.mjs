/**
 * 清除同步服务器上的腾讯文档 XLSX 缓存，用于强制刷新远端表格。
 *
 * 原理：通过 SSH 登录同步服务器（code/ 里的服务），删除缓存目录下的 .xlsx 文件。
 * 下次构建请求该文档时，服务端缓存未命中，会用 Chromium 重新同步最新数据。
 *
 * 环境变量（也可写在仓库根目录 .env.local 里，已 gitignore）：
 *   SYNC_SSH_TARGET        完整 SSH 目标，如 baimaoyun（~/.ssh/config 别名）或 root@1.2.3.4
 *                          设置后忽略下面的 HOST/USER/PORT，交给 SSH 配置处理
 *   SYNC_SSH_HOST          同步服务器地址（不使用 TARGET 时必填）
 *   SYNC_SSH_PORT          可选，SSH 端口；不填则用 SSH 默认或 config 中的 Port
 *   SYNC_SSH_USER          可选，登录用户；不填则用 SSH 默认或 config 中的 User
 *   SYNC_SSH_KEY           可选，私钥文件路径；不填则用默认密钥或 ssh-agent
 *   SYNC_CACHE_DIR         可选，缓存目录，默认 /tmp/qutwiki_xlsx_cache（Docker 镜像里是 /cache）
 *   SYNC_DOCKER_CONTAINER  可选，服务跑在 Docker 时填容器名，改用 docker exec 清理
 *   SYNC_SSH_SUDO          可选，设为 1 时用 sudo 执行删除
 *   SYNC_SSH_STRICT        可选，设为 1 时启用严格 host key 校验（默认 accept-new）
 */

import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

// 自动读取仓库根目录的 .env.local（已 gitignore），方便本地持久化配置。
// 已存在的环境变量优先，不会被文件覆盖。
try {
  const envFile = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', '.env.local')
  for (const line of readFileSync(envFile, 'utf8').split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/)
    if (!m) continue
    let val = m[2]
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1)
    }
    if (process.env[m[1]] === undefined) process.env[m[1]] = val
  }
} catch { }

const TARGET = process.env.SYNC_SSH_TARGET || ''
const HOST = process.env.SYNC_SSH_HOST || ''
const PORT = process.env.SYNC_SSH_PORT || ''
const USER = process.env.SYNC_SSH_USER || ''
const KEY = process.env.SYNC_SSH_KEY || ''
const CACHE_DIR = process.env.SYNC_CACHE_DIR || '/tmp/qutwiki_xlsx_cache'
const CONTAINER = process.env.SYNC_DOCKER_CONTAINER || ''
const USE_SUDO = process.env.SYNC_SSH_SUDO === '1'
const STRICT = process.env.SYNC_SSH_STRICT === '1'

let target = TARGET
if (!target) {
  if (!HOST) {
    console.error('[refresh-sync-cache] 需要 SYNC_SSH_TARGET 或 SYNC_SSH_HOST')
    process.exit(1)
  }
  target = USER ? `${USER}@${HOST}` : HOST
}

function shellQuote(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`
}

const rmCmd = `rm -f ${shellQuote(CACHE_DIR)}/*.xlsx`
let remoteCmd
if (CONTAINER) {
  remoteCmd = `docker exec ${shellQuote(CONTAINER)} sh -c ${shellQuote(rmCmd)}`
} else if (USE_SUDO) {
  remoteCmd = `sudo sh -c ${shellQuote(rmCmd)}`
} else {
  remoteCmd = rmCmd
}

const sshArgs = [
  '-o', STRICT ? 'StrictHostKeyChecking=yes' : 'StrictHostKeyChecking=accept-new',
  '-o', 'ConnectTimeout=15',
]
if (PORT) sshArgs.push('-p', String(PORT))
if (KEY) sshArgs.push('-i', KEY)
sshArgs.push(target, remoteCmd)

const where = `${target}:${CACHE_DIR}${CONTAINER ? `（容器 ${CONTAINER}）` : ''}`
console.log(`[refresh-sync-cache] 清理 ${where}`)

const result = spawnSync('ssh', sshArgs, { stdio: 'inherit' })
if (result.error) {
  console.error(`[refresh-sync-cache] 无法执行 ssh：${result.error.message}`)
  process.exit(1)
}
if (result.status !== 0) {
  console.error(`[refresh-sync-cache] 清理失败（退出码 ${result.status}）`)
  process.exit(result.status ?? 1)
}
console.log('[refresh-sync-cache] 远端缓存已清理，下次构建将重新同步')
