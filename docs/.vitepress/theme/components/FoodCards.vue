<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { FOODS, FOOD_CAMPUS, FOOD_CATEGORIES, getFoodPhotos } from './food-data.js'
import {
  twikooEnvId,
  ratingState,
  myRatings,
  setMyRating,
  loadRatings,
  getTwikoo,
  injectRating,
  submitRatingOnly,
  decorateRatings,
  destroyTwikoo,
  foodUrl,
} from './food-twikoo.js'

const props = defineProps({
  items: {
    type: Array,
    default: () => FOODS,
  },
})

const currentCampus = ref('all')
const currentCategory = ref('all')
const keyword = ref('')

const active = ref(null)
const viewerOpen = ref(false)
const viewerIndex = ref(0)
const commentMount = ref(null)
const commentSlot = ref(null)
const commentLoading = ref(false)
const commentFailed = ref(false)
const ratingOnlySubmitting = ref(false)
const ratingOnlyMessage = ref('')

let observer = null
let decorateTimer = null

const foods = computed(() => (Array.isArray(props.items) ? props.items : []))

const campusOptions = computed(() => {
  const keys = [...new Set(foods.value.map((item) => item.campus).filter(Boolean))]
  return keys.map((key) => ({ key, label: FOOD_CAMPUS[key] || key }))
})

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return foods.value.filter((item) => {
    if (currentCampus.value !== 'all' && item.campus !== currentCampus.value) return false
    if (currentCategory.value !== 'all' && item.category !== currentCategory.value) return false
    if (kw) {
      const hay = [item.name, item.desc, item.location, item.category, ...(item.tags || [])]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      if (!hay.includes(kw)) return false
    }
    return true
  })
})

const groups = computed(() => {
  const order = FOOD_CATEGORIES.map((category) => category.key)
  const map = new Map()
  for (const item of filtered.value) {
    const key = order.includes(item.category) ? item.category : 'other'
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(item)
  }
  return [...map.entries()]
    .sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]))
    .map(([key, list]) => ({
      key,
      label: FOOD_CATEGORIES.find((category) => category.key === key)?.label || '其他',
      list,
    }))
})

const categoryOptions = computed(() => {
  const counts = new Map()
  for (const item of foods.value) counts.set(item.category, (counts.get(item.category) || 0) + 1)
  return [
    { key: 'all', label: '全部', count: foods.value.length },
    ...FOOD_CATEGORIES.filter((category) => counts.has(category.key)).map((category) => ({
      key: category.key,
      label: category.label,
      count: counts.get(category.key),
    })),
  ]
})

const activePhotos = computed(() => getFoodPhotos(active.value))
const activeRating = computed(() => (active.value ? ratingState[active.value.id] : null))

function stateOf(item) {
  return ratingState[item.id] || { sum: 0, count: 0, avg: 0, loaded: false, loading: false }
}

function categoryLabel(key) {
  return FOOD_CATEGORIES.find((category) => category.key === key)?.label || '其他'
}

function campusLabel(key) {
  return FOOD_CAMPUS[key] || ''
}

function ratingOf(item) {
  return myRatings[item.id] || 0
}

function avgStars(item) {
  const state = stateOf(item)
  return state.count ? Math.round(state.avg) : 0
}

function onPick(item, value) {
  setMyRating(item.id, ratingOf(item) === value ? 0 : value)
}

function coverOf(item) {
  return getFoodPhotos(item)[0] || ''
}

function hideBroken(event) {
  event.currentTarget.style.display = 'none'
}

async function openDialog(item) {
  active.value = item
  viewerOpen.value = false
  viewerIndex.value = 0
  if (typeof document !== 'undefined') document.body.style.overflow = 'hidden'

  loadRatings([item.id], { force: true })

  if (!twikooEnvId) {
    commentFailed.value = true
    return
  }

  commentLoading.value = true
  commentFailed.value = false
  ratingOnlyMessage.value = ''
  await nextTick()

  const mountPoint = commentMount.value
  const slot = commentSlot.value
  if (!mountPoint || !slot) return

  try {
    const twikoo = await getTwikoo()
    await twikoo.init({
      envId: twikooEnvId,
      el: mountPoint,
      path: foodUrl(item.id),
      lang: 'zh-CN',
    })
    await nextTick()
    injectRating(slot, () => myRatings[item.id] || 0)
    decorateRatings(slot)
    observer?.disconnect()
    observer = new MutationObserver(scheduleDecorate)
    observer.observe(slot, { childList: true, subtree: true })
    // 底部刷新按钮（tk-expand）会替换评论列表，点击后补一次解析
    slot.addEventListener('click', scheduleDecorate)
    commentLoading.value = false
  } catch (error) {
    console.error('美食评论初始化失败：', error)
    commentFailed.value = true
    commentLoading.value = false
  }
}

