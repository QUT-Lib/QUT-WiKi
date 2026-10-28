#!/usr/bin/env bash
# deploy-index.sh 的离线回滚测试（小范围）：只覆盖「切换 live symlink 之后失败要恢复旧 link」。
#
# 覆盖：
#   1. systemctl restart 失败 -> 回滚到上一 release；
#   2. 健康检查失败 -> 回滚到上一 release；
#   3. 首次迁移（index 原本是真实目录）+ 健康检查失败 -> index 恢复指向 legacy 备份；
#   4. 首次迁移成功 -> legacy 备份完整、index 指向新 release（给 3 提供对照）；
#   5. 切换后等待健康检查期间收到 SIGTERM -> 回滚（依赖脚本里的 HUP/INT/TERM trap）；
#   6. 首次迁移「旧目录已 mv 走、symlink 未就位」窗口内收到 SIGTERM
#      -> 旧目录原样搬回（依赖脚本里的 LEGACY_MOVED 恢复分支）。
#
# 安全边界（重要）：
#   * 绝不写 /opt/qutwiki-rag、/var/lib/qutwiki-rag-deploy、/var/lock/qutwiki-rag，
#     也绝不调用真实 systemctl/curl：所有路径都在 mktemp 沙箱内，命令由 mockbin 拦截。
#   * 绝不修改仓库里的 deploy-index.sh：只在沙箱副本里改 4 行常量（ROOT/STAGING/LOCK/
#     PATH），并断言差异恰好 8 行；脚本结构一变测试直接失败而不是静默跳过。
#   * 校验阶段（JSON/numpy/属主校验）不在本测试范围：用「解释器替身」模拟“校验通过
#     并生成快照”，本测试只观察 bash 侧的 symlink 切换 / trap / 回滚。
#
# 需要 root（脚本自身有 EUID==0 前置检查）。CI 上普通 runner 用免密 sudo 跑：
#   sudo -n bash code/rag/tests/test_deploy_rollback.sh
# 本地 WSL：
#   wsl -u root bash code/rag/tests/test_deploy_rollback.sh
# 其他可选环境变量：
#   DEPLOY_SH=/path/to/deploy-index.sh   指向别处的脚本
#   KEEP_SANDBOX=1                       失败时保留沙箱现场
#
# 退出码：0 全部通过（或环境不满足而整体跳过）；1 有失败用例。
set -uo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
DEPLOY_SH=${DEPLOY_SH:-$SCRIPT_DIR/../deploy-index.sh}

PASS=0
FAIL=0
SKIP=0
FAILED_NAMES=()
SB=
CURRENT_CASE=
SIG_PID=

log() { printf '%s\n' "$*"; }
ok() {
    PASS=$((PASS + 1))
    printf '  ok   %s\n' "$1"
}
bad() {
    FAIL=$((FAIL + 1))
    FAILED_NAMES+=("$CURRENT_CASE :: $1")
    printf '  FAIL %s\n' "$1"
    [ $# -gt 1 ] && [ -n "$2" ] && printf '       %s\n' "$2"
    return 0
}

cleanup_sandbox() {
    if [ -n "${SB:-}" ] && [ -d "$SB" ]; then
        if [ "${FAILED_IN_CASE:-0}" -eq 0 ] || [ "${KEEP_SANDBOX:-0}" != "1" ]; then
            rm -rf -- "$SB"
        else
            log "      沙箱保留：$SB"
        fi
    fi
    SB=
}
trap cleanup_sandbox EXIT

# ---------------------------------------------------------------------------
# 沙箱与替身
# ---------------------------------------------------------------------------
write_mocks() {
    cat >"$MOCK/systemctl" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >>"$SB/log/systemctl.log"
state="$SB/state"
case \$1 in
    restart)
        n=\$(cat "\$state/restart_count" 2>/dev/null || echo 0)
        n=\$((n + 1))
        echo "\$n" >"\$state/restart_count"
        rc=\$(cat "\$state/restart_rc" 2>/dev/null || echo 0)
        if [ "\$n" -ge 2 ] && [ -f "\$state/restart_rc_after" ]; then
            rc=\$(cat "\$state/restart_rc_after")
        fi
        exit "\$rc"
        ;;
    is-active)
        exit \$(cat "\$state/isactive_rc" 2>/dev/null || echo 0)
        ;;
