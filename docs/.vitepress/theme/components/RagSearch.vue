<script setup lang="ts">
/**
 * 把 AI 问答嵌进 VitePress 原生搜索框（不另起悬浮窗）
 *
 * - 入口：导航栏「搜索」/ Ctrl+K，和原生搜索完全一致
 * - 提问：输入自然语言问题后回车（或点「问 AI」，Ctrl/Cmd+Enter 也会强制走 AI）
 * - 备选：原生 MiniSearch 结果照旧留在下方，AI 失败也能当普通搜索用
 * - 后端：/api/rag/ask（生产由 wiki 的 nginx 反代到白猫云，开发走 vite proxy）
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vitepress'

const API = ((import.meta.env.VITE_RAG_API as string | undefined) || '/api/rag').replace(/\/+$/, '')
const MAX_QUESTION = 200
const QUESTION_HINT = /([?？]|怎么|如何|怎样|在哪|哪里|哪儿|是什么|为什么|能不能|可不可以|是否|多少|几点|几天|多久|什么时候|哪个|哪些|吗[。！!]?$)/

type RagImage = { alt?: string, src: string }
type RagRef = { n: number, title: string, section?: string, url: string, type?: string, images?: RagImage[] }

const host = ref<HTMLElement | null>(null)
const query = ref('')
const answer = ref('')
const refs = ref<RagRef[]>([])
const status = ref<'idle' | 'loading' | 'done' | 'error'>('idle')
const errorMessage = ref('')
const collapsed = ref(false)
const lastAsked = ref('')
const isTouch = ref(false)
const router = useRouter()

let inputEl: HTMLInputElement | null = null
let controller: AbortController | null = null
let observer: MutationObserver | null = null
let raf = 0
const cache = new Map<string, { answer: string, refs: RagRef[] }>()

const visible = computed(() => query.value.trim().length >= 2 || status.value !== 'idle')
const isQuestion = computed(() => QUESTION_HINT.test(query.value.trim()))
const canAsk = computed(() => query.value.trim().length >= 2 && query.value.trim().length <= MAX_QUESTION)

function esc(value: string): string {
  return String(value).replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch] as string))
}

function inline(text: string, list?: RagRef[]): string {
  let html = esc(text)
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\[图(\d+)-(\d+)\]/g, (whole, n, i) => {
    const image = list?.[Number(n) - 1]?.images?.[Number(i) - 1]
    if (!image) return `<span class="rag-tag">图${n}-${i}</span>`
    return `<a class="rag-tag" href="${esc(image.src)}" target="_blank" rel="noopener">图${n}-${i}</a>`
  })
  html = html.replace(/\[(\d+(?:\s*[,，]\s*\d+)*)\]/g, (whole, nums: string) => nums
    .split(/[,，]/)
    .map((x) => x.trim())
    .filter(Boolean)
    .map((n) => {
      const ref = list?.[Number(n) - 1]
      return ref
        ? `<a class="rag-cite" href="${esc(refPath(ref))}" data-rag-path="${esc(pathOf(ref))}" target="_self">${n}</a>`
        : `<span class="rag-cite">${n}</span>`
    })
    .join(''))
  return html
}

function renderProse(text: string, list?: RagRef[]): string {
  const out: string[] = []
  let listTag: 'ul' | 'ol' | null = null
  const flush = () => {
    if (listTag) {
      out.push(`</${listTag}>`)
      listTag = null
    }
  }

  for (const raw of text.split('\n')) {
    const line = raw.trimEnd()
    if (!line.trim()) {
      flush()
      continue
    }
    const heading = line.match(/^\s*#{1,4}\s+(.+)$/)
    if (heading) {
      flush()
      out.push(`<div class="rag-h">${inline(heading[1], list)}</div>`)
      continue
    }
    const quote = line.match(/^\s*>\s?(.*)$/)
    if (quote) {
      flush()
      out.push(`<p class="rag-quote">${inline(quote[1], list)}</p>`)
      continue
    }
    const bullet = line.match(/^\s*[-*+]\s+(.+)$/)
    const ordered = line.match(/^\s*\d+[.、)]\s*(.+)$/)
    if (bullet || ordered) {
      const tag = bullet ? 'ul' : 'ol'
      if (listTag !== tag) {
        flush()
        out.push(`<${tag}>`)
        listTag = tag
      }
      out.push(`<li>${inline((bullet || ordered)![1], list)}</li>`)
      continue
    }
    flush()
    out.push(`<p>${inline(line.trim(), list)}</p>`)
  }
  flush()
  return out.join('')
}

function render(text: string, list?: RagRef[]): string {
  return String(text || '')
    .split(/```/)
    .map((part, index) => {
      if (index % 2 === 1) {
        const code = part.replace(/^[a-zA-Z0-9+#._-]*\n/, '').replace(/\n$/, '')
        return `<pre class="rag-code"><code>${esc(code)}</code></pre>`
      }
      return renderProse(part, list)
    })
    .join('')
}

/** 只保留答案真正引用到的资料；一句都没引时退回全部召回 */
const shownRefs = computed(() => {
  const list = refs.value
  if (!list.length) return []
  const cited = new Set<number>()
  const text = String(answer.value || '')
  text.replace(/\[图(\d+)-\d+\]/g, (_w, n) => {
    cited.add(Number(n))
    return ''
  })
  text.replace(/\[(\d+(?:\s*[,，]\s*\d+)*)\]/g, (_w, nums: string) => {
    nums.split(/[,，]/).forEach((x) => cited.add(Number(x.trim())))
    return ''
  })
  const picked = list.filter((ref) => cited.has(ref.n))
  return picked.length ? picked : list
})

