#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QUTWiKi -> RAG 语料提取器（只读源仓库，不做任何修改）

本文件 vendored 自 D:/code/RAG/scripts/extract_corpus.py（上游同步基线），
只把“源目录 / 输出目录 / git commit”从写死的绝对路径改成参数，
分块、清洗、表格、地图、PDF 逻辑保持完全一致，保证语料可复现。

输入：QUTWiKi 仓库根目录下的 docs/（也接受直接传 docs/）
输出（--out 目录）：
  documents.jsonl   每篇文档一条（清洗后全文 + 元数据）
  chunks.jsonl      检索块（文档块 + 表格块，统一 schema）
  tables/*.md|csv   xlsx 原始表格的 Markdown / CSV 副本
  manifest.json     源文件指纹（sha1）+ 统计 + 告警

用法：
  py -3 code/rag/extract.py --wiki-root . --out .work/corpus
  py -3 code/rag/extract.py --wiki-root D:/code/QUT-Lib/QUTWiKi --out D:/Temp/corpus

依赖：
  openpyxl  提取 xlsx 表格块（缺省时跳过表格并告警）
  pymupdf   提取 resources/*.pdf 文本（可选，缺省时跳过并告警）
两者都是可选依赖，缺失不会导致提取失败，但语料会少对应块。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

GENERATOR = "qutwiki-rag-extractor/1.0"
SITE_BASE = "https://wiki.quters.top"

RAG_DIR = Path(__file__).resolve().parent
REPO_ROOT = RAG_DIR.parent.parent  # code/rag/extract.py -> 仓库根目录

# 与 docs/.vitepress/config.ts 中的 directoryLabels 保持一致（只用于元数据打标）
DIR_LABELS = {
    "preface": "序言",
    "newstudent": "新生入学",
    "campus-life": "校园生活",
    "campus-life/study": "学习学业",
    "campus-life/systems": "校园系统",
    "campus-life/daily-life": "生活日常",
    "campus-life/qut-organization": "QUT-组织",
    "campus-life/competition": "竞赛/战队",
    "about": "关于",
}
TOP_LABELS = {
    "": "站点",
    "index": "站点",
    "map": "站点",
    "flink": "站点",
}

# 无标题页面的兜底标题
TITLE_FALLBACK = {
    "index": "QUTWiKi 首页",
    "map": "校园地图",
    "flink": "友情链接",
}

# Markdown 扫描时跳过的目录（构建产物 / 依赖 / 内部数据）
SKIP_DIRS = {"node_modules", "dist", "cache", ".vitepress", ".http_cache", ".playwright-mcp", "public"}

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([^\s`~]*)\s*(.*?)\s*$")

TABLE_GROUP_COLS = (
    "校区", "业务指导单位", "指导单位", "分类", "类别", "类型", "部门", "学院",
    "分组", "所属", "标签", "备注",
)

# 只保留文本、丢弃整个组件的空组件
DROP_COMPONENTS = (
    "PosterCards", "MapView", "FoodCards", "GitHistory", "SiteStats",
    "Contributors", "TwikooComments", "PosterCard", "Gallery",
)


class ExtractionError(RuntimeError):
    """依赖缺失或源文件解析失败。

    抽取阶段绝不允许“告警后继续”导致静默丢块：表格/地图解析失败、必需依赖缺失
    必须让调用方失败退出。PDF 未安装或扫描件无文本层属于明确的可选能力，仍只告警。
    """


def _import_openpyxl():
    """导入 xlsx 解析库；openpyxl 是生产抽取的必需依赖。"""
    try:
        from openpyxl import load_workbook
    except ImportError as e:  # pragma: no cover - 依赖缺失分支由测试 patch 覆盖
        raise ExtractionError(
            "缺少必需依赖 openpyxl，无法抽取 xlsx 表格块；"
            "生产构建不允许静默丢块。请安装：py -3 -m pip install openpyxl"
        ) from e
    return load_workbook


def require_openpyxl():
    """供 build_index 在抽取前做硬性依赖检查。"""
    return _import_openpyxl()


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------
def sha1_file(p: Path) -> str:
    h = hashlib.sha1()
    with p.open("rb") as f:
        for buf in iter(lambda: f.read(1 << 20), b""):
            h.update(buf)
    return h.hexdigest()


def mtime_iso(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")


def join_lines(pairs) -> str:
    return "\n".join(t for _, t in pairs)


def collapse_blank(text: str) -> str:
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip("\n")


def esc_table_cell(v) -> str:
    s = "" if v is None else str(v)
    s = s.replace("\r", "").replace("\n", "；").strip()
    s = s.replace("|", "\\|")
    return s


def approx_tokens(text: str) -> int:
    """粗略 token 估算：中日韩字符 ≈ 1 token，其它 ≈ 4 字符/token"""
    cjk = len(re.findall(r"[\u3000-\u9fff\uff00-\uffef]", text))
    other = max(len(text) - cjk, 0)
    return cjk + math.ceil(other / 4)


CHUNK_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def fnv1a32(value: str) -> str:
    """与站点 plugins/source-lines.ts 的 fnv1a32 保持一致（UTF-16 码元）"""
    data = (value or "").encode("utf-16-le")
    h = 0x811C9DC5
    for i in range(0, len(data), 2):
        h ^= data[i] | (data[i + 1] << 8)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def collect_images(lines: list[tuple[int, str]], limit: int = 24) -> list[dict]:
    """从块的源文件行里收集图片（去重、保序）。

    带上行号后生成的 id 与站点 `plugins/source-lines.ts` 完全一致：
    `img-<src哈希>-<源文件行号>`，同一张图在页面里出现多次也能指到正确位置。
    """
    out, seen = [], set()
    for lineno, text in lines or []:
        for m in CHUNK_IMAGE_RE.finditer(text or ""):
            src = m.group(2).strip()
            if not src or src in seen:
                continue
            seen.add(src)
            out.append({
                "alt": m.group(1).strip(),
                "src": src,
                "id": f"img-{fnv1a32(src)}-{lineno}",
                "line": lineno,
            })
            if len(out) >= limit:
                return out
    return out


# --------------------------------------------------------------------------
# frontmatter
# --------------------------------------------------------------------------
def parse_frontmatter(text: str):
    """返回 (frontmatter dict, body, body 起始行号)"""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text, 1
    for i in range(1, min(len(lines), 100)):
        if lines[i].strip() in ("---", "..."):
            raw = "\n".join(lines[1:i])
            return parse_simple_yaml(raw), "\n".join(lines[i + 1:]), i + 2
    return {}, text, 1


def parse_simple_yaml(raw: str) -> dict:
    """极简 YAML：只取顶层 key，嵌套内容原样保存为字符串"""
    out: dict = {}
    cur = None
    buf: list[str] = []
    for line in raw.split("\n"):
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m and not line.startswith((" ", "\t")):
            if cur is not None:
                out[cur] = _yaml_value("\n".join(buf))
            cur = m.group(1)
            buf = [m.group(2)]
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out[cur] = _yaml_value("\n".join(buf))
    return out


def _yaml_value(v: str):
    v = v.strip()
    if v == "":
        return None
    if "\n" in v:
        return v
    if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
        return v[1:-1]
    if v in ("true", "True"):
        return True
    if v in ("false", "False"):
        return False
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


# --------------------------------------------------------------------------
# Markdown 清洗（VitePress 组件 / HTML / 容器语法）
# --------------------------------------------------------------------------
@dataclass
class CleanResult:
    lines: list = field(default_factory=list)      # [(lineno, text)]
    components: list = field(default_factory=list)  # 遇到的组件名
    xlsx_specs: list = field(default_factory=list)  # xlsx 代码块声明
    links: list = field(default_factory=list)
    images: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)   # git 冲突标记行号
    notes: list = field(default_factory=list)
    had_script_setup: bool = False


def _script_records(block: str) -> list[str]:
    """从 <script setup> 里提取 { name, tags, links } 形式的名单（如贡献者页）"""
    records, seen = [], set()
    for m in re.finditer(r"name:\s*'([^']+)'", block):
        name = m.group(1).strip()
        if not name or name in seen:
            continue
        tail = block[m.end(): m.end() + 600]
        if "tags:" not in tail and "links:" not in tail:
            continue
        seen.add(name)
        line = f"- {name}"
        tm = re.search(r"tags:\s*\[([^\]]*)\]", tail, re.S)
        tags = [t.strip() for t in re.findall(r"'([^']*)'", tm.group(1))] if tm else []
        tags = [t for t in tags if t]
        if tags:
            line += "（" + "、".join(tags) + "）"
        lm = re.search(r"links:\s*\[(.*?)\]\s*,?\s*\}", tail, re.S)
        urls = re.findall(r"url:\s*'([^']+)'", lm.group(1)) if lm else []
        if urls:
            line += "（" + "，".join(urls[:2]) + "）"
        records.append(line)
    return records



def _component_bullets(body: str) -> tuple[list[str], list[dict]]:
    """解析 <AppCards :links="[{...}]" /> 的 JS 对象数组"""
    bullets, links = [], []
    for obj in re.findall(r"\{([^{}]*)\}", body, flags=re.S):
        attrs = {}
        for k, q, val in re.findall(r"(\w+)\s*:\s*(['\"])(.*?)\2", obj, flags=re.S):
            attrs.setdefault(k, val.strip())
        name = attrs.get("text") or attrs.get("name") or attrs.get("title")
        if not name:
            continue
        desc = attrs.get("desc") or attrs.get("descr") or attrs.get("description") or ""
        url = attrs.get("link") or attrs.get("url") or ""
        line = f"- {name}"
        if desc:
            line += f"：{desc}"
        if url and not url.startswith(("http://", "https://")):
            url = ""
        if url:
            line += f"（{url}）"
            links.append({"text": name, "url": url})
        bullets.append(line)
    return bullets, links


def _flink_bullets(body: str) -> tuple[list[str], list[dict]]:
    """解析 flink 容器里的 YAML 风格列表"""
    records, cur = [], None
    for line in body.split("\n"):
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^-\s*([A-Za-z_]+)\s*:\s*(.*)$", s)
        if m:
            if cur:
                records.append(cur)
            cur = {m.group(1): m.group(2).strip()}
            continue
        m = re.match(r"^([A-Za-z_]+)\s*:\s*(.*)$", s)
        if m and cur is not None:
            cur[m.group(1)] = m.group(2).strip()
    if cur:
        records.append(cur)

    bullets, links = [], []
    for r in records:
        name = r.get("name") or r.get("text")
        if not name:
            continue
        desc = r.get("descr") or r.get("desc") or ""
        url = r.get("link") or r.get("url") or ""
        if not url.startswith(("http://", "https://")):
            url = ""
        line = f"- {name}"
        if desc:
            line += f"：{desc}"
        if url:
            line += f"（{url}）"
            links.append({"text": name, "url": url})
        bullets.append(line)
    return bullets, links


def _inline_html(line: str, st: CleanResult, lineno: int) -> str:
    # 行内代码先占位，避免里面的 < > 被当成 HTML 标签
    codes: list[str] = []

    def stash(m):
        codes.append(m.group(0))
        return f"\x01{len(codes) - 1}\x01"

    line = re.sub(r"`[^`\n]*`", stash, line)

    # <h1..h6 align="center">X</h1>
    m = re.match(r"^\s*<h([1-6])[^>]*>(.*?)</h\1>\s*$", line)
    if m:
        line = "#" * int(m.group(1)) + " " + m.group(2).strip()
    line = re.sub(r"</?h([1-6])[^>]*>", "", line)
    if line.lstrip().startswith("|"):  # 表格行内的 <br> 不能用换行，否则拆行
        line = re.sub(r"<br\s*/?>", "；", line, flags=re.I)
        line = re.sub(r"([。！？，；、])\s*；", r"\1", line)
    else:
        line = re.sub(r"<br\s*/?>", "\n", line, flags=re.I)

    def img_sub(m):
        tag = m.group(0)
        if re.search(r"(v-if|v-else|:src|\{\{)", tag):
            return ""
        alt = re.search(r"alt\s*=\s*['\"]([^'\"]*)['\"]", tag)
        src = re.search(r"src\s*=\s*['\"]([^'\"]*)['\"]", tag)
        if src:
            st.images.append({"alt": alt.group(1) if alt else "", "src": src.group(1)})
        return f"\n[图片：{alt.group(1)}]\n" if alt and alt.group(1).strip() else ""

    line = re.sub(r"<img\b[^>]*>", img_sub, line, flags=re.I)
    line = re.sub(r"</?(div|span|p|article|section|center|picture|source|svg|path|a\b[^>]*)\s*/?>", " ", line, flags=re.I)
    line = re.sub(r"<[^>\n]{1,200}>", "", line)  # 残余标签
    line = re.sub(r"\x01(\d+)\x01", lambda m: codes[int(m.group(1))], line)
    return line


