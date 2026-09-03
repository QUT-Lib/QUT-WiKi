<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(defineProps<{ gap?: number; rowHeight?: number }>(), { gap: 8, rowHeight: 220 })
const root = ref<HTMLElement>()
let resizeObserver: ResizeObserver | undefined
let animationFrame = 0
let images: HTMLImageElement[] = []

function getItems() {
  if (!root.value) return []
  return Array.from(root.value.children).flatMap((element) => {
    const node = element as HTMLElement
    if (node.matches('img')) return [{ element: node, image: node as HTMLImageElement }]
    const image = node.querySelector('img')
    return image ? [{ element: node, image }] : []
  })
}

function layout() {
  if (!root.value?.clientWidth) return
  const width = root.value.clientWidth
  const rows: Array<ReturnType<typeof getItems>> = []
  let row: ReturnType<typeof getItems> = []
  let ratioSum = 0
  for (const item of getItems()) {
    const widthAttribute = Number(item.image.getAttribute('width'))
    const heightAttribute = Number(item.image.getAttribute('height'))
    const ratio = item.image.naturalWidth && item.image.naturalHeight
      ? item.image.naturalWidth / item.image.naturalHeight
      : widthAttribute && heightAttribute ? widthAttribute / heightAttribute : 1
    item.element.dataset.galleryItem = ''
    item.element.dataset.galleryRatio = String(ratio)
    row.push(item)
    ratioSum += ratio
    if (ratioSum * props.rowHeight + (row.length - 1) * props.gap >= width) {
      rows.push(row)
      row = []
      ratioSum = 0
    }
  }
  if (row.length) rows.push(row)
  rows.forEach((items) => {
    const totalRatio = items.reduce((sum, item) => sum + Number(item.element.dataset.galleryRatio), 0)
    const height = (width - (items.length - 1) * props.gap - 1) / totalRatio
    items.forEach((item) => {
      item.element.style.flex = `0 0 ${height * Number(item.element.dataset.galleryRatio)}px`
      item.element.style.height = `${height}px`
    })
  })
}

function scheduleLayout() {
  cancelAnimationFrame(animationFrame)
  animationFrame = requestAnimationFrame(layout)
}

onMounted(async () => {
  await nextTick()
  images = getItems().map(({ image }) => image)
  images.forEach((image) => image.addEventListener('load', scheduleLayout))
  resizeObserver = new ResizeObserver(scheduleLayout)
  resizeObserver.observe(root.value!)
  scheduleLayout()
})

onBeforeUnmount(() => {
  images.forEach((image) => image.removeEventListener('load', scheduleLayout))
  resizeObserver?.disconnect()
  cancelAnimationFrame(animationFrame)
})
</script>

<template>
  <div ref="root" class="wk-gallery" role="list" :style="{ '--wk-gallery-gap': `${gap}px` }"><slot /></div>
</template>

<style>
.wk-gallery { display: flex; flex-wrap: wrap; gap: var(--wk-gallery-gap); align-items: flex-start; margin: 16px 0; }
.wk-gallery > * { flex: 1 1 220px; min-width: 0; margin: 0 !important; }
.wk-gallery > [data-gallery-item] { display: block; overflow: hidden; border-radius: 8px; background: var(--vp-c-bg-soft); }
.wk-gallery > img[data-gallery-item], .wk-gallery > [data-gallery-item] img { display: block; width: 100%; height: 100%; margin: 0 !important; object-fit: contain; }
.wk-gallery > [data-gallery-item] > a, .wk-gallery > [data-gallery-item] > picture { display: block; width: 100%; height: 100%; }
</style>
