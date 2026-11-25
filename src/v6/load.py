"""按冻结提交 f066da8e 的预演代码装设计期面板。

只执行 `a_official.py` 在 French / `topn_longhist.py` 之前的那一段。
`sim.py` 在导入时会整文件读入 ^GSPC、^HSI（文件本身含 2016 年以后的行），
这里用空模块挡住，数据段并不调用它。
"""

from __future__ import annotations

import hashlib
import sqlite3
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd

from src.v4.engine.pool import load_mid
from src.v6.guard import (
    DESIGN_END,
    DESIGN_END_TEXT,
    IsolationError,
    assert_not_after,
    install_readers,
    restore_readers,
)

ROOT = Path(__file__).resolve().parents[2]
FREEZE = "f066da8e46f202e105a65c7abf43e4d4cf82eff9"
CUTOFF = "# ---------- 按把握调节的系统（与 topn_phi 相同的规则） ----------"
A_OFFICIAL = ROOT / "scripts/preflight/a_official.py"


def freeze_loader_text() -> str:
    text = A_OFFICIAL.read_text(encoding="utf-8")
    head, sep, _tail = text.partition(CUTOFF)
    if not sep:
        raise IsolationError("冻结加载段的截断标记不在 a_official.py")
    if "topn_longhist.py" in head:
        raise IsolationError("截断之后才应该执行 French 长历史")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return head, digest


def _stub_sim() -> None:
    """挡住 sim.py 的导入期读文件。预演数据段不调用合成行情。"""
    sys.modules["sim"] = types.ModuleType("sim")


def load_panels():
    """返回冻结数据段的命名空间，以及回填后的 A 股面板。"""
    head, digest = freeze_loader_text()
    _stub_sim()
    originals = install_readers(pd)
    namespace = {"__file__": str(A_OFFICIAL), "__name__": "v6_frozen_load"}
    saved_argv = sys.argv[:]
    # 这一段只拆开参数，不打开 French 文件。路径用空设备，避免误读一份含 2016 的文件。
    sys.argv = ["a_official.py", "/dev/null", "/dev/null"]
    try:
        exec(compile(head, str(A_OFFICIAL), "exec"), namespace)  # noqa: S102  规范即这段冻结代码
    finally:
        sys.argv = saved_argv
        restore_readers(pd, originals)
    _assert_panels(namespace)
    panels = _assemble(namespace)
    panels["loader_sha256"] = digest
    panels["freeze"] = FREEZE
    panels["cutoff"] = CUTOFF
    return panels


def _assert_panels(namespace) -> None:
    for key in ("A", "A_OLD", "US_RMB", "bond", "cash", "P", "V"):
        if key not in namespace:
            raise IsolationError(f"冻结加载段没有 {key}")
    for key in ("A", "A_OLD", "US_RMB", "P"):
        assert_not_after(namespace[key].index, key)
    assert_not_after(namespace["bond"].index, "bond")
    assert_not_after(namespace["cash"].index, "cash")
    for series in namespace["V"]["TRIN"].values():
        # PeriodIndex 或 DatetimeIndex 都不应晚于 2015-12
        last = series.index.max()
        stamp = last.to_timestamp(how="end") if hasattr(last, "to_timestamp") else pd.Timestamp(last)
        if pd.Timestamp(stamp) > DESIGN_END + pd.Timedelta(days=31):
            raise IsolationError(f"TRIN 晚于设计期：{last}")


def _assemble(namespace) -> dict:
    """附表 B 的主口径：一级行业用回填点位；美股 15 个 = 旧 14 个 + DWRTF。"""
    base = namespace["A"]
    old = namespace["A_OLD"]
    backfill = base.copy()
    for column in [c for c in base.columns if str(c).startswith("allshare-")]:
        series = old[column]
        backfill[column] = series / series.dropna().iloc[0]
    assert_not_after(backfill.index, "A_BF")
    us = namespace["US_RMB"].copy()
    us["DWRTF"] = _us_level("DWRTF", us.index, namespace)
    assert_not_after(us.index, "US15")
    if not backfill.index.equals(us.index):
        raise IsolationError("A 股日历和美股日历不一致")
    return {
        "ns": namespace,
        "A_pub": base,
        "A": backfill,
        "US": us,
        "bond": namespace["bond"],
        "cash": namespace["cash"],
        "votes": namespace["V"]["votes"],
        "trin": namespace["V"]["TRIN"],
        "vs": namespace["V"]["vs"],
        "amt": namespace["AMT"],
        "idx": namespace["idx"],
    }


def _us_level(code: str, index: pd.DatetimeIndex, namespace) -> pd.Series:
    """与 topn_dedupe.py 的 lvl 相同：原始收盘 × 补齐中间价，封在 2015-12-31。"""
    con = sqlite3.connect(ROOT / "data/market.sqlite")
    try:
        usd = load_mid(con, "USDCNY", DESIGN_END_TEXT, filled=True)
        frame = pd.read_sql_query(
            "select date, close from bars where code=? and adj='raw' and close>0 "
            "and date<=? order by date",
            con,
            params=(code, DESIGN_END_TEXT),
        )
    finally:
        con.close()
    assert_not_after(usd.index, "USDCNY")
    series = pd.Series(frame["close"].astype(float).values, pd.to_datetime(frame["date"]))
    series = series[~series.index.duplicated(keep="last")]
    assert_not_after(series.index, code)
    fx = usd.reindex(series.index.union(usd.index)).ffill().reindex(series.index)
    series = series * fx
    out = series.reindex(index.union(series.index)).ffill().reindex(index)
    return out.where(out.index >= series.index[0])


def month_ends(levels: pd.DataFrame) -> pd.DatetimeIndex:
    calendar = levels.index
    mask = np.r_[calendar.month[1:] != calendar.month[:-1], True]
    return pd.DatetimeIndex(calendar[mask])


def momentum(levels: pd.DataFrame) -> pd.DataFrame:
    """D45-1：T−1 月末 ÷ T−12 月末 − 1。"""
    ends = month_ends(levels)
    month = levels.loc[ends]
    return month.shift(1) / month.shift(12) - 1


def eligible_on(levels: pd.DataFrame, day: pd.Timestamp) -> pd.Series:
    scores = momentum(levels)
    if day not in scores.index:
        raise IsolationError(f"{day.date()} 不是月末信号日")
    row = scores.loc[day]
    return row[np.isfinite(row.to_numpy(dtype=float))].sort_index()
