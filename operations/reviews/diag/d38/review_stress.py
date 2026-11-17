"""Reviewer 独立复算 D38 真实历史压力测试（R12/R13；不用 scripts/preflight）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from review_engine import simulate_structure  # noqa: E402

from src.v3.engine.spec import load_spec  # noqa: E402
from src.v4.r5.design import Markets  # noqa: E402

WINDOWS = (
    ("2008", "2007-06-01", "2009-06-30"),
    ("2015", "2015-05-01", "2015-12-31"),
)
EVAL_START = "2006-01-01"
SERIES_START = "2005-01-01"
DATA_END = "2015-12-31"
STRUCTURES_R12 = ("K0", "K2", "K2A")
STRUCTURES_ALL = ("K0", "K1", "K2", "K2A")


def load_realized_log_returns() -> Tuple[pd.DatetimeIndex, np.ndarray]:
    """项目池 index 口径，≤2015-12-31；2005 起用作预热。"""
    markets = Markets(load_spec()).get("index", t4=False, allow_substitute=True)
    frame = markets.signal.loc[SERIES_START:DATA_END, ["csi300", "ndx100", "spx"]].dropna()
    if frame.empty:
        raise RuntimeError("项目池 index 数据为空，无法做压力测试复算")
    us = (frame["ndx100"] + frame["spx"]) / 2
    legs = np.column_stack([frame["csi300"].values, us.values])
    lr = np.log1p(legs)[None, :, :]
    return frame.index, lr


def _window_stats(nav: pd.Series, label: str, start: str, end: str) -> dict:
    seg = nav.loc[start:end]
    if seg.empty:
        raise RuntimeError(f"窗口 {label} 无交易日")
    trough_t = seg.idxmin()
    peak = nav.loc[:end].loc[:trough_t].max()
    trough = float(seg.min())
    return {
        "最低剩_万": round(trough / peak * 100, 1),
        "回撤": round((trough / peak - 1) * 100, 1),
        "见顶": str(nav.loc[:trough_t].idxmax().date()),
        "见底": str(trough_t.date()),
    }


def _period_stats(nav: pd.Series) -> dict:
    st = nav.loc[EVAL_START:]
    if st.empty:
        raise RuntimeError(f"评估段 {EVAL_START} 起无数据")
    dd = st / st.cummax() - 1
    trough_t = dd.idxmin()
    peak_t = st.loc[:trough_t].idxmax()
    mdd_pct = round(float(dd.min()) * 100, 1)
    ann = round(float((st.iloc[-1] / st.iloc[0]) ** (252 / len(st)) - 1) * 100, 2)
    worst_remain = round(float((st / st.cummax()).min() * 100), 1)
    return {
        "2006–2015 最大回撤": mdd_pct,
        "2006–2015 年化": ann,
        "2006–2015 最大回撤_见顶": str(peak_t.date()),
        "2006–2015 最大回撤_见底": str(trough_t.date()),
        "2006–2015 最差剩余_万": worst_remain,
    }


def run_stress_review(out_dir: Path, structures: tuple[str, ...] = STRUCTURES_ALL) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    idx, lr = load_realized_log_returns()
    results: Dict[str, Any] = {"meta": {"index_start": str(idx[0].date()), "index_end": str(idx[-1].date()), "eval_start": EVAL_START}}
    for kind in structures:
        nav_arr, _, _, _ = simulate_structure(lr, kind)
        nav = pd.Series(nav_arr[0], index=idx, name=kind)
        block: Dict[str, Any] = {}
        for label, a, b in WINDOWS:
            block[label] = _window_stats(nav, label, a, b)
        block.update(_period_stats(nav))
        results[kind] = block
    target = out_dir / "r12_stress.json"
    target.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


if __name__ == "__main__":
    run_stress_review(Path(__file__).parent / "out")