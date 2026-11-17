"""Reviewer 独立复算 D38 信号 IC（不用 scripts/preflight）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from src.v3.engine.spec import load_spec  # noqa: E402
from src.v4.r5.design import Markets  # noqa: E402

RAW = REPO / "data/research/long-history/raw"
SEGMENTS = {"2006–10": ("2006-01-01", "2010-12-31"), "2011–15": ("2011-01-01", "2015-12-31")}
A_SHARE_SEL = None  # filled at runtime


def spearman(x, y) -> float:
    xs, ys = pd.Series(np.asarray(x, float)), pd.Series(np.asarray(y, float))
    return float(xs.rank().corr(ys.rank()))


def to_monthly_levels(daily_returns: pd.DataFrame) -> pd.DataFrame:
    lvl = np.exp(np.log1p(daily_returns).cumsum().where(daily_returns.notna()))
    return lvl.resample("ME").last()


def lookback_return(levels: pd.DataFrame, months: int) -> pd.DataFrame:
    if months == 12:
        return levels.shift(1) / levels.shift(months) - 1
    return levels / levels.shift(months) - 1


def segment_means(series: pd.Series) -> dict:
    out = {}
    for label, (a, b) in SEGMENTS.items():
        chunk = series.loc[a:b].dropna()
        out[label] = {
            "IC均值": round(float(chunk.mean()), 3) if len(chunk) else None,
            "月数": int(len(chunk)),
        }
    return out


def load_pool_monthly():
    markets = Markets(load_spec()).get("index", t4=False, allow_substitute=True)
    daily = markets.signal.loc[:"2015-12-31"]
    levels = to_monthly_levels(daily)
    cash_m = (1 + daily["cash"].fillna(0)).resample("ME").prod() - 1
    fwd = levels.shift(-1) / levels - 1
    fwd_excess = fwd.sub(cash_m.shift(-1), axis=0)
    return levels, fwd, fwd_excess, daily


def long_history_levels():
    out = {}
    for name, fname, start, end in (
        ("标普500", "^GSPC.csv", "1955-01-01", "2003-06-30"),
        ("恒生", "^HSI.csv", "1987-01-01", "2015-12-31"),
        ("日经", "^N225.csv", "1987-01-01", "2015-12-31"),
    ):
        px = pd.read_csv(RAW / fname, parse_dates=["date"]).set_index("date")["close"]
        px = px[(px.index >= start) & (px.index <= end) & (px > 0)].resample("ME").last()
        out[name] = px
    return out


def run_ic_review(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    levels, fwd, fwd_ex, daily = load_pool_monthly()
    global A_SHARE_SEL
    A_SHARE_SEL = [c for c in levels.columns if c.startswith("allshare-")] + [
        "csi300",
        "csi500",
        "csi1000",
        "chinext",
        "csi-dividend",
    ]

    result = {}

    # ① 长历史三市场
    lh = long_history_levels()
    ma_block = {}
    for name, px in lh.items():
        signal = px / px.rolling(10).mean() - 1
        nxt = px.shift(-1) / px - 1
        frame = pd.concat([signal, nxt], axis=1).dropna()
        ma_block[name] = {"IC": round(spearman(frame.iloc[:, 0], frame.iloc[:, 1]), 3), "月数": len(frame)}
    result["①均线_长历史"] = ma_block

    # ③ A 股内挑选 12−1
    vol_m = daily[A_SHARE_SEL].rolling(60).std().resample("ME").last() * np.sqrt(252)
    sig12 = lookback_return(levels[A_SHARE_SEL], 12)
    within = {}
    for label, sig in (("12−1|涨幅", sig12), ("12−1|涨幅÷波动", sig12 / vol_m)):
        month_ics = []
        for t in sig.index:
            x, y = sig.loc[t], fwd[A_SHARE_SEL].loc[t]
            ok = x.notna() & y.notna()
            if ok.sum() >= 8:
                month_ics.append((t, spearman(x[ok], y[ok])))
        within[label] = segment_means(pd.Series({t: v for t, v in month_ics}))
    result["③A股内挑选_12-1"] = within

    target = out_dir / "r3_ic.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


if __name__ == "__main__":
    run_ic_review(Path(__file__).parent / "out")