def clean_markdown(body: str, start_line: int = 1) -> CleanResult:
    st = CleanResult()
    raw_lines = body.split("\n")
    items = [(start_line + i, t) for i, t in enumerate(raw_lines)]

    # 源文件带 git 冲突标记时，直接丢弃标记行（保留两侧内容）
    has_conflict = any(re.match(r"^<{7}(\s|$)", t) for _, t in items)

    i = 0
    out: list[tuple[int, str]] = []
    while i < len(items):
        lineno, line = items[i]
        stripped = line.strip()

        # --- 代码块（支持 ``` / ~~~ 以及 4 个以上反引号嵌套）---
        m = FENCE_RE.match(line)
        if m and not re.match(r"^\s*`{1,2}\s*$", line):
            marker = m.group(2)
            fch, flen = marker[0], len(marker)
            lang, info = m.group(3).lower(), m.group(4)
            close_re = re.compile(rf"^\s*{re.escape(fch)}{{{flen},}}\s*$")
            j, buf = i + 1, []
            while j < len(items):
                if close_re.match(items[j][1]):
                    break
                buf.append(items[j][1])
                j += 1
            if lang.startswith("xlsx"):
                spec = info.strip()
                st.xlsx_specs.append({"spec": spec, "line": lineno})
                sheet = ""
                mm = re.search(r"(?:table|sheet)=([^&\s]+)", spec) or re.search(r"#(.+)$", spec)
                if mm:
                    sheet = mm.group(1)
                out.append((lineno, f"（表格数据：{sheet or '见 tables 目录'}，已单独抽取为表格块）"))
            else:
                out.append((items[i][0], marker + lang))
                for k, b in enumerate(buf):
                    out.append((items[i + 1 + k][0], b))
                out.append((items[j][0] if j < len(items) else lineno, marker))
            i = j + 1
            continue

        # --- script / style / HTML 注释块 ---
        if re.match(r"^\s*<(script|style)\b", line, flags=re.I) or stripped.startswith("<!--"):
            tag = None
            ms = re.match(r"^\s*<(script|style)\b", line, flags=re.I)
            if ms:
                tag = ms.group(1).lower()
            j = i
            while j < len(items):
                if tag and re.search(rf"</{tag}\s*>", items[j][1], flags=re.I):
                    break
                if not tag and "-->" in items[j][1]:
                    break
                j += 1
            if tag == "script":
                block = "\n".join(t for _, t in items[i:j + 1])
                records = _script_records(block)
                if not records and re.search(r"\bname\s*:", block):
                    raise ExtractionError(
                        f"第 {lineno} 行 <script> 中的名单解析失败；拒绝静默丢弃名单"
                    )
                if records:
                    st.components.append("script-data")
                    # 脚本里的名单通常是贡献者；补一句可检索的说明，避免只有人名、没有语义关键词
                    out.append((lineno, "青理WiKi（QUTWiKi）贡献者名单：作者、编写者、维护者、资料整理者（由页面脚本数据生成）"))
                    out.extend((lineno, b) for b in records)
                if "setup" in block[:200]:
                    st.had_script_setup = True
            st.notes.append(f"第 {lineno} 行：跳过 {'<' + tag + '>' if tag else 'HTML 注释'} 块")
            i = j + 1
            continue

        # --- AppCards 组件（多行） ---
        if re.match(r"^\s*<AppCards\b", line):
            j = i
            buf = [line]
            while j < len(items) and "/>" not in items[j][1]:
                j += 1
                if j < len(items):
                    buf.append(items[j][1])
            for b in buf:
                if "/>" in b:
                    buf[buf.index(b)] = b.split("/>")[0]
            raw = "\n".join(buf)
            bullets, links = _component_bullets(raw)
            if not bullets and re.search(r"\b(?:text|name|title)\s*:", raw):
                raise ExtractionError(
                    f"第 {lineno} 行 <AppCards> 未解析出任何条目；拒绝静默丢失卡片内容"
                )
            st.components.append("AppCards")
            st.links.extend(links)
            out.extend((lineno, x) for x in bullets)
            i = j + 1
            continue

        # --- flink 容器 / 单标签 ---
        if re.match(r"^\s*<flink>\s*$", line, flags=re.I):
            j = i + 1
            buf = []
            while j < len(items) and not re.search(r"</flink>", items[j][1], flags=re.I):
                buf.append(items[j][1])
                j += 1
            raw = "\n".join(buf)
            bullets, links = _flink_bullets(raw)
            if not bullets and re.search(r"^\s*-\s*(?:name|text)\s*:", raw, re.M):
                raise ExtractionError(
                    f"第 {lineno} 行 <flink> 未解析出任何条目；拒绝静默丢失友链卡片"
                )
            st.components.append("flink")
            st.links.extend(links)
            out.extend((lineno, x) for x in bullets)
            i = j + 1
            continue
        if re.match(r"^\s*<flink\b", line, flags=re.I):
            j = i
            buf = [line]
            while j < len(items) and "/>" not in items[j][1] and "</flink>" not in items[j][1]:
                j += 1
                if j < len(items):
                    buf.append(items[j][1])
            attrs = dict(re.findall(r"([A-Za-z_]+)\s*=\s*['\"]([^'\"]*)['\"]", "\n".join(buf)))
            name = attrs.get("name", "")
            if not name:
                raise ExtractionError(
                    f"第 {lineno} 行 <flink> 缺少 name 属性；拒绝静默丢弃该友链"
                )
            desc = attrs.get("desc") or attrs.get("descr") or ""
            url = attrs.get("link", "")
            st.links.append({"text": name, "url": url})
            out.append((lineno, f"- {name}：" + (f"{desc}（{url}）" if desc else url)))
            st.components.append("flink")
            i = j + 1
            continue

        # --- 空组件 ---
        mcomp = re.match(r"^\s*<(" + "|".join(DROP_COMPONENTS) + r")\b[^>]*/?>\s*$", line)
        if mcomp:
            st.components.append(mcomp.group(1))
            i += 1
            continue
        # 成对出现的 Gallery 标签：保留内部内容
        if re.match(r"^\s*</?Gallery\b[^>]*>\s*$", line, flags=re.I):
            st.components.append("Gallery")
            i += 1
            continue

        # --- 普通行 ---
        if has_conflict and re.match(r"^(<{7}|={7}|>{7})(\s|$)", stripped):
            st.conflicts.append(lineno)
            i += 1
            continue
        if stripped.startswith("<<<<<<<") or stripped.startswith(">>>>>>>"):
            st.conflicts.append(lineno)
        line = _inline_html(line, st, lineno)
        # ::: 容器
        mc = re.match(r"^\s*:::\s*(\w*)\s*(.*?)\s*$", line)
        if mc:
            kind, title = mc.group(1).lower(), mc.group(2)
            if kind and title and kind not in ("tip", "info", "warning", "danger", "details"):
                out.append((lineno, f"**{title}**"))
            elif title and kind:
                out.append((lineno, f"**{title}**"))
            i += 1
            continue
        line = line.replace("\u200b", "").replace("\xa0", " ")
        line = unescape(line).rstrip()
        for k, seg in enumerate(line.split("\n")):
            out.append((lineno, seg))
        i += 1

    # 含 <script setup> 的页面：丢弃 Vue 模板残留（v-for / {{ }} / 多行 HTML 属性）
    if st.had_script_setup:
        kept = []
        for n, t in out:
            s = t.strip()
            if "{{" in t or "}}" in t:
                continue
            if re.match(r"^(v-[\w-]+|:[\w-]+|@[\w-]+|class|target|rel|aria-[\w-]+|title|viewBox|fill|d|width|height)\s*=", s):
                continue
            if re.match(r"^</?(article|div|span|a|svg|path|template|img|picture|source)\b", s, flags=re.I):
                continue
            kept.append((n, t))
        out = kept

    # 收集行内链接 / 图片
    joined = "\n".join(t for _, t in out)
    for m in re.finditer(r"(?<!!)\[([^\]\n]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", joined):
        st.links.append({"text": m.group(1).strip(), "url": m.group(2).strip()})
    for m in re.finditer(r"!\[([^\]]*)\]\(([^)\s]+)", joined):
        st.images.append({"alt": m.group(1).strip(), "src": m.group(2).strip()})

    # 去重 & 去空行
    seen, links = set(), []
    for l in st.links:
        key = (l["text"], l["url"])
        if key in seen or not l["url"]:
            continue
        seen.add(key)
        links.append(l)
    st.links = links

    st.lines = [(n, t) for n, t in out]
    return st


