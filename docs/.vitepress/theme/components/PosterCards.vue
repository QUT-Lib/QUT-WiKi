<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { POSTERS } from './poster-data.js'

const props = defineProps({
  items: {
    type: Array,
    default: () => POSTERS,
  },
  title: {
    type: String,
    default: '',
  },
  rowHeight: {
    type: [Number, String],
    default: 320,
  },
  gap: {
    type: [Number, String],
    default: 20,
  },
})

const posters = computed(() => (
  Array.isArray(props.items)
    ? props.items.filter((item) => item && (item.desktop || item.mobile || item.image))
    : []
))

const root = ref(null)
let resizeObserver
let frame = 0
let images = []

function px(value, fallback) {
  const number = typeof value === 'number' ? value : Number.parseFloat(value)
  return Number.isFinite(number) ? number : fallback
}

function declaredRatio(item) {
  if (!item) return 0
  const ratio = Number(item.ratio)
  if (Number.isFinite(ratio) && ratio > 0) return ratio
  if (item.orientation === 'portrait') return 9 / 16
  if (item.orientation === 'landscape') return 16 / 9
  return 0
}

function mediaStyle(item) {
  const ratio = declaredRatio(item)
  return ratio ? { '--poster-ratio': String(ratio) } : {}
}

const gridStyle = computed(() => ({
  '--poster-gap': `${px(props.gap, 20)}px`,
}))

function layout() {
  if (!root.value) return

  const width = root.value.clientWidth
  if (!width) return

  const gap = px(props.gap, 20)
  const rowHeight = px(props.rowHeight, 320)
  const maxHeight = rowHeight * 1.8

  const cards = Array.from(root.value.children).map((card) => {
    const media = card.querySelector('.qut-poster-media')
    const image = card.querySelector('img')
    const natural = image && image.naturalWidth && image.naturalHeight
      ? image.naturalWidth / image.naturalHeight
      : 0
    const ratio = natural || Number(card.getAttribute('data-ratio')) || 1

    if (media) media.style.setProperty('--poster-ratio', String(ratio))

    return { card, media, ratio }
  })

  const rows = []
  let row = []
  let ratioSum = 0

  for (const entry of cards) {
    row.push(entry)
    ratioSum += entry.ratio

    if (ratioSum * rowHeight + (row.length - 1) * gap >= width) {
      rows.push(row)
      row = []
      ratioSum = 0
    }
  }

  if (row.length) rows.push(row)

  for (const entries of rows) {
    const totalRatio = entries.reduce((sum, entry) => sum + entry.ratio, 0)
    // Leave one pixel for browser subpixel rounding so a full row never wraps.
    const availableWidth = width - (entries.length - 1) * gap - 1
    // Cap underfilled rows so a lone portrait poster does not grow absurdly tall.
    const height = Math.min(availableWidth / totalRatio, maxHeight)

    for (const entry of entries) {
      const itemWidth = height * entry.ratio
      entry.card.style.flex = `0 0 ${itemWidth}px`
      entry.card.style.maxWidth = `${itemWidth}px`
      if (entry.media) entry.media.style.height = `${height}px`
    }
  }
}

function scheduleLayout() {
  cancelAnimationFrame(frame)
  frame = requestAnimationFrame(layout)
}

onMounted(async () => {
  await nextTick()
  images = root.value ? Array.from(root.value.querySelectorAll('img')) : []
  images.forEach((image) => image.addEventListener('load', scheduleLayout))
  resizeObserver = new ResizeObserver(scheduleLayout)
  if (root.value) resizeObserver.observe(root.value)
  scheduleLayout()
})

onBeforeUnmount(() => {
  images.forEach((image) => image.removeEventListener('load', scheduleLayout))
  resizeObserver?.disconnect()
  cancelAnimationFrame(frame)
})

function desktopSrc(item) {
  return item.desktop || item.image || item.mobile || ''
}

function mobileSrc(item) {
  return item.mobile || item.image || item.desktop || ''
}

