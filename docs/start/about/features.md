---
top: 4
---

# 站点功能说明

本页介绍 QUTWiKi 在 VitePress 基础上自行开发的功能，方便编写者查阅使用。

---

## 一、XLSX 表格卡片渲染

在 Markdown 中引用 Excel 文件，自动转为卡片网格展示。

### 基本语法

````markdown
```xlsx /resources/文件.xlsx name=卡片名称列&key=分组列1,分组列2&hide=隐藏列1,隐藏列2&contact=联系方式列&avatar=头像列&desc=描述列&tag=标签列
```
````

> 路径和参数之间用**空格**分隔。旧写法 `?` 分隔仍然兼容；腾讯文档 URL 自身带查询参数时应使用空格分隔插件参数。

### 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `name=A` | 卡片名称列 | `name=学生社团名称` |
| `key=B,C` | 分组列，支持多级分组（`h3` 标题）。<br>不填则不分组，所有卡片平铺。 | `key=业务指导单位` |
| `hide=D,E` | 隐藏的列（不渲染） | `hide=序号` |
| `contact=F,G` | 底部联系方式，每个值前带链接图标；点击可复制其中的数字 | `contact=联系方式` |
| `avatar=H` | 头像列：URL 直接使用，QQ 群号自动拼接 `p.qlogo.cn` 地址 | `avatar=群头像链接` |
| `desc=I` | 描述列，显示在名称下方 | `desc=简介` |
| `tag=J,K` | 标签列（逗号分隔），指定后**只**渲染这些列为标签；<br>不指定时回退到旧行为：所有非隐藏/非联系列自动变为标签 | `tag=备注` |
| `table=Sheet名` | 指定工作表（默认读取第一个） | `table=兴趣群` |
| `#Sheet名` | 等价于 `table=Sheet名`（写文件路径后面） | `文件.xlsx#兴趣群` |

### 卡片布局

当指定 **`avatar`** 参数时（新版样式）：
```
模糊背景图 → 圆形头像 → 名称 → 描述 → 标签 → 底部联系方式（带链接图标）
```
未指定 `avatar` 时（旧版兼容）：
```
文字圆形头像 → 名称 → 标签 → 联系方式
```

- 卡片固定宽度 **240px**，按容器宽度自动折行，移动端自适应
- 卡片等高，长文字自动换行，无需担心溢出

- 只有数字部分会渲染为可点击样式，点击后复制该段数字，并在文字上方提示“复制成功”
- 多个联系方式可用换行或竖线 `|` 分隔，每一项都会单独渲染为可复制项

### 值分隔规则

- **tag** 列：按中英文逗号 `,` `，` 或换行 `↵` 分割为独立标签
- **contact** 列：按换行 `↵` 分割，多值用竖线 `|` 分隔
- **avatar** 列：URL 直接使用，纯数字自动拼接为 `https://p.qlogo.cn/gh/{数字}/{数字}/0/`

### 文件来源与限制

- 本地 XLSX 必须位于 `docs/resources/`，不能使用目录穿越、绝对路径或仓库外文件
- 远程来源仅允许规范的 `https://docs.qq.com/sheet/` 分享链接，不支持任意 HTTP(S) XLSX 直链
- 单个 XLSX 最大 20 MiB，最多 20 张工作表
- 单张工作表最多 5000 行、100 列；超限时构建会显示错误信息

### 腾讯文档

腾讯文档（`docs.qq.com`）等在线表格平台**不提供直接下载链接**，需通过后端同步服务中转：

```
markdown 在线链接 → 插件 → 后端 API → Chromium 同步 → 回传 xlsx → 本地缓存
```

**本地启动后端**：

```bash
cd code
npm ci --ignore-scripts
npm start
# 默认监听 http://localhost:3456
```

Linux 生产环境应使用 `code/Dockerfile` 构建镜像，由镜像构建阶段准备 Chromium 系统依赖；不要在服务启动时执行 `npm install` 或 `apt-get`。启动后，Markdown 中直接填写腾讯文档分享链接即可，构建时自动同步到本地 `docs/.http_cache/`，后续构建优先读缓存。

