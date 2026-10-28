# code/rag — Wiki RAG 增量索引与自动发布

从当前 QUTWiKi 仓库重新抽取语料，复用旧索引里语义等价的向量，只对新增/修改的文本调用
embedding，最后写出一个**独立的新索引目录**。本目录负责“抽取 / 向量化 / 增量构建 / 校验”，
并提供独立的 GitHub Actions 发布流程与服务器端发布器；**不参与站点构建，也不修改站点工作流**。

```
code/rag/
  extract.py             语料抽取（vendored 自 D:/code/RAG/scripts/extract_corpus.py，路径参数化）
  embedding.py           智谱 embedding、缓存 key、旧索引读取、矩阵校验、FakeEmbedder
  build_index.py         增量构建 CLI（--wiki-root / --base-index / --output / --source-commit）
  requirements-rag.txt   完整发布依赖（含 pymupdf）
  deploy-index.sh        服务器端 root 发布器（固定参数，安装到 /usr/local/libexec）
  tests/                 纯离线测试（unittest，不调用付费 API）
.github/workflows/rag-index.yml   RAG 专用 Actions（独立于站点 deploy.yml）
```

自动发布链路：

```text
push contribute / workflow_dispatch
  ├─ 同步腾讯文档（npm + Playwright，不构建 VitePress；失败即停止）
  └─ 受限 SSH 网关（qutrag-deploy）
       ├─ baseline                        拉三个运行时文件
       ├─ 增量构建（只编码变化文本）
       ├─ upload <release>                上传 tar 流
       └─ publish <release> <baseline>    sudo root 发布器
```

## 依赖

`numpy` 与 `openpyxl` 是生产必需依赖；PDF 文本层依赖 `pymupdf`：

| 依赖 | 用途 | 缺失时 |
| --- | --- | --- |
| `numpy>=1.24` | 向量矩阵与校验 | 无法构建索引 |
| `openpyxl>=3.1` | `.http_cache/*.xlsx`、`resources/*.xlsx` 表格块 | **硬报错**，不再静默少块 |
| `requests>=2.31` | 仅调用智谱 embedding 时需要 | 只在确实要给新文本编码时报错 |
| `pymupdf`（发布必需） | `resources/*.pdf` 文本层 | 跳过 PDF 并写入 warning，索引会少块 |

安装：

```powershell
py -3 -m pip install -r code/rag/requirements-rag.txt
```

> `requirements-rag.txt` 是完整发布依赖，已包含 `pymupdf`；CI 使用它安装，
> 避免服务器索引悄悄丢失 PDF 文本块。`openpyxl` 同样是生产必需依赖，
> 缺失会直接失败，不会生成少表格块的索引。本地若明确只处理文本，可自行不装
> `pymupdf`，提取器会告警并跳过 PDF（不要用于发布）。

## 用法

```powershell
# 1) 增量构建：模型/维度与旧索引一致，只编码变化文本
$env:ZHIPU_API_KEY = "..."   # 只在需要新编码时使用；本工具不读取 .env 文件
py -3 code/rag/build_index.py `
  --wiki-root . `
  --base-index D:/code/RAG/index-zhipu `
  --output D:/Temp/index-next `
  --source-commit (git rev-parse HEAD)

# 2) 没有旧索引（或明确要全量）：省略 --base-index
py -3 code/rag/build_index.py --wiki-root . --output D:/Temp/index-full

# 3) 只抽语料（供检查/调试）
py -3 code/rag/extract.py --wiki-root . --out D:/Temp/corpus
```

参数：

| 参数 | 说明 |
| --- | --- |
| `--wiki-root` | QUTWiKi 仓库根目录（也接受 `docs/`）；默认本仓库 |
| `--base-index` | 旧索引目录（含 `vectors.npy` / `chunks.jsonl` / `manifest.json`）；省略=全量 |
| `--output` | 新索引目录，**必须独立于 base**；已存在索引文件时需 `--overwrite` |
| `--source-commit` | 写进 manifest 的源提交；默认 `git rev-parse HEAD` |
| `--profile` | 默认沿用旧 manifest 的 profile，旧索引没有时用 `qut` |
| `--embed-provider` | `zhipu`（默认）或 `fake`（离线确定性向量，仅测试） |
| `--embed-model` / `--embed-dim` | 默认 `embedding-3` / `1024`（支持 256/512/1024/2048） |
| `--batch-size` | 在线编码批量，默认 32，内部上限 64 |
| `--no-pdf` | 跳过 `resources/*.pdf` |
| `--no-corpus` | 默认把抽取语料写入固定的 `<output>/corpus`；加此参数则不生成 |
| `--no-cache` | 不写 `<output>/cache/embedding-cache.npz` |
| `--allow-reembed-on-mismatch` | 旧索引模型/维度/预处理版本不一致时仍全量重编码（默认报错，避免意外 API 费用） |

