#!/usr/bin/env python3
"""Reviewer v4-R1b item 2: independent Orchestrator 17-index Rank IC baseline (≤2015-12-31).

Rebuilds the 18-series replication panel from market.sqlite (gold omitted), computes
cross-sectional Spearman IC at month-ends 2006-01 … 2015-12 vs next 20 trading-day returns.
No portfolio PnL, no 2016+ return stats.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
DB = ROOT / "data" / "market.sqlite"
OUT_JSON = Path(__file__).with_name("v4-r1b-orchestrator-ic-recompute.json")
ARTIFACT = Path("/opt/cursor/artifacts/v4-r1b-orchestrator-ic-recompute.json")

CUTOFF = "2015-12-31"
DECISION_FROM = "2006-01-01"
FORWARD_H = 20
FOCUS_LOOKBACKS = (20, 60, 120, 250)
ALL_LOOKBACKS = (5, 10, 20, 40, 60, 90, 120, 180, 250)

CN_INDEX = {
    "H00300": "沪深300",
    "H00905": "中证500",
    "H00852": "中证1000",
    "H00922": "中证红利",
    "H00986": "能源",
    "H00987": "原材料",
    "H00988": "工业",
    "H00989": "可选消费",
    "H00990": "主要消费",
    "H00991": "医药",
    "H00992": "金融地产",
    "H00993": "信息技术",
    "H00994": "通信",
    "H00995": "公用事业",
}
OVERSEAS = (
    ("HSI", "恒生指数"),
    ("XNDX", "纳指100"),
    ("^SP500TR", "标普500"),
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_close(con: sqlite3.Connection, code: str) -> pd.Series:
    df = pd.read_sql(
        "SELECT date, close FROM bars WHERE code = ? ORDER BY date",
        con,
        params=(code,),
    )
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["close"].astype(float)


def build_price_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    """18-series replication calendar; 17 tradable columns (no gold)."""
    con = sqlite3.connect(DB)
    cal = load_close(con, "H00300").loc["2005-01-01":CUTOFF].index
    usdcny = load_close(con, "USDCNY")

    series: dict[str, pd.Series] = {}
    for code, label in CN_INDEX.items():
        series[label] = load_close(con, code)

    def to_rmb_on_cal(us: pd.Series) -> pd.Series:
        shifted = us.copy()
        shifted.index = shifted.index + pd.Timedelta(days=1)
        aligned = shifted.reindex(cal, method="ffill")
        fx = usdcny.reindex(cal, method="ffill")
        return aligned * fx

    for code, label in OVERSEAS:
        series[label] = to_rmb_on_cal(load_close(con, code))

    prices = pd.DataFrame({name: s.reindex(cal, method="ffill") for name, s in series.items()})
    for name, raw in series.items():
        start = raw.dropna().index[0]
        prices.loc[prices.index < start, name] = np.nan
    prices = prices.mask(prices <= 0)
    for name in prices.columns:
        first = prices[name].first_valid_index()
        if first is not None:
            prices.loc[first:, name] = prices.loc[first:, name].ffill()

    con.close()
    prices = prices.loc[:CUTOFF]
    daily_ret = prices.pct_change(fill_method=None)
    return prices, daily_ret


def month_end_decision_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    last_in_month = index.to_series().groupby(index.to_period("M")).last()
    out = [pd.Timestamp(d) for d in last_in_month.values if pd.Timestamp(d) >= pd.Timestamp(DECISION_FROM)]
    return out


def risk_adj_momentum(
    prices: pd.DataFrame,
    daily_ret: pd.DataFrame,
    asof_loc: int,
    lookback: int,
) -> pd.Series:
    total_ret = prices.iloc[asof_loc] / prices.iloc[asof_loc - lookback] - 1.0
    vol = daily_ret.iloc[asof_loc - lookback + 1 : asof_loc + 1].std(ddof=1) * np.sqrt(lookback)
    return total_ret / vol


def cross_section_ic(scores: pd.Series, forward_ret: pd.Series) -> float | None:
    mask = scores.notna() & forward_ret.notna()
    if mask.sum() < 3:
        return None
    x = scores[mask].rank()
    y = forward_ret[mask].rank()
    return float(x.corr(y))


def blend_rank_ic(
    rank_frames: list[pd.Series],
    forward_ret: pd.Series,
) -> float | None:
    combined = pd.concat(rank_frames, axis=1).mean(axis=1)
    return cross_section_ic(combined, forward_ret)


def compute_ic_series(prices: pd.DataFrame, daily_ret: pd.DataFrame) -> pd.DataFrame:
    decision_dates = month_end_decision_dates(prices.index)
    rows: list[dict] = []
    max_lb = max(ALL_LOOKBACKS)

    for d in decision_dates:
        k = prices.index.get_loc(pd.Timestamp(d))
        if k + FORWARD_H >= len(prices) or k < max_lb:
            continue
        fwd = prices.iloc[k + FORWARD_H] / prices.iloc[k] - 1.0
        row: dict = {"date": pd.Timestamp(d)}
        blend_ranks: list[pd.Series] = []

        for lb in ALL_LOOKBACKS:
            s = risk_adj_momentum(prices, daily_ret, k, lb)
            ic = cross_section_ic(s, fwd)
            row[lb] = ic
            if lb in FOCUS_LOOKBACKS:
                blend_ranks.append(s.rank())

        row["four_avg"] = blend_rank_ic(blend_ranks, fwd)
        rows.append(row)

    return pd.DataFrame(rows).set_index("date")


def main() -> int:
    if not DB.is_file():
        print("missing DB", DB, file=sys.stderr)
        return 1

    prices, daily_ret = build_price_panel()
    assert "黄金" not in prices.columns
    ic = compute_ic_series(prices, daily_ret)

    means = ic.mean(numeric_only=True)
    summary = {
        str(lb): round(float(means[lb]), 6) for lb in FOCUS_LOOKBACKS
    }
    summary["four_avg"] = round(float(means["four_avg"]), 6)

    expected = {
        "20": 0.093,
        "60": 0.028,
        "120": -0.004,
        "250": 0.049,
        "four_avg": 0.069,
    }
    keys = ["20", "60", "120", "250", "four_avg"]
    match_3dp = all(
        round(summary[k], 3) == round(expected[k], 3) for k in keys
    )

    payload = {
        "task": "v4-R1b-reviewer-orchestrator-ic",
        "data_cutoff": CUTOFF,
        "market_sqlite_sha256": sha256_file(DB),
        "n_indices": int(prices.shape[1]),
        "index_names": list(prices.columns),
        "n_decisions": int(len(ic)),
        "forward_horizon_trading_days": FORWARD_H,
        "mean_rank_ic": summary,
        "expected_mean_rank_ic": expected,
        "numbers_ok_3dp": match_3dp,
        "mean_rank_ic_all_lookbacks": {
            str(lb): round(float(means[lb]), 6) for lb in ALL_LOOKBACKS
        },
    }

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if match_3dp else 2


if __name__ == "__main__":
    raise SystemExit(main())
