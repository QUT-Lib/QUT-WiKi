#!/bin/sh
# QUTWiKi RAG 受限 SSH 部署账号安装脚本（仅在服务器上以 root 运行）
#
# 用法：
#   sudo ./install-deploy-user.sh /path/to/qutwiki-rag-actions.pub
#   sudo ./install-deploy-user.sh --check /path/to/qutwiki-rag-actions.pub
#
# 本脚本只做以下固定动作，不生成密钥、不读取 .env：
#   1. 创建/检查 qutrag-deploy 系统账号（已有账号只检查，不覆盖未知配置；
#      发现未知 authorized_keys、sudoers、组或 shell 时直接拒绝）。
#   2. 安装 authorized_keys：restrict,command="/usr/local/libexec/qutwiki-rag-ssh-gateway"
#      禁止 PTY、端口转发、agent/X11 转发，只能执行固定网关。
#   3. 收紧 /opt/qutwiki-rag：root 拥有的真实文件/目录去掉 group/world 写权限，
#      symlink 不跟随；.env / .env.* / llm.json 设为 0600；index 目录 0755、
#      三个索引文件 0644（部署账号只读）。
#   4. 安装 root-owned 网关和部署 helper：
#        /usr/local/libexec/qutwiki-rag-ssh-gateway
#        /usr/local/libexec/qutwiki-rag-deploy
#      helper 必须由同目录的 deploy-index.sh 提供，参数固定为：
#        <release> <64hex baseline manifest sha256>
#   5. 写入唯一 sudo 规则：只允许 qutrag-deploy 免密执行上述 helper（参数由
#      helper 自行严格校验），不允许任意 rsync/sudo/命令白名单。
#   6. 创建 /var/lib/qutwiki-rag-deploy/incoming（0700，部署账号所有）作为
#      release 暂存目录；发布由 root helper 从该目录读取并再次校验。
#   7. 创建发布锁 /var/lock/qutwiki-rag/deploy.lock（目录 0755 root:root，
#      文件 0644 root:root）。gateway 加共享 flock，root helper 必须对**同一路径**
#      加独占 flock。锁目录不用公共的 /run/lock 根目录，避免部署账号预创建
#      symlink；同时写 /etc/tmpfiles.d/qutwiki-rag-lock.conf 保证重启后重建。
#
# 网关三个命令（详见 ssh-gateway.py）：
#   baseline
#   upload <40hex commit>-<run id digits>-<attempt digits>
#   publish <release> <64hex baseline manifest sha256>
#
# 与 workflow 的约定：
#   * 只用 qutrag-deploy + 专用私钥，不开 PTY、不做端口转发、不用 rsync/scp。
#   * baseline 输出未压缩 tar；upload 的 stdin 也必须是未压缩 tar，且只含
#     vectors.npy / chunks.jsonl / manifest.json 三个顶层普通文件。
#   * publish 的 baseline sha256 是 baseline tar 中 manifest.json 的 sha256；
#     root helper 必须再次计算当前 live manifest 并比对，防止基于旧 baseline 发布。

set -eu
umask 077

USER_NAME="qutrag-deploy"
GROUP_NAME="qutrag-deploy"
HOME_DIR="/var/lib/qutwiki-rag-deploy"
INCOMING_DIR="$HOME_DIR/incoming"
APP_DIR="/opt/qutwiki-rag"
INDEX_DIR="$APP_DIR/index"
GATEWAY_PATH="/usr/local/libexec/qutwiki-rag-ssh-gateway"
DEPLOY_PATH="/usr/local/libexec/qutwiki-rag-deploy"
SUDOERS_PATH="/etc/sudoers.d/qutwiki-rag-deploy"
AUTH_KEYS="$HOME_DIR/.ssh/authorized_keys"
LOCK_DIR="/var/lock/qutwiki-rag"
LOCK_FILE="$LOCK_DIR/deploy.lock"
TMPFILES_CONF="/etc/tmpfiles.d/qutwiki-rag-lock.conf"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
GATEWAY_SRC="$SCRIPT_DIR/ssh-gateway.py"
DEPLOY_SRC="$SCRIPT_DIR/deploy-index.sh"