退出码：`0` 成功，`2` 参数/配置/旧索引身份错误，`3` 索引校验失败。

## 增量语义

- **缓存 key** = `sha256(schema, provider, model, dim, preprocess_version, text)`。
- `text` 取 `embed_text`，为空时退回 `text`，两者都只做 `strip()`；不依赖 chunk id、顺序或标题。
- 因此：块重新编号、标题/正文元数据变化但参与编码的文本不变时，**复用旧向量**；
  文本变化、模型/维度/预处理版本变化时，**不会复用**。
- 新增/删除/改标题都以本次抽取结果为准；旧块不会残留，新块一定按新顺序写入。
- 旧索引没有 `preprocess_version`（上游 `build_index.py` 生成的 `index-zhipu`）时，
  按等价的 `strip-v1` 处理，并在 manifest 的 `embedding_cache.base_legacy_preprocess_assumed` 标记。
- 旧索引身份（provider/model/dim/preprocess）不一致时默认直接报错，防止把不同模型的向量混进同一索引。
- 若所有文本都命中缓存（没有变化），**不会实例化 embedding、不会发起任何网络请求**，也不需要 API Key。
- 额外缓存 `<output>/cache/embedding-cache.npz` 会保留“已从索引删除”的向量（key 排序、稳定写入）；
  下次把同一段内容加回来时仍可复用。缓存不含原文，只含 key 和向量。

## 输出与校验

```
<output>/
  vectors.npy                  float32, (n_chunks, dim)，L2 归一化
  chunks.jsonl                 与 vectors.npy 严格同序
  manifest.json                最后写入
  corpus/                      （默认，固定位置）本次抽取语料；--no-corpus 时不生成
  cache/embedding-cache.npz    （默认）跨代向量缓存
```

> 自动发布使用 `--no-corpus --no-cache`，输出目录只有前三个运行时文件。
> `corpus/` 与 `cache/` 是构建侧产物，不上传服务器；下一次 `baseline` 也只返回三个文件，
> 增量复用仍由 `chunks.jsonl` + `vectors.npy` 完成。

写出前与写出后都会校验：行数/维度、`NaN/Inf`、L2 范数（容差 `1e-4`）、
`chunks.jsonl` 回读顺序。manifest 记录：

- `profile`、`source_commit` / `source_commit_source`、`wiki_root`
- `model`、`embed_provider`、`embed_model`、`embed_dim`、`preprocess_version`
- `extraction`（文档/表格/块统计、参数、warnings、抽取时的 source commit）
- `embedding_cache`（base 路径、复用/新编码行数与唯一文本数、重复 key、缓存命中、是否 legacy）
- `validation`（shape、finite、norm min/max/max error）
- `vectors_sha1` / `chunks_sha1` / `corpus_sha1`
- 旧 manifest 里的 `ui` / `rerank` / `recommended_mode` / `fusion_strategy` 会原样保留

## 自动发布（GitHub Actions）

工作流：`.github/workflows/rag-index.yml`。它与 `deploy.yml` 完全独立，不构建 VitePress，
也不会取消正在进行的同组发布。

### 触发方式

| 触发 | 行为 |
| --- | --- |
| push 到 `contribute`，且命中 `docs/**/*.md`、`docs/**/*.xlsx`、`docs/resources/**/*.pdf`、`docs/.vitepress/theme/components/map-data.js`、`code/rag/**`、腾讯同步脚本、`package*.json` | 先同步腾讯文档，再用仓库语料增量构建并发布 |
| `workflow_dispatch` | 同样先同步腾讯文档，再构建发布 |

`.http_cache` 是 gitignored 的腾讯文档导出缓存，干净的 Actions checkout 不会包含 xlsx。
因此**每次索引更新都必须先同步腾讯文档**；工作流没有“跳过同步”的选项。同步失败时整个
任务立即失败，不会用缺失表格块的语料覆盖旧索引。腾讯文档属于外部数据，其更新本身不会
产生 Git push；外部数据变化后仍需手动运行一次 `workflow_dispatch`。
工作流固定检出 `contribute`，并用 `git rev-parse HEAD` 记录实际源提交（不使用可能不一致的
`github.sha`）。

