"""§7.5 结论报告的输出模板。

只提供空表和章节名单。不读行情，不填年化、回撤或超额。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "assets" / "templates" / "v4-conclusion-report.md"

# 标题字符串必须和模板里的二级标题一致。
SECTIONS = (
    ("character", "## 1. 性格"),
    ("regimes", "## 2. 四种行情"),
    ("any_start", "## 3. 任意起点"),
    ("contrast", "## 4. 优劣对照"),
    ("decades", "## 5. 市场和时代的变化"),
    ("adaptability", "## 6. 适应性"),
)


def template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")
