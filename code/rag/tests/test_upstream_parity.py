# -*- coding: utf-8 -*-
"""可选回归测试：与上游 D:/code/RAG 的抽取器逐字节对比。

默认跳过；在开发机上显式指定上游脚本后运行：
  $env:QUTWIKI_RAG_UPSTREAM = "D:/code/RAG/scripts/extract_corpus.py"
  py -3 -m unittest discover -s code/rag/tests -p test_upstream_parity.py -v
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from helpers import RAG_DIR, TempDirTestCase

UPSTREAM = os.environ.get("QUTWIKI_RAG_UPSTREAM", "")
REPO_ROOT = RAG_DIR.parents[1]


@unittest.skipUnless(UPSTREAM and Path(UPSTREAM).is_file(),
                     "未设置 QUTWIKI_RAG_UPSTREAM，跳过上游对比")
class UpstreamParityTest(TempDirTestCase):
    def _run(self, *args: str) -> None:
        r = subprocess.run([sys.executable, *map(str, args)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])

    def test_chunks_jsonl_is_byte_identical(self):
        ours = self.tmp / "ours"
        theirs = self.tmp / "theirs"
        self._run(RAG_DIR / "extract.py", "--wiki-root", REPO_ROOT, "--out", ours)
        self._run(UPSTREAM, "--source", REPO_ROOT / "docs", "--out", theirs)
        self.assertEqual((ours / "chunks.jsonl").read_bytes(),
                         (theirs / "chunks.jsonl").read_bytes())


if __name__ == "__main__":
    unittest.main()
