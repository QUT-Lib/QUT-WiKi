#!/usr/bin/env bash
# QUTWiKi RAG 索引发布器（服务器端、root 专用）
#
# 安装位置（root:root, 0755）：
#   /usr/local/libexec/qutwiki-rag-deploy
#
# 只允许两个位置参数，不接受任何开关、路径、服务名或解释器参数：
#   qutwiki-rag-deploy <release> <baseline_sha256>
#
# 固定约定：
#   ROOT=/opt/qutwiki-rag
#   STAGING=/var/lib/qutwiki-rag-deploy/incoming
#   index 由 qutwiki-rag.service 使用，健康检查为
#   http://127.0.0.1:8098/api/health（无需 token，也不读取 .env）
#
# 设计要点：
#   * qutrag-deploy 通过受限网关 sudo 调用本脚本；脚本运行前会清空危险环境变量。
#   * 上传目录不可信：只接受三个普通文件，校验属主/类型/权限/大小，然后用
#     O_NOFOLLOW 复制到 root 私有快照目录，再对快照做完整校验。
#   * 校验通过后才发布：flock 串行化、baseline manifest 哈希防过期覆盖、
#     首次迁移备份旧 index、后续原子切换 symlink、重启并检查 /api/health。
#   * 重启或健康检查失败时自动切回上一版本并再次检查。
#   * 被 HUP/INT/TERM 终止时也会回滚：bash 在信号终止时不会把 128+N 放进 EXIT trap 的
#     $?（实测为 0），所以必须显式 trap 成 exit 128+N，否则会误判成功而漏掉回滚。
#   * 首次迁移在“旧目录已搬走、symlink 未就位”的窗口内被中断时，把旧目录原样搬回。
#
# 退出码：0 成功；1 失败/回滚；2 用法错误；129/130/143 被 HUP/INT/TERM 终止（已回滚）。
set -Eeuo pipefail

# 固定环境，避免 sudo 继承或调用者注入解释器/动态库路径。
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL=C
umask 022
unset BASH_ENV CDPATH ENV GLOBIGNORE PYTHONHOME PYTHONPATH PYTHONSTARTUP \
      LD_PRELOAD LD_LIBRARY_PATH || true

ROOT=/opt/qutwiki-rag
STAGING=/var/lib/qutwiki-rag-deploy/incoming
RELEASES="$ROOT/releases"
LIVE="$ROOT/index"
SERVICE=qutwiki-rag.service
HEALTH_URL=http://127.0.0.1:8098/api/health
# 与网关 baseline 共享的锁：root 独占写，qutrag-deploy 只读（0644）。
LOCK=/var/lock/qutwiki-rag/deploy.lock
PYTHON="$ROOT/.venv/bin/python"
DEPLOY_USER=qutrag-deploy

log() { printf '[deploy] %s\n' "$*"; }
die() { printf '[deploy] ERROR: %s\n' "$*" >&2; exit 1; }
usage() {
    printf 'usage: %s <release> <baseline_sha256>\n' "$0" >&2
    printf '  release: 40 位小写 commit + runid + attempt，例如 <40hex>-123-1\n' >&2
}

