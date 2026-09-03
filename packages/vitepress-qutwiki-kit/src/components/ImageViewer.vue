<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

const props = withDefaults(defineProps<{ selector?: string }>(), { selector: '.vp-doc img' })
const visible = ref(false)
const src = ref('')
const alt = ref('')
const scale = ref(1)
const x = ref(0)
const y = ref(0)
const dragging = ref(false)
let pointerX = 0
let pointerY = 0
let anchorX = 0
let anchorY = 0

function close() {
  visible.value = false
  document.body.style.overflow = ''
}

function open(image: HTMLImageElement) {
  src.value = image.currentSrc || image.src
  alt.value = image.alt
  scale.value = 1
  x.value = 0
  y.value = 0
  visible.value = true
  document.body.style.overflow = 'hidden'
}

function onDocumentClick(event: MouseEvent) {
  const target = event.target
  if (target instanceof HTMLImageElement && target.matches(props.selector) && !target.hasAttribute('data-no-viewer')) open(target)
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && visible.value) close()
}

function onWheel(event: WheelEvent) {
  event.preventDefault()
  scale.value = Math.min(Math.max(scale.value + (event.deltaY < 0 ? .15 : -.15), .3), 6)
}

function onPointerDown(event: PointerEvent) {
  if (event.button !== 0) return
  dragging.value = true
  pointerX = event.clientX
  pointerY = event.clientY
  anchorX = x.value
  anchorY = y.value
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
}

function onPointerMove(event: PointerEvent) {
  if (!dragging.value) return
  x.value = anchorX + event.clientX - pointerX
  y.value = anchorY + event.clientY - pointerY
}

function resetOrZoom() {
  scale.value = scale.value > 1 ? 1 : 2.5
  x.value = 0
  y.value = 0
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="wk-viewer" role="dialog" aria-modal="true" :aria-label="alt || 'Image preview'" @click="close">
      <button class="wk-viewer-close" type="button" aria-label="Close image preview" @click="close">&times;</button>
      <div class="wk-viewer-stage" @click.stop @wheel="onWheel" @dblclick="resetOrZoom" @pointerdown="onPointerDown" @pointermove="onPointerMove" @pointerup="dragging = false">
        <img :src="src" :alt="alt" draggable="false" :style="{ transform: `translate(${x}px, ${y}px) scale(${scale})`, cursor: scale > 1 ? (dragging ? 'grabbing' : 'grab') : 'zoom-in' }">
      </div>
      <p v-if="alt">{{ alt }}</p>
    </div>
  </Teleport>
</template>

<style scoped>
.wk-viewer { position: fixed; inset: 0; z-index: 9999; display: flex; align-items: center; justify-content: center; background: rgb(0 0 0 / 85%); }
.wk-viewer-close { position: absolute; top: 16px; right: 20px; z-index: 2; width: 40px; height: 40px; border: 0; border-radius: 50%; background: rgb(255 255 255 / 15%); color: #fff; font-size: 24px; cursor: pointer; }
.wk-viewer-stage { display: flex; width: 100%; height: 100%; align-items: center; justify-content: center; overflow: hidden; }
.wk-viewer-stage img { max-width: 90vw; max-height: 90vh; object-fit: contain; user-select: none; transition: transform .1s ease-out; }
.wk-viewer p { position: absolute; bottom: 24px; left: 50%; max-width: 80vw; margin: 0; transform: translateX(-50%); color: rgb(255 255 255 / 65%); font-size: 13px; text-align: center; pointer-events: none; }
</style>
