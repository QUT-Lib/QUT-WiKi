#!/usr/bin/python3 -I
# -*- coding: utf-8 -*-
"""QUTWiKi RAG 专用 SSH 网关（root-owned，只由 forced command 调用）。

部署账号（默认 qutrag-deploy）的 authorized_keys 使用：

    restrict,command="/usr/local/libexec/qutwiki-rag-ssh-gateway" ssh-ed25519 ...

`restrict` 关闭 PTY、端口转发、agent/X11 转发和 ~/.ssh/rc；本文件不启动 shell，
只接受下面三个命令，命令参数用白名单正则校验：

    baseline
        向 stdout 输出一个未压缩 tar，且只含三个普通文件：
        vectors.npy / chunks.jsonl / manifest.json（来自 /opt/qutwiki-rag/index）。
        首次发布前 index 是真实目录；deploy helper 之后会把它换成
        /opt/qutwiki-rag/releases/<release> 的 symlink，网关只允许该范围内的链接。
        读取期间持有 /var/lock/qutwiki-rag/deploy.lock 的共享 flock；root helper
        必须对同一路径加独占 flock，锁目录和文件均由 root 拥有。

    upload <40hex-commit>-<digits-runid>-<digits-attempt>
        从 stdin 读取一个未压缩 tar，只允许上述三个文件，严格拒绝目录、符号链接、
        硬链接、设备、FIFO、绝对路径、`..`、重复项和超限尺寸。校验通过后原子地
        放到 /var/lib/qutwiki-rag-deploy/incoming/<release>/（0700/0600）。

    publish <release> <64hex-baseline-manifest-sha256>
        先以部署账号身份复查 release，再执行唯一允许的 sudo 固定 helper：
        /usr/local/libexec/qutwiki-rag-deploy <release> <baseline-sha256>
        helper 必须再次校验目录、所有者、文件类型、大小、manifest 哈希和当前
        live baseline，然后用 O_NOFOLLOW 读取并原子发布；本网关不做特权操作。

不读取 .env / llm.json，不调用 rsync，不接受任意命令、任意路径或任意 sudo。
"""

import ast
import errno
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import stat
import sys
import tarfile
import tempfile
import time
import uuid

try:  # Linux 生产环境；Windows 测试环境没有 fcntl。
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

INDEX_DIR = "/opt/qutwiki-rag/index"
INDEX_RELEASES = "/opt/qutwiki-rag/releases"
INCOMING_DIR = "/var/lib/qutwiki-rag-deploy/incoming"
DEPLOY_HELPER = "/usr/local/libexec/qutwiki-rag-deploy"
# 与 root helper 共用的发布锁；目录/文件均为 root-owned，部署账号只能只读打开。
LOCK_PATH = "/var/lock/qutwiki-rag/deploy.lock"
LOCK_TIMEOUT = 180.0

INDEX_FILES = ("vectors.npy", "chunks.jsonl", "manifest.json")
RELEASE_RE = re.compile(r"^[0-9a-f]{40}-[0-9]{1,20}-[0-9]{1,20}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA1_RE = re.compile(r"^[0-9a-fA-F]{40}$")
MAX_COMMAND_LEN = 512
MAX_CHUNKS = 5_000_000

MIB = 1024 * 1024


class GatewayError(Exception):
    """可预期错误：只把消息写到 stderr，退出码区分类型。"""

    code = 6


class UsageError(GatewayError):
    code = 2


class InputError(GatewayError):
    code = 3


class NotFoundError(GatewayError):
    code = 4


class ConflictError(GatewayError):
    code = 5


class InconsistentIndex(InputError):
    """索引三个文件不是同一代（发布/读取竞态），baseline 可重试。"""


class Limits(object):
    """所有尺寸上限，默认值同时写进安装说明。"""

    def __init__(self, total=None, vectors=None, chunks=None, manifest=None,
                 stream=None, max_line=None):
        self.total = 512 * MIB if total is None else total
        self.vectors = 384 * MIB if vectors is None else vectors
        self.chunks = 384 * MIB if chunks is None else chunks
        self.manifest = 4 * MIB if manifest is None else manifest
        self.stream = (self.total + 64 * MIB) if stream is None else stream
        self.max_line = 8 * MIB if max_line is None else max_line

    @property
    def per_file(self):
        return {
            "vectors.npy": self.vectors,
            "chunks.jsonl": self.chunks,
            "manifest.json": self.manifest,
        }


# ---------------------------------------------------------------------------
# 命令解析
# ---------------------------------------------------------------------------

def parse_command(raw):
    """把 SSH_ORIGINAL_COMMAND 解析成 (action, args...)，不做任何 shell 展开。"""
    if raw is None or raw == "":
        raise UsageError("this account only accepts the fixed qutwiki-rag gateway commands")
    if len(raw) > MAX_COMMAND_LEN:
        raise UsageError("command too long")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in raw):
        raise UsageError("control characters are not allowed in command")
    try:
        parts = shlex.split(raw, posix=True)
    except ValueError as exc:
        raise UsageError("cannot parse command: %s" % exc)
    if not parts:
        raise UsageError("empty command")

    action = parts[0]
    if action == "baseline" and len(parts) == 1:
        return ("baseline",)
    if action == "upload" and len(parts) == 2:
        check_release(parts[1])
        return ("upload", parts[1])
    if action == "publish" and len(parts) == 3:
        check_release(parts[1])
        if not SHA256_RE.match(parts[2]):
            raise UsageError("publish baseline must be 64 lowercase hex characters")
        return ("publish", parts[1], parts[2])
    raise UsageError(
        "allowed: baseline | upload <release> | publish <release> <sha256>"
    )