MODE="install"
PUBKEY=""
AUTH_LINE=""

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
note() { printf '==> %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }

usage() {
    cat >&2 <<'EOF'
Usage: install-deploy-user.sh [--check] PUBLIC_KEY_FILE

  --check   只检查当前安装状态，不修改任何文件
  PUBLIC_KEY_FILE  Actions 专用 SSH 公钥（不要传私钥）
EOF
}

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --check) MODE="check"; shift ;;
        --help|-h) usage; exit 0 ;;
        --) shift; break ;;
        -*) die "unknown option: $1" ;;
        *)
            [ -z "$PUBKEY" ] || die "only one PUBLIC_KEY_FILE is accepted"
            PUBKEY="$1"
            shift
            ;;
    esac
done

[ -n "$PUBKEY" ] || { usage; exit 2; }
[ "$(id -u)" -eq 0 ] || die "must run as root"
need_cmd awk
need_cmd getent
need_cmd stat
need_cmd find
need_cmd install
need_cmd mktemp
need_cmd ssh-keygen
need_cmd visudo

[ -d "$APP_DIR" ] || die "application directory not found: $APP_DIR"
[ -e "$INDEX_DIR" ] || [ -L "$INDEX_DIR" ] || die "index path not found: $INDEX_DIR"
for d in /opt /usr/local; do
    [ -d "$d" ] || die "required directory missing: $d"
    [ "$(stat -c '%u' "$d")" -eq 0 ] || die "$d must be owned by root"
    bad=$(find "$d" -maxdepth 0 -perm -0022 -print -quit)
    [ -z "$bad" ] || die "$d must not be group/world writable"
done
[ -f "$GATEWAY_SRC" ] || die "gateway source not found: $GATEWAY_SRC"
[ -f "$DEPLOY_SRC" ] || die "deploy helper source not found: $DEPLOY_SRC (another change must provide deploy-index.sh)"
[ -x /usr/bin/python3 ] || die "gateway requires /usr/bin/python3"
head -n 1 "$GATEWAY_SRC" | grep -qx '#!/usr/bin/python3 -I' \
    || die "gateway source must start with #!/usr/bin/python3 -I"

# ---------------------------------------------------------------------------
# 公钥
# ---------------------------------------------------------------------------
validate_public_key() {
    [ -f "$PUBKEY" ] && [ -r "$PUBKEY" ] || die "public key file is not readable: $PUBKEY"
    if [ "$(head -c 5 "$PUBKEY" 2>/dev/null || true)" = "-----" ]; then
        die "refusing private key material; pass the .pub file"
    fi
    key_count=$(awk 'NF >= 2 && $1 !~ /^#/ {n++} END {print n+0}' "$PUBKEY")
    [ "$key_count" -eq 1 ] || die "public key file must contain exactly one key"
    keytype=$(awk 'NF >= 2 && $1 !~ /^#/ {print $1; exit}' "$PUBKEY" | tr -d '\r')
    keydata=$(awk 'NF >= 2 && $1 !~ /^#/ {print $2; exit}' "$PUBKEY" | tr -d '\r')
    case "$keytype" in
        ssh-ed25519|ssh-rsa|ecdsa-sha2-*|sk-ssh-ed25519@openssh.com|sk-ecdsa-sha2-nistp256@openssh.com) ;;
        *) die "unsupported public key type: $keytype" ;;
    esac
    case "$keydata" in
        *[!A-Za-z0-9+/=]*) die "public key data contains unexpected characters" ;;
    esac
    keytmp=$(mktemp)
    printf '%s %s\n' "$keytype" "$keydata" > "$keytmp"
    if ! fingerprint=$(ssh-keygen -lf "$keytmp" 2>/dev/null | awk '{print $2}'); then
        rm -f "$keytmp"
        die "ssh-keygen rejected the public key"
    fi
    rm -f "$keytmp"
    [ -n "$fingerprint" ] || die "cannot compute public key fingerprint"
    AUTH_LINE="restrict,command=\"$GATEWAY_PATH\" $keytype $keydata qutwiki-rag-actions"
    note "key fingerprint: $fingerprint"
}

