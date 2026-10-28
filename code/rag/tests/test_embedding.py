# -*- coding: utf-8 -*-
"""纯离线测试：embedding 文本、缓存 key、矩阵校验、FakeEmbedder"""
from __future__ import annotations

import importlib.util
import unittest
from unittest import mock

import numpy as np

from helpers import TempDirTestCase  # noqa: F401  (统一临时目录基类)
from helpers import emb


class _FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, data):
        self._data = data

    def json(self):
        return {"data": self._data}


@unittest.skipUnless(importlib.util.find_spec("requests"), "未安装 requests")
class ZhipuIndexMappingTest(unittest.TestCase):
    """智谱返回的 index 必须恰好是 0..n-1，否则不能按 sort 后位置硬映射。"""

    def _embedder(self):
        return emb.ZhipuEmbedder(model="embedding-3", dimensions=256, api_key="test")

    @staticmethod
    def _vectors():
        e0 = np.zeros(256, dtype="float32")
        e1 = np.zeros(256, dtype="float32")
        e0[0] = 1.0
        e1[1] = 1.0
        return e0.tolist(), e1.tolist()

    def test_out_of_order_response_is_mapped_by_index(self):
        e0, e1 = self._vectors()
        data = [
            {"index": 1, "embedding": e1},
            {"index": 0, "embedding": e0},
        ]
        with mock.patch("requests.post", return_value=_FakeResponse(data)) as post:
            vectors = self._embedder().encode(["文本A", "文本B"])
        self.assertEqual(post.call_count, 1)
        self.assertTrue(np.allclose(vectors[0], np.asarray(e0)))
        self.assertTrue(np.allclose(vectors[1], np.asarray(e1)))

    def test_invalid_indices_are_rejected(self):
        e0, e1 = self._vectors()
        cases = {
            "重复": [{"index": 0, "embedding": e0}, {"index": 0, "embedding": e1}],
            "缺口": [{"index": 0, "embedding": e0}, {"index": 2, "embedding": e1}],
            "字符串": [{"index": "0", "embedding": e0}, {"index": 1, "embedding": e1}],
            "布尔": [{"index": True, "embedding": e0}, {"index": 1, "embedding": e1}],
            "缺失": [{"embedding": e0}, {"index": 1, "embedding": e1}],
        }
        for name, data in cases.items():
            with self.subTest(name=name):
                with mock.patch("requests.post", return_value=_FakeResponse(data)):
                    with self.assertRaises(emb.EmbeddingError):
                        self._embedder().encode(["文本A", "文本B"])

    def test_bad_embedding_shape_is_rejected(self):
        data = [
            {"index": 0, "embedding": [0.1, 0.2]},
            {"index": 1, "embedding": [0.1, 0.2]},
        ]
        with mock.patch("requests.post", return_value=_FakeResponse(data)):
            with self.assertRaises(emb.EmbeddingError):
                self._embedder().encode(["文本A", "文本B"])


class EmbedTextTest(unittest.TestCase):
    def test_embed_text_prefers_embed_text_and_strips(self):
        self.assertEqual(emb.embed_text_for({"embed_text": "  hello \n", "text": "x"}), "hello")
        self.assertEqual(emb.embed_text_for({"embed_text": "   ", "text": " fallback "}), "fallback")
        self.assertEqual(emb.embed_text_for({"text": "only text\n"}), "only text")
        self.assertEqual(emb.embed_text_for({"embed_text": None, "text": None}), "")
        self.assertEqual(emb.embed_text_for({}), "")

    def test_cache_key_semantics(self):
        base = emb.cache_key("abc", "zhipu", "embedding-3", 1024)
        self.assertEqual(base, emb.cache_key(" abc \n", "zhipu", "embedding-3", 1024))
        self.assertNotEqual(base, emb.cache_key("abc", "zhipu", "embedding-3", 512))
        self.assertNotEqual(base, emb.cache_key("abc", "zhipu", "embedding-2", 1024))
        self.assertNotEqual(base, emb.cache_key("abc", "fake", "embedding-3", 1024))
        self.assertNotEqual(base, emb.cache_key("abc", "zhipu", "embedding-3", 1024,
                                                preprocess_version="other"))
        self.assertNotEqual(base, emb.cache_key("abd", "zhipu", "embedding-3", 1024))
        self.assertEqual(len(base), 64)