def check_release(release):
    if not isinstance(release, str) or not RELEASE_RE.match(release):
        raise UsageError(
            "release must be <40 lowercase hex commit>-<run id digits>-<attempt digits>"
        )
    return release


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------

def sha1_hex(data):
    return hashlib.sha1(data).hexdigest()


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def _euid():
    return os.geteuid() if hasattr(os, "geteuid") else None


def _open_publish_lock(path):
    """只读打开 root-owned 锁文件，并检查父目录/文件不可被部署账号替换。"""
    if fcntl is None:
        raise InputError("publish lock requires POSIX fcntl")
    directory = os.path.dirname(path)
    try:
        dst = os.lstat(directory)
    except OSError as exc:
        if exc.errno in (errno.ENOENT, errno.ENOTDIR):
            raise InputError(
                "publish lock directory does not exist; run install-deploy-user.sh: %s"
                % directory
            )
        raise
    if not stat.S_ISDIR(dst.st_mode):
        raise InputError("publish lock directory is not a real directory: %s" % directory)
    if dst.st_uid != 0:
        raise InputError("publish lock directory must be owned by root")
    if stat.S_IMODE(dst.st_mode) & 0o022:
        raise InputError("publish lock directory must not be group/world writable")
    try:
        fd = os.open(
            path,
            _flags("O_RDONLY", "O_NOFOLLOW", "O_CLOEXEC", "O_BINARY"),
        )
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            raise InputError(
                "publish lock file does not exist; run install-deploy-user.sh: %s" % path
            )
        if exc.errno == errno.ELOOP:
            raise InputError("publish lock file must not be a symlink")
        if exc.errno in (errno.EACCES, errno.EPERM):
            raise InputError("cannot read publish lock (expected root:root 0644)")
        raise
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise InputError("publish lock must be a regular file")
        if st.st_uid != 0:
            raise InputError("publish lock must be owned by root")
        if stat.S_IMODE(st.st_mode) & 0o022:
            raise InputError("publish lock must not be group/world writable")
    except Exception:
        os.close(fd)
        raise
    return fd


def acquire_shared_lock(path=LOCK_PATH, timeout=LOCK_TIMEOUT):
    """阻塞式（有上限）获取共享 flock；root helper 用同一路径的独占 flock。"""
    fd = _open_publish_lock(path)
    deadline = time.monotonic() + float(timeout)
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            return fd
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EAGAIN):
                os.close(fd)
                raise
            if time.monotonic() >= deadline:
                os.close(fd)
                raise ConflictError(
                    "publish lock is busy (another publish/baseline is running)"
                )
            time.sleep(0.2)


def release_lock(fd):
    if fcntl is not None:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
    try:
        os.close(fd)
    except OSError:
        pass


def _flags(*names):
    value = 0
    for name in names:
        value |= int(getattr(os, name, 0))
    return value


class LimitedReader(object):
    """限制从 stdin 实际读取的字节数，防止 tar 流无限增长。"""

    def __init__(self, raw, limit):
        self.raw = raw
        self.remaining = int(limit)

    def read(self, size=-1):
        if size is None or size < 0:
            size = self.remaining
        else:
            size = min(int(size), self.remaining)
        if size == 0:
            # 只有 tar 还想要数据时才检查多出来的字节。
            extra = self.raw.read(1)
            if extra:
                raise InputError("tar stream exceeds size limit")
            return b""
        data = self.raw.read(size)
        if data:
            self.remaining -= len(data)
        return data


