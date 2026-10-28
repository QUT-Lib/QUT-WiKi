# -*- coding: utf-8 -*-
"""CLI 冒烟测试：验证直接运行脚本（不是 import）也能工作。"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest

from helpers import RAG_DIR, TempDirTestCase, make_wiki


class CliSmokeTest(TempDirTestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, *map(str, args)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120,
        )

    def test_help(self):
        for script in ("build_index.py", "extract.py"):
            r = self._run(RAG_DIR / script, "--help")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("--wiki-root", r.stdout)

    def test_corpus_out_flag_is_gone_and_cannot_delete_directories(self):
        wiki = self.tmp / "wiki"
        make_wiki(wiki)
        victim = self.tmp / "victim"
        victim.mkdir()
        keep = victim / "keep.txt"
        keep.write_text("do not delete", encoding="utf-8")

        r = self._run(
            RAG_DIR / "build_index.py",
            "--wiki-root", wiki,
            "--output", self.tmp / "index",
            "--corpus-out", victim,
            "--overwrite",
        )
        self.assertEqual(r.returncode, 2)
        self.assertIn("unrecognized", r.stderr.lower())
        self.assertTrue(keep.exists())
        self.assertEqual(keep.read_text(encoding="utf-8"), "do not delete")

    def test_build_offline_end_to_end(self):
        wiki = self.tmp / "wiki"
        make_wiki(wiki)
        out = self.tmp / "index"
        r = self._run(
            RAG_DIR / "build_index.py",
            "--wiki-root", wiki,
            "--output", out,
            "--embed-provider", "fake",
            "--embed-dim", "16",
            "--source-commit", "cli-test",
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        for name in ("vectors.npy", "chunks.jsonl", "manifest.json"):
            self.assertTrue((out / name).exists(), name)
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_commit"], "cli-test")
        self.assertEqual(manifest["embed_dim"], 16)
        self.assertTrue(manifest["validation"]["finite"])


if __name__ == "__main__":
    unittest.main()