function pathOf(ref: RagRef): string {
  try {
    const url = new URL(ref.url, location.origin)
    return url.pathname + url.hash
  } catch {
    return ref.url
  }
}

function refPath(ref: RagRef): string {
  return pathOf(ref)
}

async function ask() {
  if (status.value === 'loading' || !canAsk.value) return
  const question = query.value.trim()
  lastAsked.value = question
  const cached = cache.get(question)
  if (cached) {
    answer.value = cached.answer
    refs.value = cached.refs
    status.value = 'done'
    collapsed.value = false
    return
  }

  answer.value = ''
  refs.value = []
  errorMessage.value = ''
  status.value = 'loading'
  collapsed.value = false
  controller?.abort()
  controller = new AbortController()

  try {
    const response = await fetch(`${API}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, k: 6, stream: true }),
      signal: controller.signal,
    })
    if (!response.ok || !response.body) {
      const detail = await response.json().catch(() => null)
      throw new Error(detail?.error || `服务返回 ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let cut = buffer.indexOf('\n\n')
      while (cut >= 0) {
        const block = buffer.slice(0, cut)
        buffer = buffer.slice(cut + 2)
        cut = buffer.indexOf('\n\n')
        const line = block.split('\n').find((l) => l.startsWith('data:'))
        if (!line) continue
        let event: any
        try {
          event = JSON.parse(line.slice(5).trim())
        } catch {
          continue
        }
        if (event.delta) answer.value += event.delta
        else if (event.meta?.references) refs.value = event.meta.references
        else if (event.error) throw new Error(event.error)
        else if (event.done) {
          if (event.answer && !answer.value) answer.value = event.answer
        }
      }
    }

    status.value = 'done'
    if (answer.value && refs.value.length) {
      cache.set(question, { answer: answer.value, refs: refs.value })
      if (cache.size > 40) cache.delete(cache.keys().next().value as string)
    }
  } catch (error: any) {
    if (error?.name === 'AbortError') {
      status.value = answer.value ? 'done' : 'idle'
      return
    }
    errorMessage.value = error?.message || String(error)
    status.value = 'error'
  } finally {
    controller = null
  }
}

function stop() {
  controller?.abort()
  controller = null
  status.value = answer.value ? 'done' : 'idle'
}

function closeModal() {
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
}

function goTo(path: string, event?: MouseEvent) {
  if (event) event.preventDefault()
  closeModal()
  router.go(path)
}

function onCardClick(event: MouseEvent) {
  const target = (event.target as HTMLElement)?.closest?.('[data-rag-path]') as HTMLElement | null
  if (!target) return
  event.preventDefault()
  goTo(target.dataset.ragPath || '', event)
}

let lastQuery = ''

