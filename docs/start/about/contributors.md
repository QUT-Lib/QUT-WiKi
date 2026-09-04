---
top: 3
title: 贡献者
wordCount: false
---

<script setup>
import contributorsMapping from '../../.vitepress/contributors-mapping.json'

const contributorMeta = [
  {
    name: 'LucasAndrew',
    tags: [],
    links: [
      { text: 'GitHub', url: 'https://github.com/LucasAndrew0120'},
      { text: '个人主页', url: 'https://lris625.top' },
    ],
  },
  {
    name: 'youziawa',
    tags: [],
    links: [
      { text: 'GitHub', url: 'https://github.com/youziawa' },
      { text: '博客', url: 'https://www.youziawa.top' },
    ],
  },
  {
    name: 'Roseau',
    tags: [],
    links: [
      { text: 'GitHub', url: 'https://github.com/Roseau-1' },
      { text: '博客', url: 'https://www.roseau.site/' },
    ],
  },
  {
    name: '黎蛰',
    tags: [],
    links: [
      { text: 'GitHub', url: 'https://github.com/wodeshouji' },
    ],
  },
  {
    name: 'electricel',
    tags: [],
    links: [
      { text: 'GitHub', url: 'https://github.com/electricel' },
    ],
  },
  {
    name: '22Milan33',
    tags: [],
    links: [
      { text: 'GitHub', url: 'https://github.com/22Milan33' },
    ],
  },
  {
    name: 'Chen-qwq',
    tags: [],
    links: [
      { text: 'GitHub', url: 'https://github.com/Chen-qwq' },
    ],
  },
  {
    name: 'Link-Blue',
    tags: [],
    links: [
      { text: 'GitHub', url: 'https://github.com/Link-Blue' },
    ],
  },
  {
    name: 'cxz312',
    tags: [],
    links: [
      { text: 'GitHub', url: 'https://github.com/CXZ-cxz-cell' },
    ],
  }
]

const contributors = contributorMeta.map((item) => {
  const mapped = contributorsMapping[item.name] || {}
  const github = mapped.github || item.github
  return {
    ...item,
    github,
    avatar: mapped.avatar || item.avatar,
    links: item.links?.length
      ? item.links
      : github
        ? [{ text: 'GitHub', url: `https://github.com/${github}` }]
        : [],
  }
})
</script>

# 贡献者

感谢所有参与 QUTWiKi 建设、维护、资料整理和内容编写的同学。

<div class="contributors-page-grid">
  <article
    v-for="person in contributors"
    :key="person.name"
    class="contributors-page-card"
    :class="{ 'contributors-page-card-no-tags': !person.tags.length }"
  >
    <img v-if="person.avatar" class="contributors-page-avatar" :src="person.avatar" :alt="person.name" />
    <span v-else class="contributors-page-avatar contributors-page-avatar-text">{{ person.name.slice(0, 2) }}</span>
    <span class="contributors-page-name">{{ person.name }}</span>
    <span v-if="person.tags.length" class="contributors-page-tags">{{ person.tags.join(' / ') }}</span>
    <div v-if="person.links.length" class="contributors-page-links">
      <a
        v-for="link in person.links"
        :key="link.url"
        :href="link.url"
        target="_blank"
        rel="noopener noreferrer"
        :aria-label="link.text"
        :title="link.text"
      >
        <svg v-if="link.text === 'GitHub'" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden="true">
          <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82A7.65 7.65 0 0 1 8 3.87c.68 0 1.36.09 2 .26 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
        </svg>
        <span v-else>{{ link.text }}</span>
      </a>
    </div>
  </article>
</div>

<style scoped>
.contributors-page-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin: 32px 0;
}

.contributors-page-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-height: 124px;
  padding: 8px;
  text-align: center;
}

.contributors-page-card-no-tags {
  justify-content: center;
  gap: 8px;
}

.contributors-page-card-no-tags .contributors-page-avatar {
  margin: 0;
}

.contributors-page-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  object-fit: cover;
  margin: 6px 0;
}

.contributors-page-avatar-text {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  background: var(--vp-c-brand-1);
}

.contributors-page-name {
  color: var(--vp-c-text-1);
  font-size: 16px;
  line-height: 1.4;
}

.contributors-page-tags {
  min-height: 17px;
  margin-bottom: 6px;
  color: var(--vp-c-text-3);
  font-size: 12px;
  line-height: 1.4;
}

.contributors-page-links {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  min-height: 18px;
}

.contributors-page-links a {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  color: var(--vp-c-brand-1);
  font-size: 12px;
  text-decoration: none;
  transition: color 0.15s ease;
}

.contributors-page-links a:has(span) {
  width: auto;
}

.contributors-page-links a:hover {
  color: var(--vp-c-brand-2);
}

@media (max-width: 640px) {
  .contributors-page-grid {
    grid-template-columns: 1fr;
  }
}

@media (min-width: 641px) and (max-width: 960px) {
  .contributors-page-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

## 开源项目

本项目的一些前端样式和后端代码参考了[**西邮Wiki**](https://wiki.cooo.site/)，在此感谢[**西邮Wiki项目组**](https://github.com/xupt-wiki/xupt-wiki)的无私开源。

校园地图功能参考了[**CQUMAPS**（重庆大学校园地图导航系统）](https://github.com/littlemana-bot/CQUMAPS)与[**CQU-openlib**（重庆大学资源共享计划）](https://github.com/INFO-studio/CQU-openlib)，页面布局、交互设计与配色方案借鉴自其开源代码（[cqu-openlib.cn/map](https://cqu-openlib.cn/map)），在此感谢两个项目的无私开源。

## 特别鸣谢

- 感谢青岛理工大学杨鑫老师为校园地图移动端详情卡片的固定定位与浏览器底部栏适配提供解决思路。
