#!/usr/bin/env python3
"""D38 第 44 行：Grok 第六轮 7 条长日线 vs 现有美股候选，2007–2015 月收益相关（独立复算）。"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
GROK = HERE / "grok-cache" / "incoming" / "grok-d37-index-20261116"
SUMMARY = HERE / "d38-r4244-recalc.json"
WIN = ("2007-01-01", "2015-12-31")

# 登记里的 6 对 + REIT 最高相关（对池内最佳匹配）
PAIRS = [
    ("IXY", "XLY", ["d37-longhist-20261118/theme-IXY-ft-usd-pr-daily-19981216-20261116.csv"]),
    (
        "S5INFT",
        "XLK",
        [
            "d37-remain-20261118-pass2/theme-S5INFT-ft-SP500-45-usd-pr-daily-19960628-20120924.csv",
            "theme-标普500信息科技指数-tradingview.csv",
        ],
    ),
    ("DJSOEP", "XLE", ["theme-道琼斯美国石油开发与生产指数-tradingview.csv"]),
    ("SPSIOP", "XLE", ["theme-标普石油天然气勘探及生产精选行业指数-tradingview.csv"]),
    ("S35", "XLV", ["theme-标普500医疗保健等权重指数-tradingview.csv"]),
    (
        "SPSIBI",
        "NBI",
        [
            "d37-remain-20261118-pass2/theme-SPSIBI-usspindices-wayback-usd-pr-daily-20060127-20140505.csv",
            "theme-标普生物科技精选行业指数-tradingview.csv",
        ],
    ),
]
REIT_PATHS = ["theme-道琼斯美国精选REIT指数-tradingview.csv"]


def load_grok_daily(paths: list[str]) -> pd.Series:
    parts = []
    for rel in paths:
        p = GROK / rel
        if not p.exists():
            raise FileNotFoundError(p)
        df = pd.read_csv(p)
        cols = {c.lower(): c for c in df.columns}
        dcol = cols.get("date") or list(df.columns)[0]
        ccol = cols.get("close") or list(df.columns)[1]
        df[dcol] = pd.to_datetime(df[dcol])
        df = df.sort_values(dcol).drop_duplicates(dcol)
        parts.append(df.set_index(dcol)[ccol].astype(float))
    s = pd.concat(parts).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    m = s.resample("ME").last().pct_change()
    return m.loc[WIN[0]:WIN[1]].dropna()


def load_etf_monthly(code: str) -> pd.Series:
    con = sqlite3.connect(f"file:{ROOT / 'data/market.sqlite'}?mode=ro", uri=True)
    q = (
        "select date, close from bars where code=? and adj='raw' and close>0 "
        "and date between ? and ? order by date"
    )
    df = pd.read_sql_query(q, con, params=(code, WIN[0], WIN[1]))
    df["date"] = pd.to_datetime(df["date"])
    s = df.set_index("date")["close"].astype(float)
    return s.resample("ME").last().pct_change().dropna()


def best_pool_corr(grok_m: pd.Series) -> tuple[str, float]:
    pool = ["XLK", "XLV", "XLE", "XLY", "XLP", "XLF", "XLI", "XLB", "XLU", "NBI", "SOX"]
    best = ("", float("-inf"))
    for c in pool:
        etf = load_etf_monthly(c)
        idx = grok_m.index.intersection(etf.index)
        if len(idx) < 24:
            continue
        r = grok_m.loc[idx].corr(etf.loc[idx])
        if r > best[1]:
            best = (c, float(r))
    return best


def main() -> None:
    out = {"window": WIN, "pairs": {}, "cross_DJSOEP_SPSIOP": None, "reit": {}}
    for gname, etf, fnames in PAIRS:
        gm = load_grok_daily(fnames)
        em = load_etf_monthly(etf)
        idx = gm.index.intersection(em.index)
        corr = float(gm.loc[idx].corr(em.loc[idx]))
        out["pairs"][f"{gname}_vs_{etf}"] = {
            "grok_files": fnames,
            "months": len(idx),
            "corr": round(corr, 2),
        }
    d_g = load_grok_daily(["theme-道琼斯美国石油开发与生产指数-tradingview.csv"])
    o_g = load_grok_daily(["theme-标普石油天然气勘探及生产精选行业指数-tradingview.csv"])
    idx = d_g.index.intersection(o_g.index)
    out["cross_DJSOEP_SPSIOP"] = {"months": len(idx), "corr": round(float(d_g.loc[idx].corr(o_g.loc[idx])), 2)}
    reit_m = load_grok_daily(REIT_PATHS)
    code, corr = best_pool_corr(reit_m)
    out["reit"] = {"grok": "DWRTF", "best_match_code": code, "corr": round(corr, 2), "files": REIT_PATHS}
    data = {}
    if SUMMARY.exists():
        data = json.loads(SUMMARY.read_text(encoding="utf-8"))
    data["row44_correlations"] = out
    SUMMARY.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()