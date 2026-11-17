<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vitepress'
import { getPageStats, formatNumber, normPath } from '../umami-stats'

const route = useRoute()
const target = ref(false)
const hits = ref(null)

onMounted(async () => {
  target.value = Boolean(document.getElementById('qutwiki-page-views'))
  if (!target.value) return
  try {
    hits.value = await getPageStats(normPath(route.path))
  } catch (err) {
    console.warn('[PageViews] 本页浏览量加载失败（多半被广告拦截或网络拦截）', err)
  }
})
</script>

<template>
  <Teleport v-if="target && hits !== null" to="#qutwiki-page-views">
    <span class="page-views-num">浏览 {{ formatNumber(hits) }} 次</span>
  </Teleport>
</template>