# --------------------------------------------------------------------------
# Markdown -> 纯文本
# --------------------------------------------------------------------------
def to_plain(md: str) -> str:
    t = md
    t = re.sub(r"```[^\n]*\n", "", t)
    t = t.replace("```", "")
    t = re.sub(r"!\[[^\]]*\]\([^)\s]+\)", "", t)

    def link(m):
        text, url = m.group(1).strip(), m.group(2).strip()
        if not url or url.startswith(("#", "mailto:")) or text == url:
            return text
        if url.startswith("/"):
            return f"{text}（{SITE_BASE}{url}）"
        if not url.startswith(("http://", "https://")):
            return text
        return f"{text}（{url}）"

    t = re.sub(r"\[([^\]\n]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", link, t)
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", t)
    t = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"\1", t)
    t = re.sub(r"^\s*>\s?", "", t, flags=re.M)
    t = re.sub(r"^\s*\|?[\s:-]*\|[\s:|-]*$", "", t, flags=re.M)  # 表格分隔行
    t = re.sub(r"^\s*([-*+])\s+", "- ", t, flags=re.M)
    t = re.sub(r"`([^`\n]+)`", r"\1", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return collapse_blank(t)


# --------------------------------------------------------------------------
# 纯组件页：从 frontmatter 配置补全可读文本
# --------------------------------------------------------------------------
def synthesize_from_frontmatter(fm: dict) -> str:
    """首页/落地页正文为空时，把 hero / features 配置转成可检索文本"""
    lines = []
    hero = fm.get("hero")
    if isinstance(hero, str):
        def f(key):
            m = re.search(rf"^\s*{re.escape(key)}:\s*'?([^'\n]+)'?\s*$", hero, re.M)
            return m.group(1).strip() if m else ""

        name, text, tagline = f("name"), f("text"), f("tagline")
        if name or text or tagline:
            lines.append("# " + (name or text))
            for s in (text, tagline):
                if s and s != name:
                    lines.append(s)
        actions = re.findall(r"-\s*theme:\s*\w+\s*\n\s*text:\s*'?([^'\n]+)'?\s*\n\s*link:\s*'?([^'\n]+)'?", hero)
        if actions:
            lines.append("## 页面入口")
            for t, l in actions:
                lines.append(f"- {t.strip()}：{l.strip()}")

    feats = fm.get("features")
    if isinstance(feats, str):
        blocks = re.findall(r"-\s*icon:\s*(\S+)\s*\n\s*title:\s*'?([^'\n]+)'?\s*\n\s*details:\s*'?([^'\n]+)'?\s*\n\s*link:\s*'?([^'\n]+)'?", feats)
        if blocks:
            lines.append("## 栏目")
            for icon, t, d, l in blocks:
                lines.append(f"- {t.strip()}（{icon.strip()}）：{d.strip()}（{l.strip()}）")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 分块
# --------------------------------------------------------------------------
@dataclass
class Block:
    level: int
    heading: str
    path: list
    lines: list          # [(lineno, text)]
    extra: list = field(default_factory=list)  # 合并进来的其它小节标题

    @property
    def md(self) -> str:
        return join_lines(self.lines).strip()

    @property
    def line_range(self):
        nums = [n for n, _ in self.lines if n]
        return (min(nums), max(nums)) if nums else (0, 0)


def split_sections(lines: list) -> list[Block]:
    """按 H1..H6 切分为区块，保留行号"""
    blocks: list[Block] = []
    stack: list[tuple[int, str]] = []
    cur = Block(level=0, heading="", path=[], lines=[])
    in_code = False
    for lineno, text in lines:
        if text.strip().startswith("```"):
            in_code = not in_code
        m = HEADING_RE.match(text) if not in_code else None
        if m:
            if cur.lines:
                blocks.append(cur)
            level = len(m.group(1))
            heading = m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading))
            cur = Block(level=level, heading=heading, path=[h for _, h in stack], lines=[(lineno, text)])
        else:
            cur.lines.append((lineno, text))
    if cur.lines:
        blocks.append(cur)
    return blocks