def _read_exact_fd(fd, size):
    chunks = []
    remaining = size
    while remaining > 0:
        chunk = os.read(fd, min(1024 * 1024, remaining))
        if not chunk:
            raise InputError("unexpected end of file")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _write_all(fd, data):
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise InputError("short write")
        view = view[written:]


def _open_dir_nofollow(path):
    """返回目录 fd；Windows 测试环境没有 dir_fd，退化为 None。"""
    if os.name != "posix":
        return None
    flags = _flags("O_RDONLY", "O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC")
    try:
        return os.open(path, flags)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            raise NotFoundError("directory does not exist: %s" % path)
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            raise InputError("not a real directory: %s" % path)
        raise


class DirHandle(object):
    """用 dir_fd + O_NOFOLLOW 访问固定目录里的固定文件名，拒绝符号链接逃逸。"""

    def __init__(self, path):
        self.path = os.path.abspath(path)
        try:
            st = os.lstat(self.path)
        except OSError as exc:
            if exc.errno in (errno.ENOENT, errno.ENOTDIR):
                raise NotFoundError("directory does not exist: %s" % self.path)
            raise
        if not stat.S_ISDIR(st.st_mode):
            raise InputError("not a directory: %s" % self.path)
        self.fd = _open_dir_nofollow(self.path)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            finally:
                self.fd = None

    def listdir(self):
        if self.fd is not None:
            return os.listdir(self.fd)
        return os.listdir(self.path)

    def stat(self, name):
        if self.fd is not None:
            return os.stat(name, dir_fd=self.fd, follow_symlinks=False)
        return os.lstat(os.path.join(self.path, name))

    def open_read(self, name):
        flags = _flags("O_RDONLY", "O_NOFOLLOW", "O_CLOEXEC", "O_BINARY")
        try:
            if self.fd is not None:
                return os.open(name, flags, dir_fd=self.fd)
            return os.open(os.path.join(self.path, name), flags)
        except OSError as exc:
            if exc.errno in (errno.ELOOP, errno.ENOENT, errno.ENOTDIR):
                raise InputError("cannot open regular file safely: %s" % name)
            raise

    def open_write_exclusive(self, name):
        flags = _flags(
            "O_WRONLY", "O_CREAT", "O_EXCL", "O_NOFOLLOW", "O_CLOEXEC", "O_BINARY"
        )
        try:
            if self.fd is not None:
                return os.open(name, flags, 0o600, dir_fd=self.fd)
            return os.open(os.path.join(self.path, name), flags, 0o600)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                raise ConflictError("duplicate file in upload: %s" % name)
            if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                raise InputError("unsafe file in upload: %s" % name)
            raise


def _read_file_at(handle, name, max_size):
    fd = handle.open_read(name)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise InputError("not a regular file: %s" % name)
        if st.st_size > max_size:
            raise InputError("%s exceeds size limit" % name)
        data = _read_exact_fd(fd, st.st_size)
        if os.read(fd, 1):
            raise InconsistentIndex("%s changed while reading" % name)
        return data
    finally:
        os.close(fd)


def _hash_file_at(handle, name, max_size):
    fd = handle.open_read(name)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise InputError("not a regular file: %s" % name)
        if st.st_size > max_size:
            raise InputError("%s exceeds size limit" % name)
        h1 = hashlib.sha1()
        h2 = hashlib.sha256()
        remaining = st.st_size
        while remaining > 0:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                raise InconsistentIndex("%s changed while reading" % name)
            h1.update(chunk)
            h2.update(chunk)
            remaining -= len(chunk)
        if os.read(fd, 1):
            raise InconsistentIndex("%s changed while reading" % name)
        return h1.hexdigest(), h2.hexdigest(), st.st_size
    finally:
        os.close(fd)


def _npy_rows_dim(header_bytes):
    try:
        header = ast.literal_eval(header_bytes.decode("latin1"))
    except (ValueError, SyntaxError, UnicodeDecodeError) as exc:
        raise InputError("vectors.npy header is invalid: %s" % exc)
    if not isinstance(header, dict):
        raise InputError("vectors.npy header is not a dict")
    descr = header.get("descr")
    if descr not in ("<f4", "|f4", "=f4"):
        raise InputError("vectors.npy must be little-endian float32, got %r" % (descr,))
    if header.get("fortran_order") is not False:
        raise InputError("vectors.npy must be C-order")
    shape = header.get("shape")
    if (not isinstance(shape, tuple) or len(shape) != 2
            or not all(isinstance(x, int) and x > 0 for x in shape)):
        raise InputError("vectors.npy must be a non-empty 2-D array")
    rows, dim = shape
    if rows > MAX_CHUNKS or dim > 65536:
        raise InputError("vectors.npy shape is too large")
    return rows, dim