# ---------------------------------------------------------------------------
# 账号与目录检查
# ---------------------------------------------------------------------------
account_exists() {
    id "$USER_NAME" >/dev/null 2>&1
}

check_account() {
    account_exists || die "account does not exist: $USER_NAME"
    uid=$(id -u "$USER_NAME")
    [ "$uid" -ne 0 ] || die "refusing to use uid 0 account"
    passwd_home=$(getent passwd "$USER_NAME" | awk -F: '{print $6; exit}')
    [ "$passwd_home" = "$HOME_DIR" ] || die "$USER_NAME home is $passwd_home, expected $HOME_DIR"
    passwd_shell=$(getent passwd "$USER_NAME" | awk -F: '{print $7; exit}')
    case "$passwd_shell" in
        /bin/bash|/usr/bin/bash) ;;
        *) die "$USER_NAME shell is $passwd_shell, expected /bin/bash (needed for forced command)" ;;
    esac
    primary_group=$(id -gn "$USER_NAME")
    [ "$primary_group" = "$GROUP_NAME" ] || die "$USER_NAME primary group is $primary_group, expected $GROUP_NAME"
    extra_groups=$(id -Gn "$USER_NAME" | tr ' ' '\n' | grep -vx "$GROUP_NAME" | grep -v '^$' || true)
    [ -z "$extra_groups" ] || die "$USER_NAME has unexpected supplementary groups: $extra_groups"
    pstat=$(passwd -S "$USER_NAME" 2>/dev/null | awk '{print $2}')
    case "$pstat" in
        L|NP|"") ;;
        P) die "$USER_NAME has a password; lock it with: passwd -l $USER_NAME" ;;
        *) warn "unexpected passwd status '$pstat' for $USER_NAME" ;;
    esac
    if [ -e "$HOME_DIR" ]; then
        [ -d "$HOME_DIR" ] && [ ! -L "$HOME_DIR" ] || die "$HOME_DIR must be a real directory"
        owner=$(stat -c '%U:%G' "$HOME_DIR")
        [ "$owner" = "$USER_NAME:$GROUP_NAME" ] || die "$HOME_DIR owner is $owner, expected $USER_NAME:$GROUP_NAME"
    fi
}

create_account() {
    if getent group "$GROUP_NAME" >/dev/null 2>&1; then
        members=$(getent group "$GROUP_NAME" | awk -F: '{print $4}')
        [ -z "$members" ] || die "group $GROUP_NAME already has members: $members"
    else
        groupadd --system "$GROUP_NAME" || die "groupadd failed"
    fi
    useradd --system --no-create-home --home-dir "$HOME_DIR" \
        --shell /bin/bash --gid "$GROUP_NAME" \
        --comment "QUTWiKi RAG SSH deploy (forced command)" \
        "$USER_NAME" || die "useradd failed"
    passwd -l "$USER_NAME" >/dev/null 2>&1 || warn "could not lock $USER_NAME password"
    note "created system account $USER_NAME"
}

check_authorized_keys() {
    if [ ! -e "$AUTH_KEYS" ]; then
        [ "$MODE" = "check" ] && die "authorized_keys is not installed: $AUTH_KEYS"
        return 0
    fi
    [ -f "$AUTH_KEYS" ] && [ ! -L "$AUTH_KEYS" ] || die "$AUTH_KEYS must be a real file"
    owner=$(stat -c '%U:%G' "$AUTH_KEYS")
    [ "$owner" = "$USER_NAME:$GROUP_NAME" ] || die "$AUTH_KEYS owner is $owner"
    mode=$(stat -c '%a' "$AUTH_KEYS")
    [ "$mode" = "600" ] || die "$AUTH_KEYS mode is $mode, expected 600"
    existing=$(grep -vE '^[[:space:]]*(#|$)' "$AUTH_KEYS" || true)
    if [ -n "$existing" ] && [ "$existing" != "$AUTH_LINE" ]; then
        die "$AUTH_KEYS contains unknown key(s); refusing to overwrite. Back it up and remove them first."
    fi
    if [ "$MODE" = "check" ] && [ "$existing" != "$AUTH_LINE" ]; then
        die "managed key is not installed in $AUTH_KEYS"
    fi
}