def _hard_split(block: Block, max_chars: int, overlap: int) -> list[Block]:
    """长区块按段落/句子切分，带 overlap"""
    paras: list[list[tuple[int, str]]] = []
    cur: list[tuple[int, str]] = []
    for ln, t in block.lines:
        if t.strip() == "":
            if cur:
                paras.append(cur)
            cur = []
        else:
            cur.append((ln, t))
    if cur:
        paras.append(cur)

    # 单个段落过长 -> 按句子切
    units: list[list[tuple[int, str]]] = []
    for p in paras:
        text = "\n".join(t for _, t in p)
        if len(text) <= max_chars:
            units.append(p)
            continue
        sentences = re.split(r"(?<=[。！？!?；;])", text)
        buf_lines: list[tuple[int, str]] = []
        buf_len = 0
        for s in sentences:
            if not s:
                continue
            if buf_len + len(s) > max_chars and buf_lines:
                units.append(buf_lines)
                buf_lines, buf_len = [], 0
            buf_lines.append((p[0][0], s))
            buf_len += len(s)
        if buf_lines:
            units.append(buf_lines)

    # 合并成 chunk
    chunks: list[list[tuple[int, str]]] = []
    buf: list[tuple[int, str]] = []
    buf_len = 0
    for u in units:
        ulen = sum(len(t) + 1 for _, t in u)
        if buf and buf_len + ulen > max_chars:
            chunks.append(buf)
            tail = ""
            if overlap:
                seg = join_lines(buf)[-overlap:]
                nl = seg.find("\n")
                # 只取完整行，避免把 markdown 链接/图片截断
                tail = seg[nl + 1:] if nl != -1 else ""
                tail = tail.strip()
            buf = ([(buf[-1][0], tail)] if tail else []) + u
            buf_len = len(tail) + ulen
        else:
            buf.extend(u)
            buf_len += ulen
    if buf:
        chunks.append(buf)

    out = []
    for c in chunks:
        out.append(Block(level=block.level, heading=block.heading, path=list(block.path), lines=c))
    return out


def build_chunks(lines: list, max_chars: int, min_chars: int, overlap: int) -> list[Block]:
    blocks = split_sections(lines)

    # 1) 以 level<=2 的标题为主块（H1 如果紧跟 H2，则 H1 自身内容成块）
    primary: list[Block] = []
    for b in blocks:
        if b.level <= 2:
            primary.append(b)
        elif primary:
            primary[-1].lines.extend(b.lines)
        else:
            primary.append(b)

    # 2) 太长的主块：先按 H3 拆（重新扫描），再硬切
    result: list[Block] = []
    for b in primary:
        if len(b.md) <= max_chars:
            result.append(b)
            continue
        sub_blocks = split_sections(b.lines)
        if len(sub_blocks) > 1:
            for sb in sub_blocks:
                if sb.path and b.path and sb.path[0] == b.path[-1]:
                    sb.path = list(b.path[:-1]) + sb.path  # 补回父级标题
                elif not sb.path:
                    sb.path = list(b.path)
                if len(sb.md) > max_chars:
                    result.extend(_hard_split(sb, max_chars, overlap))
                else:
                    result.append(sb)
        else:
            result.extend(_hard_split(b, max_chars, overlap))

    # 3) 合并过短的相邻块（同一 H1 下）
    merged: list[Block] = []
    for b in result:
        if merged and b.md and merged[-1].md:
            same_h1 = (b.path[0] if b.path else "") == (merged[-1].path[0] if merged[-1].path else "")
            combined = len(merged[-1].md) + len(b.md)
            small = min(len(merged[-1].md), len(b.md))
            cap = max(min_chars * 2, 480) if small >= 60 else 700
            if same_h1 and combined <= cap and (
                len(merged[-1].md) < min_chars or len(b.md) < min_chars
            ):
                merged[-1].lines.append((b.line_range[0], ""))
                merged[-1].lines.extend(b.lines)
                if b.path and b.path != merged[-1].path:
                    label = b.path[-1]
                    if label and label not in merged[-1].extra:
                        merged[-1].extra.append(label)
                continue
        merged.append(b)
    return merged


# --------------------------------------------------------------------------
# 文档处理
# --------------------------------------------------------------------------
def doc_id_for(rel: str) -> str:
    rid = rel.replace("\\", "/")
    if rid.endswith(".md"):
        rid = rid[:-3]
    return rid


def category_for(doc_id: str) -> str:
    if doc_id in TOP_LABELS:
        return TOP_LABELS[doc_id]
    parts = doc_id.split("/")
    if parts and parts[0] == "start":
        parts = parts[1:]
        labels = []
        for i in range(1, len(parts)):
            key = "/".join(parts[:i])
            labels.append(DIR_LABELS.get(key, parts[i - 1]))
        return " / ".join(labels) if labels else "关于"
    return "站点"


def site_url(doc_id: str) -> str:
    if doc_id == "index":
        return f"{SITE_BASE}/"
    return f"{SITE_BASE}/{doc_id}"


def detect_site_owner(root: Path) -> str:
    """从源文档里找“本站站长 XXX”，用于给贡献者块补一条可检索的说明"""
    for p in sorted(root.rglob("*.md")):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = re.search(r"本站站长[：:\s]*([A-Za-z0-9_.\-]+)", text)
        if m:
            return m.group(1)
    return ""


def changelog_lead(md: str) -> str:
    """更新日志首条通常记录了建站/上线；生成一行可检索的说明（不改变原文事实）"""
    m = re.search(r"^\s*-\s*(?:\*\*)?(20\d{2}年\d{1,2}月\d{1,2}日)(?:\*\*)?\s*$", md, re.M)
    if not m:
        return ""
    tail = md[m.end():m.end() + 400]
    e = re.search(r"-\s*([^\n]*(?:初始化|搭建|创建|上线)[^\n]*)", tail)
    if not e:
        return ""
    return f"站点建立/上线时间：{m.group(1)}（{e.group(1).strip()}）"