def _parse_npy_header_bytes(data):
    """解析 .npy 头，返回 (rows, dim, total_size)。只接受 float32 二维 C 顺序。"""
    if len(data) < 10 or data[:6] != b"\x93NUMPY":
        raise InputError("vectors.npy has no valid .npy magic")
    major = data[6]
    if major == 1:
        header_len = int.from_bytes(data[8:10], "little")
        offset = 10
    elif major in (2, 3):
        if len(data) < 12:
            raise InputError("vectors.npy header is truncated")
        header_len = int.from_bytes(data[8:12], "little")
        offset = 12
    else:
        raise InputError("unsupported .npy version")
    if header_len <= 0 or header_len > 4096 or len(data) < offset + header_len:
        raise InputError("vectors.npy header is truncated or too large")
    rows, dim = _npy_rows_dim(data[offset:offset + header_len])
    total = offset + header_len + rows * dim * 4
    if total != len(data):
        raise InconsistentIndex(
            "vectors.npy size %d does not match shape %dx%d (%d)"
            % (len(data), rows, dim, total)
        )
    return rows, dim, total


def _read_npy_header_at(handle, name, max_size):
    fd = handle.open_read(name)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise InputError("not a regular file: %s" % name)
        if st.st_size > max_size:
            raise InputError("%s exceeds size limit" % name)
        prefix = _read_exact_fd(fd, 8)
        if prefix[:6] != b"\x93NUMPY":
            raise InputError("vectors.npy has no valid .npy magic")
        major = prefix[6]
        if major == 1:
            lens = _read_exact_fd(fd, 2)
            header_len = int.from_bytes(lens, "little")
            offset = 10
        elif major in (2, 3):
            lens = _read_exact_fd(fd, 4)
            header_len = int.from_bytes(lens, "little")
            offset = 12
        else:
            raise InputError("unsupported .npy version")
        if header_len <= 0 or header_len > 4096:
            raise InputError("vectors.npy header is truncated or too large")
        header_bytes = _read_exact_fd(fd, header_len)
        st2 = os.fstat(fd)
        if st2.st_size != st.st_size:
            raise InconsistentIndex("vectors.npy changed while reading")
    finally:
        os.close(fd)
    rows, dim = _npy_rows_dim(header_bytes)
    if offset + header_len + rows * dim * 4 != st.st_size:
        raise InconsistentIndex(
            "vectors.npy size does not match shape %dx%d" % (rows, dim)
        )
    return rows, dim, st.st_size


def _scan_chunks_at(handle, name, max_size, max_line):
    fd = handle.open_read(name)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise InputError("not a regular file: %s" % name)
        if st.st_size > max_size:
            raise InputError("%s exceeds size limit" % name)
        h1 = hashlib.sha1()
        count = 0
        total = 0
        with os.fdopen(os.dup(fd), "rb") as f:
            for raw in f:
                total += len(raw)
                if total > max_size:
                    raise InputError("%s exceeds size limit" % name)
                if len(raw) > max_line:
                    raise InputError("%s has a line that is too long" % name)
                h1.update(raw)
                line = raw.rstrip(b"\r\n")
                if not line.strip():
                    raise InputError("%s contains a blank line" % name)
                try:
                    obj = json.loads(line.decode("utf-8"))
                except (ValueError, UnicodeDecodeError) as exc:
                    raise InputError("%s is not valid JSONL: %s" % (name, exc))
                if not isinstance(obj, dict):
                    raise InputError("%s line %d is not a JSON object" % (name, count + 1))
                if not str(obj.get("id") or "").strip():
                    raise InputError("%s line %d has an empty chunk id" % (name, count + 1))
                count += 1
                if count > MAX_CHUNKS:
                    raise InputError("%s has too many chunks" % name)
        st2 = os.fstat(fd)
        if st2.st_size != st.st_size or total != st.st_size:
            raise InconsistentIndex("%s changed while reading" % name)
        if count == 0:
            raise InputError("%s is empty" % name)
        return h1.hexdigest(), count
    finally:
        os.close(fd)


