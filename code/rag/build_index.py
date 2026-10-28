#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wiki -> 增量 RAG 索引（CI 可用，不部署、不提交）

流程：
  1. 从 --wiki-root 重新抽取语料（只读源仓库）
  2. 按实际 embed_text（fallback text，strip）计算缓存 key
  3. 从 --base-index 复用模型/维度/预处理版本一致的旧向量
  4. 只为缺失的文本调用 embedding（智谱）；没有缺失时完全离线
  5. 元数据始终用本次抽取结果，新增/删除/改标题都能正确反映
  6. 有限值 / shape / 归一化校验通过后，写入独立的新目录

用法：
  py -3 code/rag/build_index.py \
      --wiki-root . \
      --base-index D:/code/RAG/index-zhipu \
      --output D:/Temp/index-next \
      --source-commit "$(git rev-parse HEAD)"

  # 没有旧索引（或想强制全量）：省略 --base-index
  py -3 code/rag/build_index.py --wiki-root . --output D:/Temp/index-full

  # 离线自测（确定性向量，不调用付费 API）
  py -3 code/rag/build_index.py --wiki-root . --output ... --embed-provider fake

依赖：numpy（必需）；openpyxl（表格块）；requests（仅调用智谱时）；
      pymupdf（PDF，可选）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

try:  # 支持包内导入（import rag.build_index）
    from . import embedding as emb
    from . import extract as extract_mod
except ImportError:  # pragma: no cover - 直接运行 python code/rag/build_index.py 时走这里
    import embedding as emb  # type: ignore
    import extract as extract_mod  # type: ignore

RAG_DIR = Path(__file__).resolve().parent
REPO_ROOT = RAG_DIR.parent.parent
GENERATOR = "qutwiki-rag-incremental/1.0"
DEFAULT_PROFILE = "qut"
OWNED_FILES = ("vectors.npy", "chunks.jsonl", "manifest.json")
OWNED_DIRS = ("corpus", "cache")
# 旧索引里的运行时配置：增量构建时保留，避免部署后行为突变
PRESERVED_MANIFEST_KEYS = ("ui", "rerank", "recommended_mode", "fusion_strategy")


class BuildError(RuntimeError):
    """配置 / 输入错误（退出码 2）"""


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for buf in iter(lambda: f.read(1 << 20), b""):
            h.update(buf)
    return h.hexdigest()


def git_commit(repo: Path) -> str | None:
    import subprocess
    try:
        out = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def read_chunks(path: Path) -> list[dict]:
    chunks: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except ValueError as e:
                raise emb.IndexValidationError(f"{path}:{lineno} 不是合法 JSON：{e}") from e
            if not isinstance(obj, dict):
                raise emb.IndexValidationError(f"{path}:{lineno} 不是 JSON 对象")
            chunks.append(obj)
    if not chunks:
        raise emb.IndexValidationError(f"语料为空：{path}")
    return chunks


def validate_chunks(chunks: list[dict]) -> None:
    ids = [str(c.get("id") or "") for c in chunks]
    if any(not cid for cid in ids):
        raise emb.IndexValidationError("存在空 chunk id")
    if len(set(ids)) != len(ids):
        dup = sorted({cid for cid in ids if ids.count(cid) > 1})
        raise emb.IndexValidationError(f"存在重复 chunk id：{dup[:8]}")
    empty = [cid for cid, c in zip(ids, chunks) if not emb.embed_text_for(c)]
    if empty:
        raise emb.IndexValidationError(f"{len(empty)} 个块没有可编码文本：{empty[:8]}")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _clean_owned_output(output: Path) -> None:
    """只清理本工具产出的文件，不动输出目录里的其它内容。"""
    for name in OWNED_FILES:
        p = output / name
        if p.is_file():
            p.unlink()
    for name in OWNED_DIRS:
        p = output / name
        if p.is_dir():
            shutil.rmtree(p)


def _output_ready(output: Path, overwrite: bool) -> None:
    if not output.exists():
        return
    if not output.is_dir():
        raise BuildError(f"--output 已存在且不是目录：{output}")
    existing = [n for n in OWNED_FILES if (output / n).exists()]
    existing += [n + "/" for n in OWNED_DIRS if (output / n).exists()]
    if existing and not overwrite:
        raise BuildError(
            f"输出目录已有本工具生成的内容 {existing}：{output}\n"
            "    增量构建要求写入独立新目录；确认覆盖请加 --overwrite"
        )


