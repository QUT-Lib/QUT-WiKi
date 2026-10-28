#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RAG 向量化后端与增量缓存（离线可测、不读取任何密钥文件）

职责：
1. 统一的 embedding 文本规范化（`embed_text` 优先，缺失时退回 `text`，只做 strip）
2. 稳定的缓存 key：模型 / 维度 / 预处理版本 / 文本内容
3. 读取旧索引（vectors.npy + chunks.jsonl + manifest.json）并校验
4. 智谱在线 embedding（密钥只从环境变量读取，绝不打印）
5. 纯离线 FakeEmbedder（仅供测试，不产生网络请求）

缓存 key 与顺序无关：索引里块的位置可以变、元数据可以更新，
只要参与编码的文本没变，就能复用旧向量。
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# 预处理版本：改动 embed_text 的规范化方式时必须升级，否则新旧向量会混用
PREPROCESS_VERSION = "strip-v1"
CACHE_KEY_SCHEMA = 1

ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4"
ZHIPU_DIMS = {"embedding-3": (256, 512, 1024, 2048), "embedding-2": (1024,)}
ZHIPU_MAX_SEQ = {"embedding-3": 3072, "embedding-2": 512}

# 旧索引（D:/code/RAG/scripts/build_index.py 生成）没有 preprocess_version 字段，
# 但它的规范就是 `(embed_text or text).strip()`，与 strip-v1 等价。
LEGACY_PREPROCESS_VERSION = "strip-v1"

NORM_TOL = 1e-4
MAX_VALIDATION_SAMPLES = 8


class EmbeddingError(RuntimeError):
    """向量化配置 / 调用错误"""


class IndexValidationError(RuntimeError):
    """索引文件损坏或不符合约束"""


