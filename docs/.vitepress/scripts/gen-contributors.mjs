import { execFileSync } from 'child_process'
import { writeFileSync, readFileSync, readdirSync, statSync, existsSync } from 'fs'
import { resolve, relative, extname, dirname } from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const repoRoot = resolve(__dirname, '..', '..', '..')
const docsDir = resolve(repoRoot, 'docs')
const outPath = resolve(__dirname, '..', 'contributors.json')
const historyOutPath = resolve(__dirname, '..', 'history.json')
const mappingPath = resolve(__dirname, '..', 'contributors-mapping.json')

function walkMdFiles(dir, base) {
  const results = []
  let entries
  try {
    entries = readdirSync(dir)
  } catch {
    return results
  }
  for (const entry of entries) {
    const full = resolve(dir, entry)
    let st
    try {
      st = statSync(full)
    } catch {
      continue
    }
    if (st.isDirectory()) {
      if (entry === '.vitepress' || entry === 'node_modules' || entry.startsWith('.')) continue
      results.push(...walkMdFiles(full, base))
    } else if (extname(entry) === '.md') {
      results.push(relative(base, full).replace(/\\/g, '/'))
    }
  }
  return results
}

function extractGitHubUsername(email) {
  const match = email.match(/^(\d+\+)?([^@]+)@users\.noreply\.github\.com$/)
  return match ? match[2] : null
}

function getContributors(relPath) {
  try {
    const output = execFileSync(
      'git',
      ['log', '--follow', '--format=%an|%ae', '--', relPath],
      { encoding: 'utf-8', cwd: repoRoot, maxBuffer: 10 * 1024 * 1024 }
    )
    const lines = output.trim().split('\n').filter(Boolean)
    const map = new Map()
    for (const line of lines) {
      const [name, email] = line.split('|')
      if (!name || !email) continue
      const key = name.toLowerCase()
      if (!map.has(key)) {
        map.set(key, { name, emails: new Map(), total: 0, firstEmail: email })
      }
      const entry = map.get(key)
      entry.emails.set(email.toLowerCase(), (entry.emails.get(email.toLowerCase()) || 0) + 1)
      entry.total++
    }
    return Array.from(map.values())
      .sort((a, b) => b.total - a.total)
      .map(c => {
        const emails = [...c.emails.keys()]
        let github = resolveGitHub(emails, c.name)
        let avatar
        if (!github) {
          const lowerEmails = emails.map(e => e.toLowerCase())
          for (const [key, val] of Object.entries(mapping)) {
            const mappedGithub = typeof val === 'object' && val !== null ? val.github : val
            if (
              lowerEmails.includes(key.toLowerCase()) ||
              c.name.toLowerCase() === key.toLowerCase() ||
              (mappedGithub && c.name.toLowerCase() === String(mappedGithub).toLowerCase())
            ) {
              if (typeof val === 'object' && val !== null) {
                github = val.github
                avatar = val.avatar
              } else {
                github = val
              }
              break
            }
          }
        }
        return {
          name: c.name,
          email: c.firstEmail,
          github,
          avatar,
          commits: c.total,
        }
      })
  } catch {
    return []
  }
}

// 解析 COMMIT_SEP 分隔的 git log，得到每篇文章的提交历史（含跨改名追踪）。
function getHistory(relPath) {
  try {
    const sep = 'COMMIT_SEP\x1f'
    const output = execFileSync(
      'git',
      ['log', '--follow', '--format=%h%x1f%an%x1f%ae%x1f%aI%x1f%s%x1f' + sep, '--', relPath],
      { encoding: 'utf-8', cwd: repoRoot, maxBuffer: 10 * 1024 * 1024 }
    )
    return output
      .split(sep)
      .map(chunk => chunk.replace(/^\r?\n/, '').trimEnd())
      .filter(Boolean)
      .map((chunk) => {
        const [hash, author, email, date, message] = chunk.split('\x1f')
        let github = null
        let avatar
        const noreply = extractGitHubUsername(email || '')
        if (noreply) {
          github = noreply
        } else {
          const val = mapping[email] || mapping[author]
          if (typeof val === 'object' && val !== null) {
            github = val.github
            avatar = val.avatar
          } else if (val) {
            github = val
          } else {
            const lower = (author || '').toLowerCase()
            for (const item of Object.values(mapping)) {
              const mappedGithub = typeof item === 'object' && item !== null ? item.github : item
              if (mappedGithub && String(mappedGithub).toLowerCase() === lower) {
                github = String(mappedGithub)
                if (typeof item === 'object' && item !== null) avatar = item.avatar
                break
              }
            }
          }
        }
        return { hash, message, author, github, avatar, date }
      })
  } catch {
    return []
  }
}