async function submitOnlyRating() {
  if (!active.value || !ratingOf(active.value) || ratingOnlySubmitting.value) return
  ratingOnlySubmitting.value = true
  ratingOnlyMessage.value = ''
  const result = await submitRatingOnly(commentSlot.value, () => ratingOf(active.value))
  if (result.ok) {
    ratingOnlyMessage.value = '评分已提交，列表刷新后会更新统计。'
    await loadRatings([active.value.id], { force: true })
  } else if (result.reason === 'meta') {
    ratingOnlyMessage.value = '请先填写昵称和邮箱。'
  } else if (result.reason === 'comment') {
    ratingOnlyMessage.value = '评论框已有文字；如需同时评论，请使用评论区的发送按钮。'
  } else if (result.reason === 'reply') {
    ratingOnlyMessage.value = '请退出回复状态后再提交评分。'
  } else if (result.reason === 'sending') {
    ratingOnlyMessage.value = '正在提交，请稍候。'
  } else if (result.reason === 'submit') {
    ratingOnlyMessage.value = result.message || '评分提交失败，请稍后重试。'
  } else {
    ratingOnlyMessage.value = '评分组件尚未加载完成，请稍后重试。'
  }
  ratingOnlySubmitting.value = false
}

function scheduleDecorate() {
  if (decorateTimer) window.clearTimeout(decorateTimer)
  decorateTimer = window.setTimeout(() => decorateRatings(commentSlot.value), 120)
}

function closeDialog() {
  active.value = null
  viewerOpen.value = false
  observer?.disconnect()
  observer = null
  if (decorateTimer) window.clearTimeout(decorateTimer)
  const slot = commentSlot.value
  if (slot) slot.removeEventListener('click', scheduleDecorate)
  destroyTwikoo(slot)
  if (typeof document !== 'undefined') document.body.style.overflow = ''
}

function openViewer(index) {
  if (!activePhotos.value.length) return
  viewerIndex.value = index
  viewerOpen.value = true
}

function changeViewer(step) {
  const count = activePhotos.value.length
  if (count < 2) return
  viewerIndex.value = (viewerIndex.value + step + count) % count
}

function onKeydown(event) {
  if (!active.value) return
  if (event.key === 'Escape') {
    viewerOpen.value ? (viewerOpen.value = false) : closeDialog()
  } else if (viewerOpen.value && event.key === 'ArrowLeft') {
    changeViewer(-1)
  } else if (viewerOpen.value && event.key === 'ArrowRight') {
    changeViewer(1)
  } else {
    return
  }
  event.preventDefault()
}

watch(
  [currentCampus, currentCategory],
  () => loadRatings(filtered.value.map((item) => item.id))
)

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  loadRatings(foods.value.map((item) => item.id))
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  observer?.disconnect()
  if (decorateTimer) window.clearTimeout(decorateTimer)
  destroyTwikoo(commentSlot.value)
  if (typeof document !== 'undefined') document.body.style.overflow = ''
})
</script>

