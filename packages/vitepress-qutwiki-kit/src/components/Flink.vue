<script setup lang="ts">
import { computed } from 'vue'
import { safeLink } from '../link.ts'

const props = defineProps<{
  name: string
  link: string
  avatar?: string
  siteshot?: string
  desc?: string
}>()

const href = computed(() => safeLink(props.link))

function hideBroken(event: Event) {
  ;(event.currentTarget as HTMLImageElement).style.display = 'none'
}
</script>

<template>
  <component :is="href ? 'a' : 'article'" class="wk-flink" :href="href" target="_blank" rel="noopener noreferrer">
    <div class="wk-flink-shot"><img v-if="siteshot" :src="siteshot" :alt="name" loading="lazy" @error="hideBroken"></div>
    <div class="wk-flink-info">
      <img v-if="avatar" class="wk-flink-avatar" :src="avatar" :alt="name" loading="lazy" @error="hideBroken">
      <span class="wk-flink-title">{{ name }}</span>
      <span v-if="desc" class="wk-flink-desc">{{ desc }}</span>
    </div>
  </component>
</template>

<style scoped>
.wk-flink { display: inline-block; width: calc(25% - 16px); margin: 8px; vertical-align: top; line-height: 1.4; color: inherit; text-decoration: none; }
.wk-flink-shot { width: 100%; aspect-ratio: 7 / 5; overflow: hidden; border-radius: 6px; box-shadow: 0 1px 2px rgb(0 0 0 / 20%); background: var(--vp-c-bg-soft); transition: box-shadow .28s; }
.wk-flink:hover .wk-flink-shot { box-shadow: 0 4px 8px rgb(0 0 0 / 10%), 0 8px 16px rgb(0 0 0 / 10%); }
.wk-flink-shot img { width: 100%; height: 100%; pointer-events: none; object-fit: cover; transition: transform 2s; }
.wk-flink:hover .wk-flink-shot img { transform: scale(1.08); }
.wk-flink-info { margin-top: 8px; }
.wk-flink-avatar { float: left; width: 32px; height: 32px; margin: 2px 8px 8px 0; border-radius: 50%; pointer-events: none; background: var(--vp-c-bg-soft); }
.wk-flink-info span { display: block; }
.wk-flink-title, .wk-flink-desc { display: -webkit-box; overflow: hidden; -webkit-box-orient: vertical; }
.wk-flink-title { color: var(--vp-c-text-1); font-size: 16px; font-weight: 600; -webkit-line-clamp: 1; transition: color .28s; }
.wk-flink:hover .wk-flink-title { color: var(--vp-c-brand-1); }
.wk-flink-desc { min-height: 2.4em; color: var(--vp-c-text-2); font-size: 16px; line-height: 1.2; -webkit-line-clamp: 2; }
@media (max-width: 768px) { .wk-flink { width: calc(33.333% - 16px); } }
@media (max-width: 500px) { .wk-flink { width: calc(50% - 16px); } }
</style>