esac
exit 0
EOF

    cat >"$MOCK/curl" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >>"$SB/log/curl.log"
if [ -f "$SB/state/curl_sleep_once" ]; then
    s=\$(cat "$SB/state/curl_sleep_once")
    rm -f "$SB/state/curl_sleep_once"
    /bin/sleep "\$s"
fi
exit \$(cat "$SB/state/curl_rc" 2>/dev/null || echo 0)
EOF

    # 加速 wait_healthy 的 30 次退避；curl 替身用 /bin/sleep 保留真实延迟。
    cat >"$MOCK/sleep" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

    cat >"$MOCK/id" <<'EOF'
#!/usr/bin/env bash
if [ "${1:-}" = "-u" ]; then
    printf '%s\n' "${FAKE_DEPLOY_UID:-1000}"
    exit 0
fi
exec /usr/bin/id "$@"
EOF

    # 只在“首次迁移窗口”阻塞：命中 mv 到 legacy-* 之后的 sha256sum，
    # 让测试能在 LIVE 缺失、symlink 还没建立的那一瞬间注入信号。
    cat >"$MOCK/sha256sum" <<EOF
#!/usr/bin/env bash
if [ -f "$SB/state/legacy_hash_delay" ]; then
    case "\$*" in
        *legacy-*)
            : >"$SB/state/in_legacy_window"
            d=\$(cat "$SB/state/legacy_hash_delay")
            rm -f "$SB/state/legacy_hash_delay"
            /bin/sleep "\$d"
            ;;
    esac
fi
exec /usr/bin/sha256sum "\$@"
EOF

    chmod 0755 "$MOCK/systemctl" "$MOCK/curl" "$MOCK/sleep" "$MOCK/id" \
        "$MOCK/sha256sum"
}

# 解释器替身：真实脚本用 -I - 调用，参数为
#   <stage> <snapshot> <release> <deploy_uid> <baseline_manifest>
# 这里只做「校验通过 + 生成快照」，不检查文件内容/属主（不在本测试范围）。
write_python_stub() {
    cat >"$ROOTD/.venv/bin/python" <<EOF
#!/usr/bin/env bash
mkdir -m 0700 -- "\$4" || exit 1
printf '{"test":true}\\n' >"\$4/manifest.json"
printf '{"id":"chunk-1"}\\n' >"\$4/chunks.jsonl"
printf 'fake-vectors-bytes\\n' >"\$4/vectors.npy"
chmod 0644 -- "\$4/manifest.json" "\$4/chunks.jsonl" "\$4/vectors.npy"
exit 0
EOF
    chmod 0755 "$ROOTD/.venv/bin/python"
}

