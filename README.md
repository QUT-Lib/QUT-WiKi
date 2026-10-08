# 青理 Wiki（QUTWiKi）

青岛理工大学 Wiki 知识库，由学生自发维护的生活指南，帮助新生和在校生快速获取校园生活、学习资源、社团活动等实用信息。

## 本地开发

需要 Node.js 22.17 或更高版本。依赖安装优先使用 `npm ci`，避免无意改动锁文件。

```bash
npm ci
npm run dev       # 启动开发服务器 http://localhost:5173
```

使用 PowerShell 构建并启动本地开发服务器：

```powershell
./build.ps1
```

网站基于 [VitePress](https://vitepress.dev/) 构建，文档使用 Markdown 编写。

## 参与编写

详见 [参与编写](https://wiki.quters.top/start/about/contribute) 页面，内容涵盖环境准备、文档规范、提交流程等完整指引。


## 致谢

本项目的部分前端样式和后端代码参考了[西邮 Wiki](https://wiki.cooo.site/)（[xupt-wiki/xupt-wiki](https://github.com/xupt-wiki/xupt-wiki)），在此感谢西邮 Wiki 项目组的无私开源。

校园地图功能参考了[重庆大学校园地图导航系统](https://github.com/littlemana-bot/CQUMAPS)（[CQUMAPS](https://github.com/littlemana-bot/CQUMAPS)）与[重庆大学资源共享计划 CQU-openlib](https://github.com/INFO-studio/CQU-openlib)（[cqu-openlib.cn/map](https://cqu-openlib.cn/map)）的页面布局、交互设计与配色方案，在此感谢两个项目的无私开源。

在线编辑功能参考了[**南华大学**的Fork项目](https://github.com/hzxyayaya/USC-Wiki-Editor)，在此感谢[**南华大学 Wiki (USC Wiki)**](https://uscwiki.com/)项目组的无私开源

感谢青岛理工大学杨鑫老师为校园地图移动端详情卡片的固定定位与浏览器底部栏适配提供解决思路。

## 贡献者

感谢所有参与 QUTWiKi 建设、维护、资料整理和内容编写的同学。

<a href="https://github.com/QUT-Lib/QUT-WiKi/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=QUT-Lib/QUT-WiKi" alt="贡献者" />
</a>



## 项目结构

<details>
<summary>展开查看完整目录结构</summary>

```
.
├── .gitattributes              # GitHub Linguist 配置
├── .gitignore
├── build.ps1                   # Windows 本地开发启动脚本
├── package.json
├── README.md
├── vendor/                     # 已核验并固定摘要的第三方依赖归档
│   └── xlsx-0.20.3.tgz
├── code/                       # 腾讯文档 XLSX 同步服务
│   ├── Dockerfile              # 非 root 生产镜像
│   ├── server.mjs              # HTTP 服务入口
│   ├── xlsx-sync.mjs           # Chromium 同步及资源限制
│   └── vendor/                 # 后端独立 npm 项目的依赖归档
│
└── docs/                       # VitePress 文档根目录
    ├── index.md                # 首页
    ├── flink.md                # 友情链接
    ├── map.md                  # 校园地图
    ├── public/
    │   ├── _headers            # 静态站安全响应头
    │   ├── _redirects          # 静态重定向规则
    │   ├── BingSiteAuth.xml    # 必应站长验证
    │   ├── images/             # 站点图片资源
    │   └── map/                # 校园地图静态资源
    ├── resources/              # 可供下载的文档与数据
    │   ├── QUT-Organization.xlsx
    │   └── 2025-2026学年学生社团主要负责人名单公示表.pdf
    ├── scripts/                # 文档辅助脚本
    │   ├── images.mjs          # 图片处理
    │   └── sync-tencent-docs.mjs   # 腾讯文档同步
    │
    ├── .vitepress/             # VitePress 配置与主题
    │   ├── config.ts           # 站点配置
    │   ├── contributors-mapping.json
    │   ├── contributors.json   # 贡献者数据
    │   ├── history.json        # 提交历史数据
    │   ├── plugins/
    │   │   ├── flink-block.ts  # 友情链接块解析
    │   │   └── xlsx-table.ts   # XLSX 卡片渲染
    │   ├── scripts/
    │   │   ├── build-fresh.mjs        # 全量构建
    │   │   ├── free-port.mjs          # 端口释放
    │   │   └── gen-contributors.mjs   # 贡献者信息生成
    │   └── theme/
    │       ├── index.ts               # 主题入口
    │       ├── MyLayout.vue           # 自定义布局
    │       ├── style.css              # 自定义样式
    │       ├── announcement.ts        # 公告配置
    │       └── components/
    │           ├── AppCards.vue       # 应用卡片组件
    │           ├── Contributors.vue   # 贡献者组件
    │           ├── Flink.vue          # 友情链接组件
    │           ├── Flinks.vue         # 友情链接列表组件
    │           ├── FoodCards.vue      # 美食卡片组件
    │           ├── Gallery.vue        # 图片集组件
    │           ├── GitHistory.vue     # 提交历史组件
    │           ├── MapView.vue        # 校园地图组件
    │           ├── SiteStats.vue      # 站点统计组件
    │           ├── TwikooComments.vue # 评论组件
    │           ├── food-data.js       # 美食数据
    │           ├── food-twikoo.js     # 美食评论配置
    │           └── map-data.js        # 地图数据
    │
    └── start/                  # 文章目录
        ├── preface/
        │   └── introduction.md       # 前言 / 项目介绍
        ├── newstudent/               # 新生入学
        │   ├── 2026-teacher-phone.md      # 2026 教师联系方式
        │   ├── admission-checklist.md     # 入学清单
        │   ├── admission-resources.md     # 入学资源
        │   ├── anti-fraud.md              # 防诈骗指南
        │   ├── campus-buildings.md        # 校园建筑
        │   ├── campus-card.md             # 校园卡
        │   ├── campus-network.md          # 校园网
        │   ├── military-assistant.md      # 军训助手
        │   └── transportation.md          # 交通出行
        ├── campus-life/              # 校园生活
        │   ├── competition/          # 学科竞赛
        │   │   ├── qut-racing.md          # 青理赛车
        │   │   └── qut-robot.md           # 青理机器人
        │   ├── daily-life/           # 日常生活
        │   │   ├── campus-surroundings.md # 校园周边
        │   │   ├── dormitory.md           # 宿舍
        │   │   ├── food.md                # 美食
        │   │   └── health-insurance.md    # 医保
        │   ├── qut-organization/     # 校内组织
        │   │   ├── club.md                # 社团
        │   │   ├── interest-group.md      # 兴趣小组
        │   │   ├── lab.md                 # 实验室
        │   │   ├── postgraduate-union.md  # 研究生会
        │   │   └── school-student&league-organizations.md  # 校学生会及社团组织
        │   ├── study/                # 学习相关
        │   │   ├── academic-system.md     # 教务系统
        │   │   ├── change-major.md        # 转专业
        │   │   ├── comprehensive-assessment.md # 综合评价
        │   │   ├── further-education.md   # 升学深造
        │   │   ├── learn-documents.md     # 学习文档
        │   │   ├── library-reservation.md # 图书馆预约
        │   │   └── schedule-calendar.md   # 校历
        │   └── systems/              # 校园系统
        │       ├── edu-email.md           # 教育邮箱
        │       ├── smart-qut.md           # 智慧学工系统
        │       ├── software.md            # 正版软件
        │       ├── tuition-fee.md         # 学费缴纳
        │       └── utility-bill.md        # 水电费缴纳
        └── about/                    # 关于 Wiki
            ├── changelog.md          # 更新日志
            ├── contribute.md         # 参与编写
            ├── contributors.md       # 贡献者
            ├── features.md           # 功能特性
            ├── join-us.md            # 加入我们
            └── todo.md               # 编写计划
```

</details>