<template>
  <section class="qut-food">
    <div class="qut-food-toolbar">
      <div class="qut-food-chips">
        <button
          v-for="category in categoryOptions"
          :key="category.key"
          class="qut-food-chip"
          :class="{ active: currentCategory === category.key }"
          type="button"
          @click="currentCategory = category.key"
        >
          {{ category.label }}<span class="qut-food-chip-count">{{ category.count }}</span>
        </button>
      </div>
      <div class="qut-food-filters">
        <select v-if="campusOptions.length > 1" v-model="currentCampus" class="qut-food-select">
          <option value="all">全部校区</option>
          <option v-for="campus in campusOptions" :key="campus.key" :value="campus.key">{{ campus.label }}</option>
        </select>
        <input v-model="keyword" class="qut-food-search" type="search" placeholder="搜索名称、地点或标签">
      </div>
    </div>

    <p v-if="!filtered.length" class="qut-food-empty">没有匹配的美食，换个关键词试试。</p>

    <div v-for="group in groups" :key="group.key" class="qut-food-group">
      <h3 class="qut-food-group-title">{{ group.label }}</h3>
      <div class="qut-food-grid">
        <article v-for="item in group.list" :key="item.id" class="qut-food-card">
          <a class="qut-food-cover" href="#" @click.stop.prevent="openDialog(item)">
            <img v-if="coverOf(item)" :src="coverOf(item)" :alt="item.name" loading="lazy" @error="hideBroken">
            <span v-else class="qut-food-cover-fallback">{{ item.name.slice(0, 1) }}</span>
          </a>
          <div class="qut-food-card-body">
            <a class="qut-food-name" href="#" @click.prevent="openDialog(item)">{{ item.name }}</a>
            <p v-if="item.location" class="qut-food-location">{{ item.location }}</p>

            <div class="qut-food-score">
              <span class="qut-food-avg" :title="stateOf(item).count ? `平均 ${stateOf(item).avg.toFixed(1)} 分，${stateOf(item).count} 人评分` : '暂无评分'">
                <span class="qut-food-stars">
                  <span v-for="n in 5" :key="n" :class="{ on: n <= avgStars(item) }">★</span>
                </span>
                <span class="qut-food-avg-text">
                  {{ stateOf(item).count ? stateOf(item).avg.toFixed(1) : '暂无' }}
                  <template v-if="stateOf(item).count">（{{ stateOf(item).count }}）</template>
                </span>
              </span>
            </div>

            <div class="qut-food-card-foot">
              <span class="qut-food-myrating" title="点击打分，在评论中提交后生效">
                <button
                  v-for="n in 5"
                  :key="n"
                  type="button"
                  class="qut-food-star-btn"
                  :class="{ on: n <= ratingOf(item) }"
                  :aria-label="`打 ${n} 分`"
                  @click="onPick(item, n)"
                >★</button>
              </span>
              <button class="qut-food-comment-btn" type="button" @click="openDialog(item)">
                评价<template v-if="stateOf(item).count"> · {{ stateOf(item).count }}</template>
              </button>
            </div>
          </div>
        </article>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="active" class="qut-food-modal" @click.self="closeDialog">
        <div class="qut-food-dialog" role="dialog" aria-modal="true" :aria-label="active.name">
          <button class="qut-food-dialog-close" type="button" aria-label="关闭" @click="closeDialog">&times;</button>

          <div class="qut-food-dialog-head">
            <h2>{{ active.name }}</h2>
            <div class="qut-food-dialog-tags">
              <span class="qut-food-badge">{{ categoryLabel(active.category) }}</span>
              <span v-if="active.campus" class="qut-food-badge ghost">{{ campusLabel(active.campus) }}</span>
              <span v-for="tag in active.tags || []" :key="tag" class="qut-food-badge ghost">{{ tag }}</span>
            </div>
          </div>

          <div class="qut-food-dialog-body">
            <dl class="qut-food-meta">
              <template v-if="active.location">
                <dt>美食地点</dt>
                <dd>{{ active.location }}</dd>
              </template>
              <template v-if="active.price">
                <dt>人均</dt>
                <dd>{{ active.price }}</dd>
              </template>
              <template v-if="active.recommend">
                <dt>推荐</dt>
                <dd>{{ active.recommend }}</dd>
              </template>
            </dl>

            <p v-if="active.desc" class="qut-food-dialog-desc">{{ active.desc }}</p>

            <div v-if="activePhotos.length" class="qut-food-photos">
              <button
                v-for="(photo, index) in activePhotos"
                :key="photo"
                class="qut-food-photo"
                type="button"
                @click="openViewer(index)"
              >
                <img :src="photo" :alt="`${active.name} 图片 ${index + 1}`" loading="lazy">
              </button>
            </div>

            <div class="qut-food-rating-block">
              <div class="qut-food-rating-summary">
                <span class="qut-food-stars large">
                  <span v-for="n in 5" :key="n" :class="{ on: n <= Math.round(activeRating?.avg || 0) }">★</span>
                </span>
                <strong>{{ activeRating?.count ? activeRating.avg.toFixed(1) : '暂无评分' }}</strong>
                <span v-if="activeRating?.count" class="qut-food-muted">{{ activeRating.count }} 人评分</span>
                <span v-else class="qut-food-muted">来打第一个分</span>
              </div>
              <div class="qut-food-rating-picker">
                <span class="qut-food-muted">我的评分</span>
                <span class="qut-food-stars pickable">
                  <button
                    v-for="n in 5"
                    :key="n"
                    type="button"
                    :class="{ on: n <= ratingOf(active) }"
                    :aria-label="`打 ${n} 分`"
                    @click="onPick(active, n)"
                  >★</button>
                </span>
                <button
                  class="qut-food-rate-only"
                  type="button"
                  :disabled="!ratingOf(active) || ratingOnlySubmitting || commentLoading"
                  @click="submitOnlyRating"
                >{{ ratingOnlySubmitting ? '提交中…' : '只提交评分' }}</button>
              </div>
              <p v-if="ratingOnlyMessage" class="qut-food-rating-message">{{ ratingOnlyMessage }}</p>
            </div>

            <div class="qut-food-comments">
              <h3>历史评论</h3>
              <p v-if="commentLoading" class="qut-food-muted">评论加载中……</p>
              <p v-else-if="!twikooEnvId" class="qut-food-muted">未配置 Twikoo 服务，评论功能暂不可用。</p>
              <p v-else-if="commentFailed" class="qut-food-muted">评论加载失败，请稍后重试。</p>
              <div ref="commentSlot" class="qut-food-comment-slot">
                <div ref="commentMount" :key="active.id" />
              </div>
            </div>
          </div>
        </div>

        <div v-if="viewerOpen" class="qut-food-viewer" @click.self="viewerOpen = false">
          <button class="qut-food-viewer-close" type="button" aria-label="关闭" @click="viewerOpen = false">&times;</button>
          <button
            v-if="activePhotos.length > 1"
            class="qut-food-viewer-nav prev"
            type="button"
            aria-label="上一张"
            @click.stop="changeViewer(-1)"
          >&#10094;</button>
          <img class="qut-food-viewer-img" :src="activePhotos[viewerIndex]" :alt="active.name" @click.stop>
          <button
            v-if="activePhotos.length > 1"
            class="qut-food-viewer-nav next"
            type="button"
            aria-label="下一张"
            @click.stop="changeViewer(1)"
          >&#10095;</button>
          <span class="qut-food-viewer-counter">{{ viewerIndex + 1 }} / {{ activePhotos.length }}</span>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.qut-food {
  margin: 16px 0;
}

