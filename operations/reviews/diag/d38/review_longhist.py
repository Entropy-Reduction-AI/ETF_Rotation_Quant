"""Reviewer 独立复算 D38 长历史 K0–K2（单市场）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[4]
RAW = REPO / "data/research/long-history/raw"
LEG_COST = 0.001


def jp_cash_rate() -> pd.Series:
    daily = pd.read_csv(RAW / "FM01-STRDCLUCON.csv", parse_dates=["date"]).set_index("date").iloc[:, 0]
    monthly = pd.read_csv(RAW / "FM02-STRACLUCON.csv")
    monthly.index = pd.to_datetime(monthly.iloc[:, 0].astype(str))
    monthly = monthly.iloc[:, 1]
    monthly = monthly[monthly.index < daily.index[0]]
    return pd.concat([monthly, daily]).sort_index().astype(float)


def us_cash_rate() -> pd.Series:
    dtb = pd.read_csv(
        REPO / "results/v5/other-market/raw/DTB3.csv",
        parse_dates=["date"],
        na_values=[".", ""],
    ).set_index("date")["DTB3"]
    return dtb.where(dtb > -100).dropna()


MARKETS = (
    ("标普500", "^GSPC.csv", "1955-01-01", "2003-06-30", "us"),
    ("恒生", "^HSI.csv", "1987-01-01", "2015-12-31", "us"),
    ("日经", "^N225.csv", "1987-01-01", "2015-12-31", "jp"),
)


def bear_episodes(px: pd.Series) -> List[Tuple[pd.Timestamp, pd.Timestamp, float]]:
    episodes, mode = [], "up"
    extreme, extreme_t, peak_t, peak = px.iloc[0], px.index[0], None, None
    for t, p in px.items():
        if mode == "up":
            if p > extreme:
                extreme, extreme_t = p, t
            elif p <= extreme * 0.8:
                mode, peak_t, peak, extreme, extreme_t = "down", extreme_t, extreme, p, t
        else:
            if p < extreme:
                extreme, extreme_t = p, t
            elif p >= extreme * 1.2:
                episodes.append((peak_t, extreme_t, extreme / peak - 1))
                mode, extreme, extreme_t = "up", p, t
    if mode == "down":
        episodes.append((peak_t, extreme_t, extreme / peak - 1))
    return episodes


def replay_one_market(px: pd.Series, cash: pd.Series, kind: str):
    ret = px.pct_change().fillna(0).values
    gap = px.index.to_series().diff().dt.days.fillna(1).values
    cash_daily = (cash.reindex(px.index, method="ffill").ffill().bfill().values / 100) * gap / 360
    log_ret = np.log1p(ret)
    month_end = np.r_[px.index.to_period("M")[1:] != px.index.to_period("M")[:-1], True]
    week_end = np.r_[px.index.to_period("W")[1:] != px.index.to_period("W")[:-1], True]
    month_idx = np.where(month_end)[0]

    w, on, frac, nav = 1.0, 1.0, 1.0, 1.0
    navs, expo = np.empty(len(px)), np.empty(len(px))
    turnover, flip_back = 0.0, 0
    last_flip, last_state = -999, 1.0
    prices = px.values

    for t in range(len(px)):
        gross = 1 + w * ret[t] + (1 - w) * cash_daily[t]
        w = w * (1 + ret[t]) / gross
        nav *= gross
        navs[t], expo[t] = nav, w

        new_on, new_frac = on, frac
        if kind in ("K1", "K2") and month_end[t]:
            k = np.searchsorted(month_idx, t)
            if k >= 9:
                new_on = float(prices[t] >= prices[month_idx[k - 9 : k + 1]].mean())
        if kind == "K2" and week_end[t] and t >= 252:
            long_v = log_ret[t - 251 : t + 1].std()
            short_v = log_ret[t - 19 : t + 1].std()
            f = min(1.0, long_v / max(short_v, 1e-12))
            if abs(f - frac) >= 0.10:
                new_frac = f

        target = new_on * new_frac if kind != "K0" else 1.0
        if abs(target - w) > 1e-12 and (new_on != on or new_frac != frac or kind == "K0"):
            trade = 2 * abs(target - w) if kind != "K0" else 0.0
            nav *= 1 - LEG_COST * trade
            turnover += trade
            w = target
        if new_on != on:
            if t - last_flip <= 31 and new_on == last_state:
                flip_back += 1
            last_state, last_flip = on, t
        on, frac = new_on, new_frac

    return pd.Series(navs, index=px.index), pd.Series(expo, index=px.index), turnover, flip_back


def annualized(nav: pd.Series) -> float:
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    return (nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1


def max_drawdown(nav: pd.Series) -> float:
    return float((nav / nav.cummax() - 1).min())


def run_longhist_review(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    us_rate, jp_rate = us_cash_rate(), jp_cash_rate()
    rows = []
    for name, fname, start, end, cash_key in MARKETS:
        px = pd.read_csv(RAW / fname, parse_dates=["date"]).set_index("date")["close"]
        px = px[(px.index >= start) & (px.index <= end) & (px > 0)]
        rate = jp_rate if cash_key == "jp" else us_rate
        results = {k: replay_one_market(px, rate, k) for k in ("K0", "K1", "K2")}
        skip_until = px.index[0] + pd.Timedelta(days=366)
        bears = bear_episodes(px[px.index >= skip_until])
        in_bear = pd.Series(False, index=px.index)
        for p0, p1, _ in bears:
            in_bear[(in_bear.index > p0) & (in_bear.index <= p1)] = True
        years = (px.index[-1] - skip_until).days / 365.25
        k0_nav = results["K0"][0][results["K0"][0].index >= skip_until]
        k0_dr = k0_nav.pct_change().fillna(0)
        bear_slice = in_bear[in_bear.index >= skip_until]
        bull_years = (~bear_slice).sum() / 252
        bear_years = bear_slice.sum() / 252

        for kind, (nav_s, expo_s, turn, fb) in results.items():
            nav = nav_s[nav_s.index >= skip_until]
            dr = nav.pct_change().fillna(0)
            rows.append(
                {
                    "市场": name,
                    "结构": kind,
                    "年化_pct": round(annualized(nav) * 100, 2),
                    "比K0年化_pct": round((annualized(nav) - annualized(k0_nav)) * 100, 2),
                    "最大回撤_pct": round(max_drawdown(nav) * 100, 1),
                    "平均仓位": round(float(expo_s[expo_s.index >= skip_until].mean()), 3),
                    "双边换手_每年": round(turn / years, 2),
                    "成本_每年_百分点": round(turn / years * LEG_COST * 100, 3),
                    "一月内翻回_每年": round(fb / years, 2),
                    "熊市段数": len(bears),
                    "熊市占时间": round(bear_years / (bull_years + bear_years), 3),
                }
            )

    out = out_dir / "r2_longhist.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    run_longhist_review(Path(__file__).parent / "out")