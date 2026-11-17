"""Reviewer 独立复算 D38 沪深300 单市场回放（项目池 index ≤2015，不用 scripts/preflight）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from review_longhist import annualized, max_drawdown, replay_one_market

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from src.v3.engine.spec import load_spec  # noqa: E402
from src.v4.r5.design import Markets  # noqa: E402

CASH_ANNUAL_PCT = 2.54  # 与 csi300.json _说明 一致


def load_csi300_prices() -> pd.Series:
    markets = Markets(load_spec()).get("index", t4=False, allow_substitute=True)
    r = markets.signal.loc["2006-01-06":"2015-12-31", "csi300"].dropna()
    return pd.Series(np.exp(np.log1p(r).cumsum()), index=r.index, name="csi300")


def run_csi300_review(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    px = load_csi300_prices()
    rate = pd.Series(CASH_ANNUAL_PCT, index=px.index)
    results = {}
    k0_nav = None
    years = (px.index[-1] - px.index[0]).days / 365.25
    for kind in ("K0", "K1", "K2"):
        nav_s, expo_s, turn, _ = replay_one_market(px, rate, kind)
        if kind == "K0":
            k0_nav = nav_s
        results[kind] = {
            "年化": round(annualized(nav_s) * 100, 2),
            "比K0年化": round((annualized(nav_s) - annualized(k0_nav)) * 100, 2),
            "最大回撤": round(max_drawdown(nav_s) * 100, 1),
            "平均仓位": round(float(expo_s.mean()), 3),
            "成本_每年_百分点": round(turn / years * 0.001 * 100, 3),
        }
    out = out_dir / "r9_csi300.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    run_csi300_review(Path(__file__).parent / "out")