`concurrency: rag-index`，`cancel-in-progress: false`。发布过程中不会被打断。

手动触发只允许从 `contribute` 分支发起；工作流仍固定检出 `contribute`。在真正调用
`publish` 之前会执行一次 `git ls-remote origin refs/heads/contribute`：
如果远端 HEAD 已不是本次构建的源提交，说明这是排队期间变旧的构建，直接失败，
不会用旧 commit 覆盖新 commit。发布过程中新提交只能排队等待，不会取消当前发布。

### 必需的 Secrets

| Secret | 用途 |
| --- | --- |
| `RAG_SSH_HOST` | SSH 主机名/IP，不写入仓库 |
| `RAG_SSH_PORT` | SSH 端口 |
| `RAG_SSH_USER` | 低权限账号，当前为 `qutrag-deploy` |
| `RAG_SSH_KEY` | 专用私钥；只用于该账号，不能复用个人运维密钥 |
| `RAG_SSH_KNOWN_HOSTS` | 固定的主机公钥（保持此名称）；不使用 `ssh-keyscan` 动态信任 |
| `ZHIPU_API_KEY` | 仅传给构建进程；不会上传到服务器，也不会写进索引 |

构建器固定为 `code/rag/build_index.py`，不通过仓库变量切换。

`RAG_SSH_KNOWN_HOSTS` 应由可信网络提前生成并核对指纹，例如：

```bash
ssh-keyscan -p "$RAG_SSH_PORT" -H "$RAG_SSH_HOST" > known_hosts
ssh-keygen -lf known_hosts   # 与服务器/云控制台指纹人工核对
```

### 工作流步骤

1. 检出 `contribute`（完整历史），记录实际 `HEAD`。
2. **始终**同步腾讯文档：安装 npm 依赖与 Playwright Chromium，执行
   `node docs/scripts/sync-tencent.mjs`；复用站点同步流程，不执行 VitePress 构建，失败即停止。
3. 安装 `requirements-rag.txt`（含 `pymupdf` 的完整发布依赖），运行索引与权限回归测试；失败即停止。
4. 写临时 SSH 私钥/known_hosts，使用固定 Host 别名 `rag-target`。
5. `baseline`：接收服务器返回的 tar，解包出 `manifest.json`、`chunks.jsonl`、`vectors.npy`；
   校验块数、形状、有限值以及 manifest 中的 SHA1，发现三文件混代立即失败；
   最后计算 `sha256(manifest.json)` 作为本次 baseline 哈希。
6. 增量构建：

   ```bash
   python code/rag/build_index.py \
     --wiki-root "$GITHUB_WORKSPACE" \
     --base-index "$BASE_DIR" \
     --output "$OUT" \
     --source-commit "$SOURCE_COMMIT" \
     --no-corpus \
     --no-cache
   ```

   基线只有三个文件，不含旧的 `cache/`；复用依赖 `chunks.jsonl` + `vectors.npy` 中的文本与向量。

7. 校验新索引：块数、唯一 id、float32、有限值、L2 归一化、SHA1、`source_commit`。
   同时强制 `profile=qut`、`model=zhipu/embedding-3`、`embed_provider=zhipu`、
   `embed_model=embedding-3`、`embed_dim=dim=1024`、`normalized=true`、
   `dtype=float32`、`corpus_path=null`；拒绝 `fake` 或其他 provider。
   `ui` / `rerank` / `recommended_mode` / `fusion_strategy` 必须与线上 baseline 完全一致，
   禁止通过上传索引新增或修改服务端配置。
8. `upload <release>`：把三个运行时文件打成普通 tar 流，通过 SSH stdin 上传。
9. 再次确认远端 `contribute` HEAD 仍等于本次源提交；不等则失败，避免旧构建覆盖新提交。
10. `publish <release> <baseline_sha256>`：由网关 `sudo` 调用 root 发布器。
11. 写 GitHub Step Summary。

工作流不执行 `scp`、`rsync` 或任意远程 shell 命令；所有远端操作都走下面三个网关命令。

### release 命名

```text
<40 位小写 commit>-<run_id>-<run_attempt>
```