function parseInlineContributor(value) {
  const text = value.trim().replace(/^['"]|['"]$/g, '')
  if (!text) return null
  if (text.startsWith('@')) return { name: text.slice(1), github: text.slice(1), commits: 0 }
  return { name: text, commits: 0 }
}

function normalizeManualContributor(item) {
  if (!item || !item.name) return null
  const contributor = {
    name: String(item.name).trim(),
    commits: 0,
  }
  if (!contributor.name) return null
  if (item.email) contributor.email = String(item.email).trim()
  if (item.github) contributor.github = String(item.github).trim().replace(/^@/, '')
  if (item.avatar) contributor.avatar = String(item.avatar).trim()
  return contributor
}

function parseContributorObject(lines, start) {
  const item = {}
  let index = start
  for (; index < lines.length; index++) {
    const line = lines[index]
    if (!/^\s{4,}\S/.test(line)) break
    const match = line.trim().match(/^(name|email|github|avatar):\s*(.+)$/)
    if (match) item[match[1]] = match[2].trim().replace(/^['"]|['"]$/g, '')
  }
  return { item, contributor: normalizeManualContributor(item), nextIndex: index }
}

function getManualContributors(filePath) {
  let raw
  try {
    raw = readFileSync(filePath, 'utf-8')
  } catch {
    return []
  }

  const fmMatch = raw.match(/^---\s*\n([\s\S]*?)\n---/)
  if (!fmMatch) return []

  const lines = fmMatch[1].split(/\r?\n/)
  const contributors = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const field = line.match(/^contributors:\s*(.*)$/)
    if (!field) continue

    const inline = field[1].trim()
    if (inline) {
      if (inline.startsWith('[') && inline.endsWith(']')) {
        const items = inline.slice(1, -1).split(',').map(parseInlineContributor).filter(Boolean)
        contributors.push(...items)
      } else {
        const contributor = parseInlineContributor(inline)
        if (contributor) contributors.push(contributor)
      }
      break
    }

    for (i += 1; i < lines.length; i++) {
      const item = lines[i].match(/^\s{2}-\s*(.*)$/)
      if (!item) {
        if (/^\S/.test(lines[i])) i--
        break
      }

      const value = item[1].trim()
      if (!value) {
        const parsed = parseContributorObject(lines, i + 1)
        if (parsed.contributor) contributors.push(parsed.contributor)
        i = parsed.nextIndex - 1
        continue
      }

      const pair = value.match(/^(name|email|github|avatar):\s*(.+)$/)
      if (pair) {
        const itemObject = { [pair[1]]: pair[2].trim().replace(/^['"]|['"]$/g, '') }
        const parsed = parseContributorObject(lines, i + 1)
        Object.assign(itemObject, parsed.item)
        const contributor = normalizeManualContributor(itemObject)
        if (contributor) contributors.push(contributor)
        i = parsed.nextIndex - 1
      } else {
        const contributor = parseInlineContributor(value)
        if (contributor) contributors.push(contributor)
      }
    }
    break
  }

  return contributors.map((contributor) => {
    if (!contributor.github && contributor.name.startsWith('@')) {
      contributor.github = contributor.name.slice(1)
      contributor.name = contributor.github
    }

    const mapped = mapping[contributor.email] || mapping[contributor.name] || mapping[contributor.github]
    if (mapped) {
      if (typeof mapped === 'object') {
        contributor.github ||= mapped.github
        contributor.avatar ||= mapped.avatar
      } else {
        contributor.github ||= mapped
      }
    }

    return contributor
  })
}

function contributorKey(contributor) {
  return (contributor.github || contributor.email || contributor.name).toLowerCase()
}

function mergeContributors(gitContributors, manualContributors) {
  const map = new Map()
  for (const contributor of gitContributors) {
    map.set(contributorKey(contributor), contributor)
  }
  for (const contributor of manualContributors) {
    const key = contributorKey(contributor)
    const existing = map.get(key)
    if (existing) {
      map.set(key, {
        ...existing,
        ...contributor,
        email: contributor.email || existing.email,
        github: contributor.github || existing.github,
        avatar: contributor.avatar || existing.avatar,
        commits: existing.commits || contributor.commits || 0,
      })
    } else {
      map.set(key, contributor)
    }
  }
  return Array.from(map.values())
}

function loadMapping() {
  try {
    return JSON.parse(readFileSync(mappingPath, 'utf-8'))
  } catch {
    return {}
  }
}

let mapping = {}

function resolveGitHub(emails, name) {
  for (const email of emails) {
    const username = extractGitHubUsername(email)
    if (username) return username
  }
  return null
}

function main() {
  if (!existsSync(resolve(repoRoot, '.git'))) {
    writeFileSync(outPath, '{}')
    writeFileSync(historyOutPath, '{}')
    console.log('No git repository found, generated empty contributors data')
    return
  }

  const docsRelToRoot = relative(repoRoot, docsDir).replace(/\\/g, '/')
  mapping = loadMapping()
  const files = walkMdFiles(docsDir, docsDir)
  const result = {}
  const history = {}

  for (const file of files) {
    const gitPath = `${docsRelToRoot}/${file}`
    const contributors = mergeContributors(
      getContributors(gitPath),
      getManualContributors(resolve(docsDir, file))
    )
    if (contributors.length > 0) {
      result[file] = contributors.map(({ email, ...publicContributor }) => publicContributor)
    }
    const commits = getHistory(gitPath)
    if (commits.length > 0) {
      history[file] = commits
    }
  }

  writeFileSync(outPath, JSON.stringify(result, null, 2))
  writeFileSync(historyOutPath, JSON.stringify(history, null, 2))
  console.log(`Generated contributors data for ${Object.keys(result).length} files`)
  console.log(`Generated git history data for ${Object.keys(history).length} files`)
}

main()