function linkOf(item) {
  const href = item.href
  if (!href) return ''
  if (/^(\/|\.\/|\.\.\/|#)/.test(href)) return href.startsWith('//') ? '' : href
  return /^https?:\/\//.test(href) ? href : ''
}

function isExternal(item) {
  return linkOf(item).startsWith('http')
}
</script>

<template>
  <section v-if="posters.length" class="qut-poster">
    <h2 v-if="title" class="qut-poster-title">{{ title }}</h2>
    <div ref="root" class="qut-poster-grid" :style="gridStyle">
      <article
        v-for="(item, index) in posters"
        :key="index"
        class="qut-poster-card"
        :class="{ 'is-link': linkOf(item) }"
        :data-ratio="declaredRatio(item) || ''"
      >
        <picture class="qut-poster-media" :style="mediaStyle(item)">
          <source v-if="desktopSrc(item)" media="(min-width: 768px)" :srcset="desktopSrc(item)" />
          <img :src="mobileSrc(item)" :alt="item.title || ''" loading="lazy" decoding="async">
        </picture>
        <div
          v-if="item.title || item.description || item.author || item.date"
          class="qut-poster-body"
        >
          <h3 v-if="item.title" class="qut-poster-name">
            <a
              v-if="linkOf(item)"
              class="qut-poster-link"
              :href="linkOf(item)"
              :target="isExternal(item) ? '_blank' : undefined"
              :rel="isExternal(item) ? 'noopener noreferrer' : undefined"
            >{{ item.title }}</a>
            <template v-else>{{ item.title }}</template>
          </h3>
          <p v-if="item.author || item.date" class="qut-poster-meta">
            <span v-if="item.author">{{ item.author }}</span>
            <span v-if="item.author && item.date" class="qut-poster-sep">|</span>
            <span v-if="item.date">{{ item.date }}</span>
          </p>
          <p v-if="item.description" class="qut-poster-desc">{{ item.description }}</p>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.qut-poster {
  margin: 40px 0 16px;
}

.qut-poster-title {
  margin: 0 0 18px !important;
  padding: 0 !important;
  border: 0 !important;
  font-size: 22px !important;
  font-weight: 600;
  text-align: center;
}

.qut-poster-grid {
  display: flex;
  flex-wrap: wrap;
  align-items: stretch;
  justify-content: flex-start;
  gap: var(--poster-gap, 20px);
}

.qut-poster-card {
  display: flex;
  flex: 1 1 320px;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  margin: 0;
  border: 1px solid var(--vp-c-divider);
  border-radius: 14px;
  background: var(--vp-c-bg-soft);
  color: inherit;
  text-decoration: none;
  transition: transform 0.25s, box-shadow 0.25s, border-color 0.25s;
}

.qut-poster-card.is-link:hover {
  transform: translateY(-3px);
  border-color: var(--vp-c-brand-1);
  box-shadow: 0 10px 30px rgb(0 0 0 / 0.12);
}

.qut-poster-media {
  display: block;
  position: relative;
  width: 100%;
  aspect-ratio: var(--poster-ratio, 9 / 16);
  overflow: hidden;
  background: var(--vp-c-bg);
}

@media (min-width: 768px) {
  .qut-poster-media {
    aspect-ratio: var(--poster-ratio, 16 / 9);
  }
}

.qut-poster-media img {
  display: block;
  width: 100%;
  height: 100%;
  margin: 0 !important;
  object-fit: cover;
  cursor: zoom-in;
  transition: transform 0.5s ease;
}

.qut-poster-card.is-link:hover .qut-poster-media img {
  transform: scale(1.03);
}

.qut-poster-body {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px 16px;
}

.qut-poster-name {
  margin: 0 !important;
  padding: 0 !important;
  border: 0 !important;
  color: var(--vp-c-text-1);
  font-size: 17px !important;
  font-weight: 600;
  line-height: 1.4;
}

.qut-poster-link {
  color: inherit;
  text-decoration: none;
}

.qut-poster-link:hover {
  color: var(--vp-c-brand-1);
}

.qut-poster-meta {
  margin: 0;
  color: var(--vp-c-text-3);
  font-size: 12.5px;
  line-height: 1.4;
}

.qut-poster-sep {
  margin: 0 6px;
  opacity: 0.5;
}

.qut-poster-desc {
  margin: 0;
  color: var(--vp-c-text-2);
  font-size: 13.5px;
  line-height: 1.6;
}
</style>