def _parse_identity(args) -> emb.IndexIdentity:
    provider = (args.embed_provider or "zhipu").strip().lower()
    model = (args.embed_model or "embedding-3").strip()
    dim = int(args.embed_dim)
    if provider == "zhipu":
        if model not in emb.ZHIPU_DIMS:
            raise BuildError(f"不支持的智谱模型：{model}（可选 {', '.join(emb.ZHIPU_DIMS)}）")
        if dim not in emb.ZHIPU_DIMS[model]:
            raise BuildError(f"{model} 只支持维度 {emb.ZHIPU_DIMS[model]}，收到 {dim}")
        if model == "embedding-2":
            raise BuildError("embedding-2 单条上限 512 tokens，会截断当前语料；请用 embedding-3")
    elif provider == "fake":
        if dim <= 0:
            raise BuildError("--embed-dim 必须为正整数")
    elif provider == "local":
        raise BuildError("code/rag 的 CI 构建只支持 zhipu / fake；本地 bge-m3 请用 D:/code/RAG 的 build_index.py")
    else:
        raise BuildError(f"不支持的 --embed-provider：{provider}（可选 zhipu / fake）")
    return emb.IndexIdentity(provider=provider, model=model, dim=dim,
                             preprocess_version=emb.PREPROCESS_VERSION)


def _resolve_commit(args, wiki_root: Path) -> tuple[str | None, str | None]:
    if args.source_commit:
        return args.source_commit.strip(), "cli"
    commit = git_commit(wiki_root)
    return commit, ("git" if commit else None)