# --------------------------------------------------------------------------
# 文本与 key
# --------------------------------------------------------------------------
def embed_text_for(chunk: dict) -> str:
    """实际参与编码的文本：embed_text 优先，空则 fallback 到 text，两者都 strip。"""
    for field_name in ("embed_text", "text"):
        value = chunk.get(field_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def cache_key(text: str, provider: str, model: str, dim: int,
              preprocess_version: str = PREPROCESS_VERSION) -> str:
    """缓存 key 只由“向量语义”决定，不含块 id / 顺序 / 元数据。

    升级 CACHE_KEY_SCHEMA 或 PREPROCESS_VERSION 会让旧 key 全部失效，
    这是有意的：确保不会把不同预处理/模型的向量错误复用。
    """
    payload = "\n".join([
        f"schema={CACHE_KEY_SCHEMA}",
        f"provider={provider.strip().lower()}",
        f"model={model.strip()}",
        f"dim={int(dim)}",
        f"preprocess={preprocess_version}",
        "text=" + (text or "").strip(),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IndexIdentity:
    provider: str
    model: str
    dim: int
    preprocess_version: str = PREPROCESS_VERSION

    @property
    def label(self) -> str:
        return f"{self.provider}/{self.model}@{self.dim}d"

    def as_dict(self) -> dict:
        return {
            "embed_provider": self.provider,
            "embed_model": self.model,
            "embed_dim": int(self.dim),
            "preprocess_version": self.preprocess_version,
        }


# --------------------------------------------------------------------------
# 矩阵校验
# --------------------------------------------------------------------------
def normalize_matrix(vectors, *, expected_rows: int | None = None,
                     expected_dim: int | None = None):
    """L2 归一化，返回 (float32 矩阵, 被重新归一化的行数, 零向量行号)"""
    arr = np.asarray(vectors, dtype="float32")
    if arr.ndim != 2:
        raise IndexValidationError(f"向量必须是二维矩阵，实际 shape={arr.shape}")
    if expected_rows is not None and arr.shape[0] != expected_rows:
        raise IndexValidationError(f"向量行数 {arr.shape[0]} != 期望 {expected_rows}")
    if expected_dim is not None and arr.shape[1] != expected_dim:
        raise IndexValidationError(f"向量维度 {arr.shape[1]} != 期望 {expected_dim}")
    if arr.size == 0:
        return arr, 0, []

    norms = np.linalg.norm(arr, axis=1)
    zero_rows = np.flatnonzero(norms <= 0).tolist()
    if zero_rows:
        raise IndexValidationError(
            f"存在零向量（行 {_sample(zero_rows)}），无法归一化"
        )
    changed = int(np.count_nonzero(np.abs(norms - 1.0) > NORM_TOL))
    out = arr / norms[:, None]
    return out.astype("float32", copy=False), changed, []


def validate_matrix(vectors, *, expected_rows: int, expected_dim: int,
                    require_normalized: bool = True) -> dict:
    """有限值 / shape / 归一化校验，返回统计信息；不合格直接抛错。"""
    arr = np.asarray(vectors)
    if arr.dtype != np.float32:
        raise IndexValidationError(f"向量 dtype 必须是 float32，实际 {arr.dtype}")
    if arr.ndim != 2:
        raise IndexValidationError(f"向量必须是二维矩阵，实际 shape={arr.shape}")
    if arr.shape != (int(expected_rows), int(expected_dim)):
        raise IndexValidationError(
            f"向量 shape={arr.shape} 与期望 ({expected_rows}, {expected_dim}) 不一致"
        )
    finite = np.isfinite(arr)
    if not finite.all():
        bad_rows = np.flatnonzero(~finite.all(axis=1)).tolist()
        raise IndexValidationError(f"向量包含 NaN/Inf（行 {_sample(bad_rows)}）")

    norms = np.linalg.norm(arr, axis=1)
    if norms.size == 0:
        raise IndexValidationError("向量为空")
    max_err = float(np.max(np.abs(norms - 1.0)))
    if require_normalized and max_err > NORM_TOL:
        bad_rows = np.flatnonzero(np.abs(norms - 1.0) > NORM_TOL).tolist()
        raise IndexValidationError(
            f"向量未归一化（{len(bad_rows)} 行偏差 > {NORM_TOL}，最大 {max_err:.6f}，"
            f"行 {_sample(bad_rows)}）"
        )
    return {
        "rows": int(arr.shape[0]),
        "dim": int(arr.shape[1]),
        "dtype": str(arr.dtype),
        "finite": True,
        "normalized": bool(max_err <= NORM_TOL),
        "norm_min": round(float(norms.min()), 6),
        "norm_max": round(float(norms.max()), 6),
        "max_norm_error": round(max_err, 8),
    }


def _sample(rows: list[int]) -> str:
    shown = ", ".join(str(r) for r in rows[:MAX_VALIDATION_SAMPLES])
    return shown + (" …" if len(rows) > MAX_VALIDATION_SAMPLES else "")


# --------------------------------------------------------------------------
# 旧索引读取 / 向量缓存
# --------------------------------------------------------------------------
@dataclass
class BaseIndexLookup:
    manifest: dict
    identity: IndexIdentity | None
    mismatches: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    vectors: dict[str, np.ndarray] = field(default_factory=dict)
    base_chunks: int = 0
    base_vector_rows: int = 0
    cache_file_rows: int = 0
    renormalized_rows: int = 0
    duplicate_keys: int = 0
    conflicting_keys: int = 0

    @property
    def usable(self) -> bool:
        return not self.mismatches


def identity_from_manifest(manifest: dict, vectors_shape: tuple[int, int] | None = None) -> IndexIdentity:
    provider = str(manifest.get("embed_provider") or "").strip().lower()
    model = str(manifest.get("embed_model") or "").strip()
    if not provider:
        raw_model = str(manifest.get("model") or "")
        provider = "zhipu" if raw_model.lower().startswith("zhipu/") else "local"
        model = model or raw_model.split("/")[-1]
    model = model or "unknown"
    dim = manifest.get("embed_dim", manifest.get("dim"))
    if dim is None and vectors_shape is not None:
        dim = vectors_shape[1]
    preprocess = manifest.get("preprocess_version") or LEGACY_PREPROCESS_VERSION
    return IndexIdentity(provider=provider, model=model, dim=int(dim or 0),
                         preprocess_version=str(preprocess))


def _read_jsonl(path: Path) -> list[dict]:
    try:
        with path.open(encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except (OSError, ValueError) as e:
        raise IndexValidationError(f"读取 {path} 失败：{e}") from e


def load_base_vectors(base_index: str | Path, expected: IndexIdentity, *,
                      allow_legacy_preprocess: bool = True) -> BaseIndexLookup:
    """读取旧索引并建立 key -> 向量 映射。

    模型 / 维度 / 预处理版本不一致时**不会复用**：返回 mismatches，
    由调用方决定报错还是显式全量重建。
    """
    base = Path(base_index)
    manifest_path = base / "manifest.json"
    chunks_path = base / "chunks.jsonl"
    vectors_path = base / "vectors.npy"
    missing = [p.name for p in (manifest_path, chunks_path, vectors_path) if not p.exists()]
    if missing:
        raise IndexValidationError(f"旧索引不完整：{base} 缺少 {', '.join(missing)}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise IndexValidationError(f"旧索引 manifest 无法解析：{e}") from e
    if not isinstance(manifest, dict):
        raise IndexValidationError("旧索引 manifest 不是 JSON 对象")

    declared_preprocess = manifest.get("preprocess_version")
    identity = identity_from_manifest(manifest)
    lookup = BaseIndexLookup(manifest=manifest, identity=identity)

    def mismatch(field_name: str, old, new):
        lookup.mismatches.append(f"{field_name} 不一致：旧索引 {old!r}，本次 {new!r}")

    if identity.provider != expected.provider:
        mismatch("embed_provider", identity.provider, expected.provider)
    if identity.model != expected.model:
        mismatch("embed_model", identity.model, expected.model)
    if int(identity.dim) != int(expected.dim):
        mismatch("embed_dim", identity.dim, expected.dim)
    if not declared_preprocess and not allow_legacy_preprocess:
        mismatch("preprocess_version", None, expected.preprocess_version)
    elif identity.preprocess_version != expected.preprocess_version:
        mismatch("preprocess_version", identity.preprocess_version, expected.preprocess_version)
    if lookup.mismatches:
        return lookup

    chunks = _read_jsonl(chunks_path)
    if not chunks:
        raise IndexValidationError(f"旧索引 {chunks_path} 为空")
    try:
        vectors = np.load(vectors_path, allow_pickle=False)
    except (OSError, ValueError) as e:
        raise IndexValidationError(f"旧索引 vectors.npy 无法读取：{e}") from e
    if vectors.ndim != 2:
        raise IndexValidationError(f"旧索引 vectors.npy 不是二维矩阵：shape={vectors.shape}")
    if vectors.shape[0] != len(chunks):
        raise IndexValidationError(
            f"旧索引向量与块数不一致：{vectors.shape[0]} vs {len(chunks)}"
        )
    if vectors.shape[1] != expected.dim:
        raise IndexValidationError(
            f"旧索引向量维度 {vectors.shape[1]} != 期望 {expected.dim}"
        )
    if not np.isfinite(vectors).all():
        raise IndexValidationError("旧索引 vectors.npy 含 NaN/Inf")
    vectors, renormalized, _ = normalize_matrix(
        vectors, expected_rows=len(chunks), expected_dim=expected.dim
    )
    lookup.renormalized_rows = renormalized
    lookup.base_chunks = len(chunks)
    lookup.base_vector_rows = int(vectors.shape[0])

    for i, chunk in enumerate(chunks):
        text = embed_text_for(chunk)
        if not text:
            lookup.warnings.append(f"旧索引块 {chunk.get('id', i)} 没有可编码文本，已跳过")
            continue
        key = cache_key(text, expected.provider, expected.model, expected.dim,
                        expected.preprocess_version)
        prev = lookup.vectors.get(key)
        if prev is not None:
            lookup.duplicate_keys += 1
            if not np.allclose(prev, vectors[i], atol=1e-6):
                lookup.conflicting_keys += 1
            continue
        lookup.vectors[key] = vectors[i]

    cache_path = base / "cache" / "embedding-cache.npz"
    if cache_path.exists():
        _merge_cache_file(cache_path, expected, lookup)
    return lookup


def _merge_cache_file(path: Path, expected: IndexIdentity, lookup: BaseIndexLookup) -> None:
    """合并本工具写出的持久化向量缓存（可包含已从索引删除的块）。"""
    try:
        with np.load(path, allow_pickle=False) as data:
            keys = [str(k) for k in data["keys"].tolist()]
            vectors = np.asarray(data["vectors"])
            provider = str(data["provider"]) if "provider" in data else ""
            model = str(data["model"]) if "model" in data else ""
            dim = int(data["dim"]) if "dim" in data else 0
            preprocess = str(data["preprocess_version"]) if "preprocess_version" in data else ""
    except (OSError, ValueError, KeyError) as e:
        lookup.warnings.append(f"忽略损坏的向量缓存 {path}：{e}")
        return
    if (provider, model, dim, preprocess) != (
            expected.provider, expected.model, expected.dim, expected.preprocess_version):
        lookup.warnings.append(
            f"忽略向量缓存 {path}：身份不一致（{provider}/{model}@{dim}，{preprocess}）"
        )
        return
    if vectors.ndim != 2 or vectors.shape[0] != len(keys) or vectors.shape[1] != expected.dim:
        lookup.warnings.append(f"忽略向量缓存 {path}：shape={vectors.shape} 与 keys={len(keys)} 不符")
        return
    if not np.isfinite(vectors).all():
        lookup.warnings.append(f"忽略向量缓存 {path}：含 NaN/Inf")
        return
    vectors, _, _ = normalize_matrix(vectors, expected_rows=len(keys), expected_dim=expected.dim)
    added = 0
    for key, vector in zip(keys, vectors):
        if key and key not in lookup.vectors:
            lookup.vectors[key] = vector
            added += 1
    lookup.cache_file_rows = added


def write_vector_cache(path: str | Path, vectors: dict[str, np.ndarray],
                       identity: IndexIdentity) -> int:
    """按 key 排序写 npz，保证同输入产生字节稳定的缓存文件。"""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted(vectors)
    if not keys:
        return 0
    matrix = np.stack([np.asarray(vectors[k], dtype="float32") for k in keys]).astype("float32")
    if matrix.shape[1] != identity.dim:
        raise IndexValidationError(
            f"缓存向量维度 {matrix.shape[1]} != {identity.dim}"
        )
    if not np.isfinite(matrix).all():
        raise IndexValidationError("缓存向量含 NaN/Inf，拒绝写出")
    np.savez_compressed(
        out,
        keys=np.asarray(keys, dtype="<U64"),
        vectors=matrix,
        provider=np.asarray(identity.provider),
        model=np.asarray(identity.model),
        dim=np.asarray(identity.dim, dtype="int32"),
        preprocess_version=np.asarray(identity.preprocess_version),
    )
    return len(keys)


# --------------------------------------------------------------------------
# 智谱在线 embedding
# --------------------------------------------------------------------------
def env_api_key() -> str:
    """只读环境变量；不解析 .env 文件，避免读取/泄露仓库里的密钥文件。"""
    for name in ("ZHIPU_API_KEY", "ZHIPUAI_API_KEY", "BIGMODEL_API_KEY"):
        value = os.environ.get(name)
        if value:
            return value.strip()
    return ""


class ZhipuEmbedder:
    provider = "zhipu"
    device = "zhipu-api"

    def __init__(self, model: str = "embedding-3", dimensions: int = 1024,
                 api_key: str | None = None, base_url: str | None = None,
                 timeout: int = 60, retries: int = 3):
        if model not in ZHIPU_DIMS:
            raise EmbeddingError(f"不支持的智谱 embedding 模型：{model}（可选 {', '.join(ZHIPU_DIMS)}）")
        allowed = ZHIPU_DIMS[model]
        if int(dimensions) not in allowed:
            raise EmbeddingError(f"{model} 只支持维度 {allowed}，收到 {dimensions}")
        self.model = model
        self.dimensions = int(dimensions)
        self.api_key = (api_key or env_api_key()).strip()
        self.base_url = (base_url or os.environ.get("ZHIPU_BASE_URL") or ZHIPU_BASE).rstrip("/")
        self.timeout = int(timeout)
        self.retries = int(retries)
        self.requests_made = 0
        self.texts_encoded = 0
        if not self.api_key:
            raise EmbeddingError(
                "缺少智谱 API Key：请设置环境变量 ZHIPU_API_KEY（本工具不读取 .env 文件）"
            )

    @property
    def max_seq_length(self) -> int:
        return ZHIPU_MAX_SEQ.get(self.model, 3072)

    @property
    def identity(self) -> IndexIdentity:
        return IndexIdentity(self.provider, self.model, self.dimensions)

    def __repr__(self) -> str:  # 绝不输出密钥
        return f"ZhipuEmbedder(model={self.model!r}, dim={self.dimensions})"

    def _request(self, texts: list[str]) -> list[list[float]]:
        try:
            import requests
        except ImportError as e:  # pragma: no cover - 依赖缺失时
            raise EmbeddingError("调用智谱 embedding 需要 requests：py -3 -m pip install requests") from e

        payload: dict = {"model": self.model, "input": texts}
        if self.dimensions:
            payload["dimensions"] = self.dimensions
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_err: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                r = requests.post(f"{self.base_url}/embeddings", json=payload,
                                  headers=headers, timeout=self.timeout)
            except requests.exceptions.RequestException as e:
                last_err = e
                if attempt >= self.retries:
                    raise EmbeddingError(f"连接智谱 embedding 失败：{e}") from e
                time.sleep(min(2 ** attempt, 8))
                continue
            if r.status_code == 200:
                try:
                    body = r.json() or {}
                except ValueError as e:
                    raise EmbeddingError(f"智谱 embedding 返回非 JSON：{r.text[:300]}") from e
                data = body.get("data")
                if not isinstance(data, list):
                    raise EmbeddingError("智谱 embedding 返回缺少 data 数组")
                if len(data) != len(texts):
                    raise EmbeddingError(
                        f"智谱 embedding 返回 {len(data)} 条，期望 {len(texts)} 条"
                    )
                # 官方返回可以乱序，但 index 必须恰好覆盖 0..n-1；否则无法可靠对齐输入
                indices: list[int] = []
                for item in data:
                    if not isinstance(item, dict):
                        raise EmbeddingError("智谱 embedding 的 data 项不是对象")
                    index = item.get("index")
                    if isinstance(index, bool) or not isinstance(index, int):
                        raise EmbeddingError(
                            f"智谱 embedding 返回的 index 非法（应为整数）：{index!r}"
                        )
                    indices.append(index)
                expected_indices = list(range(len(texts)))
                if sorted(indices) != expected_indices:
                    raise EmbeddingError(
                        f"智谱 embedding 返回的 index 不是 0..{len(texts) - 1} 的唯一排列："
                        f"{indices}；拒绝按错误顺序映射向量"
                    )
                data = sorted(data, key=lambda x: x["index"])
                rows: list[list[float]] = []
                for item in data:
                    row = item.get("embedding")
                    if not isinstance(row, list) or len(row) != self.dimensions:
                        got = len(row) if isinstance(row, list) else type(row).__name__
                        raise EmbeddingError(
                            f"智谱返回向量维度/类型非法：{got}，期望 {self.dimensions} 维数组"
                        )
                    rows.append(row)
                return rows
            if r.status_code in (429, 500, 502, 503, 504) and attempt < self.retries:
                time.sleep(min(2 ** attempt, 8))
                continue
            # 不要回显请求头；响应体按错误信息截断
            raise EmbeddingError(f"智谱 embedding 失败 HTTP {r.status_code}：{r.text[:300]}")
        raise EmbeddingError(f"智谱 embedding 失败：{last_err}")

    def encode(self, texts, batch_size: int = 32, normalize: bool = True,
               progress=None) -> np.ndarray:
        texts = [t if isinstance(t, str) else str(t) for t in texts]
        if not texts:
            return np.zeros((0, self.dimensions), dtype="float32")
        size = max(1, min(int(batch_size or 32), 64))  # 官方上限 64 条/请求
        rows: list[list[float]] = []
        for i in range(0, len(texts), size):
            rows.extend(self._request(texts[i:i + size]))
            self.requests_made += 1
            if progress:
                progress(min(i + size, len(texts)), len(texts))
        try:
            arr = np.asarray(rows, dtype="float32")
        except (TypeError, ValueError) as e:
            raise EmbeddingError(f"智谱向量无法转换为 float32 矩阵：{e}") from e
        if arr.shape != (len(texts), self.dimensions):
            raise EmbeddingError(
                f"智谱向量 shape={arr.shape} 与期望 ({len(texts)}, {self.dimensions}) 不一致"
            )
        if normalize:
            arr, _, _ = normalize_matrix(arr)
        self.texts_encoded += len(texts)
        return arr


class FakeEmbedder:
    """确定性离线向量（按文本 sha256 播种），只用于测试/演练，绝不联网。"""

    provider = "fake"
    device = "offline"

    def __init__(self, model: str = "fake-embedding", dimensions: int = 1024):
        if int(dimensions) <= 0:
            raise EmbeddingError("dimensions 必须为正整数")
        self.model = model or "fake-embedding"
        self.dimensions = int(dimensions)
        self.requests_made = 0
        self.texts_encoded = 0
        self.calls: list[list[str]] = []

    @property
    def max_seq_length(self) -> int:
        return 8192

    @property
    def identity(self) -> IndexIdentity:
        return IndexIdentity(self.provider, self.model, self.dimensions)

    def encode(self, texts, batch_size: int = 32, normalize: bool = True,
               progress=None) -> np.ndarray:
        texts = [t if isinstance(t, str) else str(t) for t in texts]
        self.calls.append(list(texts))
        self.requests_made += 1
        self.texts_encoded += len(texts)
        if not texts:
            return np.zeros((0, self.dimensions), dtype="float32")
        rows = np.empty((len(texts), self.dimensions), dtype="float32")
        for i, text in enumerate(texts):
            digest = hashlib.sha256(f"{self.model}\x00{text}".encode("utf-8")).digest()
            seed = int.from_bytes(digest[:8], "big")
            rng = np.random.default_rng(seed)
            rows[i] = rng.standard_normal(self.dimensions).astype("float32")
        if normalize:
            rows, _, _ = normalize_matrix(rows)
        return rows


def create_embedder(provider: str, model: str, dim: int, *,
                    timeout: int = 60, retries: int = 3):
    provider = (provider or "zhipu").strip().lower()
    if provider == "zhipu":
        return ZhipuEmbedder(model=model, dimensions=dim, timeout=timeout, retries=retries)
    if provider == "fake":
        return FakeEmbedder(model=model, dimensions=dim)
    raise EmbeddingError(f"不支持的 embedding provider：{provider}（可选 zhipu / fake）")


def provider_info(provider: str, model: str, dim: int) -> dict:
    """不实例化模型也能写 manifest 的静态信息。"""
    provider = (provider or "").strip().lower()
    if provider == "zhipu":
        return {
            "max_seq_length": ZHIPU_MAX_SEQ.get(model, 3072),
            "device": "zhipu-api",
            "fp16": False,
        }
    if provider == "fake":
        return {"max_seq_length": 8192, "device": "offline", "fp16": False}
    return {"max_seq_length": None, "device": "unknown", "fp16": False}