promote_incoming() {
    if [ -e "$INCOMING_DIR" ] || [ -L "$INCOMING_DIR" ]; then
        [ -d "$INCOMING_DIR" ] && [ ! -L "$INCOMING_DIR" ] || die "$INCOMING_DIR must be a real directory"
        owner=$(stat -c '%U:%G' "$INCOMING_DIR")
        [ "$owner" = "$USER_NAME:$GROUP_NAME" ] || die "$INCOMING_DIR owner is $owner, refusing to take it over"
    fi
    install -d -m 0700 -o "$USER_NAME" -g "$GROUP_NAME" "$INCOMING_DIR"
    chmod 0700 "$INCOMING_DIR"
    owner=$(stat -c '%U:%G' "$INCOMING_DIR")
    [ "$owner" = "$USER_NAME:$GROUP_NAME" ] || die "$INCOMING_DIR owner is $owner"
}

install_lock() {
    # /var/lock 在 Ubuntu 上是指向 /run/lock 的 symlink；只固定检查最终子目录。
    if [ -e "$LOCK_DIR" ] || [ -L "$LOCK_DIR" ]; then
        [ -d "$LOCK_DIR" ] && [ ! -L "$LOCK_DIR" ] || die "$LOCK_DIR must be a real directory"
        owner=$(stat -c '%U:%G' "$LOCK_DIR")
        [ "$owner" = "root:root" ] || die "$LOCK_DIR owner is $owner, refusing to take it over"
    fi
    install -d -m 0755 -o root -g root "$LOCK_DIR"
    chmod 0755 "$LOCK_DIR"

    if [ -e "$LOCK_FILE" ] || [ -L "$LOCK_FILE" ]; then
        [ -f "$LOCK_FILE" ] && [ ! -L "$LOCK_FILE" ] || die "$LOCK_FILE must be a real file"
        owner=$(stat -c '%U:%G' "$LOCK_FILE")
        [ "$owner" = "root:root" ] || die "$LOCK_FILE owner is $owner, refusing to take it over"
    else
        install -m 0644 -o root -g root /dev/null "$LOCK_FILE"
    fi
    chown root:root "$LOCK_FILE"
    chmod 0644 "$LOCK_FILE"

    if [ -d /etc/tmpfiles.d ] && [ ! -L /etc/tmpfiles.d ]; then
        tmp=$(mktemp /etc/tmpfiles.d/.qutwiki-rag-lock.XXXXXX)
        cat > "$tmp" <<'EOF'
d /run/lock/qutwiki-rag 0755 root root -
f /run/lock/qutwiki-rag/deploy.lock 0644 root root -
EOF
        chown root:root "$tmp"
        chmod 0644 "$tmp"
        mv -f "$tmp" "$TMPFILES_CONF"
        note "installed $TMPFILES_CONF"
        if command -v systemd-tmpfiles >/dev/null 2>&1; then
            systemd-tmpfiles --create "$TMPFILES_CONF" >/dev/null 2>&1 || warn "systemd-tmpfiles --create failed"
        fi
    else
        warn "/etc/tmpfiles.d not found; lock will be recreated by this installer only"
    fi
}