例如 `0123...cdef-123456789-1`。发布器会再次校验：

- `release` 整体格式；
- `release` 的 commit 前缀等于 `manifest.source_commit`；
- 目标 release 目录尚不存在。

这样同一次运行可重试，不同运行不会互相覆盖；线上 `index` 始终指向一个不可变 release。

## 低权限 SSH 网关

专用账号 `qutrag-deploy` 没有可用 shell，SSH 公钥带 forced command，禁止 pty、
端口转发、Agent 转发和 X11 转发。网关实现与安装脚本由低权限方案维护：

- `code/rag/ssh-gateway.py`
- `code/rag/install-deploy-user.sh`

`authorized_keys` 应类似（网关安装路径以 `install-deploy-user.sh` 的实际产出为准）：

```text
restrict,command="/usr/local/libexec/qutwiki-rag-ssh-gateway" ssh-ed25519 AAAA... qutrag-deploy-rag-index
```

网关只接受以下命令（参数数量和格式都在网关侧校验）：

| 命令 | stdin | stdout/行为 |
| --- | --- | --- |
| `baseline` | 无 | 输出普通 tar 流，归档根目录恰好 `manifest.json`、`chunks.jsonl`、`vectors.npy`（允许 `./` 前缀）；日志只能写 stderr |
| `upload <release>` | 普通 tar 流 | 解包到 `/var/lib/qutwiki-rag-deploy/incoming/<release>`；只允许上述三个普通文件 |
| `publish <release> <baseline_sha256>` | 无 | 执行 `sudo /usr/local/libexec/qutwiki-rag-deploy <release> <baseline_sha256>` |

网关不得提供 shell、`scp`、`rsync`、任意命令、端口转发或 SFTP。`baseline` 的 stdout 必须是纯 tar；
任何提示日志走 stderr，否则会破坏工作流解包。`baseline` 读取的是当前 `index` symlink 指向的目录，
并且必须在 `/var/lock/qutwiki-rag/deploy.lock` 上持有共享 `flock` 直到 tar 流结束；
root 发布器在同一文件上持有排他锁，从而保证三个文件来自同一代。

`baseline` 和 `upload` 的传输上限为 15 分钟，防止客户端断线后进程无限等待。
该传输超时不作用于 `publish`。
`upload` 解包出的目录/文件必须属于 `qutrag-deploy`，目录名必须正好是 `<release>`，且只含三个普通
文件；不能有符号链接、硬链接、setuid/setgid 或组/其他用户写权限。发布器会再次校验这些条件，
不满足就拒绝，因此网关的“宽松解包”不能绕过 root 发布器的检查。

## 服务器端发布器

`code/rag/deploy-index.sh` **不是**由工作流上传或执行的。它需要管理员以 root 安装：

```bash
sudo install -o root -g root -m 0755 code/rag/deploy-index.sh \
  /usr/local/libexec/qutwiki-rag-deploy
```

并把 sudo 权限限定到该文件（示例，实际由 `install-deploy-user.sh` 落地）：

```text
qutrag-deploy ALL=(root) NOPASSWD: /usr/local/libexec/qutwiki-rag-deploy
```

脚本只接受两个位置参数，不接受 `--root`、`--service`、`--python`、路径或任何其他开关：

```bash
/usr/local/libexec/qutwiki-rag-deploy <release> <baseline_sha256>
```

固定约定：

| 项 | 固定值 |
| --- | --- |
| 应用根目录 | `/opt/qutwiki-rag` |
| 线上索引 | `/opt/qutwiki-rag/index` |
| release 目录 | `/opt/qutwiki-rag/releases/<release>` |
| 上传暂存 | `/var/lib/qutwiki-rag-deploy/incoming/<release>` |
| 共享发布锁 | `/var/lock/qutwiki-rag/deploy.lock`（root:root 0644，目录 root 0755） |
| 服务 | `qutwiki-rag.service` |
| 健康检查 | `http://127.0.0.1:8098/api/health`（无需 token） |
| Python | `/opt/qutwiki-rag/.venv/bin/python` |

发布流程：