.qut-food-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px 16px;
  margin-bottom: 16px;
}

.qut-food-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.qut-food-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border: 1px solid var(--vp-c-divider);
  border-radius: 14px;
  background: var(--vp-c-bg-soft);
  color: var(--vp-c-text-2);
  font-size: 13px;
  cursor: pointer;
  transition: color 0.2s, border-color 0.2s, background 0.2s;
}

.qut-food-chip:hover {
  color: var(--vp-c-brand-1);
  border-color: var(--vp-c-brand-1);
}

.qut-food-chip.active {
  border-color: var(--vp-c-brand-1);
  background: var(--vp-c-brand-soft);
  color: var(--vp-c-brand-1);
}

.qut-food-chip-count {
  opacity: 0.7;
  font-size: 12px;
}

.qut-food-filters {
  display: flex;
  align-items: center;
  gap: 8px;
}

.qut-food-select,
.qut-food-search {
  height: 32px;
  padding: 0 10px;
  border: 1px solid var(--vp-c-divider);
  border-radius: 8px;
  background: var(--vp-c-bg);
  color: var(--vp-c-text-1);
  font-size: 13px;
  outline: none;
}

.qut-food-search {
  width: 190px;
}

.qut-food-select:focus,
.qut-food-search:focus {
  border-color: var(--vp-c-brand-1);
}

.qut-food-empty {
  padding: 32px 0;
  text-align: center;
  color: var(--vp-c-text-3);
}