[[ $# -eq 2 ]] || { usage; exit 2; }
RELEASE=$1
BASELINE_SHA256=$2

[[ $RELEASE =~ ^[0-9a-f]{40}-[0-9]{1,20}-[0-9]{1,20}$ ]] \
    || die "release 格式非法"
[[ $BASELINE_SHA256 =~ ^[0-9a-f]{64}$ ]] \
    || die "baseline_sha256 必须是 64 位小写十六进制"
COMMIT=${RELEASE%%-*}
[[ ${#COMMIT} -eq 40 ]] || die "release 中的 commit 必须是 40 位"

[[ $EUID -eq 0 ]] || die "必须以 root 运行（通过受限网关 sudo 调用）"
[[ -d $ROOT && ! -L $ROOT ]] || die "$ROOT 必须是真实目录"
[[ -x $PYTHON ]] || die "缺少可信解释器：$PYTHON"
[[ -x /usr/bin/flock ]] || die "缺少 flock"
[[ -x /usr/bin/systemctl ]] || die "缺少 systemctl"
[[ -x /usr/bin/curl ]] || die "缺少 curl"
[[ -x /usr/bin/sha256sum ]] || die "缺少 sha256sum"

# Python 及其 venv 必须由 root 拥有且不可被组/其他用户写，避免执行非 root 代码。
check_trusted_owner() {
    local path=$1 meta owner mode
    meta=$(stat -Lc '%u:%a' -- "$path") || die "无法读取 $path 的权限"
    owner=${meta%%:*}
    mode=${meta#*:}
    [[ $owner == 0 ]] || die "$path 必须由 root 拥有"
    (( (8#$mode & 8#022) == 0 )) || die "$path 不能被组/其他用户写"
}
check_trusted_owner "$PYTHON"
check_trusted_owner "$ROOT/.venv"

[[ -d $STAGING && ! -L $STAGING ]] || die "$STAGING 必须是真实目录"
STAGE_DIR="$STAGING/$RELEASE"
[[ -d $STAGE_DIR && ! -L $STAGE_DIR ]] || die "缺少上传目录：$STAGE_DIR"

DEPLOY_UID=$(id -u "$DEPLOY_USER" 2>/dev/null) \
    || die "系统用户不存在：$DEPLOY_USER"
[[ $DEPLOY_UID =~ ^[0-9]+$ ]] || die "无法解析 $DEPLOY_USER 的 UID"

[[ -e $LIVE || -L $LIVE ]] || die "线上索引不存在：$LIVE"
LIVE_REAL=$(readlink -f -- "$LIVE") || die "无法解析 $LIVE"
[[ -d $LIVE_REAL && ! -L $LIVE_REAL ]] || die "线上索引不是真实目录"
[[ -f "$LIVE_REAL/manifest.json" && ! -L "$LIVE_REAL/manifest.json" ]] \
    || die "线上索引缺少普通文件 manifest.json"

mkdir -p -- "$RELEASES"
[[ -d $RELEASES && ! -L $RELEASES ]] || die "$RELEASES 必须是真实目录"
chown root:root -- "$RELEASES"
chmod 0755 -- "$RELEASES"

# 锁必须位于 root 专用目录（不能直接用含义模糊的 /run/lock 公共目录）。
LOCK_DIR=$(dirname "$LOCK")
if [[ ! -d $LOCK_DIR ]]; then
    install -d -m 0755 -o root -g root "$LOCK_DIR"
fi
[[ -d $LOCK_DIR && ! -L $LOCK_DIR ]] || die "$LOCK_DIR 必须是真实目录"
LOCK_DIR_META=$(stat -c '%u:%a' -- "$LOCK_DIR")
[[ ${LOCK_DIR_META%%:*} == 0 ]] || die "$LOCK_DIR 必须由 root 拥有"
LOCK_DIR_MODE=${LOCK_DIR_META#*:}
(( (8#$LOCK_DIR_MODE & 8#022) == 0 )) || die "$LOCK_DIR 不能被组/其他用户写"
if [[ ! -e $LOCK ]]; then
    install -m 0644 -o root -g root /dev/null "$LOCK"
fi
[[ -f $LOCK && ! -L $LOCK ]] || die "$LOCK 不是普通文件"
chown root:root -- "$LOCK"
chmod 0644 -- "$LOCK"
exec 9<>"$LOCK"
flock -x -w 900 9 || die "等待发布锁超时（另一个发布正在进行）"

# 等锁期间另一任务可能已切换 index，必须在锁内重新解析实时目标。
LIVE_REAL=$(readlink -f -- "$LIVE") || die "无法解析锁内线上索引"
[[ -d $LIVE_REAL && -f "$LIVE_REAL/manifest.json" && ! -L "$LIVE_REAL/manifest.json" ]] \
    || die "锁内线上索引不完整"

# 关键：在持有锁后再次核对 baseline manifest 哈希。
# 工作流早先下载的 manifest 必须与当前线上完全一致，否则说明期间已有发布，
# 本次增量结果基于过期基线，必须放弃。
CURRENT_SHA=$(sha256sum -- "$LIVE_REAL/manifest.json" | awk '{print $1}')
[[ $CURRENT_SHA == "$BASELINE_SHA256" ]] \
    || die "baseline manifest 已变化（期望 $BASELINE_SHA256，实际 $CURRENT_SHA），请重新运行工作流"

if [[ -L $LIVE ]]; then
    PREV_TARGET=$(readlink -f -- "$LIVE") || die "无法解析 $LIVE 的链接目标"
    [[ $PREV_TARGET == "$RELEASES/"* ]] || die "线上 index 指向 releases 之外的目录"
    [[ -d $PREV_TARGET ]] || die "上一版本目录不存在：$PREV_TARGET"
elif [[ -d $LIVE ]]; then
    PREV_TARGET=   # 首次迁移，发布成功前不移动旧目录
else
    die "$LIVE 既不是目录也不是符号链接"
fi

TARGET="$RELEASES/$RELEASE"
[[ ! -e $TARGET && ! -L $TARGET ]] || die "release 已存在：$TARGET"

SNAPSHOT="$RELEASES/.snapshot-$RELEASE-$$"
[[ ! -e $SNAPSHOT && ! -L $SNAPSHOT ]] || die "快照目录已存在：$SNAPSHOT"

TMP_LINK=
SNAPSHOT_MOVED=0
SWITCHED=0
# 首次迁移：LIVE 是真实目录，已被 mv 成 legacy 备份、但 symlink 还没顶替上去。
# 这个窗口里 LIVE 不存在，信号中断必须能把目录原样搬回（见 rollback）。
LEGACY_MOVED=0
BACKUP=

cleanup() {
    if [[ -n ${TMP_LINK:-} ]]; then
        rm -f -- "$TMP_LINK" 2>/dev/null || true
    fi
    if [[ $SNAPSHOT_MOVED -eq 0 && -d ${SNAPSHOT:-} ]]; then
        rm -rf -- "$SNAPSHOT" 2>/dev/null || true
    fi
}

wait_healthy() {
    local i
    for i in $(seq 1 30); do
        if systemctl is-active --quiet "$SERVICE" \
            && curl -fsS --noproxy '*' --max-time 3 -o /dev/null "$HEALTH_URL"; then
            return 0
        fi
        sleep 1
    done
    return 1
}

rollback() {
    set +e
    # 首次迁移的窗口：LIVE 已从真实目录被搬成 legacy-*，symlink 还没建好，此刻 LIVE 不存在。
    # 直接原样搬回目录，比补一个 symlink 更贴近故障前状态（且无需重启服务）。
    if [[ ${LEGACY_MOVED:-0} -eq 1 && -d ${BACKUP:-} && ! -e $LIVE && ! -L $LIVE ]]; then
        log "回滚：恢复被移走的旧索引目录 $LIVE"
        if mv -T -- "$BACKUP" "$LIVE"; then
            LEGACY_MOVED=0
            BACKUP=
            log "旧索引目录已原样恢复"
        else
            log "严重：无法恢复 $LIVE，请手工执行 mv -T -- $BACKUP $LIVE"
        fi
        set -e
        return 0
    fi
    log "发布失败，回滚到 $PREV_TARGET"
    if [[ -n ${PREV_TARGET:-} && -d $PREV_TARGET ]]; then
        TMP_LINK="$ROOT/.index.rollback.$$"
        ln -sfn -- "$PREV_TARGET" "$TMP_LINK"
        mv -Tf -- "$TMP_LINK" "$LIVE"
        SWITCHED=0
        systemctl restart "$SERVICE"
        if wait_healthy; then
            log "回滚后健康检查通过"
        else
            log "严重：回滚后服务仍不健康，请立即检查 $SERVICE"
        fi
    else
        log "严重：没有可用的上一版本，无法自动回滚"
    fi
    set -e
}

on_exit() {
    local rc=$?
    if (( rc != 0 && (SWITCHED == 1 || LEGACY_MOVED == 1) )); then
        rollback
    fi
    cleanup
    exit "$rc"
}
trap on_exit EXIT
# bash 被信号终止时 EXIT trap 里的 $? 是 0 而不是 128+N（实测 bash 5.2），
# on_exit 会误判为成功而跳过回滚。这里显式转成 exit 128+N，保证一定能回滚。
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

# ---------------------------------------------------------------------------
# 1. 把不可信上传安全复制到 root 私有快照，并在快照上完成校验。
#    只接受恰好三个普通文件；不执行上传目录中的任何代码。
# ---------------------------------------------------------------------------
log "复制并校验 release=$RELEASE"
if ! (
    cd /
    "$PYTHON" -I - "$STAGE_DIR" "$SNAPSHOT" "$RELEASE" "$DEPLOY_UID" "$LIVE_REAL/manifest.json" <<'PY'
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

try:
    import numpy as np
except Exception as exc:  # noqa: BLE001
    print(f"[deploy] ERROR: 无法导入 numpy：{exc}", file=sys.stderr)
    raise SystemExit(1)

staging, snapshot, release, uid_arg, baseline_manifest_path = sys.argv[1:6]
uid = int(uid_arg)
commit = release.split("-", 1)[0]
limits = {
    "manifest.json": 8 << 20,
    "chunks.jsonl": 512 << 20,
    "vectors.npy": 1 << 30,
}
expected = set(limits)


def fail(message):
    print(f"[deploy] ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def write_all(fd, data):
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            fail("写入快照失败")
        view = view[written:]


try:
    dir_fd = os.open(staging, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
except OSError as exc:
    fail(f"无法打开上传目录：{exc}")

try:
    dir_stat = os.fstat(dir_fd)
    if not stat.S_ISDIR(dir_stat.st_mode):
        fail("上传路径不是目录")
    if dir_stat.st_uid != uid:
        fail(f"上传目录必须属于 UID {uid}")

    names = set(os.listdir(dir_fd))
    if names != expected:
        fail(
            "上传目录必须恰好包含这三个文件；"
            f"缺少 {sorted(expected - names)}，多出 {sorted(names - expected)}"
        )

    try:
        os.mkdir(snapshot, 0o700)
    except OSError as exc:
        fail(f"无法创建 root 私有快照目录：{exc}")

    for name in sorted(expected):
        limit = limits[name]
        try:
            # 先无跟随 stat，避免把 FIFO/设备节点当作可读文件打开。
            pre_stat = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
            if not stat.S_ISREG(pre_stat.st_mode):
                fail(f"{name} 必须是普通文件")
            if pre_stat.st_uid != uid:
                fail(f"{name} 必须属于 UID {uid}")
            # O_NONBLOCK 防止竞态把文件换成 FIFO 时让 root 进程阻塞。
            src_fd = os.open(
                name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=dir_fd,
            )
        except OSError as exc:
            fail(f"{name} 无法安全打开：{exc}")
        try:
            src_stat = os.fstat(src_fd)
            if not stat.S_ISREG(src_stat.st_mode):
                fail(f"{name} 必须是普通文件")
            if src_stat.st_uid != uid:
                fail(f"{name} 必须属于 UID {uid}")
            if src_stat.st_nlink != 1:
                fail(f"{name} 不允许硬链接")
            if src_stat.st_size <= 0 or src_stat.st_size > limit:
                fail(f"{name} 大小异常：{src_stat.st_size} 字节")
            if src_stat.st_mode & 0o7000:
                fail(f"{name} 不允许 setuid/setgid/sticky 位")
            if src_stat.st_mode & 0o022:
                fail(f"{name} 不允许组或其他用户写")

            dst_path = os.path.join(snapshot, name)
            dst_fd = os.open(
                dst_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
            )
            try:
                remaining = src_stat.st_size
                while remaining > 0:
                    chunk = os.read(src_fd, min(1 << 20, remaining))
                    if not chunk:
                        fail(f"{name} 读取不完整")
                    write_all(dst_fd, chunk)
                    remaining -= len(chunk)
                os.fsync(dst_fd)
            finally:
                os.close(dst_fd)
        finally:
            os.close(src_fd)
finally:
    os.close(dir_fd)

snap = Path(snapshot)


def sha1_file(path):
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


try:
    manifest = json.loads((snap / "manifest.json").read_text(encoding="utf-8"))
except Exception as exc:  # noqa: BLE001
    fail(f"manifest.json 不是合法 JSON：{exc}")
if not isinstance(manifest, dict):
    fail("manifest.json 必须是 JSON 对象")
try:
    baseline_manifest = json.loads(Path(baseline_manifest_path).read_text(encoding="utf-8"))
except Exception as exc:  # noqa: BLE001
    fail(f"baseline manifest 无法读取：{exc}")
if not isinstance(baseline_manifest, dict):
    fail("baseline manifest 必须是 JSON 对象")

if manifest.get("source_commit") != commit:
    fail(
        "manifest.source_commit 与 release 不一致："
        f"{manifest.get('source_commit')!r} != {commit!r}"
    )
if manifest.get("profile") != "qut":
    fail(f"manifest.profile 必须是 qut：{manifest.get('profile')!r}")

chunks = manifest.get("chunks")
dim = manifest.get("dim")
if isinstance(chunks, bool) or not isinstance(chunks, int) or not 0 < chunks <= 2_000_000:
    fail(f"manifest.chunks 非法：{chunks!r}")
if dim != 1024:
    fail(f"manifest.dim 必须是 1024：{dim!r}")
if chunks * dim * 4 > limits["vectors.npy"]:
    fail("manifest 声明的向量尺寸超过限制")

model = manifest.get("model")
if model != "zhipu/embedding-3":
    fail(f"manifest.model 必须是 zhipu/embedding-3：{model!r}")
if manifest.get("embed_provider") != "zhipu":
    fail("manifest.embed_provider 必须是 zhipu（拒绝 fake/其他 provider）")
if manifest.get("embed_model") != "embedding-3":
    fail("manifest.embed_model 必须是 embedding-3")
if manifest.get("embed_dim") != 1024:
    fail("manifest.embed_dim 必须是 1024")
if manifest.get("normalized") is not True:
    fail("manifest.normalized 必须为 true")
if manifest.get("dtype") != "float32":
    fail(f"manifest.dtype 必须是 float32：{manifest.get('dtype')!r}")
if manifest.get("corpus_path") is not None:
    fail("manifest.corpus_path 必须为 null（服务器只加载三个运行时文件）")

# 这些键会进入服务端配置；只允许与线上 baseline 完全相同，
# 禁止通过上传索引新增/修改 rerank、ui 等可能加载额外代码或模型的配置。
for key in ("ui", "rerank", "recommended_mode", "fusion_strategy"):
    if manifest.get(key) != baseline_manifest.get(key):
        fail(f"manifest.{key} 与线上 baseline 不一致，拒绝发布")

vectors_sha1 = manifest.get("vectors_sha1")
chunks_sha1 = manifest.get("chunks_sha1")
for key, value in (("vectors_sha1", vectors_sha1), ("chunks_sha1", chunks_sha1)):
    if not isinstance(value, str) or len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
        fail(f"manifest.{key} 非法")

rows = 0
ids = set()
try:
    with (snap / "chunks.jsonl").open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError as exc:
                fail(f"chunks.jsonl:{lineno} 不是合法 JSON：{exc}")
            if not isinstance(row, dict):
                fail(f"chunks.jsonl:{lineno} 不是 JSON 对象")
            chunk_id = row.get("id")
            if not isinstance(chunk_id, str) or not chunk_id:
                fail(f"chunks.jsonl:{lineno} 缺少有效 id")
            if chunk_id in ids:
                fail(f"chunks.jsonl:{lineno} 存在重复 id：{chunk_id}")
            ids.add(chunk_id)
            rows += 1
except UnicodeDecodeError as exc:
    fail(f"chunks.jsonl 不是 UTF-8：{exc}")
if rows != chunks:
    fail(f"chunks.jsonl 行数与 manifest.chunks 不一致：{rows} != {chunks}")

try:
    vectors = np.load(snap / "vectors.npy", allow_pickle=False)
except Exception as exc:  # noqa: BLE001
    fail(f"vectors.npy 无法读取：{exc}")
if vectors.dtype != np.float32:
    fail(f"vectors.npy dtype 必须是 float32：{vectors.dtype}")
if vectors.shape != (chunks, dim):
    fail(f"vectors.npy 形状不匹配：{vectors.shape} != {(chunks, dim)}")
if not np.isfinite(vectors).all():
    fail("vectors.npy 含 NaN/Inf")
norms = np.linalg.norm(vectors, axis=1)
if not np.allclose(norms, 1.0, rtol=0.0, atol=1e-3):
    fail("vectors.npy 存在未归一化向量")

if sha1_file(snap / "vectors.npy") != vectors_sha1:
    fail("vectors.npy 的 SHA1 与 manifest 不一致")
if sha1_file(snap / "chunks.jsonl") != chunks_sha1:
    fail("chunks.jsonl 的 SHA1 与 manifest 不一致")

for name in sorted(expected):
    os.chmod(snap / name, 0o644)
os.chmod(snap, 0o755)

print(
    f"[deploy] 校验通过：{chunks} 块 × {dim} 维，模型 {model}，提交 {commit}",
    flush=True,
)
PY
); then
    die "上传内容校验失败，线上索引未改变"
fi

chmod 0755 -- "$SNAPSHOT"
chmod 0644 -- "$SNAPSHOT/manifest.json" "$SNAPSHOT/chunks.jsonl" "$SNAPSHOT/vectors.npy"

# ---------------------------------------------------------------------------
# 2. 发布。先把已验证快照改名为不可变 release 目录，再处理 /opt/qutwiki-rag/index。
# ---------------------------------------------------------------------------
[[ ! -e $TARGET && ! -L $TARGET ]] || die "release 在发布期间被创建：$TARGET"
mv -T -- "$SNAPSHOT" "$TARGET"
SNAPSHOT_MOVED=1

if [[ ! -L $LIVE ]]; then
    BACKUP="$RELEASES/legacy-$(date -u +%Y%m%dT%H%M%SZ)-$$"
    [[ ! -e $BACKUP && ! -L $BACKUP ]] || die "备份目录已存在：$BACKUP"
    # mv 与下面 ln -s 之间 LIVE 短暂缺失；先置位，任何信号/失败都能搬回目录。
    LEGACY_MOVED=1
    mv -T -- "$LIVE" "$BACKUP"
    if [[ "$(sha256sum -- "$BACKUP/manifest.json" | awk '{print $1}')" != "$BASELINE_SHA256" ]]; then
        if mv -T -- "$BACKUP" "$LIVE"; then
            LEGACY_MOVED=0
        else
            log "严重：无法恢复 $LIVE，请手工执行 mv -T -- $BACKUP $LIVE"
        fi
        die "迁移旧 index 后 baseline 哈希不一致"
    fi
    if ! ln -s -- "$BACKUP" "$LIVE"; then
        if mv -T -- "$BACKUP" "$LIVE"; then
            LEGACY_MOVED=0
        else
            log "严重：无法恢复 $LIVE，请手工执行 mv -T -- $BACKUP $LIVE"
        fi
        die "无法为旧 index 创建临时符号链接"
    fi
    LEGACY_MOVED=0
    PREV_TARGET="$BACKUP"
    log "首次迁移完成：旧 index 已完整备份到 $BACKUP"
fi

TMP_LINK="$ROOT/.index.new.$$"
rm -f -- "$TMP_LINK"
ln -s -- "$TARGET" "$TMP_LINK"
# 在原子替换前置位，覆盖 mv 成功后、下一条赋值前收到信号的窗口。
SWITCHED=1
mv -Tf -- "$TMP_LINK" "$LIVE"
TMP_LINK=

[[ "$(readlink -f -- "$LIVE")" == "$TARGET" ]] || die "symlink 切换后的目标不正确"

log "重启 $SERVICE"
systemctl restart "$SERVICE"
if ! wait_healthy; then
    die "服务重启后健康检查失败：$HEALTH_URL"
fi

log "发布成功：release=$RELEASE commit=$COMMIT"
log "线上路径：$LIVE -> $TARGET"
log "上一版本保留：$PREV_TARGET"

# 成功后才清理 qutrag-deploy 的上传目录；失败时保留现场便于排查。
rm -rf -- "$STAGE_DIR" 2>/dev/null || true
exit 0
