---
top: 1
---

# 参与编写

本指南介绍如何向青理 Wiki（QUTWiKi）贡献内容。

## 通过**邮箱**

如果您有文档需要提交，但不熟悉 Git 或 GitHub，也可以通过邮箱发送到这个邮箱: [**lucasandrew0120@outlook.com**](mailto:lucasandrew0120@outlook.com)。文档格式Markdown（.md）或Word（.docx）均可，若有图片请打包发送并标明插入位置。收到后我会帮您提交到仓库。

## 通过 **GitHub PR** 流程

### 一、准备环境

- [Node.js](https://nodejs.org/) 22.17+，推荐 [nvm-windows](https://github.com/coreybutler/nvm-windows)
- [Git](https://git-scm.com/)，配置用户名和邮箱
- 推荐编辑器：[VS Code](https://code.visualstudio.com/)

::: tip 国内加速
```bash
npm config set registry https://registry.npmmirror.com
```
:::

---

### 二、获取代码

```bash
# 先 Fork 源仓库，再在 GitHub 上复制你的 Fork 仓库地址
git clone https://github.com/YOUR_USERNAME/QUT-WiKi.git
cd QUT-WiKi

# 添加源仓库为 upstream，后续用于同步官方分支
git remote add upstream https://github.com/QUT-Lib/QUT-WiKi.git
git fetch upstream
```

::: warning 分支说明
本站 `contribute` 是日常贡献分支，所有文档改动请提交到源仓库的 `contribute` 分支。`main` 与 `contribute` 内容保持一致，仅作为镜像分支，不接收普通贡献 PR。

如果你的 Fork 仓库里没有 `contribute` 分支，这是正常情况。你需要先从源仓库拉取 `upstream/contribute`，在本地创建自己的 `contribute` 分支，然后推送到自己的 Fork 仓库。
:::

创建并推送自己的 `contribute` 分支：

```bash
git fetch upstream
git checkout -b contribute upstream/contribute
git push origin contribute
```

---

### 三、安装并预览

```bash
npm ci
npm run dev
```

浏览器访问 `http://localhost:5173`，修改 `.md` 后自动热更新。

普通文档贡献请优先使用 `npm ci` 安装依赖，避免不同 npm 版本执行 `npm install` 时改动 `package-lock.json`。

项目将 SheetJS 归档保存在 `vendor/`，安装时不会在线获取该依赖。不要自行替换归档；如确需升级，必须同步更新两个 vendor 副本、lockfile、来源说明和 SHA-256，并确认两份文件字节一致。

如需本地构建，请使用 PowerShell 运行：

```powershell
./build.ps1
```

---

### 四、编写文档

###### 文件位置

`docs/start/` 下按目录分类存放：

| 目录 | 内容 |
|------|------|
| `newstudent/` | 新生入学 |
| `campus-life/` | 校园生活 |
| `campus-life/study/` | 学习学业（教务系统、综测、学历提升、图书馆预约） |
| `campus-life/systems/` | 校园系统（智慧学工、缴费、水电、邮箱、常用软件） |
| `campus-life/daily-life/` | 生活日常（宿舍、校园周边） |
| `campus-life/qut-organization/` | QUT-组织 |
| `campus-life/competition/` | 竞赛--战队 |
| `about/` | 关于本站 |

###### 命名与格式

- 小写英文 + 短横线：`canteen-guide.md`
- 必含一个 `# 标题`，或写 `title: 标题` 在 frontmatter 中
- 更多自定义功能（xlsx 表格、Gallery 画廊、贡献者显示等）见 [站点功能说明](./features)
- XLSX 本地文件只能放在 `docs/resources/`；远程表格只接受 `https://docs.qq.com/sheet/` 分享链接
- AppCards 和友情链接只填写 `http`、`https` 或站内相对链接，禁止 `javascript:`、`data:` 等协议

---

### 五、提交 PR

###### 1. 确认 GitHub 身份

提交前请先确认本地 Git 的用户名和邮箱与 GitHub 账号匹配，否则贡献记录可能显示为空头像或无法关联到你的 GitHub 账号。

```bash
git config user.name
git config user.email
```

如果不匹配，请在当前仓库内设置为你的 GitHub 用户名和已验证邮箱。也可以使用 GitHub 提供的 noreply 邮箱：

```bash
git config user.name "YOUR_GITHUB_USERNAME"
git config user.email "YOUR_ID+YOUR_GITHUB_USERNAME@users.noreply.github.com"
```

如果已经提交但还没有 push，可以修正身份后重新写入提交作者信息：

```bash
git commit --amend --reset-author
```

###### 2. 在自己的 `contribute` 分支提交

如果你已经按前文创建过 `contribute` 分支，后续贡献时执行：

```bash
# 切换到自己的 contribute 分支
git checkout contribute

# 同步源仓库改动
git fetch upstream
git merge upstream/contribute

# 正常修改、提交并推送到自己的 Fork 仓库 contribute 分支
git add .
git commit -m "新增: 文档说明"
git push origin contribute
```

::: warning 为什么不能只 fetch？
`git fetch upstream` 只会把源仓库的最新提交下载到本地的 `upstream/contribute` 这个"只读引用"，并不会改动你的本地 `contribute` 分支，更不会改动你的 Fork 仓库。只有再执行 `git merge upstream/contribute`，本地分支才会真正跟上源仓库的最新内容。否则你很可能在过时的基础上提交，PR 里出现冲突。

等价写法：在 `contribute` 分支上直接执行 `git pull upstream contribute`（fetch + merge 一步完成）。

如果你的 `contribute` 分支已有尚未推送的本地提交，被合并后推送即可；若分支上已落后多代、改动较大，也可以改用变基让历史更干净：

```bash
git pull --rebase upstream contribute
```

变基会重写本地提交历史，若该分支此前已经推送到 Fork 并用于 PR，之后需用 `git push --force-with-lease origin contribute`（注意：`--force-with-lease` 比 `git push --force` 安全）。
:::

同步后若产生冲突，需手动解决：编辑冲突文件保留想要的内容，然后执行：

```bash
# 使用 merge 时
git add .
git commit

# 或使用 rebase 时
git add .
git rebase --continue
```

如果本地还没有 `contribute` 分支，请先执行：

```bash
git fetch upstream
git checkout -b contribute upstream/contribute
git push origin contribute
```

在 GitHub 上发起 Pull Request：

- base repository：源仓库 `QUT-Lib/QUT-WiKi`
- base 分支：`contribute`
- compare repository：你的 Fork 仓库 `YOUR_USERNAME/QUT-WiKi`
- compare 分支：你的 `contribute` 分支

请不要把 PR 直接提交到 `main`。`main` 仅作为镜像分支，日常贡献统一提交到 `contribute`。

---

### 六、注意事项

- 每次贡献前先同步上游：`git checkout contribute && git fetch upstream && git merge upstream/contribute`，确保本地 `contribute` 分支基于最新的 `upstream/contribute`（仅 fetch 不会更新本地分支，详见上文）
- 一 PR 一事，不混入无关修改
- 引用资料注明出处，个人信息须经本人同意
- 不要在图片说明、链接或表格中嵌入脚本、事件属性或不受信任的远程资源
- 如果没有修改依赖，请不要提交 `package.json` 或 `package-lock.json` 的变化
- 本地构建统一使用 PowerShell 执行 `./build.ps1`
- 收到 review 后在同一分支继续修改并 push 即可

---

### 七、提交前检查清单

仓库已配置 CI 自动校验，会在你发起 PR 后检查**目标分支**与**提交信息规范**，不符合会在 PR 上标红，并在检查摘要中逐条列出原因。以下清单供你自查；通过 CI 后仍需维护者人工审阅内容质量。

###### 目标分支

- [ ] 本 PR 的 base 分支是源仓库 `QUT-Lib/QUT-WiKi` 的 `contribute` 分支（不是 `main`）
- [ ] 本 PR 来自你 Fork 仓库的 `contribute` 分支，且已同步最新的 `upstream/contribute`
- [ ] 本地已执行 `git fetch upstream && git merge upstream/contribute`（或 `git pull --rebase upstream contribute`）

###### 提交信息规范

本仓库提交信息统一使用「中文前缀: 详细说明」格式：

```
新增: 添加市北校区建筑与设施信息
修订: 校园卡余额查询方式
优化: Gallery 图片排列
修复: 贡献者别名问题
docs: 补充参与编写说明
更新: 依赖目录
```

常用前缀：`新增` / `修订` / `优化` / `修复` / `更新` / `下线` / `重构`（也接受 `docs`、`chore` 等英文前缀）。冒号后需用中文写清改动内容。

- [ ] 每个提交均以约定前缀开头，前缀后跟冒号与空格
- [ ] 说明用中文且能准确描述改动，未使用 `update`、`fix`、`修改` 等无前缀或过于笼统的信息
- [ ] 未改写他人已有提交历史（如需变基，已使用 `git push --force-with-lease`）

###### 内容自检

- [ ] 已运行 `npm run dev` 或 `./build.ps1` 本地预览，页面显示正常
- [ ] 一 PR 一事，未混入无关修改
- [ ] 未修改依赖时，未提交 `package.json` / `package-lock.json` 的变化
- [ ] 新增/修改的文档包含 `# 标题` 或 frontmatter 的 `title`
- [ ] 文件名使用小写英文 + 短横线（如 `canteen-guide.md`）
- [ ] 引用资料已注明出处，个人信息已获本人同意
- [ ] 未在图片说明、链接或表格中嵌入脚本、事件属性或不受信任的远程资源
- [ ] XLSX 本地文件仅放在 `docs/resources/`，远程表格仅使用 `https://docs.qq.com/sheet/` 链接

---

## 通过**飞书**流程
- 欢迎您使用 [**飞书**](https://ycnbhi79uv2d.feishu.cn/wiki/YrIOwlkXlidu4zkAeOjcMP7XnFg?from=from_copylink) 进行 [**QUTWiKi**](https://wiki.quters.top) 的编写工作。
- 在左侧三栏有**序言，新生入学，校园生活**三个分区，您可以在其中修订文章或者新增篇目。
- 由于我不会经常登录飞书进行文档的查阅，所以如果您对文档有所更改，欢迎进入 [**QUTWiKi**](https://wiki.quters.top) 的项目组QQ群（**752307273**）进行反馈，或者联系我的个人邮箱说明情况（[**lucasandrew0120@outlook.com**](mailto:lucasandrew0120@outlook.com)）
- 反馈时请说明修改时间，修改人名称和修改内容