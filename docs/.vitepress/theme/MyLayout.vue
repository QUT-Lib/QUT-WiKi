<script setup>
import DefaultTheme from 'vitepress/theme'
import { useData, useRoute } from 'vitepress'
import { computed, ref, onMounted, onUnmounted } from 'vue'
import Contributors from './components/Contributors.vue'
import TwikooComments from './components/TwikooComments.vue'

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

function open(s, a) {
  src.value = s
  alt.value = a || ''
  visible.value = true
  scale.value = 1
  tx.value = 0
  ty.value = 0
  updateBodyOverflow()
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
  if (e.key !== 'Escape') return
  if (visible.value) close()
}

function onDocumentClick(e) {
  const target = e.target
  if (target instanceof HTMLImageElement && target.closest('.main')) {
    open(target.currentSrc || target.src, target.alt)
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

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onKeydown)
  warmupLocalSearch()
})

onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onKeydown)
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
      </template>
    </DefaultTheme.Layout>
  </div>
  <Teleport to="body">
    <div v-if="visible" class="img-viewer-bg" @click="close">
      <button class="img-viewer-close" @click="close">&times;</button>
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