def process_md(path: Path, root: Path, max_chars: int, min_chars: int, overlap: int,
               site_owner: str = "") -> tuple[dict, list[dict]]:
    rel = path.relative_to(root).as_posix()
    did = doc_id_for(rel)
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, body, body_start = parse_frontmatter(text)
    try:
        clean = clean_markdown(body, body_start)
    except ExtractionError as e:
        raise ExtractionError(f"{path}: {e}") from e
    md = collapse_blank(join_lines(clean.lines))
    synth = None
    if len(to_plain(md)) < 40:
        extra = synthesize_from_frontmatter(fm)
        if extra:
            md = collapse_blank((md + "\n\n" + extra) if md else extra)
            synth = "frontmatter"

    # 站点元信息（站长、建站时间）在原页面里只以零散句子出现，补成可检索的说明，
    # 事实仍来自语料本身，不引入外部信息。必须改 clean.lines，分块才会带上。
    if did == "start/about/contributors" and site_owner:
        clean.lines = [
            (n, t.replace("资料整理者（由页面脚本数据生成）",
                          f"资料整理者；本站站长：{site_owner}（由页面脚本数据生成）", 1))
            for n, t in clean.lines
        ]
        md = collapse_blank(join_lines(clean.lines))
    if did == "start/about/changelog":
        lead = changelog_lead(md)
        if lead:
            out = []
            inserted = False
            for n, t in clean.lines:
                out.append((n, t))
                if not inserted and re.match(r"^#\s+", t):
                    out.append((n, lead))
                    inserted = True
            if inserted:
                clean.lines = out
                md = collapse_blank(join_lines(clean.lines))

    comps = sorted(set(clean.components))
    if not to_plain(md):
        note = f"页面「{TITLE_FALLBACK.get(did, did)}」为交互式组件页面：{'、'.join(comps) or '无'}，源文件本身没有静态正文。"
        if "MapView" in comps:
            note += "校园地图的建筑点位、分类与描述已单独抽取为表格块（tables/map-data.BUILDINGS）。"
        md = note
        synth = "component"

    plain = to_plain(md)
    headings = [HEADING_RE.match(l).group(2) for l in md.split("\n") if HEADING_RE.match(l)]
    title = (fm.get("title") or (headings[0] if headings else "") or TITLE_FALLBACK.get(did) or path.stem).strip()

    warnings = []
    if clean.conflicts:
        warnings.append(f"源文件存在 git 合并冲突标记（行 {', '.join(map(str, clean.conflicts))}），标记行已剥离，两侧内容保留")
    if clean.xlsx_specs:
        warnings.append("包含 xlsx 表格块，表格内容已单独抽取为表格块")
    if synth == "frontmatter":
        warnings.append("源文件无静态正文，正文由 frontmatter（hero/features）补全")
    elif synth == "component":
        warnings.append("源文件只有交互式组件，正文为占位说明")
    if len(plain) < 120 and not synth:
        warnings.append("正文极短，真实内容可能在组件/远程数据中（如评论、卡片数据）")

    doc = OrderedDict(
        id=did,
        title=title,
        description=fm.get("description"),
        category=category_for(did),
        source_path=f"docs/{rel}",
        source_sha1=sha1_file(path),
        source_mtime=mtime_iso(path),
        url=site_url(did),
        frontmatter=OrderedDict((k, (v if not isinstance(v, str) or len(v) < 4000 else v[:4000])) for k, v in fm.items()),
        headings=headings,
        components=comps,
        table_refs=[s["spec"] for s in clean.xlsx_specs],
        links=clean.links[:200],
        images=clean.images[:100],
        char_count=len(plain),
        token_estimate=approx_tokens(plain),
        warnings=warnings,
        markdown=md,
        text=plain,
    )

    src_lines = clean.lines if not synth else [(0, l) for l in md.split("\n")]
    blocks = build_chunks(src_lines, max_chars, min_chars, overlap)
    chunks = []
    for idx, b in enumerate(blocks):
        bmd = collapse_blank(b.md)
        if not bmd:
            continue
        bplain = to_plain(bmd)
        if len(bplain) < 25:
            continue
        # 纯“表格占位说明”的块没有回答价值，表格块才是真内容
        if "已单独抽取为表格块" in bplain and len(bplain) < 100:
            continue
        path_list = [p for p in b.path if p] or [title]
        start, end = b.line_range
        cid = f"{did}#{len(chunks) + 1:03d}"
        bimgs = collect_images(b.lines)

        # 正文开头常常就是本节标题，避免 embed_text 里重复
        body = bplain
        if path_list and body.startswith(path_list[-1]):
            body = body[len(path_list[-1]):].lstrip(" \n：:")
        embed = ((" > ".join(path_list) + "\n\n") if path_list else "") + (body or bplain)

        chunks.append(OrderedDict(
            id=cid,
            doc_id=did,
            chunk_index=len(chunks) + 1,
            type="doc",
            title=title,
            heading_path=path_list,
            section=(path_list[-1] if path_list else title),
            sections=[(path_list[-1] if path_list else title)] + list(b.extra),
            category=doc["category"],
            source_path=doc["source_path"],
            url=doc["url"],
            anchor=path_list[-1] if path_list else "",
            markdown=bmd,
            text=bplain,
            embed_text=embed,
            char_len=len(bplain),
            token_estimate=approx_tokens(bplain),
            line_start=start,
            line_end=end,
            has_table=bmd.count("|") > 4,
            has_code="```" in bmd,
            image_count=len(bimgs),
            images=bimgs,
            source_sha1=doc["source_sha1"],
        ))
    return doc, chunks


# --------------------------------------------------------------------------
# 表格（xlsx）
# --------------------------------------------------------------------------
def norm_cell(v) -> str:
    """清洗单元格：处理 Excel 换行转义、多行内容"""
    s = "" if v is None else str(v)
    s = s.replace("_x000d_", "；").replace("_x000a_", "；").replace("_x000D_", "；")
    s = s.replace("\r", "；").replace("\n", "；")
    s = re.sub(r"[；;]{2,}", "；", s)
    s = re.sub(r"[；;]\s*、\s*", "、", s)
    s = re.sub(r"、\s*[；;]\s*", "、", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip(" ；\t")


def read_xlsx(path: Path) -> "OrderedDict[str, list[list]]":
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True, read_only=True)
    sheets = OrderedDict()
    for name in wb.sheetnames:
        ws = wb[name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            vals = [norm_cell(v) for v in row]
            while vals and vals[-1] == "":
                vals.pop()
            rows.append(vals)
        while rows and not any(c for c in rows[-1]):
            rows.pop()
        rows = [r for r in rows if any(c for c in r)]
        sheets[name] = rows
    wb.close()
    return sheets


def sheet_to_markdown(rows: list[list]) -> str:
    if not rows:
        return "（空表）"
    width = max(len(r) for r in rows)
    norm = [r + [""] * (width - len(r)) for r in rows]
    header = norm[0]
    # 表头去重 / 补空
    seen = {}
    head = []
    for i, h in enumerate(header):
        h = esc_table_cell(h) or f"列{i + 1}"
        if h in seen:
            seen[h] += 1
            h = f"{h}_{seen[h]}"
        else:
            seen[h] = 1
        head.append(h)
    out = ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] * width) + "|"]
    for r in norm[1:]:
        out.append("| " + " | ".join(esc_table_cell(c) for c in r) + " |")
    body = "\n".join(out)
    note = ""
    if rows and all(len([c for c in rows[0] if c]) == 1 for _ in [0]) and len(rows) == 1:
        note = "\n\n（该工作表只有一段说明文字，不是数据表）"
    return body + note