def _scan_chunks_bytes(data, max_line):
    if not data:
        raise InputError("chunks.jsonl is empty")
    if len(data) > 384 * MIB:
        raise InputError("chunks.jsonl exceeds size limit")
    h1 = hashlib.sha1(data)
    count = 0
    last_index = data.count(b"\n") + 1
    for lineno, raw in enumerate(data.split(b"\n"), 1):
        if raw == b"" and lineno == last_index:
            continue
        if len(raw) > max_line:
            raise InputError("chunks.jsonl line %d is too long" % lineno)
        line = raw[:-1] if raw.endswith(b"\r") else raw
        if not line.strip():
            raise InputError("chunks.jsonl contains a blank line")
        try:
            obj = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise InputError("chunks.jsonl is not valid JSONL: %s" % exc)
        if not isinstance(obj, dict):
            raise InputError("chunks.jsonl line %d is not a JSON object" % lineno)
        if not str(obj.get("id") or "").strip():
            raise InputError("chunks.jsonl line %d has an empty chunk id" % lineno)
        count += 1
        if count > MAX_CHUNKS:
            raise InputError("chunks.jsonl has too many chunks")
    if count == 0:
        raise InputError("chunks.jsonl is empty")
    return h1.hexdigest(), count


def _manifest_dim(manifest):
    value = manifest.get("embed_dim", manifest.get("dim"))
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _check_manifest_hashes(manifest, vectors_sha1, chunks_sha1, strict):
    for key, actual, label in (
        ("vectors_sha1", vectors_sha1, "vectors.npy"),
        ("chunks_sha1", chunks_sha1, "chunks.jsonl"),
    ):
        declared = manifest.get(key)
        if declared is None:
            if strict:
                raise InputError("manifest.json is missing %s" % key)
            continue
        if not isinstance(declared, str) or not SHA1_RE.match(declared):
            raise InputError("manifest.json %s is not a SHA-1 hex string" % key)
        if declared.lower() != actual:
            raise InconsistentIndex(
                "%s does not match manifest.json %s" % (label, key)
            )


