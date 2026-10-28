# -*- coding: utf-8 -*-
"""测试用临时 wiki / 索引工具（不联网、不读 .env、不写仓库）"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

import build_index  # noqa: E402
import embedding as emb  # noqa: E402
import extract  # noqa: E402

LONG_A = (
    "校园卡是校内消费和身份识别的主要凭证，丢失后应第一时间在校园卡服务中心或线上平台挂失，"
    "避免余额被他人使用。补办时需要携带学生证或身份证，补卡工本费以现场公示为准。"
    "如果卡面信息模糊或芯片损坏，也可以按同样流程申请换卡。挂失后原卡立即停用，"
    "新卡一般当场发放，余额会在系统同步后转入新卡。"
)
LONG_B = (
    "宿舍水电费按月度抄表结算，学生可以在后勤服务大厅或线上缴费平台查询账单。"
    "缴费后请保留电子凭证，遇到重复扣费可以带着凭证到后勤服务大厅登记处理。"
    "寒暑假离校前建议检查电表余额并关闭不必要的电器，避免产生欠费或安全隐患。"
)
LONG_C = (
    "图书馆开放时间随学期和节假日调整，借阅图书需要在自助借还机或服务台办理。"
    "本科生可借阅的册数和期限以图书馆官网公布的最新规则为准。"
    "逾期未还会产生滞纳金并影响后续借阅，毕业离校前需要完成清欠手续。"
)
LONG_D = (
    "校医院提供常见病诊疗、预防接种和健康咨询服务。就诊时请携带校园卡和医保相关材料。"
    "门诊时间通常与工作日一致，急诊安排以医院门口公告为准。"
    "需要转诊时先由校医院开具转诊单，再前往定点医院就诊。"
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_wiki(root: Path, *, guide_title: str = "校园指南", guide_extra: str = "",
              include_extra: bool = True, with_table: bool = True) -> Path:
    docs = root / "docs"
    write(docs / "index.md", """---
title: QUTWiKi 测试首页
description: 离线测试站点
---

# QUTWiKi 测试首页

这是用于 RAG 增量索引离线测试的站点首页，包含校园卡、宿舍、图书馆等常见问题入口。
""")
    write(docs / "start" / "guide.md", f"""---
title: {guide_title}
description: 校园服务指南
---

# 校园指南

## 校园卡

{LONG_A}{guide_extra}

## 宿舍水电

{LONG_B}
""")
    # 刻意不写 H1：让两个 H2 各自成块，便于测试“插入新小节后旧块 id 变化但文本不变”
    write(docs / "start" / "library.md", f"""---
title: 图书馆
description: 借阅规则
---

## 开放与借阅

{LONG_C}
""")
    if include_extra:
        write(docs / "start" / "clinic.md", f"""---
title: 校医院
description: 就诊说明
---

# 校医院

## 就诊流程

{LONG_D}
""")
    # 必须被跳过：node_modules / public / .vitepress
    write(docs / "node_modules" / "ignored.md", "# 不应出现\n\n" + LONG_A)
    write(docs / "public" / "ignored.md", "# 不应出现\n\n" + LONG_B)

    write(docs / ".vitepress" / "theme" / "components" / "map-data.js", """\
export const BUILDINGS = [
  { campusId: 'sjz', category: 'canteen', name: '第一食堂', desc: '靠近一号宿舍楼', coord: [120.11, 36.11] },
  { campusId: 'sjz', category: 'teaching', name: '一号教学楼', desc: '公共课教室', coord: [120.12, 36.12] }
]
export const CAMPUS = { sjz: { name: '市北校区' } }
export const CATEGORIES = { canteen: { label: '食堂' }, teaching: { label: '教学' } }
""")

    if with_table:
        try:
            from openpyxl import Workbook
        except ImportError:
            pass
        else:
            wb = Workbook()
            ws = wb.active
            ws.title = "学生社团"
            ws.append(["序号", "分类", "社团名称", "简介"])
            ws.append([1, "学术", "数学建模协会", "组织数学建模培训与竞赛"])
            ws.append([2, "学术", "程序设计协会", "算法与工程实践交流"])
            ws.append([3, "体育", "篮球社", "每周组织院系友谊赛"])
            ws.append([4, "体育", "羽毛球社", "场地预约与日常训练"])
            (docs / ".http_cache").mkdir(parents=True, exist_ok=True)
            wb.save(docs / ".http_cache" / "org.xlsx")
    return docs


def run_build(*argv: str) -> tuple[int, str, str]:
    """在进程内跑 CLI，返回 (退出码, stdout, stderr)"""
    import contextlib
    import io

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = build_index.main(list(argv))
    return code, out.getvalue(), err.getvalue()


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def read_index(index_dir: Path) -> tuple[list[dict], "emb.np.ndarray", dict]:
    import numpy as np
    chunks = read_jsonl(index_dir / "chunks.jsonl")
    vectors = np.load(index_dir / "vectors.npy", allow_pickle=False)
    manifest = json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))
    return chunks, vectors, manifest


def key_map(chunks: list[dict], identity: emb.IndexIdentity) -> dict[str, "emb.np.ndarray"]:
    return {
        emb.cache_key(emb.embed_text_for(c), identity.provider, identity.model,
                      identity.dim, identity.preprocess_version): c
        for c in chunks
    }


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="qutwiki-rag-test-")
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()