class MatrixValidationTest(unittest.TestCase):
    def test_normalize_and_validate(self):
        raw = np.array([[3.0, 4.0], [0.0, 2.0]], dtype="float32")
        normed, changed, zero = emb.normalize_matrix(raw)
        self.assertEqual(zero, [])
        self.assertEqual(changed, 2)
        info = emb.validate_matrix(normed, expected_rows=2, expected_dim=2)
        self.assertTrue(info["finite"])
        self.assertTrue(info["normalized"])
        self.assertAlmostEqual(info["norm_min"], 1.0, places=6)

    def test_reject_bad_shape(self):
        with self.assertRaises(emb.IndexValidationError):
            emb.validate_matrix(np.zeros((3, 4), dtype="float32"), expected_rows=2, expected_dim=4)

    def test_reject_nan(self):
        bad = np.ones((2, 4), dtype="float32")
        bad[1, 2] = np.nan
        with self.assertRaises(emb.IndexValidationError):
            emb.validate_matrix(bad, expected_rows=2, expected_dim=4)

    def test_reject_unnormalized(self):
        bad = np.full((2, 4), 2.0, dtype="float32")
        with self.assertRaises(emb.IndexValidationError):
            emb.validate_matrix(bad, expected_rows=2, expected_dim=4, require_normalized=True)

    def test_zero_vector_rejected(self):
        with self.assertRaises(emb.IndexValidationError):
            emb.normalize_matrix(np.zeros((1, 4), dtype="float32"))


class FakeEmbedderTest(TempDirTestCase):
    def test_deterministic_and_normalized(self):
        e1 = emb.FakeEmbedder(dimensions=32)
        e2 = emb.FakeEmbedder(dimensions=32)
        a = e1.encode(["校园卡", "宿舍"])
        b = e2.encode(["校园卡", "宿舍"])
        self.assertEqual(a.shape, (2, 32))
        self.assertTrue(np.allclose(a, b))
        self.assertTrue(np.allclose(np.linalg.norm(a, axis=1), 1.0, atol=1e-6))

    def test_vector_cache_roundtrip(self):
        identity = emb.IndexIdentity("fake", "embedding-3", 32)
        e = emb.FakeEmbedder(dimensions=32)
        key_a = emb.cache_key("a", "fake", "embedding-3", 32)
        key_b = emb.cache_key("b", "fake", "embedding-3", 32)
        vectors = {key_a: e.encode(["a"])[0], key_b: e.encode(["b"])[0]}
        path = self.tmp / "cache.npz"
        self.assertEqual(emb.write_vector_cache(path, vectors, identity), 2)

        index_dir = self.tmp / "base"
        index_dir.mkdir()
        import json
        np.save(index_dir / "vectors.npy", e.encode(["a"]))
        (index_dir / "chunks.jsonl").write_text(
            json.dumps({"id": "x#001", "embed_text": "a"}, ensure_ascii=False) + "\n",
            encoding="utf-8")
        (index_dir / "manifest.json").write_text(json.dumps({
            "embed_provider": "fake", "embed_model": "embedding-3", "embed_dim": 32,
            "preprocess_version": emb.PREPROCESS_VERSION, "normalized": True,
        }), encoding="utf-8")
        (index_dir / "cache").mkdir()
        import shutil
        shutil.copy2(path, index_dir / "cache" / "embedding-cache.npz")

        lookup = emb.load_base_vectors(index_dir, identity)
        self.assertFalse(lookup.mismatches)
        self.assertEqual(lookup.base_chunks, 1)
        self.assertEqual(lookup.cache_file_rows, 1)  # bbb 只存在于缓存文件
        self.assertEqual(len(lookup.vectors), 2)


if __name__ == "__main__":
    unittest.main()
