<script setup lang="ts">
import { computed } from 'vue'
import { useData } from 'vitepress'
import Flink from './Flink.vue'

export interface FlinkItem {
  name: string
  link: string
  avatar?: string
  siteshot?: string
  desc?: string
  descr?: string
}

const props = defineProps<{ links?: FlinkItem[] }>()
const { frontmatter } = useData()
const items = computed(() => props.links ?? (frontmatter.value.flinks as FlinkItem[] | undefined) ?? [])
</script>

<template>
  <div class="wk-flinks" role="list">
    <Flink v-for="(item, index) in items" :key="`${item.name}-${index}`" v-bind="item" :desc="item.desc ?? item.descr" />
  </div>
</template>

<style scoped>
.wk-flinks { max-width: 904px; margin: 0 auto; }
</style>
