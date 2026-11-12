<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { loadAMap, MAP_STYLES } from './amap-loader.js'

const props = defineProps({
  items: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['select'])

/* 贴吧楼主分享的两个高德收藏夹（每个 10 个地点） */
const AMAP_FOOD_MAPS = [
  {
    name: '青岛美味地图1',
    url: 'https://guinness.autonavi.com/activity/2020CommonLanding/index.html?id=default&local=1&logId=&logParams=&gd_from=jinisi&schema=amapuri%3A%2F%2Fajx_favorites%2Ffolder%3Fdata%3D%257B%2522ugcId%2522%253A%252207409928610324540958%2522%252C%2522forceCustom%2522%253Atrue%252C%2522pathId%2522%253A6%252C%2522isCreatorShare%2522%253Atrue%257D&share_from=favorites_FavoriteFolder&share_from_type=AJX&share_type=url&share_lastClickSpm=amap.P01079.0.D044&share_bid=thq9kekb1mqmc2kfbbe7967g47dg5f533255a01',
  },
  {
    name: '青岛美味地图2',
    url: 'https://guinness.autonavi.com/activity/2020CommonLanding/index.html?id=default&local=1&logId=&logParams=&gd_from=jinisi&schema=amapuri%3A%2F%2Fajx_favorites%2Ffolder%3Fdata%3D%257B%2522ugcId%2522%253A%252207409928610324542912%2522%252C%2522forceCustom%2522%253Atrue%252C%2522pathId%2522%253A6%252C%2522isCreatorShare%2522%253Atrue%257D&share_from=favorites_FavoriteFolder&share_from_type=AJX&share_type=url&share_lastClickSpm=amap.P01079.0.D044&share_bid=ithkek8b1qomkcf7bbe9767g4dg53f53q255a01',
  },
]

const mapEl = ref(null)
const error = ref('')
const loading = ref(true)

let map = null
let AMap = null
let markers = []
let themeObserver = null
let viewObserver = null

const points = computed(() =>
  props.items.filter((item) => Array.isArray(item.coord) && item.coord.length === 2)
)

const campusCount = computed(() => {
  const counts = { s: 0, h: 0, other: 0 }
  for (const item of points.value) {
    if (item.campus === 's') counts.s++
    else if (item.campus === 'h') counts.h++
    else counts.other++
  }
  return counts
})

const hasHuangdao = computed(() => campusCount.value.h > 0)
const hasShibei = computed(() => campusCount.value.s > 0 || campusCount.value.other > 0)

function isDark() {
  return typeof document !== 'undefined' && document.documentElement.classList.contains('dark')
}

function pinContent(item) {
  const kind = item.campus === 'h' ? 'h' : 's'
  return `<span class="qut-food-pin qut-food-pin--${kind}"><i></i></span>`
}

function clearMarkers() {
  for (const marker of markers) marker.setMap(null)
  markers = []
}

function renderMarkers() {
  if (!map || !AMap) return
  clearMarkers()
  const list = points.value
  if (!list.length) return

  markers = list.map((item) => {
    const marker = new AMap.Marker({
      position: item.coord,
      title: item.name,
      content: pinContent(item),
      anchor: 'center',
      zIndex: 120,
    })
    marker.on('click', () => emit('select', item))
    marker.setMap(map)
    return marker
  })

  if (list.length === 1) {
    map.setZoomAndCenter(14, list[0].coord)
  } else {
    map.setFitView(markers, false, [56, 56, 56, 56], 15)
  }
}

async function initMap() {
  try {
    AMap = await loadAMap()
    if (!mapEl.value) return
    map = new AMap.Map(mapEl.value, {
      zoom: 11,
      center: [120.3, 36.03],
      viewMode: '2D',
      resizeEnable: true,
      mapStyle: MAP_STYLES[isDark() ? 'dark' : 'light'],
    })
    loading.value = false
    renderMarkers()

    themeObserver = new MutationObserver(() => {
      if (map) map.setMapStyle(MAP_STYLES[isDark() ? 'dark' : 'light'])
    })
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
  } catch (err) {
    console.error('美食地图加载失败：', err)
    error.value = err?.message || '未知错误'
    loading.value = false
  }
}

watch(
  () => points.value.map((item) => item.id).join(','),
  () => renderMarkers()
)

onMounted(() => {
  if (typeof IntersectionObserver === 'undefined' || !mapEl.value) {
    initMap()
    return
  }
  /* 地图 SDK 体积较大，滚动到可视区域附近再加载 */
  viewObserver = new IntersectionObserver(
    (entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return
      viewObserver.disconnect()
      viewObserver = null
      initMap()
    },
    { rootMargin: '240px 0px' }
  )
  viewObserver.observe(mapEl.value)
})

onBeforeUnmount(() => {
  viewObserver?.disconnect()
  viewObserver = null
  themeObserver?.disconnect()
  themeObserver = null
  clearMarkers()
  if (map) {
    map.destroy()
    map = null
  }
})
</script>

<template>
  <section class="qut-food-map">
    <div class="qut-food-map-head">
      <div>
        <h3 class="qut-food-map-title">美食地图</h3>
        <p class="qut-food-map-sub">
          <template v-if="points.length">
            当前筛选下共 {{ points.length }} 个地点
            <span v-if="hasShibei" class="qut-food-map-dot s">市北</span>
            <span v-if="hasHuangdao" class="qut-food-map-dot h">黄岛</span>
          </template>
          <template v-else>当前筛选下没有带坐标的地点</template>
        </p>
      </div>
      <div class="qut-food-map-sources">
        <a
          v-for="source in AMAP_FOOD_MAPS"
          :key="source.name"
          class="qut-food-map-source"
          :href="source.url"
          target="_blank"
          rel="noopener"
        >高德「{{ source.name }}」</a>
      </div>
    </div>

    <div class="qut-food-map-canvas-wrap">
      <div ref="mapEl" class="qut-food-map-canvas" role="application" aria-label="校外美食地图" />
      <p v-if="loading" class="qut-food-map-status">地图加载中……</p>
      <p v-else-if="error" class="qut-food-map-status">
        地图加载失败，可点击上方高德链接查看（{{ error }}）
      </p>
    </div>

    <p class="qut-food-map-tip">
      点位来自贴吧「青岛美味地图」探店帖，坐标已按高德 GCJ02 校准。点击标记可直接打开该店的详情、评分与评论；切换分类、校区或搜索时，地图会同步更新。
    </p>
  </section>
</template>

<style scoped>
.qut-food-map {
  margin: 4px 0 22px;
  padding: 14px 14px 12px;
  border: 1px solid var(--vp-c-divider);
  border-radius: 14px;
  background: var(--vp-c-bg-soft);
}

.qut-food-map-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px 16px;
  margin-bottom: 10px;
}

