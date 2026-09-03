<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'

const props = withDefaults(defineProps<{ envId: string; lang?: string; title?: string; errorText?: string }>(), {
  lang: 'zh-CN',
  title: '评论',
  errorText: '评论加载失败，请稍后重试。',
})
const container = ref<HTMLElement>()
const loadFailed = ref(false)

onMounted(async () => {
  await nextTick()
  try {
    const twikoo = await import('twikoo')
    await twikoo.init({ envId: props.envId, el: container.value, lang: props.lang })
  } catch (error) {
    loadFailed.value = true
    console.error('Failed to initialize Twikoo:', error)
  }
})
</script>

<template>
  <section class="wk-comments" aria-labelledby="wk-comments-title">
    <h2 id="wk-comments-title">{{ title }}</h2>
    <div ref="container" />
    <p v-if="loadFailed" class="wk-comments-error">{{ errorText }}</p>
  </section>
</template>

<style scoped>
.wk-comments { margin-top: 48px; padding-top: 24px; border-top: 1px solid var(--vp-c-divider); }
.wk-comments h2 { margin: 0 0 24px; border: 0; padding: 0; font-size: 24px; line-height: 32px; }
.wk-comments-error { color: var(--vp-c-danger-1); font-size: 14px; }
</style>
