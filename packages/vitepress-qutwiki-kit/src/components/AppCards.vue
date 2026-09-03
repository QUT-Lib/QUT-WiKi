<script setup lang="ts">
import { safeLink } from '../link.ts'

export interface AppCardItem {
  text?: string
  icon?: string
  desc?: string
  link?: string
}

withDefaults(defineProps<{
  links: AppCardItem[]
  width?: string
  textLines?: number
  descLines?: number | false
}>(), {
  width: '12em',
  textLines: 2,
  descLines: false,
})

function isExternal(value?: string) {
  return safeLink(value)?.startsWith('http') ?? false
}
</script>

<template>
  <div class="wk-app-cards" :style="{ '--wk-col-width': width }">
    <component
      :is="safeLink(item.link) ? 'a' : 'span'"
      v-for="(item, index) in links"
      :key="`${item.text}-${index}`"
      class="wk-app-card"
      :href="safeLink(item.link)"
      :target="isExternal(item.link) ? '_blank' : undefined"
      :rel="isExternal(item.link) ? 'noopener noreferrer' : undefined"
    >
      <img v-if="item.icon?.startsWith('http')" class="wk-app-card-icon" :src="item.icon" alt="">
      <span v-if="item.text || item.desc" class="wk-app-card-body">
        <span class="wk-ellipsis wk-app-card-title" :style="{ '--wk-lines': textLines }">{{ item.text }}</span>
        <span
          v-if="item.desc"
          class="wk-ellipsis wk-app-card-desc"
          :style="descLines ? { '--wk-lines': descLines } : undefined"
        >{{ item.desc }}</span>
      </span>
    </component>
  </div>
</template>

<style scoped>
.wk-app-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(var(--wk-col-width, 12em), 1fr)); gap: .8em; margin: 1em 0; }
.wk-app-card { display: flex; align-items: center; gap: .7em; margin: 0; padding: .6em .8em; border: 1px solid transparent; border-radius: .5em; background: var(--vp-c-bg-soft); color: inherit; line-height: 1.4; text-decoration: none; transition: .2s; }
a.wk-app-card:hover { border-color: var(--vp-c-brand-1); background: var(--vp-c-bg); color: var(--vp-c-brand-1); }
.wk-app-card-icon { flex-shrink: 0; width: 2.2em; height: 2.2em; margin: 0; border-radius: .45em; object-fit: contain; }
.wk-app-card-body { display: flex; flex: 1; min-width: 0; flex-direction: column; }
.wk-app-card-title { font-weight: 500; }
.wk-app-card-desc { margin-top: .2em; opacity: .8; font-size: .8em; }
.wk-ellipsis { display: -webkit-box; overflow: hidden; -webkit-line-clamp: var(--wk-lines); line-clamp: var(--wk-lines); -webkit-box-orient: vertical; }
</style>