.qut-food-group {
  margin-bottom: 28px;
}

.qut-food-group-title {
  margin: 0 0 12px !important;
  padding-bottom: 6px;
  border-bottom: 2px solid var(--vp-c-divider);
  font-size: 18px !important;
}

.qut-food-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(216px, 1fr));
  gap: 16px;
}

.qut-food-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  background: var(--vp-c-bg-soft);
  transition: box-shadow 0.2s, transform 0.2s;
}

.qut-food-card:hover {
  box-shadow: 0 2px 16px rgb(0 0 0 / 0.1);
  transform: translateY(-2px);
}

.qut-food-cover {
  display: block;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  background: var(--vp-c-bg);
}

.qut-food-cover img {
  width: 100%;
  height: 100%;
  margin: 0 !important;
  object-fit: cover;
  transition: transform 0.4s ease;
}

.qut-food-card:hover .qut-food-cover img {
  transform: scale(1.05);
}

.qut-food-cover-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: rgb(1 93 149 / 0.35);
  font-size: 40px;
  font-weight: 700;
}

.qut-food-card-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px 12px;
}

.qut-food-name {
  color: var(--vp-c-text-1);
  font-size: 15px;
  font-weight: 600;
  line-height: 1.4;
  text-decoration: none;
  word-break: break-word;
}

.qut-food-name:hover {
  color: var(--vp-c-brand-1);
}

.qut-food-location {
  margin: 0;
  color: var(--vp-c-text-3);
  font-size: 12.5px;
  line-height: 1.4;
}

.qut-food-score {
  display: flex;
  align-items: center;
  gap: 6px;
}

.qut-food-stars,
.qut-food-myrating {
  display: inline-flex;
  gap: 1px;
  color: #93d5dc;
  font-size: 14px;
  line-height: 1;
}

.qut-food-stars .on {
  color: #1781b5;
}

.qut-food-stars.large {
  font-size: 18px;
}

.qut-food-stars.pickable button,
.qut-food-star-btn {
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font-size: inherit;
  line-height: 1;
  cursor: pointer;
  transition: transform 0.15s, color 0.15s;
}

.qut-food-stars.pickable button.on,
.qut-food-star-btn.on {
  color: #1781b5;
}

.qut-food-stars.pickable button:hover,
.qut-food-star-btn:hover {
  transform: scale(1.15);
}

.qut-food-avg {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.qut-food-avg-text {
  color: var(--vp-c-text-2);
  font-size: 12.5px;
}

.qut-food-card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px solid var(--vp-c-divider);
}

.qut-food-comment-btn {
  padding: 3px 10px;
  border: 1px solid var(--vp-c-brand-1);
  border-radius: 12px;
  background: transparent;
  color: var(--vp-c-brand-1);
  font-size: 12.5px;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}

.qut-food-comment-btn:hover {
  background: var(--vp-c-brand-1);
  color: #fff;
}

.qut-food-modal {
  position: fixed;
  inset: 0;
  z-index: 9998;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.55);
}

.qut-food-dialog {
  position: relative;
  display: flex;
  flex-direction: column;
  width: min(880px, 100%);
  max-height: 90vh;
  overflow: hidden;
  border-radius: 14px;
  background: var(--vp-c-bg);
  box-shadow: 0 12px 40px rgb(0 0 0 / 0.3);
}

.qut-food-dialog-close {
  position: absolute;
  top: 10px;
  right: 12px;
  z-index: 2;
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: 50%;
  background: var(--vp-c-bg-soft);
  color: var(--vp-c-text-2);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
}

.qut-food-dialog-close:hover {
  color: var(--vp-c-danger-1);
}

.qut-food-dialog-head {
  padding: 18px 52px 12px 20px;
  border-bottom: 1px solid var(--vp-c-divider);
}

.qut-food-dialog-head h2 {
  margin: 0 !important;
  border: 0 !important;
  padding: 0 !important;
  font-size: 20px !important;
}

.qut-food-dialog-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.qut-food-badge {
  display: inline-block;
  padding: 1px 8px;
  border: 1px solid var(--vp-c-tip-soft);
  border-radius: 12px;
  background: var(--vp-c-tip-soft);
  color: var(--vp-c-tip);
  font-size: 11.5px;
  font-weight: 500;
  line-height: 1.5;
}