check_lock() {
    [ -d "$LOCK_DIR" ] && [ ! -L "$LOCK_DIR" ] || die "$LOCK_DIR missing or symlink"
    [ "$(stat -c '%U:%G' "$LOCK_DIR")" = "root:root" ] || die "$LOCK_DIR must be root:root"
    bad=$(find "$LOCK_DIR" -maxdepth 0 -perm -0022 -print -quit)
    [ -z "$bad" ] || die "$LOCK_DIR must not be group/world writable"
    [ -f "$LOCK_FILE" ] && [ ! -L "$LOCK_FILE" ] || die "$LOCK_FILE missing or symlink"
    [ "$(stat -c '%U:%G' "$LOCK_FILE")" = "root:root" ] || die "$LOCK_FILE must be root:root"
    mode=$(stat -c '%a' "$LOCK_FILE")
    [ "$mode" = "644" ] || die "$LOCK_FILE mode is $mode, expected 644"
    bad=$(find "$LOCK_FILE" -maxdepth 0 -perm -0022 -print -quit)
    [ -z "$bad" ] || die "$LOCK_FILE must not be group/world writable"
    if command -v runuser >/dev/null 2>&1; then
        runuser -u "$USER_NAME" -- test -r "$LOCK_FILE" \
            || die "$USER_NAME cannot read $LOCK_FILE"
        if runuser -u "$USER_NAME" -- test -w "$LOCK_FILE"; then
            die "$USER_NAME can write $LOCK_FILE"
        fi
    fi
}

check_dirs() {
    [ -d "$HOME_DIR" ] && [ ! -L "$HOME_DIR" ] || die "$HOME_DIR missing or symlink"
    [ -d "$HOME_DIR/.ssh" ] && [ ! -L "$HOME_DIR/.ssh" ] || die "$HOME_DIR/.ssh missing or symlink"
    [ -d "$INCOMING_DIR" ] && [ ! -L "$INCOMING_DIR" ] || die "$INCOMING_DIR missing or symlink"
    for d in "$HOME_DIR" "$HOME_DIR/.ssh" "$INCOMING_DIR"; do
        mode=$(stat -c '%a' "$d")
        [ "$mode" = "700" ] || die "$d mode is $mode, expected 700"
        owner=$(stat -c '%U:%G' "$d")
        [ "$owner" = "$USER_NAME:$GROUP_NAME" ] || die "$d owner is $owner"
    done
}

# ---------------------------------------------------------------------------
# /opt/qutwiki-rag 权限收紧
# ---------------------------------------------------------------------------
app_real() {
    real=$(readlink -f "$APP_DIR")
    [ -n "$real" ] && [ -d "$real" ] || die "cannot resolve $APP_DIR"
    printf '%s\n' "$real"
}

tighten_app() {
    real=$(app_real)
    owner_uid=$(stat -c '%u' "$real")
    [ "$owner_uid" -eq 0 ] || die "$real must be owned by root"
    bad=$(find "$real" \( -type d -o -type f \) ! -uid 0 -print -quit)
    [ -z "$bad" ] || die "refusing: application contains non-root-owned entry: $bad"
    note "removing group/world write from $real (symlinks are not followed)"
    find "$real" -type d -exec chmod go-w {} +
    find "$real" -type f -exec chmod go-w {} +
    chmod 0755 "$real"

    # deploy helper 首次发布后会把 index 换成 releases/<release> 的 symlink；
    # 这里允许这种唯一形态，但目标必须仍在 root-owned releases/ 内。
    if [ -L "$real/index" ]; then
        index_path=$(readlink -f "$real/index")
        case "$index_path" in
            "$real/releases/"*) ;;
            *) die "index symlink target escapes $real/releases: $index_path" ;;
        esac
        [ -d "$index_path" ] && [ ! -L "$index_path" ] || die "index symlink target is not a real directory"
    else
        [ -d "$real/index" ] && [ ! -L "$real/index" ] || die "index must be a real directory or a releases/ symlink"
        index_path="$real/index"
    fi
    chmod 0755 "$index_path"
    find "$index_path" -maxdepth 1 -type f \
        \( -name vectors.npy -o -name chunks.jsonl -o -name manifest.json \) \
        -exec chmod 0644 {} +

    if [ -e "$real/releases" ] || [ -L "$real/releases" ]; then
        [ -d "$real/releases" ] && [ ! -L "$real/releases" ] || die "$real/releases must be a real directory"
        chmod 0755 "$real/releases"
        find "$real/releases" -mindepth 1 -maxdepth 1 -type d -exec chmod 0755 {} +
    fi

    bad=$(find "$real" -type l \
        \( -name '.env' -o -name '.env.*' -o -name 'llm.json' \) -print -quit)
    [ -z "$bad" ] || die "secret file must not be a symlink: $bad"
    find "$real" -type f \
        \( -name '.env' -o -name '.env.*' -o -name 'llm.json' \) \
        -exec chmod 0600 {} +
}