def build(args) -> dict:
    wiki_root = Path(args.wiki_root).resolve()
    output = Path(args.output).resolve()
    base_index = Path(args.base_index).resolve() if args.base_index else None
    if not (wiki_root / "docs" / "index.md").exists() and not (wiki_root / "index.md").exists():
        raise BuildError(f"--wiki-root 不像 QUTWiKi 仓库：{wiki_root}")
    if base_index is not None:
        if not base_index.is_dir():
            raise BuildError(f"--base-index 不存在或不是目录：{base_index}")
        if (base_index == output or base_index in output.parents
                or output in base_index.parents):
            raise BuildError(
                "--output 与 --base-index 不能相同或互相嵌套；增量构建必须写入独立新目录"
            )
    if output == wiki_root:
        raise BuildError("--output 不能是 wiki 仓库根目录")
    try:
        rel_out = output.relative_to(wiki_root)
    except ValueError:
        pass
    else:
        if rel_out.parts and rel_out.parts[0] in ("docs", "code", ".github"):
            raise BuildError(f"--output 不能写进源仓库的 {rel_out.parts[0]}/ 目录：{output}")
    # openpyxl 是生产抽取的必需依赖：缺失会导致表格块整批消失，必须硬失败。
    # PDF（pymupdf）是可选能力：未安装或扫描件无文本层只告警，不影响构建。
    try:
        extract_mod.require_openpyxl()
    except extract_mod.ExtractionError as e:
        raise BuildError(str(e)) from e

    _output_ready(output, args.overwrite)

    identity = _parse_identity(args)
    source_commit, commit_source = _resolve_commit(args, wiki_root)

    # ---- 1. 旧索引（先做身份检查，不一致时不加载大文件）----
    base = None
    if base_index is not None:
        base = emb.load_base_vectors(base_index, identity)
        if base.mismatches:
            detail = "；".join(base.mismatches)
            if not args.allow_reembed_on_mismatch:
                raise BuildError(
                    f"旧索引与本次向量配置不一致，拒绝复用：{detail}\n"
                    "    换用匹配的 --base-index，或省略 --base-index 做全量构建；\n"
                    "    确实要重编码请显式加 --allow-reembed-on-mismatch（会产生 API 费用）"
                )
            print(f"[!] 旧索引身份不一致，已按 --allow-reembed-on-mismatch 全量重编码：{detail}",
                  file=sys.stderr)
        for warning in base.warnings:
            print(f"[!] {warning}", file=sys.stderr)

    # ---- 2. 重新抽取 ----
    with tempfile.TemporaryDirectory(prefix="qutwiki-rag-") as tmp:
        corpus_dir = Path(tmp) / "corpus"
        extraction = extract_mod.extract_all(
            wiki_root, corpus_dir,
            max_chars=args.max_chars, min_chars=args.min_chars,
            overlap=args.overlap, table_chars=args.table_chars,
            source_commit=source_commit, include_pdf=not args.no_pdf,
            verbose=False,
        )
        chunks_path = corpus_dir / "chunks.jsonl"
        chunks = read_chunks(chunks_path)
        validate_chunks(chunks)
        stats = extraction.get("stats") or {}
        if stats.get("chunks") != len(chunks):
            raise emb.IndexValidationError(
                f"抽取统计块数 {stats.get('chunks')} 与 chunks.jsonl {len(chunks)} 不一致"
            )

        texts = [emb.embed_text_for(c) for c in chunks]
        keys = [emb.cache_key(t, identity.provider, identity.model, identity.dim,
                              identity.preprocess_version) for t in texts]

        # 同一文本只编码一次（表格/导航等重复块很常见）
        unique_texts: "OrderedDict[str, str]" = OrderedDict()
        for key, text in zip(keys, texts):
            unique_texts.setdefault(key, text)
        duplicate_keys = len(keys) - len(unique_texts)

        available = base.vectors if (base is not None and base.usable) else {}
        lookup: dict = {}
        missing_keys: list[str] = []
        missing_texts: list[str] = []
        for key, text in unique_texts.items():
            if key in available:
                lookup[key] = available[key]
            else:
                missing_keys.append(key)
                missing_texts.append(text)

        # 统计按“新索引的行”计，唯一文本数单独记录（重复块只编码一次）
        reused_rows = sum(1 for key in keys if key in available)
        embedded_rows = len(keys) - reused_rows

        # ---- 3. 仅对缺失文本调用 embedding ----
        api_seconds = 0.0
        embedder = None
        if missing_texts:
            t0 = time.time()
            try:
                embedder = emb.create_embedder(
                    identity.provider, identity.model, identity.dim,
                    timeout=args.timeout, retries=args.retries,
                )
                new_vectors = embedder.encode(missing_texts, batch_size=args.batch_size)
            except emb.EmbeddingError as e:
                raise BuildError(
                    f"需要为新文本编码 {len(missing_texts)} 个唯一文本（"
                    f"复用 {len(unique_texts) - len(missing_texts)} 个），但 {e}"
                ) from e
            api_seconds = time.time() - t0
            if getattr(new_vectors, "shape", None) != (len(missing_texts), identity.dim):
                raise emb.IndexValidationError(
                    f"新向量 shape={getattr(new_vectors, 'shape', None)} "
                    f"与期望 ({len(missing_texts)}, {identity.dim}) 不一致"
                )
            new_vectors, _, _ = emb.normalize_matrix(new_vectors)
            for key, vector in zip(missing_keys, new_vectors):
                lookup[key] = vector

        # ---- 4. 按新语料顺序组装（元数据/顺序全部取本次抽取）----
        import numpy as np

        matrix = np.empty((len(chunks), identity.dim), dtype="float32")
        for i, key in enumerate(keys):
            vector = lookup.get(key)
            if vector is None:  # 理论上不会发生，防御性检查
                raise emb.IndexValidationError(f"第 {i} 块缺少向量（key={key[:12]}…）")
            matrix[i] = vector
        matrix, renormalized, _ = emb.normalize_matrix(
            matrix, expected_rows=len(chunks), expected_dim=identity.dim
        )
        validation = emb.validate_matrix(
            matrix, expected_rows=len(chunks), expected_dim=identity.dim,
            require_normalized=True,
        )
        cache_stats = OrderedDict(
            status=(
                "full-build" if base is None
                else "mismatch-reembed" if base.mismatches
                else "incremental"
            ),
            base_index=str(base_index) if base_index else None,
            base_built_at=(base.manifest.get("built_at") if base else None),
            base_chunks=(base.base_chunks if base and base.usable else 0),
            base_vector_rows=(base.base_vector_rows if base and base.usable else 0),
            base_preprocess_version=(base.identity.preprocess_version if base and base.identity else None),
            base_legacy_preprocess_assumed=(
                base is not None and base.usable
                and not (base.manifest or {}).get("preprocess_version")
            ),
            cache_file_vectors=(base.cache_file_rows if base and base.usable else 0),
            reused_rows=int(reused_rows),
            reused_unique=int(len(unique_texts) - len(missing_texts)),
            embedded_rows=int(embedded_rows),
            embedded_unique=int(len(missing_keys)),
            duplicate_text_keys=int(duplicate_keys),
            renormalized_rows=int(renormalized + (base.renormalized_rows if base and base.usable else 0)),
            duplicate_base_keys=(base.duplicate_keys if base and base.usable else 0),
            conflicting_base_keys=(base.conflicting_keys if base and base.usable else 0),
        )

        # ---- 5. 写独立新目录 ----
        _clean_owned_output(output)
        output.mkdir(parents=True, exist_ok=True)
        np.save(output / "vectors.npy", matrix)
        write_jsonl(output / "chunks.jsonl", chunks)

        if not args.no_corpus:
            # 语料只允许写进本次独立输出目录，避免误删/覆盖任意已有目录
            corpus_out = output / "corpus"
            shutil.copytree(corpus_dir, corpus_out)
        else:
            corpus_out = None

        if not args.no_cache:
            cache_vectors = dict(lookup)
            if base is not None and base.usable:
                cache_vectors.update({k: v for k, v in base.vectors.items()})
            emb.write_vector_cache(output / "cache" / "embedding-cache.npz",
                                   cache_vectors, identity)

        # 回读校验：确认落盘内容与内存一致（防写一半/顺序错位）
        written = np.load(output / "vectors.npy", allow_pickle=False)
        written_chunks = read_chunks(output / "chunks.jsonl")
        emb.validate_matrix(written, expected_rows=len(chunks), expected_dim=identity.dim,
                            require_normalized=True)
        if [c.get("id") for c in written_chunks] != [c.get("id") for c in chunks]:
            raise emb.IndexValidationError("写出的 chunks.jsonl 顺序与内存不一致")

        info = emb.provider_info(identity.provider, identity.model, identity.dim)
        manifest = OrderedDict(
            generator=GENERATOR,
            built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            profile=(args.profile or (base.manifest.get("profile") if base else None) or DEFAULT_PROFILE),
            source_repo="QUT-Lib/QUTWiKi",
            source_commit=source_commit,
            source_commit_source=commit_source,
            wiki_root=str(wiki_root),
            model=f"{identity.provider}/{identity.model}",
            **identity.as_dict(),
            dim=int(identity.dim),
            chunks=int(len(chunks)),
            max_seq_length=info["max_seq_length"],
            normalized=True,
            dtype=str(matrix.dtype),
            device=info["device"],
            fp16=info["fp16"],
            encode_seconds=round(api_seconds, 2),
            corpus_path=(str(corpus_out / "chunks.jsonl") if corpus_out else None),
            corpus_sha1=sha1_file(chunks_path),
            chunk_series="doc+table"
                         + ("+pdf" if (stats.get("pdf_chunks") or 0) else ""),
            extraction=OrderedDict(
                source_commit=extraction.get("source_commit"),
                source_root=extraction.get("source_root"),
                documents=stats.get("documents"),
                md_docs=stats.get("md_docs"),
                pdf_docs=stats.get("pdf_docs"),
                tables=stats.get("tables"),
                chunks=stats.get("chunks"),
                doc_chunks=stats.get("doc_chunks"),
                table_chunks=stats.get("table_chunks"),
                pdf_chunks=stats.get("pdf_chunks"),
                params=extraction.get("params"),
                warnings=(extraction.get("warnings") or [])[:100],
            ),
            embedding_cache=cache_stats,
            validation=OrderedDict(validation),
            vectors_sha1=sha1_file(output / "vectors.npy"),
            chunks_sha1=sha1_file(output / "chunks.jsonl"),
            note=(
                "增量构建：按 embed_text(strip, fallback=text) + 模型/维度/预处理版本缓存复用旧向量；"
                "元数据与块顺序始终来自本次抽取；L2 归一化，余弦相似度 = 点积"
            ),
        )
        if base is not None:
            for key in PRESERVED_MANIFEST_KEYS:
                if base.manifest.get(key) is not None:
                    manifest[key] = base.manifest[key]
        (output / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return {
        "manifest": manifest,
        "chunks": chunks,
        "stats": stats,
        "cache": cache_stats,
        "validation": validation,
        "output": str(output),
        "api_seconds": api_seconds,
    }


def _print_summary(result: dict) -> None:
    m = result["manifest"]
    c = result["cache"]
    v = result["validation"]
    label = "全量" if c["status"] == "full-build" else (
        "重编码" if c["status"] == "mismatch-reembed" else "增量")
    print(f"\n完成（{label}）：{m['chunks']} 块 × {m['dim']} 维  ·  "
          f"{Path(result['output']).joinpath('vectors.npy').stat().st_size / 1024 / 1024:.2f} MB")
    print(f"抽取：文档 {m['extraction']['documents']} 篇 / 表格 {m['extraction']['tables']} 张 / "
          f"块 {m['chunks']}（doc {m['extraction']['doc_chunks']} · "
          f"table {m['extraction']['table_chunks']} · pdf {m['extraction']['pdf_chunks']}）")
    print(f"向量：{m['model']}（{m['dim']} 维，{m['device']}）")
    print(f"缓存：复用 {c['reused_rows']} 块（unique {c['reused_unique']}） · "
          f"新编码 {c['embedded_rows']} 块（unique {c['embedded_unique']}）"
          + (f" · 耗时 {result['api_seconds']:.1f}s" if result["api_seconds"] else ""))
    if c["base_index"]:
        print(f"基准：{c['base_index']}（{c['base_chunks']} 块，"
              f"{c['base_preprocess_version']}"
              + ("，旧版未记录预处理版本，按 strip-v1 处理" if c["base_legacy_preprocess_assumed"] else "")
              + "）")
    print(f"校验：finite={v['finite']} · norm {v['norm_min']}–{v['norm_max']} · "
          f"max|n-1|={v['max_norm_error']}")
    print(f"提交：{m['source_commit'] or '-'}（{m['source_commit_source'] or '未提供'}）")
    print(f"输出：{result['output']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="从 QUTWiKi 抽取语料并构建增量 RAG 索引（只读源仓库、不部署）")
    ap.add_argument("--wiki-root", default=str(REPO_ROOT), help="QUTWiKi 仓库根目录（默认本仓库）")
    ap.add_argument("--base-index", default=None,
                    help="旧索引目录（vectors.npy/chunks.jsonl/manifest.json）；省略则全量构建")
    ap.add_argument("--output", required=True, help="新索引输出目录（必须独立于 --base-index）")
    ap.add_argument("--source-commit", default=None,
                    help="写入 manifest 的源提交；默认 git rev-parse HEAD")
    ap.add_argument("--profile", default=None,
                    help="索引 profile（默认沿用旧 manifest，缺省 qut）")
    ap.add_argument("--embed-provider", choices=["zhipu", "fake"], default="zhipu",
                    help="zhipu=在线 API（默认）；fake=离线确定性向量，仅供测试")
    ap.add_argument("--embed-model", default="embedding-3", help="智谱模型，默认 embedding-3")
    ap.add_argument("--embed-dim", type=int, default=1024,
                    help="智谱维度 256/512/1024/2048，默认 1024")
    ap.add_argument("--batch-size", type=int, default=32, help="在线编码批量，默认 32（上限 64）")
    ap.add_argument("--timeout", type=int, default=60, help="单次 API 超时秒数")
    ap.add_argument("--retries", type=int, default=3, help="API 重试次数")
    ap.add_argument("--max-chars", type=int, default=900, help="单块目标最大字符数")
    ap.add_argument("--min-chars", type=int, default=180, help="短块合并阈值")
    ap.add_argument("--overlap", type=int, default=120, help="硬切重叠字符数")
    ap.add_argument("--table-chars", type=int, default=1500, help="表格块目标最大字符数")
    ap.add_argument("--no-pdf", action="store_true", help="跳过 resources/*.pdf")
    ap.add_argument("--no-corpus", action="store_true",
                    help="不把抽取语料复制到 <output>/corpus（默认复制，语料位置固定在输出目录内）")
    ap.add_argument("--no-cache", action="store_true",
                    help="不写 <output>/cache/embedding-cache.npz（默认写）")
    ap.add_argument("--allow-reembed-on-mismatch", action="store_true",
                    help="旧索引模型/维度/预处理版本不一致时仍全量重编码（默认报错）")
    ap.add_argument("--overwrite", action="store_true", help="允许覆盖输出目录里本工具生成的文件")
    args = ap.parse_args(argv)

    try:
        result = build(args)
    except BuildError as e:
        print(f"[!] {e}", file=sys.stderr)
        return 2
    except extract_mod.ExtractionError as e:
        print(f"[!] 抽取失败：{e}", file=sys.stderr)
        return 3
    except emb.IndexValidationError as e:
        print(f"[!] 索引校验失败：{e}", file=sys.stderr)
        return 3
    _print_summary(result)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