环境变量 `QUTWIKI_XLSX_API` 可指定后端地址，用于服务器部署场景。

同步 API 不支持 `force` 参数。服务端会执行请求限流、全局 Chromium 并发控制以及工作表和输出大小限制。

---

## 二、Gallery 图片画廊

将多张图片按原始比例排列为杂志式网格布局。

### 用法

图片无需指定宽高，组件自动按原始比例适配每行高度：

```md
<Gallery :row-height="220" :gap="8">

![图片说明](https://example.com/pic1.jpg)

![图片说明](https://example.com/pic2.jpg)

</Gallery>
```

| 属性 | 默认值 | 说明 |
|------|--------|------|
| `row-height` | `220` | 每行目标高度 (px)，为空时自动计算 |
| `gap` | `8` | 图片间距 (px) |

> 图片前后需保留空行，否则不会被解析。

---

## 三、AppCards 应用卡片

将应用/链接以图标卡片网格展示，自动响应式折行，适配深色模式。

### 用法

直接在 Markdown 中写组件即可（组件已全局注册，无需 import）：

```md
<AppCards :links="[
  { text: '学习通', icon: 'https://example.com/xuexitong.png', desc: '多数课程均在此；不要忘记期末考试' },
  { text: 'U校园', icon: 'https://example.com/ucampus.png', desc: '大学英语要用', link: 'https://example.com' },
]" />
```

### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `links` | array | - | 卡片数组（必填），每项字段见下表 |
| `width` | string | `11em` | 卡片最小列宽，容器放不下时自动折行 |
| `text-lines` | number | `2` | 名称最大显示行数，超出省略 |
| `desc-lines` | number \| `false` | `false` | 描述最大显示行数，超出省略；`false` 不限制 |

`links` 每项字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `text` | string | 卡片名称 |
| `icon` | string | 图标 URL（`http`/`https` 开头渲染为图片），固定尺寸圆角展示在卡片左侧 |
| `desc` | string | 描述文字，显示在名称下方，灰色小字 |
| `link` | string | 仅允许 `http`、`https` 或站内相对链接；外部链接自动新窗口打开，不填或协议不安全时渲染为普通卡片 |

### 示例

