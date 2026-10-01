<script setup>
import DefaultTheme from 'vitepress/theme'
import { useData, useRoute } from 'vitepress'
import { computed, ref, onMounted, onUnmounted } from 'vue'
import Contributors from './components/Contributors.vue'
import GitHistory from './components/GitHistory.vue'
import TwikooComments from './components/TwikooComments.vue'
import SiteStats from './components/SiteStats.vue'

const { frontmatter } = useData()
const route = useRoute()
const twikooEnvId = import.meta.env.VITE_TWIKOO_ENV_ID

const sidebarDrawerEnabled = computed(() => frontmatter.value.sidebarDrawer === true)
const commentsEnabled = computed(() =>
  Boolean(twikooEnvId) &&
  frontmatter.value.comments !== false &&
  !['home', 'page'].includes(frontmatter.value.layout)
)
const visible = ref(false)
const src = ref('')
const alt = ref('')
const sources = ref([])
const index = ref(0)
const scale = ref(1)
const tx = ref(0)
const ty = ref(0)
const dragging = ref(false)
const lastX = ref(0)
const lastY = ref(0)
const anchorX = ref(0)
const anchorY = ref(0)

function updateBodyOverflow() {
  document.body.style.overflow = visible.value ? 'hidden' : ''
}

const hasGallery = computed(() => sources.value.length > 1)

function resetTransform() {
  scale.value = 1
  tx.value = 0
  ty.value = 0
}

function open(element) {
  const inMain = element.closest('.main') || document
  const nodes = Array.from(inMain.querySelectorAll('img')).filter((img) => img.closest('.main'))
  sources.value = nodes
  const at = nodes.indexOf(element)
  index.value = at >= 0 ? at : 0
  apply(at >= 0 ? element : nodes[0])
  visible.value = true
  updateBodyOverflow()
}

function apply(element) {
  if (!element) return
  src.value = element.currentSrc || element.src
  alt.value = element.alt || ''
  resetTransform()
}

function go(step) {
  if (!hasGallery.value) return
  const len = sources.value.length
  index.value = (index.value + step + len) % len
  apply(sources.value[index.value])
}

function close() {
  visible.value = false
  updateBodyOverflow()
}

function onWheel(e) {
  e.preventDefault()
  const rect = e.currentTarget.getBoundingClientRect()
  const ox = e.clientX - rect.left - rect.width / 2
  const oy = e.clientY - rect.top - rect.height / 2
  const delta = e.deltaY < 0 ? 0.15 : -0.15
  const ns = Math.min(Math.max(scale.value + delta, 0.3), 6)
  const ratio = ns / scale.value
  tx.value = tx.value * ratio - ox * (ratio - 1)
  ty.value = ty.value * ratio - oy * (ratio - 1)
  scale.value = ns
}

function onDblClick(e) {
  e.preventDefault()
  if (scale.value > 1) {
    scale.value = 1
    tx.value = 0
    ty.value = 0
  } else {
    scale.value = 2.5
    tx.value = 0
    ty.value = 0
  }
}

function onPointerDown(e) {
  if (e.button !== 0) return
  dragging.value = true
  lastX.value = e.clientX
  lastY.value = e.clientY
  anchorX.value = tx.value
  anchorY.value = ty.value
  e.currentTarget.setPointerCapture(e.pointerId)
}

function onPointerMove(e) {
  if (!dragging.value) return
  tx.value = anchorX.value + (e.clientX - lastX.value)
  ty.value = anchorY.value + (e.clientY - lastY.value)
}

function onPointerUp(e) {
  const dx = Math.abs(e.clientX - lastX.value)
  const dy = Math.abs(e.clientY - lastY.value)
  if (scale.value <= 1 && dx < 3 && dy < 3) close()
  dragging.value = false
}

function onKeydown(e) {
  if (!visible.value) return
  if (e.key === 'Escape') {
    close()
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault()
    go(-1)
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    go(1)
  }
}

function onDocumentClick(e) {
  const target = e.target
  if (target instanceof HTMLImageElement && target.closest('.main')) {
    open(target)
  }
}

function warmupLocalSearch() {
  const schedule = window.requestIdleCallback || ((cb) => window.setTimeout(cb, 1200))
  schedule(() => {
    import('vitepress/dist/client/theme-default/components/VPLocalSearchBox.vue').catch(() => {})
    import('@localSearchIndex')
      .then((module) => {
        Object.values(module.default || {}).forEach((load) => {
          if (typeof load === 'function') load()
        })
      })
      .catch(() => {})
  })
}

