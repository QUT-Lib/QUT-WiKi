<script setup>
import { useData } from 'vitepress'
import { computed } from 'vue'
import historyData from '../../history.json'

const REPO_URL = 'https://github.com/QUT-Lib/QUT-WiKi'

const { page } = useData()

const commits = computed(() => {
  const path = page.value?.relativePath
  if (!path) return []
  return historyData[path] || []
})

const lastCommit = computed(() => commits.value[0] || null)

function formatDate(iso) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
</script>

<template>
  <section v-if="commits.length" class="git-history" aria-labelledby="git-history-title">
    <h2 id="git-history-title" class="git-history-title">
      页面历史
      <a class="header-anchor" href="#git-history-title" aria-label="Permalink to 页面历史">#</a>
    </h2>
    <details class="git-history-details">
      <summary class="git-history-summary">
        <span class="git-history-summary-main">
          <svg class="git-history-icon" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M11.93 8.5a4.002 4.002 0 0 1-7.86 0H.75a.75.75 0 0 1 0-1.5h3.32a4.002 4.002 0 0 1 7.86 0h3.32a.75.75 0 0 1 0 1.5Zm-1.43-.75a2.5 2.5 0 1 0-5 0 2.5 2.5 0 0 0 5 0Z" />
          </svg>
          <span>最后编辑于 {{ formatDate(lastCommit.date) }}</span>
        </span>
        <span class="git-history-summary-action">查看完整历史</span>
        <svg class="git-history-chevron" viewBox="0 0 16 16" aria-hidden="true">
          <path d="M12.78 5.22a.749.749 0 0 1 0 1.06l-4.25 4.25a.749.749 0 0 1-1.06 0L3.22 6.28a.749.749 0 1 1 1.06-1.06L8 8.939l3.72-3.719a.749.749 0 0 1 1.06 0Z" />
        </svg>
      </summary>
      <ul class="git-history-list">
        <li v-for="c in commits" :key="c.hash" class="git-history-item">
          <span class="git-history-hash-block">
            <a
              class="git-history-hash"
              :href="`${REPO_URL}/commit/${c.hash}`"
              target="_blank"
              rel="noopener noreferrer"
              :title="`查看提交 ${c.hash}`"
            >{{ c.hash }}</a>
          </span>
          <span class="git-history-message" :title="c.message">{{ c.message }}</span>
          <span class="git-history-meta">
            <a
              v-if="c.github"
              class="git-history-author"
              :href="`https://github.com/${c.github}`"
              target="_blank"
              rel="noopener noreferrer"
              :title="`${c.author} 的 GitHub 主页`"
            >{{ c.author }}</a>
            <span v-else class="git-history-author">{{ c.author }}</span>
            <span class="git-history-time">于 {{ formatDate(c.date) }}</span>
          </span>
        </li>
      </ul>
    </details>
  </section>
</template>

<style scoped>
.git-history {
  margin-top: 48px;
}

.git-history-title {
  position: relative;
  margin: 0 0 16px;
  border-top: 1px solid var(--vp-c-divider);
  padding-top: 24px;
  font-size: 24px;
  line-height: 32px;
  font-weight: 600;
  color: var(--vp-c-text-1);
}

.git-history-title .header-anchor {
  opacity: 0;
  transition: opacity 0.2s;
}

.git-history-title:hover .header-anchor {
  opacity: 1;
}

.git-history-details {
  overflow: hidden;
  border: 1px solid var(--vp-c-divider);
  border-radius: 10px;
  background: var(--vp-c-bg-soft);
}

.git-history-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  color: var(--vp-c-text-2);
  font-size: 14px;
  cursor: pointer;
  list-style: none;
  user-select: none;
}

.git-history-summary::-webkit-details-marker {
  display: none;
}

.git-history-summary::after {
  display: none;
}

.git-history-details[open] .git-history-chevron {
  transform: rotate(180deg);
}

.git-history-summary:hover {
  color: var(--vp-c-brand-1);
}

.git-history-summary-main,
.git-history-summary-action {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.git-history-summary-main {
  font-weight: 700;
}

.git-history-summary-action {
  margin-left: auto;
  color: var(--vp-c-text-3);
  font-size: 13px;
  font-weight: 400;
}

.git-history-icon {
  flex: 0 0 auto;
  width: 20px;
  height: 20px;
  color: var(--vp-c-brand-1);
  fill: currentColor;
  transform: rotate(90deg);
}

.git-history-chevron {
  flex: 0 0 auto;
  width: 16px;
  height: 16px;
  color: var(--vp-c-text-3);
  fill: currentColor;
  transition: transform 0.2s ease;
}

.git-history-list {
  list-style: none;
  margin: 0;
  padding: 0 16px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.git-history-item {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 8px;
  padding: 0;
  font-size: 13px;
  line-height: 1.6;
}

.git-history-hash {
  flex-shrink: 0;
  font-family: var(--vp-font-family-mono, monospace);
  font-size: 12px;
  color: var(--vp-c-brand-1);
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
  text-decoration-color: color-mix(in srgb, currentColor 55%, transparent);
  transition: color 0.15s, text-decoration-color 0.15s;
}

.git-history-hash-block {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  padding: 3px 7px;
  border: 1px solid var(--vp-c-divider);
  border-radius: 5px;
  background: var(--vp-c-bg);
  line-height: 1;
}

.git-history-hash:hover {
  color: var(--vp-c-brand-2);
  text-decoration-color: currentColor;
}

.git-history-message {
  color: var(--vp-c-text-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.git-history-meta {
  margin-left: auto;
  flex-shrink: 0;
  color: var(--vp-c-text-3);
  font-size: 12px;
  display: inline-flex;
  gap: 6px;
  align-items: baseline;
}

.git-history-author {
  color: var(--vp-c-text-2);
  text-decoration: none;
}

a.git-history-author:hover {
  color: var(--vp-c-brand-1);
  text-decoration: underline;
}

.git-history-time {
  white-space: nowrap;
}

</style>