def validate_index_bytes(files, strict=False, limits=None):
    """校验内存中的三个索引文件；返回 manifest.json 的 sha256。"""
    limits = limits or Limits()
    if set(files) != set(INDEX_FILES):
        raise InputError("index must contain exactly: %s" % ", ".join(INDEX_FILES))
    for name in INDEX_FILES:
        data = files[name]
        if len(data) > limits.per_file[name]:
            raise InputError("%s exceeds size limit" % name)
    manifest_data = files["manifest.json"]
    try:
        manifest = json.loads(manifest_data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise InputError("manifest.json is not valid UTF-8 JSON: %s" % exc)
    if not isinstance(manifest, dict):
        raise InputError("manifest.json is not a JSON object")

    rows, dim, _ = _parse_npy_header_bytes(files["vectors.npy"])
    chunk_count = _scan_chunks_bytes(files["chunks.jsonl"], limits.max_line)[1]
    if chunk_count != rows:
        raise InconsistentIndex(
            "chunks.jsonl has %d rows but vectors.npy has %d" % (chunk_count, rows)
        )

    declared_chunks = manifest.get("chunks")
    if declared_chunks is None:
        if strict:
            raise InputError("manifest.json is missing chunks")
    elif isinstance(declared_chunks, bool) or not isinstance(declared_chunks, int):
        raise InputError("manifest.json chunks is not an integer")
    elif declared_chunks != rows:
        raise InconsistentIndex(
            "manifest.json chunks=%d but vectors.npy has %d" % (declared_chunks, rows)
        )

    declared_dim = _manifest_dim(manifest)
    if declared_dim is None:
        if strict:
            raise InputError("manifest.json is missing embed_dim/dim")
    elif declared_dim != dim:
        raise InconsistentIndex(
            "manifest.json dim=%d but vectors.npy has %d" % (declared_dim, dim)
        )

    vectors_sha1 = sha1_hex(files["vectors.npy"])
    chunks_sha1 = sha1_hex(files["chunks.jsonl"])
    _check_manifest_hashes(manifest, vectors_sha1, chunks_sha1, strict)
    return sha256_hex(manifest_data)


def validate_index_dir_handle(handle, strict=True, limits=None,
                              require_private=False, expected_uid=None):
    """校验目录中的三个固定文件；使用 dir_fd/O_NOFOLLOW 防止符号链接逃逸。"""
    limits = limits or Limits()
    entries = set(handle.listdir())
    if entries != set(INDEX_FILES):
        missing = sorted(set(INDEX_FILES) - entries)
        extra = sorted(entries - set(INDEX_FILES))
        raise InputError(
            "release directory must contain exactly the three index files"
            + (" (missing: %s)" % ", ".join(missing) if missing else "")
            + (" (extra: %s)" % ", ".join(extra) if extra else "")
        )

    total = 0
    for name in INDEX_FILES:
        st = handle.stat(name)
        if not stat.S_ISREG(st.st_mode):
            raise InputError("not a regular file: %s" % name)
        if st.st_size > limits.per_file[name]:
            raise InputError("%s exceeds size limit" % name)
        total += st.st_size
        if require_private and os.name == "posix":
            if stat.S_IMODE(st.st_mode) & 0o077:
                raise InputError("%s must not be group/world accessible" % name)
            if expected_uid is not None and st.st_uid != expected_uid:
                raise InputError("%s is not owned by the deploy account" % name)
    if total > limits.total:
        raise InputError("index files exceed total size limit")

    if require_private and os.name == "posix":
        dst = os.stat(handle.path) if handle.fd is None else os.fstat(handle.fd)
        if expected_uid is not None and dst.st_uid != expected_uid:
            raise InputError("release directory is not owned by the deploy account")
        if stat.S_IMODE(dst.st_mode) & 0o077:
            raise InputError("release directory must be 0700")

    manifest_data = _read_file_at(handle, "manifest.json", limits.manifest)
    try:
        manifest = json.loads(manifest_data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise InputError("manifest.json is not valid UTF-8 JSON: %s" % exc)
    if not isinstance(manifest, dict):
        raise InputError("manifest.json is not a JSON object")

    rows, dim, _ = _read_npy_header_at(handle, "vectors.npy", limits.vectors)
    vectors_sha1, _, _ = _hash_file_at(handle, "vectors.npy", limits.vectors)
    chunks_sha1, chunk_count = _scan_chunks_at(
        handle, "chunks.jsonl", limits.chunks, limits.max_line
    )
    if chunk_count != rows:
        raise InconsistentIndex(
            "chunks.jsonl has %d rows but vectors.npy has %d" % (chunk_count, rows)
        )

    declared_chunks = manifest.get("chunks")
    if declared_chunks is None:
        if strict:
            raise InputError("manifest.json is missing chunks")
    elif isinstance(declared_chunks, bool) or not isinstance(declared_chunks, int):
        raise InputError("manifest.json chunks is not an integer")
    elif declared_chunks != rows:
        raise InconsistentIndex(
            "manifest.json chunks=%d but vectors.npy has %d" % (declared_chunks, rows)
        )

    declared_dim = _manifest_dim(manifest)
    if declared_dim is None:
        if strict:
            raise InputError("manifest.json is missing embed_dim/dim")
    elif declared_dim != dim:
        raise InconsistentIndex(
            "manifest.json dim=%d but vectors.npy has %d" % (declared_dim, dim)
        )

    _check_manifest_hashes(manifest, vectors_sha1, chunks_sha1, strict)
    return sha256_hex(manifest_data)


def _normalize_tar_name(name):
    if not isinstance(name, str) or not name:
        raise InputError("tar member has an empty name")
    if "\x00" in name:
        raise InputError("tar member name contains NUL")
    if name.startswith("./"):
        name = name[2:]
    if name not in INDEX_FILES:
        raise InputError(
            "tar may only contain top-level vectors.npy, chunks.jsonl, manifest.json"
        )
    return name


def _copy_member(src, size, fd):
    remaining = size
    while remaining > 0:
        chunk = src.read(min(1024 * 1024, remaining))
        if not chunk:
            raise InputError("tar member is truncated")
        if len(chunk) > remaining:
            raise InputError("tar member is longer than declared")
        _write_all(fd, chunk)
        remaining -= len(chunk)
    if src.read(1):
        raise InputError("tar member is longer than declared")
    return size


def extract_upload_tar(stream, limits, sink):
    """严格读取未压缩 tar，把三个文件交给 sink(name, size, src)。

    只接受普通文件；拒绝目录、符号链接、硬链接、设备、FIFO、稀疏文件、绝对路径、
    `..`、额外文件、重复文件和超限尺寸。sink 必须返回写入字节数。
    """
    if limits is None:
        limits = Limits()
    reader = LimitedReader(stream, limits.stream)
    seen = set()
    total = 0
    try:
        tf = tarfile.open(fileobj=reader, mode="r|")
    except tarfile.TarError as exc:
        raise InputError("stdin is not a valid uncompressed tar: %s" % exc)
    try:
        for member in tf:
            name = _normalize_tar_name(member.name)
            if name in seen:
                raise InputError("duplicate tar member: %s" % name)
            if member.isdir() or not member.isreg():
                raise InputError("tar member must be a regular file: %s" % name)
            if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                raise InputError("links/devices are not allowed in tar: %s" % name)
            if getattr(member, "sparse", None):
                raise InputError("sparse files are not allowed: %s" % name)
            if member.linkname:
                raise InputError("tar member has a link target: %s" % name)
            if member.size < 0 or member.size > limits.per_file[name]:
                raise InputError("%s exceeds size limit" % name)
            total += member.size
            if total > limits.total:
                raise InputError("uploaded index exceeds total size limit")
            src = tf.extractfile(member)
            if src is None:
                raise InputError("tar member has no data: %s" % name)
            written = sink(name, member.size, src)
            if written != member.size:
                raise InputError("tar member size mismatch: %s" % name)
            seen.add(name)
    except tarfile.TarError as exc:
        raise InputError("invalid tar stream: %s" % exc)
    except (EOFError, OSError) as exc:
        if isinstance(exc, GatewayError):
            raise
        raise InputError("cannot read tar stream: %s" % exc)
    finally:
        tf.close()

    if seen != set(INDEX_FILES):
        missing = sorted(set(INDEX_FILES) - seen)
        raise InputError("tar is missing: %s" % ", ".join(missing))
    return seen


def _write_tar(out, files):
    with tarfile.open(fileobj=out, mode="w|", format=tarfile.USTAR_FORMAT) as tf:
        for name in INDEX_FILES:
            data = files[name]
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            info.uid = os.getuid() if hasattr(os, "getuid") else 0
            info.gid = os.getgid() if hasattr(os, "getgid") else 0
            info.uname = ""
            info.gname = ""
            tf.addfile(info, io.BytesIO(data))


def _resolve_live_index(index_dir):
    """首次发布前 index 是真实目录；之后 deploy helper 会把它换成 releases/ 下的 symlink。"""
    if not os.path.islink(index_dir):
        return index_dir
    real = os.path.realpath(index_dir)
    allowed = os.path.realpath(INDEX_RELEASES)
    try:
        inside = os.path.commonpath([real, allowed]) == allowed
    except ValueError:
        inside = False
    if not inside:
        raise InputError("live index symlink escapes %s" % INDEX_RELEASES)
    if not os.path.isdir(real):
        raise NotFoundError("live index symlink target does not exist")
    return real


def _read_live_index(index_dir, limits):
    index_dir = _resolve_live_index(index_dir)
    with DirHandle(index_dir) as handle:
        entries = set(handle.listdir())
        missing = [name for name in INDEX_FILES if name not in entries]
        if missing:
            raise NotFoundError("live index is missing: %s" % ", ".join(missing))
        files = {}
        for name in INDEX_FILES:
            st = handle.stat(name)
            if not stat.S_ISREG(st.st_mode):
                raise InputError("live index entry is not a regular file: %s" % name)
            if st.st_size > limits.per_file[name]:
                raise InputError("live %s exceeds size limit" % name)
            files[name] = _read_file_at(handle, name, limits.per_file[name])
        return files


def cmd_baseline(index_dir, stdout, limits=None, lock_path=None):
    limits = limits or Limits()
    last = None
    for attempt in range(5):
        try:
            lock_fd = acquire_shared_lock(lock_path) if lock_path else None
            try:
                files = _read_live_index(index_dir, limits)
                validate_index_bytes(files, strict=False, limits=limits)
            finally:
                if lock_fd is not None:
                    release_lock(lock_fd)
            # 锁只保护读取；三个文件已经是一致快照，tar 可以在锁外慢慢发。
            _write_tar(stdout, files)
            stdout.flush()
            return
        except (InconsistentIndex, NotFoundError) as exc:
            last = exc
            time.sleep(0.15)
    raise InputError(
        "live index is unavailable or changed while reading "
        "(another publish in progress): %s" % last
    )


def _ensure_incoming(incoming):
    try:
        st = os.lstat(incoming)
    except OSError as exc:
        if exc.errno in (errno.ENOENT, errno.ENOTDIR):
            raise NotFoundError("incoming directory does not exist: %s" % incoming)
        raise
    if not stat.S_ISDIR(st.st_mode):
        raise NotFoundError("incoming directory does not exist: %s" % incoming)
    if os.name == "posix":
        if st.st_uid != _euid():
            raise InputError("incoming directory must be owned by the deploy account")
        if stat.S_IMODE(st.st_mode) & 0o077:
            raise InputError("incoming directory must be 0700")


def _replace_release(incoming, temp_path, release):
    final_path = os.path.join(incoming, release)
    old_path = None
    if os.path.lexists(final_path):
        st = os.lstat(final_path)
        if not stat.S_ISDIR(st.st_mode):
            raise ConflictError("release path exists and is not a directory")
        if os.name == "posix" and _euid() is not None and st.st_uid != _euid():
            raise ConflictError("existing release is not owned by the deploy account")
        old_path = os.path.join(
            incoming, ".old-%s-%s" % (release, uuid.uuid4().hex)
        )
        os.rename(final_path, old_path)
    try:
        os.rename(temp_path, final_path)
    except Exception:
        if old_path is not None and not os.path.lexists(final_path):
            try:
                os.rename(old_path, final_path)
            except OSError:
                pass
        raise
    if old_path is not None:
        shutil.rmtree(old_path, ignore_errors=True)


def cmd_upload(release, incoming, stdin, stdout, limits=None):
    limits = limits or Limits()
    _ensure_incoming(incoming)
    temp_path = tempfile.mkdtemp(prefix=".incoming-%s-" % release, dir=incoming)
    os.chmod(temp_path, 0o700)
    tmp = DirHandle(temp_path)
    try:
        def sink(name, size, src):
            fd = tmp.open_write_exclusive(name)
            try:
                written = _copy_member(src, size, fd)
                if os.name == "posix":
                    os.fchmod(fd, 0o600)
                os.fsync(fd)
                return written
            finally:
                os.close(fd)

        extract_upload_tar(stdin, limits, sink)
        manifest_sha256 = validate_index_dir_handle(
            tmp, strict=True, limits=limits, require_private=True,
            expected_uid=_euid(),
        )
        tmp.close()
        _replace_release(incoming, temp_path, release)
        stdout.write(
            ("OK upload %s %s\n" % (release, manifest_sha256)).encode("ascii")
        )
        stdout.flush()
    except Exception:
        tmp.close()
        shutil.rmtree(temp_path, ignore_errors=True)
        raise


def _release_path(incoming, release):
    return os.path.join(incoming, release)


def _verify_release(incoming, release, limits):
    check_release(release)
    path = _release_path(incoming, release)
    try:
        st = os.lstat(path)
    except OSError as exc:
        if exc.errno in (errno.ENOENT, errno.ENOTDIR):
            raise NotFoundError("release was not uploaded: %s" % release)
        raise
    if not stat.S_ISDIR(st.st_mode):
        raise ConflictError("release is not a directory")
    if os.name == "posix":
        if st.st_uid != _euid():
            raise ConflictError("release is not owned by the deploy account")
        if stat.S_IMODE(st.st_mode) & 0o077:
            raise ConflictError("release directory must be 0700")
    with DirHandle(path) as handle:
        return validate_index_dir_handle(
            handle, strict=True, limits=limits, require_private=True,
            expected_uid=_euid(),
        )


def build_publish_argv(release, baseline_sha256, helper=DEPLOY_HELPER, sudo=None):
    check_release(release)
    if not SHA256_RE.match(baseline_sha256):
        raise UsageError("baseline must be 64 lowercase hex characters")
    if sudo is None:
        for candidate in ("/usr/bin/sudo", "/bin/sudo"):
            if os.path.exists(candidate):
                sudo = candidate
                break
    if sudo is None:
        raise NotFoundError("sudo not found")
    return [sudo, "-n", "--", helper, release, baseline_sha256]


def cmd_publish(release, baseline_sha256, incoming, limits=None):
    limits = limits or Limits()
    _verify_release(incoming, release, limits)
    if not os.path.isfile(DEPLOY_HELPER):
        raise NotFoundError("deploy helper is not installed: %s" % DEPLOY_HELPER)
    argv = build_publish_argv(release, baseline_sha256)
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C",
        "LC_ALL": "C",
        "HOME": "/var/lib/qutwiki-rag-deploy",
    }
    os.execve(argv[0], argv, env)


def main():
    try:
        action = parse_command(os.environ.get("SSH_ORIGINAL_COMMAND"))
        # 断线或停滞的客户端不能无限占用传输进程；发布交给 helper 自身管理。
        if action[0] in ("baseline", "upload"):
            import signal

            def transfer_timeout(signum, frame):
                raise InputError("index transfer exceeded 15 minutes")

            signal.signal(signal.SIGALRM, transfer_timeout)
            signal.alarm(900)
        if action[0] == "baseline":
            cmd_baseline(INDEX_DIR, sys.stdout.buffer, lock_path=LOCK_PATH)
        elif action[0] == "upload":
            cmd_upload(action[1], INCOMING_DIR, sys.stdin.buffer, sys.stdout.buffer)
        elif action[0] == "publish":
            cmd_publish(action[1], action[2], INCOMING_DIR)
        else:  # pragma: no cover - parse_command 已穷尽
            raise UsageError("unknown action")
        return 0
    except GatewayError as exc:
        try:
            sys.stderr.write("ERROR: %s\n" % exc)
            sys.stderr.flush()
        except Exception:
            pass
        return exc.code
    except BrokenPipeError:
        return 0
    except Exception as exc:
        try:
            sys.stderr.write("ERROR: internal failure: %s\n" % exc)
            sys.stderr.flush()
        except Exception:
            pass
        return 6


if __name__ == "__main__":
    sys.exit(main())