function migrateDetailedSearchDefault() {
  const migrationKey = 'qutwiki:detailed-search-default-v1'
  if (localStorage.getItem(migrationKey)) return
  localStorage.setItem('vitepress:local-search-detailed-list', 'true')
  localStorage.setItem(migrationKey, 'true')
}

// ---- 搜索跳转后高亮搜索词 ----
const HIGHLIGHT_HOLD = 3000
const HIGHLIGHT_FADE = 1000
const HIGHLIGHT_TIMEOUT = 3000

let highlightToken = 0
let highlightTimer = null

function normalizePath(path) {
  return path.replace(/index\.html$/, '').replace(/\/+$/, '')
}

function escapeRegExp(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function getDocRoot() {
  const docs = document.querySelectorAll('.vp-doc')
  for (const doc of docs) {
    if (!doc.closest('.VPLocalSearchBox')) return doc
  }
  return null
}

function unwrapHighlights() {
  if (highlightTimer) {
    clearTimeout(highlightTimer)
    highlightTimer = null
  }
  document.querySelectorAll('mark.search-term-highlight').forEach((mark) => {
    const parent = mark.parentNode
    if (!parent) return
    parent.replaceChild(document.createTextNode(mark.textContent || ''), mark)
    parent.normalize()
  })
}

function wrapMatches(root, terms) {
  const marks = []
  const valid = terms.filter(Boolean).sort((a, b) => b.length - a.length)
  if (!valid.length) return marks
  const pattern = new RegExp(valid.map(escapeRegExp).join('|'), 'gi')
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT
      const parent = node.parentElement
      if (!parent) return NodeFilter.FILTER_REJECT
      if (['SCRIPT', 'STYLE', 'TEXTAREA', 'INPUT', 'MARK'].includes(parent.tagName)) {
        return NodeFilter.FILTER_REJECT
      }
      if (parent.closest('.search-term-highlight, .word-count, .img-caption, .header-anchor')) {
        return NodeFilter.FILTER_REJECT
      }
      return NodeFilter.FILTER_ACCEPT
    },
  })
  const nodes = []
  while (walker.nextNode()) nodes.push(walker.currentNode)

  for (const node of nodes) {
    const text = node.nodeValue
    pattern.lastIndex = 0
    if (!pattern.test(text)) continue
    pattern.lastIndex = 0
    const frag = document.createDocumentFragment()
    let last = 0
    let match
    while ((match = pattern.exec(text)) !== null) {
      if (match.index > last) frag.appendChild(document.createTextNode(text.slice(last, match.index)))
      const mark = document.createElement('mark')
      mark.className = 'search-term-highlight'
      mark.textContent = match[0]
      frag.appendChild(mark)
      marks.push(mark)
      last = match.index + match[0].length
      if (match[0].length === 0) pattern.lastIndex++
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)))
    node.parentNode.replaceChild(frag, node)
  }
  return marks
}

function applyHighlight(query, hash) {
  unwrapHighlights()
  const doc = getDocRoot()
  if (!doc) return
  const terms = query.split(/\s+/).filter(Boolean)
  const marks = wrapMatches(doc, terms)
  if (!marks.length) return
  if (!hash) {
    marks[0].scrollIntoView({ block: 'center', behavior: 'smooth' })
  }
  highlightTimer = setTimeout(() => {
    marks.forEach((mark) => mark.classList.add('search-term-fade'))
    highlightTimer = setTimeout(unwrapHighlights, HIGHLIGHT_FADE)
  }, HIGHLIGHT_HOLD)
}

function getSearchQuery() {
  const input = document.querySelector('.VPLocalSearchBox .search-input')
  let query = (input && input.value) || sessionStorage.getItem('vitepress:local-search-filter') || ''
  try {
    const parsed = JSON.parse(query)
    if (typeof parsed === 'string') query = parsed
  } catch {}
  return query.trim()
}

function startHighlight(href) {
  const query = getSearchQuery()
  if (!query || !href) return

  let target
  try {
    target = new URL(href, location.origin)
  } catch {
    return
  }
  const targetPath = normalizePath(target.pathname)
  const hash = target.hash
  const token = ++highlightToken
  const startedAt = Date.now()
  const lowerTerms = query.toLowerCase().split(/\s+/).filter(Boolean)
  const samePath = normalizePath(location.pathname) === targetPath
  const initialDoc = getDocRoot()

  const tick = () => {
    if (token !== highlightToken) return
    const doc = getDocRoot()
    const arrived = normalizePath(location.pathname) === targetPath
    const swapped = samePath || doc !== initialDoc
    const text = doc && doc.textContent ? doc.textContent.toLowerCase() : ''
    const ready = arrived && swapped && doc && lowerTerms.some((term) => text.includes(term))
    if (!ready && Date.now() - startedAt < HIGHLIGHT_TIMEOUT) {
      setTimeout(tick, 60)
      return
    }
    if (!doc) return
    applyHighlight(query, hash)
  }
  setTimeout(tick, 0)
}