check_app() {
    real=$(app_real)
    owner_uid=$(stat -c '%u' "$real")
    [ "$owner_uid" -eq 0 ] || die "$real must be owned by root"
    bad=$(find "$real" \( -type d -o -type f \) ! -uid 0 -print -quit)
    [ -z "$bad" ] || die "application contains non-root-owned entry: $bad"
    bad=$(find "$real" \( -type d -o -type f \) \( -perm -0020 -o -perm -0002 \) -print -quit)
    [ -z "$bad" ] || die "group/world-writable entry remains: $bad"

    if [ -L "$real/index" ]; then
        index_path=$(readlink -f "$real/index")
        case "$index_path" in
            "$real/releases/"*) ;;
            *) die "index symlink target escapes $real/releases: $index_path" ;;
        esac
        [ -d "$index_path" ] && [ ! -L "$index_path" ] || die "index symlink target is not a real directory"
    else
        [ -d "$real/index" ] && [ ! -L "$real/index" ] || die "index must be a real directory or a releases/ symlink"
        index_path="$real/index"
    fi
    for f in "$index_path/vectors.npy" "$index_path/chunks.jsonl" "$index_path/manifest.json"; do
        [ -f "$f" ] && [ ! -L "$f" ] || die "missing regular index file: $f"
    done

    # 机密文件必须是真实普通文件且 0600
    bad=$(find "$real" -type l \
        \( -name '.env' -o -name '.env.*' -o -name 'llm.json' \) -print -quit)
    [ -z "$bad" ] || die "secret file must not be a symlink: $bad"
    bad=$(find "$real" -type f \
        \( -name '.env' -o -name '.env.*' -o -name 'llm.json' \) \
        ! -perm 0600 -print -quit)
    [ -z "$bad" ] || die "$bad must be mode 0600"
    if command -v runuser >/dev/null 2>&1; then
        runuser -u "$USER_NAME" -- test -r "$real/index/manifest.json" \
            || die "$USER_NAME cannot read $real/index/manifest.json"
        for p in "$real" "$real/scripts" "$real/index"; do
            [ -e "$p" ] || continue
            if runuser -u "$USER_NAME" -- test -w "$p"; then
                die "$USER_NAME can write $p"
            fi
        done
        for f in "$real/.env" "$real/llm.json"; do
            [ -e "$f" ] || continue
            if runuser -u "$USER_NAME" -- test -r "$f"; then
                die "$USER_NAME can read secret $f"
            fi
        done
    else
        warn "runuser not found; skipped live permission probes"
    fi
}

# ---------------------------------------------------------------------------
# root-owned 文件与 sudo
# ---------------------------------------------------------------------------
install_root_file() {
    src=$1
    dst=$2
    mode=$3
    [ -f "$src" ] && [ ! -L "$src" ] || die "source is not a regular file: $src"
    dir=$(dirname "$dst")
    [ -d "$dir" ] || install -d -m 0755 -o root -g root "$dir"
    [ "$(stat -c '%u' "$dir")" -eq 0 ] || die "$dir must be root-owned"
    tmp=$(mktemp "$dir/.qutwiki-rag-install.XXXXXX")
    cp "$src" "$tmp"
    chown root:root "$tmp"
    chmod "$mode" "$tmp"
    mv -f "$tmp" "$dst"
}

install_root_files() {
    install -d -m 0755 -o root -g root /usr/local/libexec
    [ "$(stat -c '%u' /usr/local/libexec)" -eq 0 ] || die "/usr/local/libexec must be root-owned"
    bad=$(find /usr/local/libexec -maxdepth 0 -perm -0022 -print -quit)
    [ -z "$bad" ] || die "/usr/local/libexec must not be group/world writable"
    install_root_file "$GATEWAY_SRC" "$GATEWAY_PATH" 0755
    install_root_file "$DEPLOY_SRC" "$DEPLOY_PATH" 0755
    note "installed root-owned $GATEWAY_PATH and $DEPLOY_PATH"
}

