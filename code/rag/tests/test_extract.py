# -*- coding: utf-8 -*-
"""离线测试：语料抽取（复用上游逻辑，绝对路径全部参数化）"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from unittest import mock

from helpers import (TempDirTestCase, emb, extract, make_wiki, read_jsonl,
                     run_build)

HAS_PYMUPDF = (importlib.util.find_spec("pymupdf") is not None
               or importlib.util.find_spec("fitz") is not None)


class ExtractTest(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.wiki = self.tmp / "wiki"
        make_wiki(self.wiki)

    def _extract(self, name="corpus", **kwargs):
        out = self.tmp / name
        manifest = extract.extract_all(self.wiki, out, verbose=False, **kwargs)
        return out, manifest, read_jsonl(out / "chunks.jsonl")

    def test_chunks_are_valid_and_filtered(self):
        out, manifest, chunks = self._extract()
        self.assertGreater(len(chunks), 3)
        ids = [c["id"] for c in chunks]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(c.get("embed_text", "").strip() for c in chunks))
        self.assertTrue(all(c["source_path"].startswith("docs/") for c in chunks))
        self.assertFalse(any("node_modules" in c["source_path"] for c in chunks))
        self.assertFalse(any("/public/" in c["source_path"] for c in chunks))
        self.assertEqual(manifest["stats"]["chunks"], len(chunks))
        self.assertEqual(manifest["wiki_root"], str(self.wiki.resolve()))
        self.assertTrue((out / "documents.jsonl").exists())
        self.assertTrue((out / "manifest.json").exists())

    def test_map_and_table_dependencies(self):
        out, manifest, chunks = self._extract()
        map_chunks = [c for c in chunks if c["id"].startswith("tables/map-data#BUILDINGS")]
        self.assertTrue(map_chunks, "校园地图表格块未生成")
        map_chunk = map_chunks[0]
        self.assertEqual(map_chunk["type"], "table")
        self.assertIn("市北校区", map_chunk["text"])
        self.assertTrue((out / "tables" / "map-data.BUILDINGS.md").exists())

        # openpyxl 是必需依赖：没有它构建应直接失败，而不是少块成功
        table_chunks = [c for c in chunks if c["id"].startswith("tables/org#学生社团")]
        self.assertTrue(table_chunks, "xlsx 表格块未生成")
        self.assertTrue(all(c["type"] == "table" for c in table_chunks))

    def test_deterministic(self):
        _, _, a = self._extract("corpus-a")
        _, _, b = self._extract("corpus-b")
        self.assertEqual([c["id"] for c in a], [c["id"] for c in b])
        self.assertEqual([emb.embed_text_for(c) for c in a],
                         [emb.embed_text_for(c) for c in b])

    def test_source_commit_override(self):
        _, manifest, _ = self._extract(source_commit="deadbeefcafe")
        self.assertEqual(manifest["source_commit"], "deadbeefcafe")

    def test_accepts_docs_dir_and_repo_root(self):
        for root in (self.wiki, self.wiki / "docs"):
            out = self.tmp / ("out-" + root.name)
            manifest = extract.extract_all(root, out, verbose=False)
            self.assertEqual(manifest["source_root"], str((self.wiki / "docs").resolve()))

    def test_rejects_non_wiki_dir(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        with self.assertRaises(FileNotFoundError):
            extract.extract_all(empty, self.tmp / "corpus-empty", verbose=False)

    def test_frontmatter_metadata_is_used(self):
        out, _, chunks = self._extract()
        guide = [c for c in chunks if c["doc_id"] == "start/guide"]
        self.assertTrue(guide)
        self.assertEqual(guide[0]["title"], "校园指南")
        doc = next(d for d in read_jsonl(out / "documents.jsonl")
                   if d["id"] == "start/guide")
        self.assertEqual(doc["description"], "校园服务指南")
        self.assertEqual(doc["category"], "关于")


class ExtractionFailureTest(TempDirTestCase):
    """依赖缺失 / 源文件解析失败必须硬失败，不能告警后少块成功。"""

    def setUp(self):
        super().setUp()
        self.wiki = self.tmp / "wiki"
        make_wiki(self.wiki)
        self.docs = self.wiki / "docs"

    def test_openpyxl_import_is_required(self):
        with mock.patch.dict(sys.modules, {"openpyxl": None}):
            with self.assertRaises(extract.ExtractionError) as cm:
                extract._import_openpyxl()
        self.assertIn("openpyxl", str(cm.exception))

    def test_extract_tables_without_openpyxl_is_fatal(self):
        with mock.patch.object(
                extract, "_import_openpyxl",
                side_effect=extract.ExtractionError("缺少必需依赖 openpyxl")):
            with self.assertRaises(extract.ExtractionError):
                extract.extract_tables(self.docs, self.tmp / "out", 1500)

    def test_build_without_openpyxl_is_fatal(self):
        out = self.tmp / "index"
        with mock.patch.object(
                extract, "_import_openpyxl",
                side_effect=extract.ExtractionError("缺少必需依赖 openpyxl")):
            code, _, err = run_build(
                "--wiki-root", str(self.wiki), "--output", str(out),
                "--embed-provider", "fake", "--embed-dim", "16",
            )
        self.assertEqual(code, 2)
        self.assertIn("openpyxl", err)
        self.assertFalse(out.exists())

    def test_xlsx_parse_error_is_fatal(self):
        out = self.tmp / "index"
        with mock.patch.object(extract, "read_xlsx", side_effect=ValueError("boom")):
            code, _, err = run_build(
                "--wiki-root", str(self.wiki), "--output", str(out),
                "--embed-provider", "fake", "--embed-dim", "16",
            )
        self.assertEqual(code, 3)
        self.assertIn("xlsx 解析失败", err)
        self.assertFalse(out.exists())

    def test_empty_xlsx_is_fatal(self):
        with mock.patch.object(extract, "read_xlsx", return_value={"Sheet": []}):
            with self.assertRaises(extract.ExtractionError) as cm:
                extract.extract_tables(self.docs, self.tmp / "out", 1500)
        self.assertIn("没有可抽取", str(cm.exception))

    def test_map_parse_error_is_fatal(self):
        (self.docs / ".vitepress" / "theme" / "components" / "map-data.js").write_text(
            "export const SOMETHING_ELSE = []\n", encoding="utf-8")
        with self.assertRaises(extract.ExtractionError) as cm:
            extract.extract_all(self.wiki, self.tmp / "corpus", verbose=False)
        self.assertIn("BUILDINGS", str(cm.exception))

    def test_map_object_without_name_is_fatal(self):
        p = self.docs / ".vitepress" / "theme" / "components" / "map-data.js"
        p.write_text(p.read_text(encoding="utf-8").replace(
            "name: '第一食堂'", "label: '第一食堂'", 1), encoding="utf-8")
        with self.assertRaises(extract.ExtractionError) as cm:
            extract.extract_all(self.wiki, self.tmp / "corpus", verbose=False)
        self.assertIn("name", str(cm.exception))

    def test_component_parse_failure_is_fatal(self):
        cases = {
            "AppCards": "<AppCards :links=\"[\n  { text: '没有闭合对象' \n]\" />\n",
            "flink": '<flink link="https://example.com/" />\n',
        }
        for name, block in cases.items():
            with self.subTest(name=name):
                bad = self.docs / f"bad-{name}.md"
                bad.write_text(f"# 坏组件 {name}\n\n{block}", encoding="utf-8")
                try:
                    with self.assertRaises(extract.ExtractionError):
                        extract.extract_all(self.wiki, self.tmp / f"corpus-{name}",
                                            verbose=False)
                finally:
                    bad.unlink()

    @unittest.skipUnless(HAS_PYMUPDF, "未安装 pymupdf，跳过 PDF 失败路径测试")
    def test_broken_pdf_is_fatal(self):
        try:
            import pymupdf
        except ImportError:  # pragma: no cover - 兼容旧包名
            import fitz as pymupdf  # type: ignore

        resources = self.docs / "resources"
        resources.mkdir(parents=True, exist_ok=True)
        (resources / "broken.pdf").write_bytes(b"%PDF-1.4\nthis is not a pdf")
        # 不用真实损坏文件触发，避免 PyMuPDF 在 Windows 上失败打开时短暂占用句柄
        with mock.patch.object(pymupdf, "open", side_effect=RuntimeError("boom")):
            with self.assertRaises(extract.ExtractionError) as cm:
                extract.extract_pdf(self.docs, self.tmp / "corpus")
        self.assertIn("PDF 解析失败", str(cm.exception))

    @unittest.skipUnless(HAS_PYMUPDF, "未安装 pymupdf，跳过扫描件 PDF 测试")
    def test_scanned_pdf_without_text_only_warns(self):
        import pymupdf

        resources = self.docs / "resources"
        resources.mkdir(parents=True, exist_ok=True)
        pdf = pymupdf.open()
        pdf.new_page()  # 空白页，无文本层
        pdf.save(resources / "scan.pdf")
        pdf.close()

        docs, chunks, warnings = extract.extract_pdf(self.docs, self.tmp / "corpus")
        self.assertEqual(docs, [])
        self.assertEqual(chunks, [])
        self.assertTrue(any("扫描件" in w or "无文本层" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
