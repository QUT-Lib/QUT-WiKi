# -*- coding: utf-8 -*-
"""QUTWiKi RAG 增量索引工具（抽取 / embedding 缓存 / 构建 / 校验）。

入口（直接运行脚本，避免与标准库 ``code`` 模块重名）：
  py -3 code/rag/extract.py --wiki-root . --out .work/corpus
  py -3 code/rag/build_index.py --wiki-root . --base-index ... --output ...
"""

__version__ = "1.0.0"