def table_chunks(sheet: str, rows: list[list], table_id: str, meta: dict, max_chars: int = 1500) -> list[dict]:
    if not rows:
        return []
    header = [esc_table_cell(c) for c in rows[0]]
    body = rows[1:]
    if not body:  # 单行说明
        note = " ".join(str(c) for c in rows[0] if str(c).strip())
        return [OrderedDict(
            id=f"{table_id}#001", doc_id=table_id, chunk_index=1, type="table",
            title=meta["title"], heading_path=[meta["title"], sheet], section=sheet,
            sections=[sheet],
            category=meta["category"], source_path=meta["source_path"], url=meta.get("url"),
            anchor=sheet, markdown=f"# {sheet}\n\n" + note, text=note,
            embed_text=f"{meta['title']} > {sheet}\n\n{note}",
            char_len=len(note), token_estimate=approx_tokens(note),
            line_start=0, line_end=0, has_table=False, has_code=False, image_count=0,
            source_sha1=meta["sha1"], table_id=table_id, records=1,
        )]

    # 选取分组列：优先语义明确的列，其次是"取值少且短"的文本列；组太散则不分组
    n_rows = max(len(body), 1)
    min_group = max(3, int(n_rows * 0.4))
    key_idx = None
    for pref in TABLE_GROUP_COLS:
        if pref in header:
            i = header.index(pref)
            vals = [r[i] for r in body if i < len(r) and str(r[i]).strip()]
            if 1 < len(set(vals)) <= min(25, min_group):
                key_idx = i
                break
    if key_idx is None:
        for i, h in enumerate(header):
            if h in ("序号", "编号", "No", ""):
                continue
            vals = [r[i] for r in body if i < len(r) and str(r[i]).strip()]
            if 1 < len(set(vals)) <= min(15, min_group) and all(len(str(v)) <= 12 for v in set(vals)):
                key_idx = i
                break

    groups: "OrderedDict[str, list[list]]" = OrderedDict()
    for r in body:
        g = (str(r[key_idx]).strip() if key_idx is not None and key_idx < len(r) else "") or "其他"
        groups.setdefault(g, []).append(r)

    chunks_raw: list[tuple[list[str], list[str]]] = []  # (所属分组, 文本行)
    cur_lines: list[str] = []
    cur_size = 0
    cur_groups: list[str] = []

    def flush(carry: str | None = None):
        nonlocal cur_lines, cur_size, cur_groups
        if cur_lines:
            chunks_raw.append((cur_groups, cur_lines))
        cur_lines, cur_size, cur_groups = [], 0, []
        if carry:  # 大分组被切开时，续块补回分组标题
            cur_lines.append(carry)
            cur_size = len(carry) + 1
            cur_groups.append(carry.lstrip("# ").strip())

    for gname, grows in groups.items():
        heading = f"### {gname}" if key_idx is not None else ""
        block: list[str] = [heading] if heading else []
        for r in grows:
            name = ""
            for i, h in enumerate(header):
                if i == key_idx or h in ("序号", "编号"):
                    continue
                if i < len(r) and str(r[i]).strip():
                    name = f"{h}：{str(r[i]).strip()}"
                    break
            fields = []
            for i, h in enumerate(header):
                if i == key_idx or h in ("序号", "编号", "群头像链接", "头像"):
                    continue
                v = str(r[i]).strip() if i < len(r) else ""
                if not v or name.startswith(f"{h}："):
                    continue
                fields.append(f"{h}：{v}")
            block.append(f"- {name}" + ("；" + "；".join(fields) if fields else ""))

        bsize = sum(len(x) + 1 for x in block)
        if bsize > max_chars:  # 单组过大：逐行切
            for line in block:
                if heading and line == heading:
                    cur_lines.append(line)
                    cur_size += len(line) + 1
                    continue
                lsize = len(line) + 1
                if cur_lines and cur_size + lsize > max_chars:
                    flush(carry=heading or None)
                cur_lines.append(line)
                cur_size += lsize
        else:
            if cur_lines and cur_size + bsize > max_chars:
                flush()
            cur_lines.extend(block)
            cur_size += bsize
        if gname not in cur_groups:
            cur_groups.append(gname)
    flush()

    chunks = [_make_table_chunk(table_id, meta, sheet, groups_in, lines)
              for groups_in, lines in chunks_raw]
    for i, c in enumerate(chunks, 1):
        c["chunk_index"] = i
        c["id"] = f"{table_id}#{i:03d}"
    return chunks


def _make_table_chunk(table_id, meta, sheet, groups_in, lines) -> dict:
    gname = " / ".join(groups_in)
    md = f"## {sheet}\n\n" + "\n".join(lines)
    plain = to_plain("\n".join(lines))
    return OrderedDict(
        id="", doc_id=table_id, chunk_index=0, type="table",
        title=meta["title"], heading_path=[meta["title"], sheet] + list(groups_in[:3]),
        section=gname or sheet, sections=list(groups_in) or [sheet],
        category=meta["category"], source_path=meta["source_path"], url=meta.get("url"),
        anchor=sheet, markdown=md, text=plain,
        embed_text=f"{meta['title']} > {sheet}" + (f" > {gname}" if gname else "") + f"\n\n{plain}",
        char_len=len(plain), token_estimate=approx_tokens(plain),
        line_start=0, line_end=0, has_table=True, has_code=False, image_count=0,
        images=[],
        source_sha1=meta["sha1"], table_id=table_id,
        records=sum(1 for l in lines if l.startswith("- ")),
    )


TABLE_DOC_META = {
    "学生社团": ("学生社团", "校园生活 / QUT-组织", "start/campus-life/qut-organization/club"),
    "实验室": ("实验室", "校园生活 / QUT-组织", "start/campus-life/qut-organization/lab"),
    "兴趣群": ("兴趣群", "校园生活 / QUT-组织", "start/campus-life/qut-organization/interest-group"),
    "填写说明": ("QUT-Organization 填写说明", "校园生活 / QUT-组织", "start/campus-life/qut-organization"),
}