function onSearchResultClick(e) {
  const link = e.target.closest && e.target.closest('.VPLocalSearchBox a.result')
  if (link) startHighlight(link.getAttribute('href'))
}

// 键盘回车选中搜索结果时不会触发 click，这里补上。
function onSearchResultKeydown(e) {
  if (e.key !== 'Enter' || e.isComposing) return
  const selected = document.querySelector('.VPLocalSearchBox a.result.selected')
  if (selected) startHighlight(selected.getAttribute('href'))
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('click', onSearchResultClick, true)
  document.addEventListener('keydown', onSearchResultKeydown, true)
  document.addEventListener('keydown', onKeydown)
  migrateDetailedSearchDefault()
  warmupLocalSearch()
})

onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('click', onSearchResultClick, true)
  document.removeEventListener('keydown', onSearchResultKeydown, true)
  document.removeEventListener('keydown', onKeydown)
  unwrapHighlights()
  document.body.style.overflow = ''
})
</script>

<template>
  <div
    :class="{
      'page-no-outline': !sidebarDrawerEnabled && (frontmatter.outline === false || frontmatter.sidebar === false),
      'page-hide-outline': sidebarDrawerEnabled && frontmatter.outline === false,
      'page-sidebar-drawer': sidebarDrawerEnabled,
    }"
    :key="route.path"
  >
    <DefaultTheme.Layout>
      <template #doc-footer-before>
        <Contributors />
      </template>
      <template #doc-after>
        <TwikooComments v-if="commentsEnabled" :key="route.path" :env-id="twikooEnvId" />
        <GitHistory />
      </template>
    </DefaultTheme.Layout>
  </div>
  <SiteStats />
  <Teleport to="body">
    <div v-if="visible" class="img-viewer-bg" @click="close">
      <button class="img-viewer-close" @click="close">&times;</button>
      <button
        v-if="hasGallery"
        class="img-viewer-nav img-viewer-prev"
        type="button"
        aria-label="上一张"
        @click.stop="go(-1)"
      >&#10094;</button>
      <button
        v-if="hasGallery"
        class="img-viewer-nav img-viewer-next"
        type="button"
        aria-label="下一张"
        @click.stop="go(1)"
      >&#10095;</button>
      <div
        class="img-viewer-stage"
        @click.stop
        @wheel="onWheel"
        @dblclick="onDblClick"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
      >
        <img
          :src="src"
          class="img-viewer-img"
          :style="{
            transform: `translate(${tx}px, ${ty}px) scale(${scale})`,
            cursor: scale > 1 ? (dragging ? 'grabbing' : 'grab') : 'zoom-in',
          }"
          draggable="false"
        />
      </div>
      <p v-if="alt" class="img-viewer-caption">{{ alt }}</p>
      <span v-if="hasGallery" class="img-viewer-counter">{{ index + 1 }} / {{ sources.length }}</span>
    </div>
  </Teleport>
</template>

<style>
.img-viewer-bg {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
}

.img-viewer-close {
  position: absolute;
  top: 16px;
  right: 20px;
  z-index: 2;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  font-size: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.img-viewer-close:hover {
  background: rgba(255, 255, 255, 0.3);
}

.img-viewer-nav {
  position: absolute;
  top: 50%;
  z-index: 2;
  width: 48px;
  height: 48px;
  border: 1px solid var(--vp-c-brand-1);
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.88);
  color: var(--vp-c-brand-1);
  font-size: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  transform: translateY(-50%);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
}

.img-viewer-nav:hover {
  background: var(--vp-c-brand-1);
  color: #fff;
}

.img-viewer-prev {
  left: 20px;
}

.img-viewer-next {
  right: 20px;
}

.img-viewer-counter {
  position: absolute;
  top: 28px;
  left: 50%;
  transform: translateX(-50%);
  color: rgba(255, 255, 255, 0.6);
  font-size: 13px;
  pointer-events: none;
}

.img-viewer-stage {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.img-viewer-img {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
  user-select: none;
  -webkit-user-drag: none;
  transition: transform 0.1s ease-out;
}

.img-viewer-caption {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  color: rgba(255, 255, 255, 0.6);
  font-size: 13px;
  margin: 0;
  max-width: 80vw;
  text-align: center;
  pointer-events: none;
}
</style>
