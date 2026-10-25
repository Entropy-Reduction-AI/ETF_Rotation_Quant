"""§6③ 跨年代。2016 年及之后的两段在 G3 之前标成未计算，不读组合收益。"""
from __future__ import annotations

import pandas as pd

from src.v3.engine.book import DESIGN_END

from .common import annualized_return, require_design_period

ERAS = (
    ("2006-2010", pd.Timestamp("2006-01-01"), pd.Timestamp("2010-12-31")),
    ("2011-2015", pd.Timestamp("2011-01-01"), pd.Timestamp("2015-12-31")),
    ("2016-2020", pd.Timestamp("2016-01-01"), pd.Timestamp("2020-12-31")),
    ("2021-2026", pd.Timestamp("2021-01-01"), pd.Timestamp("2026-09-30")),
)
MIN_DAYS = 60
FLOOR = -0.03


def four_era_check(rows: list[dict]) -> bool | None:
    """至少 3 段超额 > 0，且没有一段低于 −3 个百分点。还有未计算的段时不给布尔值。"""
    if any(row["status"] == "未计算" for row in rows):
        return None
    if any(row["below_floor"] for row in rows):
        return False
    return sum(1 for row in rows if row["positive"]) >= 3


def criterion_3(strategy, benchmark, calendar) -> dict:
    require_design_period(pd.Series(strategy).index)
    require_design_period(pd.Series(benchmark).index)
    sessions = pd.DatetimeIndex(pd.to_datetime(calendar)).sort_values().unique()
    left_all = pd.Series(strategy, dtype=float).sort_index()
    right_all = pd.Series(benchmark, dtype=float).sort_index()
    rows = []
    for name, start, end in ERAS:
        if start > DESIGN_END:
            rows.append({
                "era": name, "status": "未计算", "n": 0, "complete": False,
                "ann_strategy": None, "ann_benchmark": None, "excess": None,
                "positive": False, "below_floor": False,
            })
            continue
        era_days = sessions[(sessions >= start) & (sessions <= end) & (sessions <= DESIGN_END)]
        left = left_all.reindex(era_days)
        right = right_all.reindex(era_days)
        complete = len(era_days) > 0 and bool(left.notna().all() and right.notna().all())
        if len(era_days) < MIN_DAYS:
            rows.append({
                "era": name, "status": "样本不足", "n": int(len(era_days)), "complete": complete,
                "ann_strategy": None, "ann_benchmark": None, "excess": None,
                "positive": False, "below_floor": False,
            })
            continue
        if not complete:
            covered = int((left.notna() & right.notna()).sum())
            rows.append({
                "era": name, "status": "未覆盖全段", "n": covered, "complete": False,
                "ann_strategy": None, "ann_benchmark": None, "excess": None,
                "positive": False, "below_floor": False,
            })
            continue
        ann_strategy = annualized_return(left.to_numpy())
        ann_benchmark = annualized_return(right.to_numpy())
        excess = ann_strategy - ann_benchmark
        rows.append({
            "era": name, "status": "ok", "n": int(len(era_days)), "complete": True,
            "ann_strategy": ann_strategy, "ann_benchmark": ann_benchmark, "excess": excess,
            "positive": bool(excess > 0.0), "below_floor": bool(excess < FLOOR),
        })
    return {"eras": rows, "engineering_check": four_era_check(rows), "formal_pass": None}
