<script setup>
import { useData } from 'vitepress'
import { computed } from 'vue'
import contributorsData from '../../contributors.json'

const { page } = useData()

const contributors = computed(() => {
  const path = page.value?.relativePath
  if (!path) return []
  return contributorsData[path] || []
})

// 在线编辑器地址（公开编辑模式）。如需更换部署地址，可用 VITE_EDITOR_URL 覆盖。
const EDITOR_BASE = import.meta.env.VITE_EDITOR_URL || 'https://web-edit.quters.top'

// 当前页在编辑器中的深链。VitePress 的 relativePath 相对 docs/（如 start/about/contribute.md），
// 而编辑器内容根为 docs/start，故去掉开头的 start/ 前缀；仅可编辑目录内的页面显示按钮。
const editUrl = computed(() => {
  const rel = page.value?.relativePath
  if (!rel || !rel.startsWith('start/')) return ''
  const editorPath = rel.slice('start/'.length)
  return `${EDITOR_BASE}/note/${editorPath.split('/').map(encodeURIComponent).join('/')}`
})

const lastUpdated = computed(() => {
  const ts = page.value?.lastUpdated
  if (!ts) return ''
  const d = new Date(ts)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${min}`
})

function avatarUrl(contributor) {
  if (contributor.avatar) return contributor.avatar
  if (contributor.github) {
    return `https://github.com/${contributor.github}.png?size=40`
  }
  return null
}

function initials(name) {
  const ascii = name.match(/[A-Za-z]+/g)
  if (ascii && ascii.length) {
    return ascii.map(p => p[0].toUpperCase()).join('').slice(0, 2)
  }
  return name.slice(0, 2).toUpperCase()
}

function hue(name) {
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  return Math.abs(hash) % 360
}
</script>

<template>
  <div v-if="contributors.length" class="contributors">
    <div class="contributors-head">
      <h3 class="contributors-title">本文贡献者</h3>
      <a
        v-if="editUrl"
        class="contributors-edit"
        :href="editUrl"
        target="_blank"
        rel="noopener noreferrer"
        title="在在线编辑器中打开本文"
      >
        <svg class="contributors-edit-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M12 20h9" />
          <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z" />
        </svg>
        <span>在线编辑</span>
      </a>
    </div>
    <div class="contributors-row">
      <div class="contributors-list">
        <a
          v-for="(c, index) in contributors"
          :key="c.github || `${c.name}-${index}`"
          class="contributor-item"
          :href="c.github ? `https://github.com/${c.github}` : undefined"
          :target="c.github ? '_blank' : undefined"
          :rel="c.github ? 'noopener noreferrer' : undefined"
          :title="c.name"
        >
          <img
            v-if="avatarUrl(c)"
            :src="avatarUrl(c)"
            :alt="c.name"
            class="contributor-avatar"
            loading="lazy"
          />
          <span
            v-else
            class="contributor-avatar contributor-avatar-text"
            :style="{ background: `hsl(${hue(c.name)}, 50%, 50%)` }"
          >{{ initials(c.name) }}</span>
          <span class="contributor-name">{{ c.name }}</span>
        </a>
      </div>
      <span v-if="lastUpdated" class="contributors-date">更新于：{{ lastUpdated }}</span>
    </div>
  </div>
</template>

<style scoped>
.contributors {
  margin-top: 32px;
  padding-top: 20px;
  border-top: 1px solid var(--vp-c-divider);
}

.contributors-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.contributors-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--vp-c-text-2);
  margin: 0;
}

.contributors-edit {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border: 1px solid var(--vp-c-divider);
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  color: var(--vp-c-text-2);
  text-decoration: none;
  white-space: nowrap;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}

.contributors-edit:hover {
  color: var(--vp-c-brand-1);
  border-color: var(--vp-c-brand-1);
  background: var(--vp-c-bg-soft);
}

.contributors-edit-icon {
  flex-shrink: 0;
}

.contributors-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.contributors-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.contributors-date {
  font-size: 13px;
  color: var(--vp-c-text-3);
  white-space: nowrap;
  flex-shrink: 0;
}

.contributor-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px 3px 3px;
  border-radius: 20px;
  background: var(--vp-c-bg-soft);
  text-decoration: none;
  transition: background 0.15s;
}

.contributor-item:hover {
  background: var(--vp-c-bg-mute);
}

.contributor-avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}

.contributor-avatar-text {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  color: #fff;
}

.contributor-name {
  font-size: 13px;
  color: var(--vp-c-text-1);
}

.contributor-commits {
  font-size: 10px;
  color: var(--vp-c-text-3);
  background: var(--vp-c-bg-mute);
  padding: 0 5px;
  border-radius: 8px;
  line-height: 16px;
}
</style>
