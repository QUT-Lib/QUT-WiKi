<script setup>
import { onMounted, ref } from 'vue'

const SHARE_ID = 'iib1PnzFrZEe9dVR'
const UMAMI_ORIGIN = 'https://umami.lris625.top'
const CACHE_KEY = 'qutwiki:site-stats'
const CACHE_TTL = 10 * 60 * 1000

const pageviews = ref(null)
const visitors = ref(null)
const ready = ref(false)

function formatNumber(value) {
  if (value >= 10000) return `${(value / 1000).toFixed(1)}K`
  return value.toLocaleString('zh-CN')
}

function readCache() {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY)
    if (!raw) return null
    const cached = JSON.parse(raw)
    if (!cached || Date.now() - cached.at > CACHE_TTL) return null
    return cached
  } catch {
    return null
  }
}

function writeCache(data) {
  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify({ at: Date.now(), ...data }))
  } catch {}
}

async function loadStats() {
  const cached = readCache()
  if (cached) {
    pageviews.value = cached.pageviews
    visitors.value = cached.visitors
    return
  }

  try {
    const share = await (await fetch(`${UMAMI_ORIGIN}/api/share/${SHARE_ID}`)).json()
    const headers = {
      'x-umami-share-token': share.token,
      'x-umami-share-context': '1',
    }
    const stats = await (
      await fetch(
        `${UMAMI_ORIGIN}/api/websites/${share.websiteId}/stats?startAt=0&endAt=${Date.now()}`,
        { headers },
      )
    ).json()
    pageviews.value = stats.pageviews
    visitors.value = stats.visitors
    writeCache({ pageviews: stats.pageviews, visitors: stats.visitors })
  } catch {}
}

onMounted(() => {
  ready.value = Boolean(document.getElementById('qutwiki-site-stats'))
  loadStats()
})
</script>

<template>
  <Teleport v-if="ready" to="#qutwiki-site-stats">
    <template v-if="pageviews !== null || visitors !== null">
      <span class="site-stats-sep">·</span>
      <span v-if="visitors !== null" class="site-stats-item">
        访客 <strong>{{ formatNumber(visitors) }}</strong>
      </span>
      <span v-if="visitors !== null && pageviews !== null" class="site-stats-sep">·</span>
      <span v-if="pageviews !== null" class="site-stats-item">
        浏览量 <strong>{{ formatNumber(pageviews) }}</strong>
      </span>
    </template>
  </Teleport>
</template>

<style>
.site-stats-item strong {
  color: rgb(1, 93, 149);
  font-weight: 700;
}

.site-stats-sep {
  margin: 0 6px;
  color: var(--vp-c-text-3);
}
</style>
