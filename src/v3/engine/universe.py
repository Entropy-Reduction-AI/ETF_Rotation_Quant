"""从冻结的 universe.toml 取池成员和费率。不改登记表。"""
from __future__ import annotations

import pandas as pd

from .spec import Spec

A_SHARE = {"A股宽基", "A股行业", "A股红利"}
MISSING = {"", "取不到", "TBD"}


def parse_date(value) -> pd.Timestamp | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in MISSING:
        return None
    return pd.Timestamp(text)


def is_qdii(container: dict) -> bool:
    research = container.get("research") or {}
    return container.get("asset_class") == "美股和全球主题" or research.get("return_basis") == "unit_nav"


def signal_kinds(container: dict, arm: str, pool: str) -> tuple[str, str]:
    """返回 (信号序列, 计价序列)。S1 只把 QDII 的动量从净值改成场内价格。"""
    if container.get("asset_class") == "现金":
        return "cash", "cash"
    qdii = is_qdii(container)
    if pool == "index":
        pnl = "nav" if qdii else "research"
        if arm == "S1" and qdii:
            return "price", pnl
        if qdii:
            return "nav", pnl
        return "research", pnl
    if arm != "S1" and qdii:
        return "nav", "price"
    return "price", "price"


def pool_members(containers: list[dict], arm: str, pool: str) -> list[dict]:
    flag = "in_pool_index" if pool == "index" else "in_pool_tradable"
    if arm in {"A", "B", "S1"}:
        return [row for row in containers if row.get("arm") == "main" and row.get(flag)]
    if arm == "S2":
        chosen = []
        for row in containers:
            if not row.get(flag):
                continue
            if row.get("arm") == "S2":
                chosen.append(row)
            elif row.get("arm") == "main" and row.get("asset_class") not in A_SHARE:
                chosen.append(row)
        return chosen
    raise ValueError(arm)


def fee_for(container: dict, spec: Spec) -> float:
    return spec.fee(str(container.get("asset_class")), name=str(container.get("name") or ""),
                    arm=str(container.get("arm") or "main"))


def execution_code(container: dict) -> str | None:
    """L2 还没有溢价模块。同一容器多只基金时用登记表里的第一只。§5.4 留给 L3。"""
    rows = container.get("execution") or []
    if not rows:
        return None
    code = str(rows[0].get("code") or "")
    return code or None


def research_code(container: dict) -> str | None:
    research = container.get("research") or {}
    code = str(research.get("series_code") or "")
    if code in MISSING:
        return None
    return code