以下数据来自[西邮 Wiki](https://wiki.cooo.site/campus/apps)：

```md
<AppCards width="12em" :desc-lines="2" :links="[
  { text: '菜鸟', icon: 'https://p16.qhimg.com/dr/_72_/t01950c338d20f6ccaa.png', desc: '查快递、身份码取快递；淘宝“我的驿站”小程序也可' },
  { text: '云达人', icon: 'https://p18.qhimg.com/t011e18028f5c93e2a1.png', desc: '洗澡用水；APP 设置使用码，无需手机', link: 'https://example.com' },
]" />
```

### 许可说明

组件改编自 [xupt-wiki/xupt-wiki](https://github.com/xupt-wiki/xupt-wiki)（西邮 Wiki）的 `LinkList` 组件，遵循 [MIT License](https://github.com/xupt-wiki/xupt-wiki/blob/main/LICENCE)，可自由使用、修改、商用。

---

## 四、Flink 友链卡片

批量渲染友情链接卡片，截图背景图 + 圆形头像 + 名称 + 描述的杂志式网格布局，自动适配深色模式。

### 批量渲染（推荐）

在 `<flink>` 和 `</flink>` 之间写列表，一个 `-` 一条：

```markdown
<flink>
  - name: AnTooLot
    link: https://antoolot.top/
    avatar: https://pic.imgdb.cn/i/033pozBkOwFBKXlEQHEDWx.webp
    descr: 我们人品的一切可取之处，都该感谢沉默的教诲。
    siteshot: https://pic.imgdb.cn/i/033pozTuyso0j0PLfxl9LG.webp
</flink>
```

> 容器写法由 `docs/.vitepress/plugins/flink-block.ts` 在构建时解析为组件渲染。

每条支持以下参数：

| 参数 | 必填 | 说明 |
|------|------|------|
| `name` | ✅ | 站点名称 |
| `link` | ✅ | 站点链接，仅允许 `http`、`https` 或站内相对链接，外部链接自动新窗口打开 |
| `avatar` | ❌ | 头像图片链接，圆形展示 |
| `descr` | ❌ | 站点描述（也兼容 `desc`），最多两行 |
| `siteshot` | ❌ | 友链卡片背景图链接，按 16:9 比例裁剪展示 |

### 单张卡片

任意 Markdown 页面可直接用 `<flink>` 标签生成单张卡片：

```markdown
<flink name="站点名称" link="https://example.com/" avatar="头像链接" siteshot="背景图链接" desc="描述"></flink>
```

多个连续书写（中间不要空行）自动排布为网格卡片。

### 布局说明

- 桌面端 4 列、平板 3 列、手机 2 列，按容器宽度自动折行
- 背景图固定 **16:9** 比例，移动端等比缩小
- 悬停时名称变为主题色，背景图轻微放大并加深阴影
- 头像或背景图加载失败自动隐藏，不破坏卡片布局

---

## 五、贡献者自动识别

每条文档底部会自动显示 Git 贡献者头像。由 `docs/.vitepress/scripts/gen-contributors.mjs` 在构建前通过 `git log` 生成 `contributors.json`。

无需手动配置，每次 `npm run build` 或 `npm run dev` 自动执行。

如需为资料整理、线下供稿等非 Git 提交者额外署名，可在 Markdown frontmatter 中添加 `contributors`：

```yaml
---
contributors:
  - name: 张三
  - name: Li Si
    github: lisi
  - name: 王五
    avatar: https://example.com/avatar.png
---
```

每个贡献者支持以下参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 展示名称，也会用于匹配 `contributors-mapping.json` |
| `github` | string | 否 | GitHub 用户名，可写 `lisi` 或 `@lisi` |
| `email` | string | 否 | 仅在构建阶段用于匹配 `contributors-mapping.json`，不会写入公开前端数据 |
| `avatar` | string | 否 | 自定义头像地址，优先级高于 GitHub 头像 |

简写 GitHub 用户名时也可以使用：

```yaml
---
contributors: ['@lisi', 张三]
---
```

手动填写的贡献者会与 Git 贡献者合并展示。若额外贡献者与 Git 自动识别结果指向同一人，会优先使用 frontmatter 中填写的 `name`、`avatar`、`github` 等展示信息，并隐藏重复的 Git 自动识别结果。

如果额外贡献者未填写 `github` 或 `avatar`，会尝试通过 `docs/.vitepress/contributors-mapping.json` 按 `name`、`email` 或 `github` 补全。例如：

```json
{
  "黎蛰": { "github": "wodeshouji", "avatar": "https://example.com/avatar.webp" }
}
```

此时文章只需写：

```yaml
---
contributors:
  - name: 黎蛰
---
```

最终会展示为 `黎蛰`，链接到 GitHub 用户 `wodeshouji`，并使用映射中的头像。

关联配置：
- `docs/.vitepress/contributors-mapping.json`——在构建阶段按姓名、邮箱或 GitHub 用户名补全展示信息；邮箱不会进入公开产物

---

## 六、Twikoo 评论

普通文档页底部使用 [Twikoo](https://twikoo.js.org/) 提供评论功能。首页和 `layout: page` 的页面不会显示评论区。

部署 Twikoo 后，在构建环境中设置服务地址：

```dotenv
VITE_TWIKOO_ENV_ID=https://twikoo.quters.top
```

本地开发时可复制仓库根目录的 `.env.example` 为 `.env.local` 并填写地址。环境变量变更后需要重启开发服务器；未配置该变量时不显示评论区。

如需在某篇普通文档中关闭评论，可在 frontmatter 中添加：

```yaml
---
comments: false
---
```

Twikoo 客户端采用动态加载，不参与服务端渲染，也不会进入站点首屏主包。

---

## 七、美食评分卡片

`<FoodCards>` 将美食条目渲染为「封面 + 名称 + 平均分 + 星级选择器 + 评价按钮」的卡片，点「评价」弹出详情窗口，内含地点、人均、推荐、多图、聚合评分与该店铺的 Twikoo 评论。评分复用 Twikoo 存储：提交评论时自动在正文前拼上 `[rating:n]` 标记，前端解析后统计平均分，评论列表中的标记会渲染成星级徽章。

> 依赖 Twikoo：未配置 `VITE_TWIKOO_ENV_ID` 时卡片仍可浏览，但打分提交与评论区不可用。

### 用法

组件已全局注册，直接在 Markdown 中写标签即可：

```md
<FoodCards />
```

### 数据文件

条目写在 `docs/.vitepress/theme/components/food-data.js`，在 `FOODS` 数组中追加：

```js
{
  id: 'xicaochang-kfc',
  name: '肯德基（西操场店）',
  cover: 'https://pic1.imgdb.cn/i/xxxx.webp',
  gallery: ['https://pic1.imgdb.cn/i/xxxx.webp'],
  category: 'inside',
  campus: 'h',
  location: '西操场下餐饮商铺',
  price: '¥15-40',
  tags: ['快餐', '炸鸡'],
  recommend: '套餐、全家桶',
  desc: '一句话介绍。'
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | ✅ | 唯一标识，决定评论归属（`/food/<id>`）。**上线后不可修改**，否则历史评论与评分会丢失 |
| `name` | ✅ | 卡片标题、弹窗标题 |
| `cover` | ❌ | 卡片封面，缺省时显示名称首字占位 |
| `gallery` | ❌ | 弹窗多图，兼容 `photos` 字段；留空时回退为 `cover` 单图 |
| `category` | ❌ | 分组依据，取值为下表分类键；未匹配时归入「其他」 |
| `campus` | ❌ | 校区键（`h` 黄岛 / `s` 市北 / `l` 临沂），用于筛选与标签 |
| `location` | ❌ | 美食地点，显示在卡片与弹窗 |
| `price` | ❌ | 人均，仅弹窗展示 |
| `recommend` | ❌ | 推荐菜，仅弹窗展示 |
| `tags` | ❌ | 标签数组，渲染为徽章 |
| `desc` | ❌ | 简介，同时参与搜索匹配 |

### 分类键

在 `FOOD_CATEGORIES` 中维护，顺序即分组展示顺序：

| 键 | 名称 |
|----|------|
| `canteen` | 校内食堂 |
| `inside` | 校内店铺 |
| `outside` | 校外周边 |
| `night` | 夜市小吃 |
| `dessert` | 饮品甜点 |
| `takeout` | 外卖 |

### 交互说明

- 顶部为分类筛选（带条目数）与校区下拉、关键词搜索（匹配名称、地点、标签、简介）
- 卡片星级选择器：未选中 `#93d5dc`，选中 `#1781b5`；平均分星星同色系
- 选星后打开详情，填写 Twikoo 要求的昵称、邮箱，可点「只提交评分」直接保存；也可写评论，由 Twikoo 一并提交评分与文字
- 同一访客的选择记在 `localStorage`（键 `qutwiki:food-ratings`），用于回显；防刷分能力弱，同一账号可重复评分
- 评分聚合按每 40 个条目一批请求，单批最多翻 5 页（每页 100 条），超出部分不计入平均分

### 图片要求

`cover`、`gallery` 必须是 `https://` 直链（与校园地图的 `photos` 一致），不支持 QQ 群号等缩写形式。

---

## 八、Frontmatter 扩展配置

QUTWiKi 在 VitePress 原生 frontmatter 之外新增以下配置项：

```yaml
---
wordCount: false
comments: false
contributors:
  - name: 张三
---
```

| 配置项 | 类型 | 默认 | 说明 |
|--------|------|------|------|
| `wordCount` | boolean | `true` | `false` 关闭字数统计与阅读时间 |
| `comments` | boolean | `true` | `false` 关闭当前文档的 Twikoo 评论区 |
| `contributors` | array/string | 自动读取 Git 提交者 | 额外添加本文贡献者，支持姓名、GitHub 用户名和头像 |

---

## 九、全站公告横条

网站支持在顶部导航栏下方显示一条全站公告，适合发布维护通知、重要提醒或临时消息。公告会显示在所有页面，并自动适配桌面端和移动端。

编辑 `docs/.vitepress/theme/announcement.ts`：

```ts
export const siteAnnouncement = {
  message: '这里填写全站消息',
  background: '#176b87',
  color: '#fff',
}
```

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `message` | string | 公告文字；设为空字符串 `''` 时隐藏公告横条 |
| `background` | string | 横条背景色，支持十六进制、RGB 等合法 CSS 颜色值 |
| `color` | string | 公告文字颜色，支持任意合法 CSS 颜色值 |

修改配置后需要重新构建或重启开发服务器。移动端遇到过长消息时会以省略号收束，避免撑高顶栏；建议公告内容保持简短。

---

## 十、图床资源批量下载与本地化

站点图片目前托管在第三方图床（`pic1.imgdb.cn`、`pic.imgdb.cn`）。若图床失效、需要整体备份或迁移到自建存储，可用 `docs/scripts/images.mjs` 一键抓取并精确替换链接。

脚本零第三方依赖，基于 Node 18+ 内置 `fetch`，适用于任意 VitePress（或一般 Markdown）仓库。

### 三个命令

```bash
npm run images:check      # 体检：并发探测所有图床链接是否有效
npm run images:download   # 下载：抓取全部图片到 docs/public/images/
npm run images:rewrite    # 替换：把图床链接改写为本地路径
```

每个命令都支持：

| 参数 | 说明 |
|------|------|
| `--dry` | 预演，只统计不写盘（下载不落文件、替换不修改源文件） |
| `--concurrency N` | 并发数，默认 `8` |

典型流程：

```bash
npm run images:check -- --dry          # 先看看有没有失效链接
npm run images:download                # 抓取图片（已存在的自动跳过）
npm run images:rewrite -- --dry        # 预览将要替换的位置
npm run images:rewrite                 # 确认无误后执行替换
```

> 两个命令均可重复执行：已下载的文件会跳过，已替换的链接不会被二次处理。

### 迁移到别的仓库

只需修改 `docs/scripts/images.mjs` 配置区的 `SRC_HOSTS`（图床域名），其余无需适配：

```js
// 需要抓取的图床域名（可写多个）。只处理这些域名的图片。
const SRC_HOSTS = ['pic1.imgdb.cn', 'pic.imgdb.cn']
```

替换后的路径统一走根路径前缀，与仓库、域名解耦。例如：

```
https://pic1.imgdb.cn/i/0349E4NqLje1oLHNowvJ4R.png
  →  /images/pic1.imgdb.cn/0349E4NqLje1oLHNowvJ4R.png
```

本地路径保留原始 `host/文件名` 结构，因此多个图床的图片不会重名冲突；换域名或换仓库时内容文件完全不用改。

### 覆盖范围与行为

- 扫描 `docs/` 下的 `.md`、`.markdown`、`.vue`、`.html`、`.ts`、`.js`、`.mjs`、`.json`、`.yml` 文件
- 自动跳过 `node_modules`、`dist`、`cache`、`vendor` 和 `.git` 目录
- 识别带 `png/jpg/jpeg/gif/webp/svg/bmp/avif/ico/tiff` 扩展名的绝对 URL，支持查询串
- 替换时同步删除指向源图床的 `dns-prefetch` / `preconnect` 提示（图片已本地化，无需预连接远端）
- 非图床域名的图片（如 `example.com`、`qhimg.com`）不受影响

### 本地图片目录

抓取结果存放在 `docs/public/images/`，构建时会原样复制进站点产物，通过 `/images/...` 直接访问，无需额外配置。

---

## 十一、构建脚本

项目根目录的 `build.ps1` 一键构建并启动开发服务器：

```powershell
./build.ps1
```

流程：生成贡献者数据 → `npm run build` → 清理 5173 端口旧进程 → `npm run dev`

`npm run build:fresh` 会忽略本地 `docs/.http_cache/` 的有效期并重新请求同步服务，但服务端仍按自身缓存和限流策略处理，不提供强制绕过缓存的参数。
