"""v3.1 官方回溯主口径，以及仍可打开的发布日对照。

不新增容器，不把国债总财富写进池，也不补造库里没有的序列。
"""
from __future__ import annotations

from datetime import date

OFFICIAL = "official"
PUBLISH_DATE = "publish_date"
MODES = (OFFICIAL, PUBLISH_DATE)
THEME = "美股和全球主题"
MISSING = {"", "取不到", "TBD"}
USD_TR = {"XNDX", "^SP500TR"}


def _text(value) -> str:
    return str(value or "").strip()


def _date(value) -> str:
    text = _text(value)
    if text in MISSING or len(text) < 10 or text[4] != "-" or text[7] != "-":
        return ""
    return text[:10]


def history_floor(container: dict, mode: str) -> str:
    """主口径的序列起点，或对照口径的发布日。返回空字符串表示没有可核实的截断日。

    官方口径用基日（核实时），不再用指数发布日。美股和全球主题在两种口径下都不早于
    登记的 ETF 上市日。基日或上市日缺失时不假定一个更早的起点。
    """
    if mode not in MODES:
        raise ValueError(f"未知的历史口径 {mode}")
    research = container.get("research") or {}
    publish = _date(research.get("publish_date"))
    base = _date(research.get("base_date"))
    listing = publish if _text(container.get("asset_class")) == THEME else ""
    start = publish if mode == PUBLISH_DATE else base
    dates = [item for item in (start, listing) if item]
    if not dates:
        return ""
    return max(dates)


def history_gap(container: dict, first_date: str = "") -> str:
    """登记缺口。有句子就表示这里没有补造数据。"""
    research = container.get("research") or {}
    asset = _text(container.get("asset_class"))
    name = _text(container.get("name"))
    code = _text(research.get("series_code"))
    status = _text(research.get("series_status"))
    publish = _date(research.get("publish_date"))
    base = _date(research.get("base_date"))
    first = _date(first_date)
    parts: list[str] = []
    if code in MISSING or status in MISSING:
        parts.append("无已登记官方序列")
    if asset == THEME and not publish:
        parts.append("上市日无法核实，不把首根K线写成上市日")
    if asset not in {THEME, "现金"} and code not in MISSING and not base:
        parts.append("基日无法核实，官方口径不假定起点")
    if asset != "现金" and code not in MISSING and not publish:
        parts.append("发布日无法核实，对照口径不能按发布日截断")
    if base and first:
        span = (date.fromisoformat(first) - date.fromisoformat(base)).days
        if span > 10:
            parts.append("已登记序列晚于基日，缺官方回溯，不补造")
    if container.get("id") == "gold" or (asset == "商品" and name == "黄金"):
        if not first or first > "2006-01-04":
            parts.append("2008-08-11 之前没有连续黄金行情，不补造")
    if asset == "债券" and code not in MISSING:
        parts.append("中债财富在 2008 年之前不补造")
    if code in USD_TR:
        parts.append("没有单独的人民币全收益发布序列，不把美元点位乘汇率写成新序列")
    if code == "CBA00601":
        parts.append("国债总财富不进入池")
    return "；".join(parts)
