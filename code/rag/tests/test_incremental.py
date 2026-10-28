# -*- coding: utf-8 -*-
"""离线测试：增量索引（复用 / 新增 / 删除 / 元数据 / 身份校验 / 损坏索引）

所有测试都用 FakeEmbedder，不会发起网络请求，也不会读取 .env。
"""
from __future__ import annotations

import shutil
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from helpers import (TempDirTestCase, emb, make_wiki, read_index, read_jsonl,
                     run_build)

DIM = 64
MODEL = "embedding-3"
COMMIT = "0123456789abcdef"


class IncrementalBuildTest(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.wiki = self.tmp / "wiki"
        make_wiki(self.wiki)
        self.identity = emb.IndexIdentity("fake", MODEL, DIM)
        self.base = self.tmp / "index-base"
        code, out, err = self._build(self.base, profile="custom-test")
        self.assertEqual(code, 0, err)
        self.base_chunks, self.base_vectors, self.base_manifest = read_index(self.base)
        self.base_by_text = {
            emb.embed_text_for(c): self.base_vectors[i] for i, c in enumerate(self.base_chunks)
        }

    def _build(self, out: Path, base: Path | None = None, *extra: str,
               profile: str | None = None):
        argv = [
            "--wiki-root", str(self.wiki),
            "--output", str(out),
            "--embed-provider", "fake",
            "--embed-model", MODEL,
            "--embed-dim", str(DIM),
            "--source-commit", COMMIT,
        ]
        if base is not None:
            argv += ["--base-index", str(base)]
        if profile is not None:
            argv += ["--profile", profile]
        argv += list(extra)
        return run_build(*argv)

    def test_incremental_reuse_add_delete_and_fresh_metadata(self):
        # 1) 正文修改（key 变化）
        guide = self.wiki / "docs" / "start" / "guide.md"
        text = guide.read_text(encoding="utf-8")
        text = text.replace("校园卡是校内消费", "校园卡是校内消费（新修订说明：支持线上补办）", 1)
        guide.write_text(text, encoding="utf-8")
        # 2) 只改元数据 title（embed_text 不变 -> 必须复用向量）
        library = self.wiki / "docs" / "start" / "library.md"
        lib_text = library.read_text(encoding="utf-8")
        lib_text = lib_text.replace("title: 图书馆", "title: 图书馆（新）", 1)
        library.write_text(lib_text, encoding="utf-8")
        # 3) 删除一篇
        (self.wiki / "docs" / "start" / "clinic.md").unlink()
        # 4) 新增一篇
        (self.wiki / "docs" / "start" / "new.md").write_text("""---
title: 新页面
description: 新增测试
---

# 新页面

## 选课说明

选课系统在每学期开学前开放，学生需要先完成学期注册，再按培养方案选择课程。
退课和补选的时间窗口以教务处通知为准，逾期不能自行修改。
""", encoding="utf-8")

        new_out = self.tmp / "index-new"
        captured = {}

        def factory(*args, **kwargs):
            e = emb.FakeEmbedder(model=args[1], dimensions=args[2])
            captured["embedder"] = e
            return e

        with mock.patch.object(emb, "create_embedder", side_effect=factory):
            code, out, err = self._build(new_out, self.base)
        self.assertEqual(code, 0, err)

        chunks, vectors, manifest = read_index(new_out)
        self.assertEqual(vectors.shape, (len(chunks), DIM))
        self.assertEqual(manifest["chunks"], len(chunks))
        self.assertEqual(manifest["profile"], "custom-test")
        self.assertEqual(manifest["source_commit"], COMMIT)
        self.assertEqual(manifest["extraction"]["documents"], 4)  # 删 1 增 1
        self.assertEqual(manifest["embedding_cache"]["status"], "incremental")
        self.assertFalse(manifest["embedding_cache"]["base_legacy_preprocess_assumed"])

        # 删除的文档不再出现
        self.assertFalse(any(c["doc_id"] == "start/clinic" for c in chunks))
        # 新增的文档出现
        self.assertTrue(any(c["doc_id"] == "start/new" for c in chunks))
        # 只改 title 的文档：元数据最新、文本 key 不变、向量逐位复用
        lib_chunks = [(i, c) for i, c in enumerate(chunks) if c["doc_id"] == "start/library"]
        self.assertTrue(lib_chunks)
        for i, c in lib_chunks:
            self.assertEqual(c["title"], "图书馆（新）")
            old = self.base_by_text[emb.embed_text_for(c)]
            self.assertTrue(np.allclose(vectors[i], old, atol=1e-6))
        # 正文修改的块：重新编码
        guide_chunks = [c for c in chunks if c["doc_id"] == "start/guide"]
        self.assertTrue(any("新修订说明" in emb.embed_text_for(c) for c in guide_chunks))
        self.assertNotIn(
            next(emb.embed_text_for(c) for c in guide_chunks if "新修订说明" in emb.embed_text_for(c)),
            self.base_by_text,
        )

        # 缓存统计与实际 key 命中一致
        new_keys = [emb.cache_key(emb.embed_text_for(c), "fake", MODEL, DIM) for c in chunks]
        expected_reused = sum(1 for k in new_keys if k in set(
            emb.cache_key(t, "fake", MODEL, DIM) for t in self.base_by_text))
        expected_embedded = len(chunks) - expected_reused
        self.assertEqual(manifest["embedding_cache"]["reused_rows"], expected_reused)
        self.assertEqual(manifest["embedding_cache"]["embedded_rows"], expected_embedded)
        self.assertEqual(
            manifest["embedding_cache"]["embedded_unique"],
            len(set(k for k in new_keys if k not in set(
                emb.cache_key(t, "fake", MODEL, DIM) for t in self.base_by_text))),
        )
        # 只对缺失文本调用了编码（且 unique 去重）
        expected_texts = {
            emb.embed_text_for(c) for c, k in zip(chunks, new_keys)
            if k not in set(emb.cache_key(t, "fake", MODEL, DIM) for t in self.base_by_text)
        }
        self.assertEqual(set(captured["embedder"].calls[0]), expected_texts)
        self.assertEqual(vectors.dtype, np.float32)
        self.assertTrue(np.isfinite(vectors).all())
        self.assertTrue(np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-4))

        # corpus 默认随输出目录发布，manifest 指向它
        self.assertTrue((new_out / "corpus" / "chunks.jsonl").exists())
        self.assertEqual(manifest["corpus_path"],
                         str((new_out / "corpus" / "chunks.jsonl").resolve()))
        self.assertTrue((new_out / "cache" / "embedding-cache.npz").exists())

    def test_reuse_when_chunk_ids_shift(self):
        """同一段文本因为前面插入新小节而换了 chunk id，向量仍应按文本复用。"""
        old_chunk = next(c for c in self.base_chunks
                         if c["doc_id"] == "start/library" and "图书馆开放时间" in c["text"])
        old_text = emb.embed_text_for(old_chunk)
        old_id = old_chunk["id"]
        old_vector = self.base_vectors[self.base_chunks.index(old_chunk)]

        library = self.wiki / "docs" / "start" / "library.md"
        text = library.read_text(encoding="utf-8")
        text = text.replace("## 开放与借阅", """## 入馆须知

入馆需要刷校园卡，校外人员须提前预约并登记。馆内保持安静，禁止携带食品进入阅览区。
考试周座位紧张，建议使用座位预约系统，离馆时请带走个人物品。

## 开放与借阅""", 1)
        library.write_text(text, encoding="utf-8")

        out = self.tmp / "index-shift"
        code, _, err = self._build(out, self.base)
        self.assertEqual(code, 0, err)
        chunks, vectors, manifest = read_index(out)
        new_idx = next(i for i, c in enumerate(chunks) if emb.embed_text_for(c) == old_text)
        new_chunk = chunks[new_idx]
        self.assertNotEqual(new_chunk["id"], old_id)
        self.assertEqual(new_chunk["title"], "图书馆")
        self.assertTrue(np.allclose(vectors[new_idx], old_vector, atol=1e-6))
        new_keys = {emb.cache_key(emb.embed_text_for(c), "fake", MODEL, DIM) for c in chunks}
        base_keys = {emb.cache_key(t, "fake", MODEL, DIM) for t in self.base_by_text}
        self.assertEqual(manifest["embedding_cache"]["embedded_unique"],
                         len(new_keys - base_keys))

    def test_full_reuse_is_offline_and_calls_no_embedder(self):
        out = self.tmp / "index-same"
        with mock.patch.object(emb, "create_embedder",
                               side_effect=AssertionError("不应调用 embedding")):
            code, stdout, err = self._build(out, self.base)
        self.assertEqual(code, 0, err)
        chunks, vectors, manifest = read_index(out)
        self.assertEqual(manifest["embedding_cache"]["embedded_rows"], 0)
        self.assertEqual(manifest["embedding_cache"]["reused_rows"], len(chunks))
        self.assertEqual(vectors.shape[0], len(self.base_chunks))

    def test_model_or_dim_mismatch_is_refused(self):
        out = self.tmp / "index-mismatch"
        code, stdout, err = run_build(
            "--wiki-root", str(self.wiki), "--output", str(out),
            "--base-index", str(self.base), "--embed-provider", "fake",
            "--embed-model", MODEL, "--embed-dim", "32",
        )
        self.assertEqual(code, 2)
        self.assertIn("不一致", err)
        self.assertFalse(out.exists(), "身份不一致时不应写出索引")

        # 显式允许后才全量重编码
        out2 = self.tmp / "index-mismatch-ok"
        code, stdout, err = run_build(
            "--wiki-root", str(self.wiki), "--output", str(out2),
            "--base-index", str(self.base), "--embed-provider", "fake",
            "--embed-model", MODEL, "--embed-dim", "32",
            "--allow-reembed-on-mismatch",
        )
        self.assertEqual(code, 0, err)
        chunks, vectors, manifest = read_index(out2)
        self.assertEqual(vectors.shape, (len(chunks), 32))
        self.assertEqual(manifest["embedding_cache"]["status"], "mismatch-reembed")
        self.assertEqual(manifest["embedding_cache"]["reused_rows"], 0)

    def test_corrupt_base_is_rejected(self):
        corrupt = self.tmp / "base-nan"
        shutil.copytree(self.base, corrupt)
        v = np.load(corrupt / "vectors.npy", allow_pickle=False)
        v[0, 0] = np.nan
        np.save(corrupt / "vectors.npy", v)
        code, _, err = self._build(self.tmp / "out-nan", corrupt)
        self.assertEqual(code, 3)
        self.assertIn("NaN", err)

        corrupt2 = self.tmp / "base-shape"
        shutil.copytree(self.base, corrupt2)
        v = np.load(corrupt2 / "vectors.npy", allow_pickle=False)
        np.save(corrupt2 / "vectors.npy", v[:-1])
        code, _, err = self._build(self.tmp / "out-shape", corrupt2)
        self.assertEqual(code, 3)
        self.assertIn("不一致", err)

    def test_output_must_be_independent(self):
        code, _, err = self._build(self.base, self.base)
        self.assertEqual(code, 2)
        self.assertIn("独立", err)

        existing = self.tmp / "index-existing"
        code, _, err = self._build(existing)
        self.assertEqual(code, 0, err)
        code, _, err = self._build(existing)
        self.assertEqual(code, 2)
        self.assertIn("--overwrite", err)

    def test_deleted_vectors_survive_in_cache_for_future_reuse(self):
        clinic = self.wiki / "docs" / "start" / "clinic.md"
        clinic_text = clinic.read_text(encoding="utf-8")
        clinic_chunks = [c for c in self.base_chunks if c["doc_id"] == "start/clinic"]
        self.assertTrue(clinic_chunks)
        clinic_keys = {emb.cache_key(emb.embed_text_for(c), "fake", MODEL, DIM)
                       for c in clinic_chunks}
        clinic_vecs = {emb.embed_text_for(c): self.base_vectors[i]
                       for i, c in enumerate(self.base_chunks) if c["doc_id"] == "start/clinic"}

        # 删除后构建：索引里没有 clinic，但缓存里保留其向量
        clinic.unlink()
        out2 = self.tmp / "index-without-clinic"
        code, _, err = self._build(out2, self.base)
        self.assertEqual(code, 0, err)
        with np.load(out2 / "cache" / "embedding-cache.npz", allow_pickle=False) as data:
            cached = {str(k) for k in data["keys"].tolist()}
        self.assertTrue(clinic_keys.issubset(cached))
        self.assertFalse(any(c["doc_id"] == "start/clinic"
                             for c in read_jsonl(out2 / "chunks.jsonl")))

        # 原样加回：向量应直接从缓存复用，不需要重新编码
        clinic.write_text(clinic_text, encoding="utf-8")
        out3 = self.tmp / "index-restored"
        captured = {}

        def factory(*args, **kwargs):
            e = emb.FakeEmbedder(model=args[1], dimensions=args[2])
            captured["embedder"] = e
            return e

        with mock.patch.object(emb, "create_embedder", side_effect=factory):
            code, _, err = self._build(out3, out2)
        self.assertEqual(code, 0, err)
        chunks, vectors, manifest = read_index(out3)
        self.assertGreater(manifest["embedding_cache"]["cache_file_vectors"], 0)
        restored = {emb.embed_text_for(c): vectors[i]
                    for i, c in enumerate(chunks) if c["doc_id"] == "start/clinic"}
        self.assertTrue(restored)
        for text, vector in restored.items():
            self.assertTrue(np.allclose(vector, clinic_vecs[text], atol=1e-6))
        # 若全部命中缓存，embedder 只能收到 0 条或缺页之外的新文本；clinic 文本不应出现
        if "embedder" in captured:
            called = {t for batch in captured["embedder"].calls for t in batch}
            self.assertFalse(called & set(clinic_vecs))

    def test_manifest_records_validation_and_hashes(self):
        manifest = self.base_manifest
        self.assertEqual(manifest["embed_dim"], DIM)
        self.assertEqual(manifest["dim"], DIM)
        self.assertEqual(manifest["preprocess_version"], emb.PREPROCESS_VERSION)
        self.assertTrue(manifest["validation"]["finite"])
        self.assertTrue(manifest["validation"]["normalized"])
        self.assertEqual(manifest["validation"]["rows"], len(self.base_chunks))
        self.assertLessEqual(abs(manifest["validation"]["norm_min"] - 1.0), 1e-4)
        self.assertIn("vectors_sha1", manifest)
        self.assertIn("chunks_sha1", manifest)
        self.assertEqual(manifest["extraction"]["source_commit"], COMMIT)


if __name__ == "__main__":
    unittest.main()