check_root_files() {
    [ "$(stat -c '%u' /usr/local/libexec)" -eq 0 ] || die "/usr/local/libexec must be root-owned"
    bad=$(find /usr/local/libexec -maxdepth 0 -perm -0022 -print -quit)
    [ -z "$bad" ] || die "/usr/local/libexec must not be group/world writable"
    for f in "$GATEWAY_PATH" "$DEPLOY_PATH"; do
        [ -f "$f" ] && [ ! -L "$f" ] || die "root-owned file missing: $f"
        owner=$(stat -c '%U:%G' "$f")
        [ "$owner" = "root:root" ] || die "$f owner is $owner"
        if [ "$(stat -c '%a' "$f" | cut -c1)" != "7" ]; then
            die "$f must be executable and not group/world writable"
        fi
        bad=$(find "$f" -maxdepth 0 -perm -0022 -print -quit)
        [ -z "$bad" ] || die "$f is group/world writable"
    done
}

sudoers_content() {
    cat <<EOF
Defaults:$USER_NAME !requiretty
Defaults:$USER_NAME !setenv
Defaults:$USER_NAME secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
$USER_NAME ALL=(root) NOPASSWD: $DEPLOY_PATH *
EOF
}

check_sudoers_include() {
    grep -Eq '^[#@]includedir[[:space:]]+/etc/sudoers\.d([[:space:]]|$)' /etc/sudoers \
        || die "/etc/sudoers does not include /etc/sudoers.d"
    for p in /etc/sudoers /etc/sudoers.d; do
        [ -e "$p" ] || die "missing $p"
        [ "$(stat -c '%u' "$p")" -eq 0 ] || die "$p must be owned by root"
        bad=$(find "$p" -maxdepth 0 -perm -0022 -print -quit)
        [ -z "$bad" ] || die "$p must not be group/world writable"
    done
}

install_sudoers() {
    check_sudoers_include
    tmp=$(mktemp /etc/sudoers.d/.qutwiki-rag-deploy.XXXXXX)
    sudoers_content > "$tmp"
    chmod 0440 "$tmp"
    chown root:root "$tmp"
    if ! visudo -cf "$tmp" >/dev/null; then
        rm -f "$tmp"
        die "generated sudoers fragment is invalid"
    fi
    if [ -e "$SUDOERS_PATH" ]; then
        [ -f "$SUDOERS_PATH" ] && [ ! -L "$SUDOERS_PATH" ] || die "$SUDOERS_PATH must be a real file"
        if ! cmp -s "$tmp" "$SUDOERS_PATH"; then
            backup="/var/backups/qutwiki-rag-deploy.sudoers.$(date +%Y%m%d%H%M%S)"
            mkdir -p /var/backups
            cp -p "$SUDOERS_PATH" "$backup"
            note "backed up previous sudoers to $backup"
        fi
    fi
    chmod 0440 "$tmp"
    chown root:root "$tmp"
    mv -f "$tmp" "$SUDOERS_PATH"
    note "installed $SUDOERS_PATH (only $DEPLOY_PATH is allowed)"
}

check_sudoers() {
    check_sudoers_include
    [ -f "$SUDOERS_PATH" ] && [ ! -L "$SUDOERS_PATH" ] || die "$SUDOERS_PATH missing or symlink"
    owner=$(stat -c '%U:%G' "$SUDOERS_PATH")
    [ "$owner" = "root:root" ] || die "$SUDOERS_PATH owner is $owner"
    mode=$(stat -c '%a' "$SUDOERS_PATH")
    [ "$mode" = "440" ] || die "$SUDOERS_PATH mode is $mode, expected 440"
    tmp=$(mktemp)
    sudoers_content > "$tmp"
    if ! cmp -s "$tmp" "$SUDOERS_PATH"; then
        rm -f "$tmp"
        die "$SUDOERS_PATH differs from the expected fixed rule"
    fi
    rm -f "$tmp"
    visudo -cf "$SUDOERS_PATH" >/dev/null || die "$SUDOERS_PATH is invalid"
}