function onInputEvent() {
  const value = inputEl?.value || ''
  query.value = value
  if (value.trim() !== lastQuery.trim()) {
    lastQuery = value
    if (status.value === 'done' || status.value === 'error') {
      answer.value = ''
      refs.value = []
      errorMessage.value = ''
      status.value = 'idle'
    }
  }
}

function onNativeKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || event.isComposing) return
  const force = event.ctrlKey || event.metaKey
  // 已经答过的同一问题：回车交回原生搜索（进入选中的页面），要重答用 Ctrl+Enter 或「重新生成」
  const asked = status.value === 'done' && lastAsked.value === query.value.trim()
  if (!force && (asked || !isQuestion.value)) return
  if (!canAsk.value) return
  event.preventDefault()
  event.stopPropagation()
  ask()
}

function teardown() {
  if (inputEl) {
    inputEl.removeEventListener('input', onInputEvent)
    inputEl.removeEventListener('keydown', onNativeKeydown)
    inputEl = null
  }
  stop()
  host.value = null
  query.value = ''
  answer.value = ''
  refs.value = []
  errorMessage.value = ''
  status.value = 'idle'
  lastQuery = ''
  lastAsked.value = ''
}

function attach() {
  const shell = document.querySelector('.VPLocalSearchBox .shell')
  if (!shell) {
    if (host.value) teardown()
    return
  }
  if (host.value && shell.contains(host.value)) return
  if (host.value) teardown()

  const el = document.createElement('div')
  el.className = 'rag-search-host'
  const results = shell.querySelector('ul.results')
  shell.insertBefore(el, results || null)

  inputEl = shell.querySelector<HTMLInputElement>('.search-input')
  if (inputEl) {
    inputEl.placeholder = '搜索文档，或直接输入问题…'
    inputEl.addEventListener('input', onInputEvent)
    inputEl.addEventListener('keydown', onNativeKeydown)
    query.value = inputEl.value
    lastQuery = inputEl.value
  }
  host.value = el
}

function scheduleAttach() {
  if (raf) return
  raf = window.requestAnimationFrame(() => {
    raf = 0
    attach()
  })
}

watch(query, () => {
  // 输入新问题时收起上一次的“已收起”状态
  if (status.value === 'idle') collapsed.value = false
})

onMounted(() => {
  isTouch.value = window.matchMedia?.('(hover: none)').matches || false
  scheduleAttach()
  observer = new MutationObserver((records) => {
    for (const record of records) {
      if (record.addedNodes.length || record.removedNodes.length) {
        scheduleAttach()
        break
      }
    }
  })
  observer.observe(document.body, { childList: true, subtree: true })
})

onBeforeUnmount(() => {
  observer?.disconnect()
  observer = null
  if (raf) cancelAnimationFrame(raf)
  teardown()
})
</script>