# 只改写 4 行常量；改不动说明脚本结构变了，直接硬失败（退出 2）。
install_deploy_copy() {
    local copy=$SB/deploy.sh changed
    sed \
        -e "s|^ROOT=/opt/qutwiki-rag\$|ROOT=$ROOTD|" \
        -e "s|^STAGING=/var/lib/qutwiki-rag-deploy/incoming\$|STAGING=$SB/staging/incoming|" \
        -e "s|^LOCK=/var/lock/qutwiki-rag/deploy.lock\$|LOCK=$SB/lock/deploy.lock|" \
        -e "s|^export PATH=/usr/local/sbin:|export PATH=$MOCK:/usr/local/sbin:|" \
        -- "$DEPLOY_SH" >"$copy"
    chmod 0755 "$copy"

    changed=$(diff -u -- "$DEPLOY_SH" "$copy" | awk '
        /^[+-]/ && !/^(\+\+\+|---)/ { n++ }
        END { print n + 0 }')
    if [ "$changed" -ne 8 ]; then
        printf '测试基础设施失败：deploy-index.sh 的常量行已变化（差异 %s 行，期望 8 行）\n' "$changed" >&2
        diff -u -- "$DEPLOY_SH" "$copy" >&2 || true
        exit 2
    fi
    if ! grep -qx "ROOT=$ROOTD" "$copy" || ! grep -q "^export PATH=$MOCK:" "$copy"; then
        printf '测试基础设施失败：沙箱路径改写未生效\n' >&2
        exit 2
    fi
}

sandbox_init() {
    SB=$(mktemp -d "${TMPDIR:-/tmp}/qutwiki-deploy.XXXXXX") || exit 1
    MOCK=$SB/mockbin
    ROOTD=$SB/opt/qutwiki-rag
    mkdir -p "$MOCK" "$ROOTD/.venv/bin" "$ROOTD/releases" \
        "$SB/staging/incoming" "$SB/lock" "$SB/log" "$SB/state" "$SB/out"
    chmod 0755 "$ROOTD" "$ROOTD/.venv" "$ROOTD/releases" \
        "$SB/staging" "$SB/staging/incoming" "$SB/lock"
    write_mocks
    write_python_stub
    install_deploy_copy
    echo 0 >"$SB/state/restart_count"
    FAILED_IN_CASE=0
}

make_index() { # $1=目录 $2=manifest 内容
    mkdir -p -- "$1"
    printf '%s\n' "${2:-manifest}" >"$1/manifest.json"
}

make_release() { make_index "$ROOTD/releases/$1" "release-$1"; }

make_stage() { # $1=release；上传目录属主模拟成 DEPLOY_UID=1000
    local d=$SB/staging/incoming/$1
    mkdir -p -- "$d"
    printf '{"ok":true}\n' >"$d/manifest.json"
    printf '{"id":"chunk-1"}\n' >"$d/chunks.jsonl"
    printf 'fake-vectors-bytes\n' >"$d/vectors.npy"
    chown 1000:1000 -- "$d" "$d/manifest.json" "$d/chunks.jsonl" "$d/vectors.npy"
    chmod 0755 -- "$d"
    chmod 0644 -- "$d/manifest.json" "$d/chunks.jsonl" "$d/vectors.npy"
}

set_state() { printf '%s\n' "$2" >"$SB/state/$1"; }
sha_of() { sha256sum -- "$1" | awk '{print $1}'; }
live_target() { readlink -f -- "$ROOTD/index" 2>/dev/null || true; }

run_deploy() {
    : >"$SB/out/run.log"
    "$SB/deploy.sh" "$@" >>"$SB/out/run.log" 2>&1
    RC=$?
}

expect_rc() { # $1=描述 $2=期望
    if [ "$RC" -eq "$2" ]; then
        ok "$1"
    else
        bad "$1" "rc=$RC，期望 $2；输出：$(head -c 400 "$SB/out/run.log" 2>/dev/null | tr '\n' ' ')"
    fi
}

expect_live_is() { # $1=描述 $2=期望的绝对路径
    local got
    got=$(live_target)
    if [ "$got" = "$2" ]; then
        ok "$1"
    else
        bad "$1" "index -> ${got:-<空>}，期望 $2"
    fi
}

expect_log_has() {
    if grep -q -- "$2" "$SB/out/run.log"; then ok "$1"; else bad "$1" "输出中没有：$2"; fi
}

expect_log_lacks() {
    if grep -q -- "$2" "$SB/out/run.log"; then bad "$1" "输出中不应出现：$2"; else ok "$1"; fi
}

expect_true() { # $1=描述，其余为命令
    local desc=$1
    shift
    if "$@"; then ok "$desc"; else bad "$desc" "断言失败：$*"; fi
}

COMMIT=0123456789abcdef0123456789abcdef01234567
REL="$COMMIT-7-1"

# ---------------------------------------------------------------------------
# 用例
# ---------------------------------------------------------------------------

# 常规路径：健康检查一直失败 -> 必须回滚到上一个 release。
case_health_fail_rolls_back_symlink() {
    sandbox_init
    make_release prev
    ln -s -- "$ROOTD/releases/prev" "$ROOTD/index"
    local base
    base=$(sha_of "$ROOTD/releases/prev/manifest.json")
    make_stage "$REL"
    set_state curl_rc 1

    run_deploy "$REL" "$base"
    expect_rc "健康检查失败返回 1" 1
    expect_log_has "日志说明回滚目标" "回滚到 $ROOTD/releases/prev"
    expect_live_is "回滚后 index 指向旧 release" "$ROOTD/releases/prev"
    expect_log_has "回滚后仍不健康要告警" "严重：回滚后服务仍不健康"
    expect_log_lacks "不打印发布成功" "发布成功"
    expect_true "回滚时再次重启服务" test "$(cat "$SB/state/restart_count")" -eq 2
    expect_true "健康检查确实被重试" test "$(grep -c . "$SB/log/curl.log")" -gt 1
    expect_true "未残留临时 symlink" \
        test -z "$(find "$ROOTD" -maxdepth 1 -name '.index.*' -print -quit)"
}

# switch 之后 systemctl restart 直接失败（非零退出）：走 EXIT trap 回滚。
case_restart_failure_rolls_back() {
    sandbox_init
    make_release prev
    ln -s -- "$ROOTD/releases/prev" "$ROOTD/index"
    local base
    base=$(sha_of "$ROOTD/releases/prev/manifest.json")
    make_stage "$REL"
    set_state restart_rc 1
    set_state curl_rc 0

    run_deploy "$REL" "$base"
    expect_rc "restart 失败返回 1" 1
    expect_live_is "restart 失败后回滚到旧 release" "$ROOTD/releases/prev"
    expect_true "回滚时再次尝试 restart" test "$(cat "$SB/state/restart_count")" -eq 2
    expect_true "未残留临时 symlink" \
        test -z "$(find "$ROOTD" -maxdepth 1 -name '.index.*' -print -quit)"
}

# 首次迁移 + 健康检查失败：旧 index 已被 mv 成 legacy-*，必须回滚指向它。
case_first_migration_health_fail() {
    sandbox_init
    make_index "$ROOTD/index" "legacy-manifest-content"
    local base legacy
    base=$(sha_of "$ROOTD/index/manifest.json")
    make_stage "$REL"
    set_state curl_rc 1

    run_deploy "$REL" "$base"
    expect_rc "首次迁移健康检查失败返回 1" 1
    expect_log_has "记录了首次迁移备份" "首次迁移完成"
    expect_log_has "回滚日志出现" "回滚到"
    expect_true "index 变成指向 legacy 备份的 symlink" test -L "$ROOTD/index"
    legacy=$(live_target)
    expect_true "回滚目标位于 releases 下" \
        bash -c '[[ $1 == "$2"/legacy-* ]]' _ "$legacy" "$ROOTD/releases"
    expect_true "旧 index 内容完整保留" \
        grep -qx "legacy-manifest-content" "$legacy/manifest.json"
    expect_true "回滚后不再指向新 release" test "$legacy" != "$ROOTD/releases/$REL"
}

# 首次迁移成功：给上一个用例做对照（证明 legacy 备份与切换的真实形态）。
case_first_migration_success() {
    sandbox_init
    make_index "$ROOTD/index" "legacy-manifest-content"
    local base legacy
    base=$(sha_of "$ROOTD/index/manifest.json")
    make_stage "$REL"
    set_state curl_rc 0

    run_deploy "$REL" "$base"
    expect_rc "首次迁移成功返回 0" 0
    expect_live_is "index 指向新 release" "$ROOTD/releases/$REL"
    expect_log_has "打印发布成功" "发布成功"
    legacy=$(find "$ROOTD/releases" -maxdepth 1 -name 'legacy-*' -print -quit)
    expect_true "生成 legacy 备份目录" test -n "$legacy"
    expect_true "备份内容完整" grep -qx "legacy-manifest-content" "$legacy/manifest.json"
    expect_true "只重启一次" test "$(cat "$SB/state/restart_count")" -eq 1
}

# 公共：切到新 release 后、第一次健康检查阻塞期间发送 <signal>，返回 RC。
start_signal_scenario() {
    local sig=$1 base i
    sandbox_init
    make_release prev
    ln -s -- "$ROOTD/releases/prev" "$ROOTD/index"
    base=$(sha_of "$ROOTD/releases/prev/manifest.json")
    make_stage "$REL"
    set_state curl_rc 0
    set_state curl_sleep_once 5
    : >"$SB/out/run.log"

    "$SB/deploy.sh" "$REL" "$base" >>"$SB/out/run.log" 2>&1 &
    SIG_PID=$!
    # 等到“已进入 wait_healthy 的 curl 调用”，确保 SWITCHED=1 且时机稳定。
    for i in $(seq 1 500); do
        [ -s "$SB/log/curl.log" ] && break
        /bin/sleep 0.01
    done
    kill -"$sig" "$SIG_PID" 2>/dev/null
    wait "$SIG_PID"
    RC=$?
}

# 切换后、健康检查等待期间收到 SIGTERM：必须回滚（脚本显式 trap 成 exit 143）。
case_sigterm_rollback_after_switch() {
    start_signal_scenario TERM
    expect_rc "SIGTERM 后返回 143" 143
    expect_log_has "SIGTERM 后执行回滚" "回滚到"
    expect_live_is "SIGTERM 后 index 回到旧 release" "$ROOTD/releases/prev"
    expect_true "回滚时再次重启服务" test "$(cat "$SB/state/restart_count")" -eq 2
}

# 首次迁移窗口：旧目录已 mv 成 legacy-*、symlink 还没建好时被 SIGTERM。
# 期望把旧目录原样搬回（不留下 symlink，也不需要重启服务）。
case_first_migration_signal_window() {
    sandbox_init
    make_index "$ROOTD/index" "legacy-manifest-content"
    local base i
    base=$(sha_of "$ROOTD/index/manifest.json")
    make_stage "$REL"
    set_state curl_rc 0
    set_state legacy_hash_delay 5
    : >"$SB/out/run.log"

    "$SB/deploy.sh" "$REL" "$base" >>"$SB/out/run.log" 2>&1 &
    SIG_PID=$!
    for i in $(seq 1 500); do
        [ -f "$SB/state/in_legacy_window" ] && break
        /bin/sleep 0.01
    done
    kill -TERM "$SIG_PID" 2>/dev/null
    wait "$SIG_PID"
    RC=$?

    expect_rc "迁移窗口内 SIGTERM 返回 143" 143
    expect_log_has "窗口内中断也回滚" "恢复被移走的旧索引目录"
    expect_true "LIVE 恢复成真实目录（不是 symlink）" \
        test -d "$ROOTD/index" -a ! -L "$ROOTD/index"
    expect_true "旧 manifest 内容完整" \
        grep -qx "legacy-manifest-content" "$ROOTD/index/manifest.json"
    expect_true "不再遗留 legacy 备份副本" \
        test -z "$(find "$ROOTD/releases" -maxdepth 1 -name 'legacy-*' -print -quit)"
    expect_true "窗口回滚不重启服务" test "$(cat "$SB/state/restart_count")" -eq 0
}

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
main() {
    log "deploy-index.sh 离线回滚测试"
    log "脚本：$DEPLOY_SH"
    if [ ! -f "$DEPLOY_SH" ]; then
        log "找不到被测脚本，退出"
        exit 1
    fi
    if [ "$(id -u)" -ne 0 ]; then
        log "SKIP：需要 root（deploy-index.sh 有 EUID==0 前置检查）；请在 WSL/容器里用 root 运行。"
        printf 'RESULT skipped need-root\n'
        exit 0
    fi
    local script_sha case_name
    script_sha=$(sha_of "$DEPLOY_SH")
    for case_name in \
        case_health_fail_rolls_back_symlink \
        case_restart_failure_rolls_back \
        case_first_migration_health_fail \
        case_first_migration_success \
        case_sigterm_rollback_after_switch \
        case_first_migration_signal_window; do
        CURRENT_CASE=$case_name
        FAILED_IN_CASE=0
        local before_fail=$FAIL
        log ""
        log "[$case_name]"
        "$case_name" || bad "$case_name 异常退出" "rc=$?"
        if [ "$FAIL" -ne "$before_fail" ]; then
            FAILED_IN_CASE=1
        fi
        cleanup_sandbox
    done

    if [ "$(sha_of "$DEPLOY_SH")" != "$script_sha" ]; then
        FAIL=$((FAIL + 1))
        FAILED_NAMES+=("被测脚本在测试过程中被修改")
    fi

    log ""
    log "结果：$PASS 通过，$SKIP 跳过，$FAIL 失败"
    # ASCII 结果标记：给 unittest wrapper / CI 解析用，避免依赖中文输出的编码。
    printf 'RESULT pass=%d skip=%d fail=%d\n' "$PASS" "$SKIP" "$FAIL"
    if [ "$FAIL" -ne 0 ]; then
        local name
        for name in "${FAILED_NAMES[@]}"; do
            log "  - $name"
        done
        return 1
    fi
    return 0
}

main "$@"