1. 必须以 root 运行；清空 `PYTHONPATH`、`LD_PRELOAD` 等危险环境变量，固定 `PATH`。
2. 校验 `release` 与 64 位 baseline 哈希格式；取得 `qutrag-deploy` 的 UID。
3. 打开 `/var/lock/qutwiki-rag/deploy.lock`（root:root，0644；目录 `/var/lock/qutwiki-rag`
   root 0755）并获取**排他** `flock`，串行化所有发布。网关的 `baseline` 必须在同一文件上
   获取**共享**锁后再 tar 三个文件，这样不会读到跨代的混合文件；发布期间新接入的
   baseline 会等待。锁放在 root 专用子目录，不使用 `/run/lock` 里的公共文件。
4. 在锁内重新计算线上 `manifest.json` 的 SHA-256；与 `baseline_sha256` 不一致立即放弃，
   防止基于过期 baseline 的并发覆盖。
5. **不可信上传处理**：只接受恰好三个普通文件；校验属主为 `qutrag-deploy`、无符号链接、
   无硬链接、无 setuid/setgid/sticky、组/其他用户不可写、大小在限制内。
6. 用 `O_NOFOLLOW` 把三个文件复制到 `releases/.snapshot-<release>-<pid>`（初始 0700，
   root 私有），只对快照做 JSON/行数/SHA1/float32/finite/L2 校验；不执行上传目录中的任何代码。
   校验还要求 `profile=qut`、`model=zhipu/embedding-3`、1024 维、`normalized=true`，
   且 `ui` / `rerank` / `recommended_mode` / `fusion_strategy` 与当前线上 manifest 完全一致；
   `corpus_path` 必须为 null。任何 fake/其他 provider、错维或新增 rerank/ui 配置都会被拒绝。
7. 校验通过后把快照改名为 `releases/<release>`，文件 0644、目录 0755。
8. 首次发布时 `/opt/qutwiki-rag/index` 还是普通目录：先整体移动到
   `releases/legacy-<UTC 时间>-<pid>` 保留备份，再为 `index` 建立 symlink。
9. 后续发布用临时 symlink + `mv -Tf` 原子替换 `index`。
10. `systemctl restart qutwiki-rag.service`，最多等待 30 秒：
    服务 active 且 `GET /api/health` 成功才视为成功。
11. 重启失败、服务不 active 或 health 非 2xx：自动把 symlink 切回上一版本并再次重启/检查；
    新 release 目录保留用于排查。脚本退出非 0，工作流失败。
12. 成功后才删除暂存目录；失败保留现场。旧 `legacy-*` 备份不会被自动清理。

健康检查直接访问本机 `/api/health`，**不读取 `.env`、不传 token**，也不会把任何密钥写入日志。

## 服务器布局与首次 bootstrap

```text
/opt/qutwiki-rag/
  index -> releases/<release>          # 首次发布后变成符号链接
  releases/
    <release>/                        # 三个运行时文件
    legacy-<UTC>-<pid>/               # 首次迁移保留的旧 index 完整备份
  .venv/                              # 必须 root 拥有且不可被组/其他用户写
  scripts/serve.py
/var/lib/qutwiki-rag-deploy/incoming/ # qutrag-deploy 可写，root 发布器只读
/var/lock/qutwiki-rag/
  deploy.lock                         # root:root 0644；baseline 共享锁 / 发布排他锁
/usr/local/libexec/
  qutwiki-rag-ssh-gateway             # 低权限网关（安装脚本决定）
  qutwiki-rag-deploy                  # root 发布器（固定路径）
```

首次部署前提（服务器上已只读确认）：

- `/opt/qutwiki-rag/index` 是普通目录，`qutwiki-rag.service` 为 active；
- 服务命令包含 `.venv/bin/python scripts/serve.py --host 0.0.0.0 --port 8098 --index index --mode hybrid`；
- 索引是 numpy 文件（`vectors.npy` / `chunks.jsonl` / `manifest.json`），当前约 230 块、
  `embedding-3` 1024 维；
- 服务器具备 `flock`、`rsync`（本流程不再从 CI 使用 rsync）和 `systemctl`。

推荐顺序：

将 `install-deploy-user.sh`、`ssh-gateway.py`、`deploy-index.sh` 和专用公钥放在服务器同一目录，执行：

```bash
sudo sh install-deploy-user.sh ./qutwiki-rag-actions.pub
# 只检查已安装配置与权限：
sudo sh install-deploy-user.sh --check ./qutwiki-rag-actions.pub
```

1. 运行低权限方案的 `install-deploy-user.sh`：创建 `qutrag-deploy`、网关、incoming 目录、
   `authorized_keys` 与 sudoers；创建 root 专用锁目录 `/var/lock/qutwiki-rag`（root 0755）
   和 `deploy.lock`（root:root 0644）；确认账号不能登录 shell、不能转发。
   网关 `baseline` 必须在该锁上取共享 `flock`，root 发布器取排他 `flock`。