.qut-food-map-title {
  margin: 0 !important;
  padding: 0 !important;
  border: 0 !important;
  font-size: 17px !important;
  line-height: 1.4;
}

.qut-food-map-sub {
  margin: 2px 0 0;
  color: var(--vp-c-text-3);
  font-size: 12.5px;
}

.qut-food-map-dot {
  display: inline-flex;
  align-items: center;
  margin-left: 8px;
  color: var(--vp-c-text-2);
}

.qut-food-map-dot::before {
  content: '';
  width: 8px;
  height: 8px;
  margin-right: 4px;
  border-radius: 50%;
  background: #015d95;
}

.qut-food-map-dot.h::before {
  background: #7ba8e0;
}

.qut-food-map-sources {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.qut-food-map-source {
  padding: 2px 9px;
  border: 1px solid var(--vp-c-brand-1);
  border-radius: 12px;
  color: var(--vp-c-brand-1);
  font-size: 12px;
  text-decoration: none;
  transition: background 0.2s, color 0.2s;
}

.qut-food-map-source:hover {
  background: var(--vp-c-brand-1);
  color: #fff;
}

.qut-food-map-canvas-wrap {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--vp-c-divider);
  border-radius: 10px;
  background: var(--vp-c-bg);
}

.qut-food-map-canvas {
  width: 100%;
  height: 420px;
}

.qut-food-map-status {
  position: absolute;
  inset: 0;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  padding: 16px;
  background: var(--vp-c-bg);
  color: var(--vp-c-text-3);
  font-size: 13px;
  text-align: center;
}

.qut-food-map-tip {
  margin: 8px 0 0;
  color: var(--vp-c-text-3);
  font-size: 12px;
  line-height: 1.6;
}

@media (max-width: 720px) {
  .qut-food-map-canvas {
    height: 320px;
  }
}
</style>

<style>
/* 地图标记由高德 SDK 动态插入，不能使用 scoped 样式 */
.qut-food-pin {
  display: block;
  width: 22px;
  height: 22px;
  border: 2px solid #fff;
  border-radius: 50% 50% 50% 0;
  background: #015d95;
  box-shadow: 0 2px 8px rgb(0 0 0 / 0.35);
  transform: rotate(-45deg);
  transition: transform 0.15s ease;
}

.qut-food-pin i {
  display: block;
  width: 6px;
  height: 6px;
  margin: 6px;
  border-radius: 50%;
  background: #fff;
  transform: rotate(45deg);
}

.qut-food-pin--h {
  background: #7ba8e0;
}

.amap-marker:hover .qut-food-pin {
  transform: rotate(-45deg) scale(1.15);
}
</style>