.qut-food-badge.ghost {
  border-color: var(--vp-c-divider);
  background: transparent;
  color: var(--vp-c-text-2);
}

.qut-food-dialog-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px 24px;
}

.qut-food-meta {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 6px 12px;
  margin: 0 0 12px;
  font-size: 13.5px;
}

.qut-food-meta dt {
  color: var(--vp-c-text-3);
  white-space: nowrap;
}

.qut-food-meta dd {
  margin: 0;
  color: var(--vp-c-text-1);
}

.qut-food-dialog-desc {
  margin: 0 0 16px;
  color: var(--vp-c-text-2);
  font-size: 14px;
  line-height: 1.7;
}

.qut-food-photos {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
  margin-bottom: 16px;
}

.qut-food-photo {
  padding: 0;
  border: 1px solid var(--vp-c-divider);
  border-radius: 8px;
  overflow: hidden;
  background: var(--vp-c-bg-soft);
  cursor: zoom-in;
}

.qut-food-photo img {
  display: block;
  width: 100%;
  height: 100%;
  margin: 0 !important;
  aspect-ratio: 4 / 3;
  object-fit: cover;
}

.qut-food-rating-block {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px 20px;
  margin-bottom: 20px;
  padding: 12px 14px;
  border: 1px solid var(--vp-c-divider);
  border-radius: 10px;
  background: var(--vp-c-bg-soft);
}

.qut-food-rating-summary,
.qut-food-rating-picker {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
}

.qut-food-rating-summary strong {
  color: #1781b5;
  font-size: 16px;
}

.qut-food-rate-only {
  padding: 3px 9px;
  border: 1px solid #1781b5;
  border-radius: 12px;
  background: transparent;
  color: #1781b5;
  font-size: 12px;
  cursor: pointer;
}

.qut-food-rate-only:hover:not(:disabled) {
  background: #1781b5;
  color: #fff;
}

.qut-food-rate-only:disabled {
  border-color: var(--vp-c-divider);
  color: var(--vp-c-text-3);
  cursor: not-allowed;
}

.qut-food-rating-message {
  flex-basis: 100%;
  margin: 0;
  color: var(--vp-c-text-2);
  font-size: 12.5px;
  line-height: 1.5;
}

.qut-food-muted {
  color: var(--vp-c-text-3);
  font-size: 12.5px;
}

.qut-food-comments h3 {
  margin: 0 0 8px !important;
  border: 0 !important;
  padding: 0 !important;
  font-size: 16px !important;
}

.qut-food-viewer {
  position: fixed;
  inset: 0;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.85);
}

.qut-food-viewer-img {
  max-width: 92vw;
  max-height: 90vh;
  margin: 0 !important;
  object-fit: contain;
}

.qut-food-viewer-close {
  position: absolute;
  top: 16px;
  right: 20px;
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  font-size: 24px;
  cursor: pointer;
}

.qut-food-viewer-nav {
  position: absolute;
  top: 50%;
  width: 48px;
  height: 48px;
  border: 1px solid var(--vp-c-brand-1);
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.88);
  color: var(--vp-c-brand-1);
  font-size: 20px;
  cursor: pointer;
  transform: translateY(-50%);
}

.qut-food-viewer-nav.prev {
  left: 20px;
}

.qut-food-viewer-nav.next {
  right: 20px;
}

.qut-food-viewer-counter {
  position: absolute;
  top: 28px;
  left: 50%;
  transform: translateX(-50%);
  color: rgba(255, 255, 255, 0.65);
  font-size: 13px;
}

@media (max-width: 720px) {
  .qut-food-modal {
    padding: 0;
  }

  .qut-food-dialog {
    width: 100%;
    max-height: 100vh;
    height: 100vh;
    border-radius: 0;
  }

  .qut-food-search {
    width: 100%;
  }

  .qut-food-filters {
    width: 100%;
  }
}
</style>

<style>
.qut-food-rating-badge {
  display: inline-block;
  margin-right: 6px;
  color: #1781b5;
  font-size: 13px;
  letter-spacing: 1px;
  vertical-align: baseline;
}
</style>
