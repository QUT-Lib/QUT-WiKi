<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(defineProps<{
  gap?: number
  rowHeight?: number
}>(), {
  gap: 8,
  rowHeight: 220,
})

const root = ref<HTMLElement>()
let resizeObserver: ResizeObserver | undefined
let animationFrame = 0
let images: HTMLImageElement[] = []

function getItems() {
  if (!root.value) return []

  const items: Array<{ element: HTMLElement; image: HTMLImageElement }> = []

  Array.from(root.value.children).forEach((item) => {
    const element = item as HTMLElement

    if (element.matches('img')) {
      items.push({ element, image: element as HTMLImageElement })
      return
    }

    const images = element.querySelectorAll('img')
    if (images.length === 1) {
      items.push({ element, image: images[0] as HTMLImageElement })
    } else if (images.length > 1) {
      images.forEach((img) => {
        const wrapper = document.createElement('div')
        wrapper.dataset.galleryItem = ''
        const caption = img.nextElementSibling
        const hasCaption = caption?.classList?.contains('img-caption')

        root.value!.insertBefore(wrapper, element)
        wrapper.appendChild(img)
        if (hasCaption) wrapper.appendChild(caption)

        items.push({ element: wrapper, image: img as HTMLImageElement })
      })
      element.remove()
    }
  })

  return items
}

function layout() {
  if (!root.value) return

  const width = root.value.clientWidth
  if (!width) return

  const items = getItems()

  items.forEach((item) => {
    const widthAttribute = Number(item.image.getAttribute('width'))
    const heightAttribute = Number(item.image.getAttribute('height'))
    const ratio = item.image.naturalWidth && item.image.naturalHeight
      ? item.image.naturalWidth / item.image.naturalHeight
      : widthAttribute && heightAttribute
        ? widthAttribute / heightAttribute
        : 1

    item.element.dataset.galleryItem = ''
    item.element.dataset.galleryRatio = String(ratio)
  })

  const rows: Array<ReturnType<typeof getItems>> = []

  if (items.length >= 4 && items.length % 2 === 0) {
    // Keep even galleries balanced instead of letting image ratios create a 3+1 row.
    const midpoint = items.length / 2
    rows.push(items.slice(0, midpoint), items.slice(midpoint))
  } else {
    let row: ReturnType<typeof getItems> = []
    let ratioSum = 0

    for (const item of items) {
      row.push(item)
      ratioSum += Number(item.element.dataset.galleryRatio)

      if (ratioSum * props.rowHeight + (row.length - 1) * props.gap >= width) {
        rows.push(row)
        row = []
        ratioSum = 0
      }
    }

    if (row.length) rows.push(row)
  }

  rows.forEach((items, index) => {
    const totalRatio = items.reduce(
      (sum, item) => sum + Number(item.element.dataset.galleryRatio),
      0,
    )
    // Leave one pixel for browser subpixel rounding so a full row never wraps.
    const availableWidth = width - (items.length - 1) * props.gap - 1
    const height = availableWidth / totalRatio

    items.forEach((item) => {
      const itemWidth = height * Number(item.element.dataset.galleryRatio)
      item.element.style.flex = `0 0 ${itemWidth}px`
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
  <div
    ref="root"
    class="qut-gallery"
    role="list"
    :style="{ '--gallery-gap': `${gap}px` }"
  >
    <slot />
  </div>
</template>

<style>
.qut-gallery {
  display: flex;
  flex-wrap: wrap;
  gap: var(--gallery-gap);
  align-items: flex-start;
  margin: 16px 0;
}

.qut-gallery > * {
  flex: 1 1 220px;
  min-width: 0;
  margin: 0 !important;
}

.qut-gallery > [data-gallery-item] {
  display: block;
  overflow: hidden;
  border-radius: 8px;
  background: var(--vp-c-bg-soft);
}

.qut-gallery > img[data-gallery-item],
.qut-gallery > [data-gallery-item] img {
  display: block;
  width: 100%;
  height: 100%;
  margin: 0 !important;
  object-fit: contain;
}

.qut-gallery > [data-gallery-item] > a,
.qut-gallery > [data-gallery-item] > picture {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