<template>
  <Teleport v-if="host" :to="host">
    <section v-if="visible" class="rag-search-card" @click="onCardClick">
      <header class="rag-card-head">
        <span class="rag-badge">AI</span>
        <span class="rag-card-title">
          {{ status === 'loading' ? '正在检索本站资料…' : status === 'done' ? 'AI 回答' : status === 'error' ? 'AI 回答失败' : '用站内文章回答' }}
        </span>
        <span v-if="status === 'done'" class="rag-card-hint">答案由 AI 生成，请核对原文</span>
        <span v-else-if="status === 'idle'" class="rag-card-hint">
          <template v-if="isTouch">点「问 AI」提问</template>
          <template v-else-if="isQuestion">回车直接提问</template>
          <template v-else>选中结果回车进入页面</template>
        </span>
      </header>

      <div v-if="status === 'idle'" class="rag-idle">
        <p class="rag-idle-text">「{{ query.trim() }}」{{ isQuestion ? '看起来是个问题，' : '' }}可以让 AI 先读一遍本站文章再回答。</p>
        <div class="rag-actions">
          <button class="rag-btn rag-btn-primary" type="button" :disabled="!canAsk" @click="ask">
            问 AI
          </button>
          <kbd v-if="!isTouch" class="rag-kbd">Enter</kbd>
          <span v-if="!isTouch" class="rag-kbd-tip">Ctrl / ⌘ + Enter 也可</span>
        </div>
      </div>

      <div v-else-if="status === 'loading'" class="rag-loading">
        <span class="rag-typing"><i /><i /><i /></span>
        <span class="rag-loading-text">{{ answer ? '生成中…' : '检索并组织答案…' }}</span>
        <button class="rag-btn rag-btn-ghost" type="button" @click="stop">停止</button>
      </div>

      <div v-else-if="status === 'error'" class="rag-error-box">
        <p>{{ errorMessage || '服务暂时不可用' }}</p>
        <p class="rag-error-tip">下方的站内搜索结果仍然可用。</p>
        <button class="rag-btn rag-btn-ghost" type="button" @click="ask">重试</button>
      </div>

      <div v-else class="rag-answer">
        <div v-if="collapsed" class="rag-collapsed">
          <button class="rag-btn rag-btn-ghost" type="button" @click="collapsed = false">展开 AI 回答</button>
        </div>
        <template v-else>
          <div class="rag-md" v-html="render(answer, refs)" />
          <div v-if="shownRefs.length" class="rag-refs">
            <a
              v-for="ref in shownRefs"
              :key="ref.n"
              class="rag-ref"
              :href="refPath(ref)"
              :data-rag-path="pathOf(ref)"
            >
              <span class="rag-ref-n">{{ ref.n }}</span>
              <span class="rag-ref-t">{{ ref.title }}<em v-if="ref.section"> · {{ ref.section }}</em></span>
            </a>
          </div>
          <div class="rag-answer-foot">
            <button class="rag-btn rag-btn-ghost" type="button" @click="ask">重新生成</button>
            <button class="rag-btn rag-btn-ghost" type="button" @click="collapsed = true">收起</button>
            <span class="rag-foot-tip">共 {{ refs.length }} 条召回，仅列出被引用的</span>
          </div>
        </template>
      </div>
    </section>
  </Teleport>
</template>

<style scoped>
.rag-search-card {
  padding: 0.75rem 0.9rem;
  border: 1px solid var(--vp-c-divider);
  border-radius: 0.375rem;
  background: var(--vp-c-bg-soft);
}

.rag-card-head {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.8rem;
  color: var(--vp-c-text-2);
}

.rag-badge {
  display: inline-grid;
  place-items: center;
  width: 1.35rem;
  height: 1.35rem;
  border-radius: 0.3rem;
  background: linear-gradient(135deg, var(--vp-c-brand-1), var(--vp-c-brand-3, var(--vp-c-brand-2)));
  color: #fff;
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.rag-card-title {
  font-weight: 600;
  color: var(--vp-c-text-1);
}

.rag-card-hint {
  margin-left: auto;
  color: var(--vp-c-text-3);
  font-size: 0.72rem;
}

.rag-idle-text {
  margin: 0.55rem 0 0.6rem;
  color: var(--vp-c-text-2);
  font-size: 0.85rem;
  line-height: 1.6;
}

.rag-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.rag-btn {
  padding: 0.3rem 0.8rem;
  border: 1px solid var(--vp-c-divider);
  border-radius: 0.3rem;
  background: var(--vp-c-bg);
  color: var(--vp-c-text-1);
  font-size: 0.8rem;
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease;
}

.rag-btn:hover {
  border-color: var(--vp-c-brand-1);
  color: var(--vp-c-brand-1);
}

.rag-btn-primary {
  border-color: var(--vp-c-brand-1);
  background: var(--vp-c-brand-1);
  color: #fff;
}

.rag-btn-primary:hover {
  color: #fff;
  filter: brightness(1.06);
}

.rag-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.rag-btn-ghost {
  padding: 0.2rem 0.55rem;
  font-size: 0.75rem;
  color: var(--vp-c-text-2);
}

.rag-kbd {
  padding: 0.05rem 0.35rem;
  border: 1px solid var(--vp-c-divider);
  border-radius: 0.25rem;
  background: var(--vp-c-bg);
  color: var(--vp-c-text-3);
  font-size: 0.68rem;
  font-family: var(--vp-font-family-mono);
}

.rag-kbd-tip {
  color: var(--vp-c-text-3);
  font-size: 0.7rem;
}

.rag-loading {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.55rem;
  color: var(--vp-c-text-2);
  font-size: 0.82rem;
}

.rag-typing {
  display: inline-flex;
  gap: 3px;
}

.rag-typing i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--vp-c-brand-1);
  animation: rag-blink 1.1s infinite ease-in-out;
}

