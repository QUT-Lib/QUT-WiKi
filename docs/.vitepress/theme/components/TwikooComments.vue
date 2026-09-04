<script setup>
import { nextTick, onMounted, ref } from 'vue'

const props = defineProps({
  envId: {
    type: String,
    required: true,
  },
})

const container = ref(null)
const loadFailed = ref(false)

onMounted(async () => {
  await nextTick()

  try {
    // Twikoo accesses browser globals while loading, so it must not be imported during SSR.
    const twikoo = await import('twikoo')
    await twikoo.init({
      envId: props.envId,
      el: container.value,
      lang: 'zh-CN',
    })
  } catch (error) {
    loadFailed.value = true
    console.error('Twikoo 初始化失败：', error)
  }
})
</script>

<template>
  <section class="twikoo-comments" aria-labelledby="twikoo-comments-title">
    <h2 id="twikoo-comments-title">评论</h2>
    <div ref="container" />
    <p v-if="loadFailed" class="twikoo-comments-error">评论加载失败，请稍后重试。</p>
  </section>
</template>

<style scoped>
.twikoo-comments {
  margin-top: 48px;
  padding-top: 24px;
  border-top: 1px solid var(--vp-c-divider);
}

.twikoo-comments h2 {
  margin: 0 0 24px;
  border: 0;
  padding: 0;
  font-size: 24px;
  line-height: 32px;
}

.twikoo-comments-error {
  color: var(--vp-c-danger-1);
  font-size: 14px;
}
</style>