def extract_tables(root: Path, out_dir: Path, max_chars: int):
    """xlsx -> tables/*.md|csv + 表格块。缓存文件（站点实际渲染数据）优先。

    存在 xlsx 时若缺少 openpyxl 或任一文件解析失败，直接抛 ExtractionError，
    避免生成“少了一批表格块”但仍然成功的索引。
    """
    sources = []
    for sub in ("resources", ".http_cache"):
        d = root / sub
        if d.is_dir():
            for p in sorted(d.glob("*.xlsx")):
                sources.append((sub, p))
    if not sources:
        return [], [], []
    require_openpyxl()

    # 先判断哪些工作表被 markdown 通过腾讯文档 URL 引用（走 http_cache）
    cache_tables: "OrderedDict[str, dict]" = OrderedDict()
    local_tables: "OrderedDict[str, dict]" = OrderedDict()
    table_docs, chunks, warnings = [], [], []

    tables_dir = out_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    for old in list(tables_dir.glob("*.md")) + list(tables_dir.glob("*.csv")):
        old.unlink()  # tables/ 为生成目录，每次重建

    for sub, p in sources:
        try:
            sheets = read_xlsx(p)
        except Exception as e:  # noqa: BLE001
            raise ExtractionError(
                f"xlsx 解析失败：{p}（{type(e).__name__}: {e}）；"
                "拒绝跳过该表格以免索引静默缺块"
            ) from e
        if not any(sheets.values()):
            raise ExtractionError(
                f"xlsx 中没有可抽取的工作表数据：{p}；"
                "拒绝把空表当作正常结果，请检查同步文件是否损坏"
            )
        for sheet, rows in sheets.items():
            if not rows:
                continue
            label, cat, url_doc = TABLE_DOC_META.get(sheet, (sheet, "数据表格", ""))
            tid = f"tables/{p.stem}#{sheet}"
            meta = {
                "title": label,
                "category": cat,
                "source_path": f"docs/{sub}/{p.name}",
                "url": f"{SITE_BASE}/{url_doc}" if url_doc else None,
                "sha1": sha1_file(p),
            }
            entry = {"tid": tid, "sheet": sheet, "rows": len(rows), "meta": meta,
                     "file": p.name, "kind": sub, "rows_data": rows,
                     "safe": re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", f"{p.stem}.{sheet}")}
            target = cache_tables if sub == ".http_cache" else local_tables
            prev = target.get(sheet)
            if prev is None or entry["rows"] > prev["rows"]:
                target[sheet] = entry

    # 站点渲染用的是 .http_cache（腾讯文档同步结果），同名表以缓存为准
    merged: "OrderedDict[str, dict]" = OrderedDict()
    for sheet, e in local_tables.items():
        merged[sheet] = e
    for sheet, e in cache_tables.items():
        if sheet in merged:
            warnings.append(f"工作表「{sheet}」同时存在于本地 xlsx 与站点缓存，采用缓存版本"
                            f"（{e['rows']} 行，本地 {merged[sheet]['rows']} 行），本地版本未导出")
        merged[sheet] = e

    if sources and not merged:
        raise ExtractionError(
            f"找到 {len(sources)} 个 xlsx 文件，但没有任何可抽取的工作表数据；"
            "拒绝生成缺少表格块的语料"
        )

    for sheet, e in merged.items():
        meta = e["meta"]
        md = sheet_to_markdown(e["rows_data"])
        (tables_dir / f"{e['safe']}.md").write_text(
            f"# {meta['title']} - {sheet}\n\n> 来源：{meta['source_path']}\n\n{md}\n", encoding="utf-8")
        with (tables_dir / f"{e['safe']}.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            for r in e["rows_data"]:
                w.writerow(["" if c is None else c for c in r])

        tchunks = table_chunks(sheet, e["rows_data"], e["tid"], meta, max_chars)
        chunks.extend(tchunks)
        table_docs.append(OrderedDict(
            id=e["tid"], title=meta["title"], sheet=sheet, source_path=meta["source_path"],
            source_kind=e["kind"], source_sha1=meta["sha1"], rows=max(len(e["rows_data"]) - 1, 0),
            columns=e["rows_data"][0] if e["rows_data"] else [],
            chunks=len(tchunks), url=meta["url"],
        ))
    if sources and not chunks:
        raise ExtractionError(
            "xlsx 已读取但未生成任何表格块；拒绝静默丢弃表格内容"
        )
    return table_docs, chunks, warnings


# --------------------------------------------------------------------------
# 校园地图数据（.vitepress/theme/components/map-data.js）
# --------------------------------------------------------------------------
def _js_array_range(src: str, name: str) -> tuple[int, int] | None:
    m = re.search(rf"export const {name}\s*=\s*\[", src)
    if not m:
        return None
    start = m.end() - 1
    depth = 0
    for i in range(start, len(src)):
        c = src[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return start, i
    return None


def _js_objects(src: str) -> list[str]:
    objs, i = [], 0
    while True:
        i = src.find("{", i)
        if i == -1:
            return objs
        depth, j = 0, i
        while j < len(src):
            if src[j] == "{":
                depth += 1
            elif src[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        objs.append(src[i:j + 1])
        i = j + 1


def _js_str(obj: str, key: str) -> str:
    m = re.search(rf"\b{key}\s*:\s*'((?:[^'\\]|\\.)*)'", obj)
    if m:
        return m.group(1).replace("\\'", "'")
    m = re.search(rf'\b{key}\s*:\s*"((?:[^"\\]|\\.)*)"', obj)
    return m.group(1) if m else ""


def extract_map_data(root: Path, out_dir: Path, max_chars: int):
    p = root / ".vitepress" / "theme" / "components" / "map-data.js"
    if not p.exists():
        return [], [], []
    src = p.read_text(encoding="utf-8", errors="replace")
    rng = _js_array_range(src, "BUILDINGS")
    if not rng:
        raise ExtractionError(
            f"{p} 中未找到 BUILDINGS 数组；地图数据解析失败，拒绝静默丢失地图块"
        )
    objs = _js_objects(src[rng[0]:rng[1] + 1])
    rows = [["校区", "分类", "名称", "描述", "经度", "纬度"]]
    for o in objs:
        if "name:" not in o:
            raise ExtractionError(
                f"{p} 的 BUILDINGS 中存在缺少 name 的对象；地图条目解析失败，"
                "拒绝静默丢弃该建筑点位"
            )
        coord = re.search(r"coord\s*:\s*\[\s*([\d.]+)\s*,\s*([\d.]+)", o)
        photos = re.search(r"photos?\s*:\s*\[", o)
        rows.append([
            _js_str(o, "campusId"), _js_str(o, "category"), _js_str(o, "name"),
            _js_str(o, "desc"), coord.group(1) if coord else "", coord.group(2) if coord else "",
        ])
    if len(rows) <= 1:
        raise ExtractionError(
            f"{p} 的 BUILDINGS 解析结果为空；地图数据解析失败，拒绝静默丢失地图块"
        )

    cat_labels = dict(re.findall(r"(\w+):\s*\{\s*label:\s*'([^']+)'", src))
    campus_names = dict(re.findall(r"(\w+):\s*\{\s*name:\s*'([^']+)'", src))
    for r in rows[1:]:
        r[0] = campus_names.get(r[0], r[0])
        r[1] = cat_labels.get(r[1], r[1])

    meta = {
        "title": "校园地图-建筑点位",
        "category": "站点 / 校园地图",
        "source_path": "docs/.vitepress/theme/components/map-data.js",
        "url": f"{SITE_BASE}/map",
        "sha1": sha1_file(p),
    }
    tid = "tables/map-data#BUILDINGS"
    md = sheet_to_markdown(rows)
    (out_dir / "tables").mkdir(parents=True, exist_ok=True)
    (out_dir / "tables" / "map-data.BUILDINGS.md").write_text(
        f"# 校园地图-建筑点位\n\n> 来源：{meta['source_path']}\n\n{md}\n", encoding="utf-8")
    with (out_dir / "tables" / "map-data.BUILDINGS.csv").open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)

    chunks = table_chunks("建筑点位", rows, tid, meta, max_chars)
    tdoc = OrderedDict(
        id=tid, title=meta["title"], sheet="BUILDINGS", source_path=meta["source_path"],
        source_kind="map-data.js", source_sha1=meta["sha1"], rows=len(rows) - 1,
        columns=rows[0], chunks=len(chunks), url=meta["url"],
    )
    return [tdoc], chunks, []


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
def extract_pdf(root: Path, out_dir: Path):
    docs, chunks, warnings = [], [], []
    d = root / "resources"
    if not d.is_dir():
        return docs, chunks, warnings
    pdf_files = sorted(d.glob("*.pdf"))
    if not pdf_files:
        return docs, chunks, warnings
    try:
        import pymupdf as fitz  # type: ignore
    except Exception:  # noqa: BLE001
        try:
            import fitz  # type: ignore
        except Exception:
            # PDF 是明确的可选能力：缺依赖只告警，不阻断构建
            warnings.append(
                f"未安装 pymupdf（可选依赖），跳过 {len(pdf_files)} 个 PDF："
                f"{'、'.join(p.name for p in pdf_files)}；如其中有可检索文本层，语料会缺少该文档"
            )
            return docs, chunks, warnings
    for p in pdf_files:
        try:
            pdf = fitz.open(p)
            try:
                pages, total = [], 0
                for i, page in enumerate(pdf):
                    t = page.get_text().strip()
                    total += len(t)
                    if t:
                        pages.append((i + 1, t))
            finally:
                pdf.close()
        except Exception as e:  # noqa: BLE001
            # PDF 本身是可选能力，但“文件存在却打不开”属于解析失败，不能静默丢内容
            raise ExtractionError(
                f"PDF 解析失败：{p}（{type(e).__name__}: {e}）；"
                "如该文件确实不可读请从 resources/ 移除后重试"
            ) from e
        if total < 200:
            warnings.append(f"PDF 为扫描件/无文本层，未提取正文：{p.name}（{len(pages)} 页有文本，共 {total} 字符）；建议 OCR 后单独入库")
            continue
        did = f"pdf/{p.stem}"
        md = "\n\n".join(f"## 第 {n} 页\n\n{t}" for n, t in pages)
        plain = to_plain(md)
        docs.append(OrderedDict(
            id=did, title=p.stem, description=None, category="文档资料",
            source_path=f"docs/resources/{p.name}", source_sha1=sha1_file(p),
            source_mtime=mtime_iso(p), url=None, frontmatter={}, headings=[],
            components=[], table_refs=[], links=[], images=[],
            char_count=len(plain), token_estimate=approx_tokens(plain),
            warnings=[], markdown=md, text=plain,
        ))
        made = 0
        for i, (n, t) in enumerate(pages, 1):
            pt = to_plain(t)
            if len(pt) < 20:
                continue
            made += 1
            chunks.append(OrderedDict(
                id=f"{did}#{i:03d}", doc_id=did, chunk_index=i, type="pdf",
                title=p.stem, heading_path=[p.stem, f"第 {n} 页"], section=f"第 {n} 页",
                category="文档资料", source_path=f"docs/resources/{p.name}", url=None,
                anchor=f"page-{n}", markdown=t, text=pt,
                embed_text=f"{p.stem} > 第 {n} 页\n\n{pt}",
                char_len=len(pt), token_estimate=approx_tokens(pt),
                line_start=n, line_end=n, has_table=False, has_code=False, image_count=0,
                source_sha1=docs[-1]["source_sha1"],
            ))
        if pages and made == 0:
            warnings.append(
                f"PDF 有文本层但每页内容过短，未生成检索块：{p.name}；请人工确认是否需要补充"
            )
    return docs, chunks, warnings


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------
def write_jsonl(path: Path, rows: list[dict]):
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def docs_root_for(wiki_root: str | Path) -> Path:
    """--wiki-root 既接受仓库根目录，也接受 docs/ 本身"""
    root = Path(wiki_root).resolve()
    if (root / "docs" / "index.md").exists():
        return root / "docs"
    if (root / "index.md").exists():
        return root
    return root / "docs"


def extract_all(wiki_root: str | Path = REPO_ROOT,
                out_dir: str | Path = RAG_DIR / ".work" / "corpus",
                *, max_chars: int = 900, min_chars: int = 180, overlap: int = 120,
                table_chars: int = 1500, dump_markdown: bool = False,
                source_commit: str | None = None, include_pdf: bool = True,
                verbose: bool = False) -> dict:
    """抽取整个 wiki，返回并写出 manifest。不做任何源文件修改。"""
    wiki_root = Path(wiki_root).resolve()
    docs = docs_root_for(wiki_root)
    out = Path(out_dir).resolve()
    if not (docs / "index.md").exists():
        raise FileNotFoundError(
            f"不像 QUTWiKi 仓库：{wiki_root}（找不到 docs/index.md）；请用 --wiki-root 指定仓库根目录"
        )
    out.mkdir(parents=True, exist_ok=True)

    md_files = []
    for p in sorted(docs.rglob("*.md")):
        rel = p.relative_to(docs)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        md_files.append(p)

    documents, chunks, per_doc = [], [], []
    site_owner = detect_site_owner(docs)
    if site_owner and verbose:
        print(f"站点站长：{site_owner}")
    for p in md_files:
        doc, cks = process_md(p, docs, max_chars, min_chars, overlap, site_owner)
        documents.append(doc)
        chunks.extend(cks)
        per_doc.append(OrderedDict(
            id=doc["id"], title=doc["title"], category=doc["category"],
            source_path=doc["source_path"], source_sha1=doc["source_sha1"],
            source_mtime=doc["source_mtime"], chars=doc["char_count"],
            chunks=len(cks), warnings=doc["warnings"],
        ))

    table_docs, table_cks, table_warn = extract_tables(docs, out, table_chars)
    map_docs, map_cks, map_warn = extract_map_data(docs, out, table_chars)
    table_docs.extend(map_docs)
    table_cks.extend(map_cks)
    chunks.extend(table_cks)
    if include_pdf:
        pdf_docs, pdf_cks, pdf_warn = extract_pdf(docs, out)
    else:
        pdf_docs, pdf_cks, pdf_warn = [], [], []
    documents.extend(pdf_docs)
    chunks.extend(pdf_cks)

    write_jsonl(out / "documents.jsonl", documents)
    write_jsonl(out / "chunks.jsonl", chunks)
    write_jsonl(out / "tables.jsonl", table_docs)

    if dump_markdown:
        clean_dir = out / "clean"
        for d in documents:
            if not d["source_path"].endswith(".md"):
                continue
            rel = d["source_path"][len("docs/"):]
            p = clean_dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(d["markdown"] + "\n", encoding="utf-8")

    all_warn = table_warn + map_warn + pdf_warn
    manifest = OrderedDict(
        generator=GENERATOR,
        built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        source_root=str(docs),
        wiki_root=str(wiki_root),
        source_repo="QUT-Lib/QUTWiKi",
        source_commit=source_commit or _git_commit(wiki_root),
        site_base=SITE_BASE,
        params=OrderedDict(
            max_chars=max_chars, min_chars=min_chars,
            overlap=overlap, table_chars=table_chars,
            skip_dirs=sorted(SKIP_DIRS),
            include_pdf=bool(include_pdf),
        ),
        stats=OrderedDict(
            md_docs=len(documents) - len(pdf_docs),
            pdf_docs=len(pdf_docs),
            tables=len(table_docs),
            documents=len(documents),
            chunks=len(chunks),
            doc_chunks=len(chunks) - len(table_cks) - len(pdf_cks),
            table_chunks=len(table_cks),
            pdf_chunks=len(pdf_cks),
            total_chars=sum(c["char_len"] for c in chunks),
            avg_chunk_chars=round(sum(c["char_len"] for c in chunks) / max(len(chunks), 1), 1),
            max_chunk_chars=max((c["char_len"] for c in chunks), default=0),
            total_token_estimate=sum(c["token_estimate"] for c in chunks),
        ),
        files=per_doc,
        tables=table_docs,
        warnings=all_warn + [f"{d['id']}: {w}" for d in documents for w in d["warnings"]],
    )
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if verbose:
        print(f"OK  文档 {manifest['stats']['documents']} 篇 / 表格 {len(table_docs)} 张 / 块 {len(chunks)} 个")
        print(f"    {out}")
        for w in all_warn:
            print(f"  [!] {w}")
    return manifest


def _git_commit(root: Path) -> str | None:
    import subprocess
    try:
        return subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="QUTWiKi -> RAG 语料提取（只读源目录）")
    ap.add_argument("--wiki-root", default=str(REPO_ROOT), help="QUTWiKi 仓库根目录（默认本仓库）")
    ap.add_argument("--out", default=str(RAG_DIR / ".work" / "corpus"), help="输出目录")
    ap.add_argument("--max-chars", type=int, default=900, help="单块目标最大字符数")
    ap.add_argument("--min-chars", type=int, default=180, help="小于该长度的块会尝试与相邻块合并")
    ap.add_argument("--overlap", type=int, default=120, help="硬切时的重叠字符数")
    ap.add_argument("--table-chars", type=int, default=1500, help="表格块目标最大字符数")
    ap.add_argument("--dump-markdown", action="store_true", help="额外把清洗后的 Markdown 按源码树写出到 <out>/clean/")
    ap.add_argument("--source-commit", default=None, help="写入 manifest 的源提交（默认取 git HEAD）")
    ap.add_argument("--no-pdf", action="store_true", help="跳过 resources/*.pdf（即使已安装 pymupdf）")
    args = ap.parse_args(argv)

    try:
        extract_all(args.wiki_root, args.out, max_chars=args.max_chars,
                    min_chars=args.min_chars, overlap=args.overlap,
                    table_chars=args.table_chars, dump_markdown=args.dump_markdown,
                    source_commit=args.source_commit, include_pdf=not args.no_pdf,
                    verbose=True)
    except FileNotFoundError as e:
        print(f"[!] {e}", file=sys.stderr)
        return 2
    except ExtractionError as e:
        print(f"[!] 抽取失败：{e}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
