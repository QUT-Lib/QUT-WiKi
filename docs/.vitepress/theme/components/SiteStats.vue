<script setup>
import { onMounted, ref } from 'vue'
import { getSiteStats, formatNumber } from '../umami-stats'

const pageviews = ref(null)
const visitors = ref(null)
const ready = ref(false)

onMounted(async () => {
  ready.value = Boolean(document.getElementById('qutwiki-site-stats'))
  try {
    const stats = await getSiteStats()
    pageviews.value = stats.pageviews
    visitors.value = stats.visitors
  } catch (err) {
    console.warn('[SiteStats] 全站统计加载失败（多半被广告拦截或网络拦截）', err)
  }
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