# ---------------------------------------------------------------------------
# 最终运行验证
# ---------------------------------------------------------------------------
verify_gateway_baseline() {
    command -v runuser >/dev/null 2>&1 || { warn "runuser not found; skipped gateway baseline test"; return 0; }
    note "testing gateway baseline as $USER_NAME"
    if ! runuser -u "$USER_NAME" -- env -i SSH_ORIGINAL_COMMAND=baseline "$GATEWAY_PATH" >/dev/null; then
        die "gateway baseline failed as $USER_NAME (check /opt/qutwiki-rag permissions and index files)"
    fi
}

install_all() {
    if ! account_exists; then
        create_account
    fi
    check_account
    if [ -e "$HOME_DIR" ] || [ -L "$HOME_DIR" ]; then
        [ -d "$HOME_DIR" ] && [ ! -L "$HOME_DIR" ] || die "$HOME_DIR must be a real directory"
        owner=$(stat -c '%U:%G' "$HOME_DIR")
        [ "$owner" = "$USER_NAME:$GROUP_NAME" ] || die "$HOME_DIR owner is $owner, refusing to take it over"
    fi
    if [ -e "$HOME_DIR/.ssh" ] || [ -L "$HOME_DIR/.ssh" ]; then
        [ -d "$HOME_DIR/.ssh" ] && [ ! -L "$HOME_DIR/.ssh" ] || die "$HOME_DIR/.ssh must be a real directory"
        owner=$(stat -c '%U:%G' "$HOME_DIR/.ssh")
        [ "$owner" = "$USER_NAME:$GROUP_NAME" ] || die "$HOME_DIR/.ssh owner is $owner, refusing to take it over"
    fi
    install -d -m 0700 -o "$USER_NAME" -g "$GROUP_NAME" "$HOME_DIR"
    chmod 0700 "$HOME_DIR"
    install -d -m 0700 -o "$USER_NAME" -g "$GROUP_NAME" "$HOME_DIR/.ssh"
    chmod 0700 "$HOME_DIR/.ssh"

    check_authorized_keys
    tmp=$(mktemp "$HOME_DIR/.ssh/.authorized_keys.XXXXXX")
    if [ -e "$AUTH_KEYS" ]; then
        # 只保留注释/空行；未知 key 已在 check_authorized_keys 中拒绝。
        grep -E '^[[:space:]]*(#|$)' "$AUTH_KEYS" > "$tmp" || true
    fi
    printf '%s\n' "$AUTH_LINE" >> "$tmp"
    chown "$USER_NAME:$GROUP_NAME" "$tmp"
    chmod 0600 "$tmp"
    mv -f "$tmp" "$AUTH_KEYS"
    note "installed managed key in $AUTH_KEYS"
    chown "$USER_NAME:$GROUP_NAME" "$AUTH_KEYS"
    chmod 0600 "$AUTH_KEYS"

    promote_incoming
    install_lock
    tighten_app
    install_root_files
    install_sudoers

    check_account
    check_dirs
    check_lock
    check_authorized_keys
    check_app
    check_root_files
    check_sudoers
    verify_gateway_baseline

    note "installation complete"
    note "ensure sshd allows this account (PubkeyAuthentication yes, AllowUsers if used)"
    note "publish lock: $LOCK_FILE (gateway shared flock; root helper must use exclusive flock on the same path)"
    note "workflow: baseline -> build -> upload <release> -> publish <release> <baseline manifest sha256>"
}

check_all() {
    check_account
    check_dirs
    check_lock
    check_authorized_keys
    check_app
    check_root_files
    check_sudoers
    verify_gateway_baseline
    note "check passed"
}

validate_public_key

if [ "$MODE" = "check" ]; then
    check_all
else
    install_all
fi