2. 安装器同时将 `deploy-index.sh` 安装到 `/usr/local/libexec/qutwiki-rag-deploy`（0755 root:root）。
3. 确认 `/opt/qutwiki-rag/.venv` 及其 `bin/python` 由 root 拥有且不可被组/其他用户写。
4. 在 GitHub 配置上表 Secrets；`RAG_SSH_USER=qutrag-deploy`。
5. 手动运行一次工作流。第一次发布会自动保留 `releases/legacy-*` 备份，
   检查服务与 `/api/health` 后再清理旧备份。

> 发布器不创建或修复 venv。若 venv 由非 root 用户拥有，脚本会拒绝运行，这是为了避免
> 以 root 执行可被低权限用户修改的 Python/依赖。

## 内容维护约定

- **不要手动维护 `chunks.jsonl`**。源文本是 `docs/**/*.md`、`docs/**/*.xlsx`、
  `docs/resources/**/*.pdf` 等；改文档后让工作流重新抽取和增量构建。
- `chunks.jsonl`、`vectors.npy`、`manifest.json` 都是生成物，不提交回仓库。
- 腾讯文档等外部数据更新后，手动触发工作流；工作流每次都会先同步腾讯文档。
  仅同步不会产生 Git 提交，因此外部数据变化不能靠 push 触发。
- 只有内容变化才会调用 embedding；文本/模型/维度/预处理版本不变时复用旧向量。

## 运维与排障

| 场景 | 处理 |
| --- | --- |
| `publish` 报 baseline 已变化 | 说明期间有另一发布或线上被改动；重新运行工作流即可 |
| 健康检查失败 | 脚本已自动回滚；用 `journalctl -u qutwiki-rag -n 100 --no-pager` 查看原因 |
| 首次发布看到 `legacy-*` | 正常迁移备份；确认新版本稳定后再人工清理 |
| 需要回退 | 管理员把 `/opt/qutwiki-rag/index` 原子切到目标 `releases/*`，再重启服务；不要手工改运行中的 release 目录 |
| 磁盘增长 | `releases/` 不会自动清理；确认不再需要后人工删除旧 release，`legacy-*` 请先备份 |
| 改了 `deploy-index.sh` | 工作流不会更新服务器脚本；需要管理员重新执行 `install` 安装 |

## 离线测试

```powershell
py -3 -m unittest discover -s code/rag/tests -v
```

测试覆盖：抽取过滤与依赖、缓存 key/fallback、有限值与归一化校验、增量复用、
元数据更新、新增/删除、仅改标题时复用、chunk id 变化时按文本复用、删除后缓存保留、
模型/维度不一致拒绝、损坏旧索引拒绝、输出目录独立性、CLI 直接运行、
`profile`/commit 记录，以及 SSH 命令限制和归档文件校验。模型调用使用 `FakeEmbedder`
或模拟响应，不访问网络、不读取 `.env`。

发布回滚测试使用临时目录和模拟服务命令，验证服务重启失败、健康检查失败和进程中断时恢复旧索引，
不会操作真实 `/opt/qutwiki-rag`。它需要 Linux root 环境（Windows 可通过 WSL 运行）。

可选的上游一致性测试（默认跳过，仅在有 `D:/code/RAG` 的开发机运行）：

```powershell
$env:QUTWIKI_RAG_UPSTREAM = "D:/code/RAG/scripts/extract_corpus.py"
py -3 -m unittest discover -s code/rag/tests -p test_upstream_parity.py -v
```

## 注意事项

- 本工具**不读取** `D:/code/RAG/.env` 或仓库里的密钥文件，只读环境变量
  `ZHIPU_API_KEY`（兼容 `ZHIPUAI_API_KEY` / `BIGMODEL_API_KEY`）。
- 模型不一致默认是硬错误；确实要重建请显式加 `--allow-reembed-on-mismatch`，并确认 API 费用。
- 默认输出目录外置；不要指向源仓库的 `docs/`、`code/` 或 `.github/`（脚本会拒绝）。
- 自动发布使用 `.github/workflows/rag-index.yml`；服务器端只安装
  `deploy-index.sh` 与低权限网关。构建器本身不直接操作远端。