.rag-typing i:nth-child(2) {
  animation-delay: 0.16s;
}

.rag-typing i:nth-child(3) {
  animation-delay: 0.32s;
}

@keyframes rag-blink {
  0%, 80%, 100% { opacity: 0.25; }
  40% { opacity: 1; }
}

.rag-loading-text {
  flex: 1;
}

.rag-md {
  max-height: min(38vh, 22rem);
  margin-top: 0.5rem;
  overflow-y: auto;
  color: var(--vp-c-text-1);
  font-size: 0.87rem;
  line-height: 1.72;
  word-break: break-word;
}

.rag-md :deep(p) {
  margin: 0 0 0.45rem;
}

.rag-md :deep(p:last-child) {
  margin-bottom: 0;
}

.rag-md :deep(ul),
.rag-md :deep(ol) {
  margin: 0.2rem 0 0.5rem;
  padding-left: 1.25rem;
}

.rag-md :deep(li) {
  margin: 0.1rem 0;
}

.rag-md :deep(.rag-h) {
  margin: 0.55rem 0 0.3rem;
  font-weight: 700;
}

.rag-md :deep(.rag-quote) {
  margin: 0.4rem 0;
  padding: 0.1rem 0 0.1rem 0.6rem;
  border-left: 3px solid var(--vp-c-divider);
  color: var(--vp-c-text-2);
  font-size: 0.82rem;
}

.rag-md :deep(code) {
  padding: 0.08rem 0.3rem;
  border-radius: 0.25rem;
  background: var(--vp-c-default-soft);
  font-size: 0.8rem;
}

.rag-md :deep(.rag-code) {
  margin: 0.45rem 0;
  padding: 0.6rem 0.75rem;
  overflow-x: auto;
  border-radius: 0.35rem;
  background: var(--vp-code-block-bg, #1b1b1f);
  color: var(--vp-code-block-color, #e6e9ef);
  font-size: 0.78rem;
  line-height: 1.6;
}

.rag-md :deep(.rag-code code) {
  padding: 0;
  background: none;
  color: inherit;
  white-space: pre;
}

.rag-cite,
.rag-tag {
  display: inline-block;
  min-width: 0.95rem;
  margin: 0 0.14rem;
  padding: 0 0.2rem;
  border-radius: 0.25rem;
  background: var(--vp-c-brand-soft, rgba(52, 81, 178, 0.14));
  color: var(--vp-c-brand-1);
  font-size: 0.68rem;
  font-weight: 600;
  line-height: 1rem;
  text-align: center;
  text-decoration: none;
  vertical-align: 1px;
}

.rag-cite:hover,
.rag-tag:hover {
  background: var(--vp-c-brand-1);
  color: #fff;
}

.rag-refs {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-top: 0.55rem;
  padding-top: 0.5rem;
  border-top: 1px dashed var(--vp-c-divider);
}

.rag-ref {
  display: flex;
  gap: 0.4rem;
  align-items: baseline;
  color: var(--vp-c-text-2);
  font-size: 0.78rem;
  line-height: 1.5;
  text-decoration: none;
}

.rag-ref:hover .rag-ref-t {
  color: var(--vp-c-brand-1);
  text-decoration: underline;
}

.rag-ref-n {
  flex: none;
  min-width: 1rem;
  color: var(--vp-c-brand-1);
  font-weight: 700;
  text-align: center;
}

.rag-ref-t em {
  color: var(--vp-c-text-3);
  font-style: normal;
}

.rag-answer-foot {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.5rem;
}

.rag-foot-tip {
  margin-left: auto;
  color: var(--vp-c-text-3);
  font-size: 0.68rem;
}

.rag-error-box {
  margin-top: 0.5rem;
  color: var(--vp-c-danger-1, #b91c1c);
  font-size: 0.82rem;
  line-height: 1.6;
}

.rag-error-box p {
  margin: 0 0 0.35rem;
}

.rag-error-tip {
  color: var(--vp-c-text-3);
}

.rag-collapsed {
  margin-top: 0.45rem;
}
</style>
