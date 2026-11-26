"""D51 预演窗口的独立复算。只写本目录的锁定文件。

检验段 2011-01-01 → 2015-12-31 是唯一判定窗口。
2006 起的连续运行只为截出提供状态，不另报全段判据。
行情查询停在 2015-12-31。不读 src/v6、results/v6，不开考。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_d45 import A_SPEC, OFFICIAL, US_SPEC, bars_frame, build_levels, mix_monthly  # noqa: E402
from run_d47_health import (  # noqa: E402
    load_market,
    premium,
    require_cutoff,
    total_return_benchmarks,
    window_stats,
)
from run_d48_health import k2a_book  # noqa: E402
from src.report.metrics import cagr, max_drawdown  # noqa: E402
from v6ind.d45_engine import CUTOFF, US_TRIN, run_slot, trin_from_prices, votes  # noqa: E402
from v6ind.d45_french import us_prior, value_weighted_market  # noqa: E402
from v6ind.load import connect_readonly, load_fx  # noqa: E402

OUT = Path(__file__).resolve().parent / "output" / "d51-rehearsal-lock.json"
WINDOW = ("2011-01-01", "2015-12-31")
COST = 0.002
COST_S1 = 0.004


def sleeve_votes(levels_a, amounts_a, levels_u, us_px, us_am, clip: str):
    trin_columns = [name for name in levels_a.columns if name in US_TRIN or name.startswith("allshare-")
                    or name.startswith("theme-") or name in {"csi500", "csi1000", "chinext"}]
    vote_a = votes(levels_a, "csi300", trin_from_prices(levels_a[trin_columns], amounts_a[trin_columns], clip=clip))
    vote_u = votes(levels_u, "SPX", trin_from_prices(us_px, us_am, clip=clip))
    return vote_a, vote_u


def one_sleeve(levels, parent, vote, bond, cash, tags, prior, mode: str, cost: float,
               exclude: frozenset[str] | None = None):
    series, _turn, log = run_slot(
        levels, parent, vote, bond, cash, tags, prior,
        mode=mode, cost=cost, exclude=exclude,
    )
    require_cutoff(series.index, mode)
    return series, log


def book(levels_a, levels_u, vote_a, vote_u, bond, cash, tags_a, tags_u, prior,
         mode: str, cost: float, exclude: frozenset[str] | None = None):
    left, log_a = one_sleeve(levels_a, "csi300", vote_a, bond, cash, tags_a, None, mode, cost, exclude)
    right, log_u = one_sleeve(levels_u, "SPX", vote_u, bond, cash, tags_u, prior, mode, cost, exclude)
    mixed = mix_monthly(left, right, cost)
    require_cutoff(mixed.index, "组合")
    return mixed, {"A股": log_a, "美股": log_u}


def precise(series: pd.Series) -> dict:
    block = series.loc[WINDOW[0]:WINDOW[1]].dropna()
    require_cutoff(block.index, "判定窗口")
    if block.index[0] < pd.Timestamp("2011-01-01") or block.index[-1] > pd.Timestamp(CUTOFF):
        raise SystemExit("判定窗口越出 2011-01 至 2015-12")
    depth = max_drawdown(block)
    growth = float(cagr(block))
    drawdown = float(depth["max_drawdown"])
    return {
        "days": int(len(block)),
        "first": str(block.index[0].date()),
        "last": str(block.index[-1].date()),
        "cagr": growth,
        "max_drawdown": drawdown,
        "ratio": None if drawdown == 0.0 else growth / abs(drawdown),
        "peak": pd.Timestamp(depth["peak"]).date().isoformat(),
        "trough": pd.Timestamp(depth["trough"]).date().isoformat(),
    }


def criteria(v6: pd.Series, undefended: pd.Series, k2a: pd.Series, bm_same: pd.Series, bm_main: pd.Series) -> dict:
    held = precise(v6)
    plain = precise(undefended)
    bench = precise(k2a)
    same = precise(bm_same)
    prem = premium(undefended, v6, bm_main, *WINDOW)
    rounded = window_stats(v6, *WINDOW)
    excess = held["cagr"] - same["cagr"]
    flags = {
        "①": held["max_drawdown"] >= -0.40,
        "②": prem["premium_pp"] is not None and prem["premium_pp"] <= 4.0,
        "③": held["ratio"] is not None and bench["ratio"] is not None and held["ratio"] > bench["ratio"],
        "④": excess >= 0.0,
    }
    return {
        "最大回撤": held["max_drawdown"],
        "最大回撤_百分点": rounded["maxdd_pct"],
        "年化": held["cagr"],
        "年化_百分点": rounded["annual_pct"],
        "保费_百分点": prem["premium_pp"],
        "保费年份": prem["years"],
        "年化除以回撤": held["ratio"],
        "K2A年化除以回撤": bench["ratio"],
        "K2A年化": bench["cagr"],
        "K2A最大回撤": bench["max_drawdown"],
        "对同仓位超额": excess,
        "对同仓位超额_百分点": round(rounded["annual_pct"] - window_stats(bm_same, *WINDOW)["annual_pct"], 6),
        "不设防守年化": plain["cagr"],
        "高点": held["peak"],
        "低点": held["trough"],
        "判定": flags,
        "四条都过": all(flags.values()),
    }


def contributions(levels: pd.DataFrame, log: dict) -> dict[str, float]:
    """检验段内、下月仍不晚于 2015-12-31 的持有权重乘下月价格收益。"""
    stamps = sorted(log)
    total: dict[str, float] = {}
    start, end = pd.Timestamp(WINDOW[0]), pd.Timestamp(CUTOFF)
    for pos, stamp in enumerate(stamps[:-1]):
        nxt = stamps[pos + 1]
        if stamp < start or nxt > end:
            continue
        weights = log[stamp].get("权重") or {}
        for name, weight in weights.items():
            if name not in levels.columns or weight == 0.0:
                continue
            left = float(levels.at[stamp, name])
            right = float(levels.at[nxt, name])
            if not np.isfinite(left) or not np.isfinite(right) or left == 0.0:
                continue
            total[name] = total.get(name, 0.0) + float(weight) * (right / left - 1.0)
    return total


def main() -> None:
    if not OFFICIAL.exists():
        raise SystemExit(f"缺少已允许的 French 文件 {OFFICIAL}")
    con = connect_readonly(ROOT / "data" / "market.sqlite")
    codes = sorted({row[1] for row in A_SPEC} | {row[1] for row in US_SPEC} | {
        "XLK", "XLV", "XLE", "XLY", "XLP", "XLF", "XLI", "XLB", "XLU",
    })
    raw = bars_frame(con, codes)
    fx_rows = load_fx(con)
    con.close()
    fx = pd.Series([value for _day, value in fx_rows], index=pd.to_datetime([day for day, _value in fx_rows]))
    fx = fx[~fx.index.duplicated(keep="last")].sort_index()
    require_cutoff(fx.index, "汇率")
    frame = load_market()
    bond = frame["cgb-10y"].reindex(frame.index)
    cash = frame["cash"].reindex(frame.index)
    levels_a, amounts_a = build_levels(raw, A_SPEC, frame.index, None)
    levels_u, _amounts_u = build_levels(raw, US_SPEC, frame.index, fx)
    require_cutoff(levels_a.index, "A股面板")
    require_cutoff(levels_u.index, "美股面板")
    tags_a = {row[0]: row[3] for row in A_SPEC}
    tags_u = {row[0]: row[3] for row in US_SPEC}
    prior = us_prior(value_weighted_market(OFFICIAL.read_text(errors="replace")))
    us_prices, us_amounts = [], []
    for code in ("XLK", "XLV", "XLE", "XLY", "XLP", "XLF", "XLI", "XLB", "XLU"):
        close = raw[code]["close"]
        close = close[close > 0]
        close = close[~close.index.duplicated(keep="last")].sort_index()
        require_cutoff(close.index, code)
        volume = raw[code]["volume"].reindex(close.index)
        us_prices.append(close.rename(code))
        us_amounts.append((close * volume).where(lambda values: values > 0).rename(code))
    us_px = pd.concat(us_prices, axis=1).sort_index()
    us_am = pd.concat(us_amounts, axis=1).reindex(us_px.index)
    vote_a, vote_u = sleeve_votes(levels_a, amounts_a, levels_u, us_px, us_am, "full")
    benchmarks = total_return_benchmarks()
    k2a = k2a_book(frame)
    require_cutoff(k2a.index, "K2A")
    require_cutoff(benchmarks["BM-主"].index, "BM-主")

    v6, logs = book(levels_a, levels_u, vote_a, vote_u, bond, cash, tags_a, tags_u, prior, "v6", COST)
    plain, _plain_logs = book(
        levels_a, levels_u, vote_a, vote_u, bond, cash, tags_a, tags_u, prior, "top", COST)
    base = criteria(v6, plain, k2a, benchmarks["BM-同仓位"], benchmarks["BM-主"])

    v6_s1, _logs_s1 = book(
        levels_a, levels_u, vote_a, vote_u, bond, cash, tags_a, tags_u, prior, "v6", COST_S1)
    plain_s1, _plain_s1 = book(
        levels_a, levels_u, vote_a, vote_u, bond, cash, tags_a, tags_u, prior, "top", COST_S1)
    s1 = criteria(v6_s1, plain_s1, k2a, benchmarks["BM-同仓位"], benchmarks["BM-主"])

    ranked: dict[str, float] = {}
    for sleeve, levels in (("A股", levels_a), ("美股", levels_u)):
        for name, value in contributions(levels, logs[sleeve]).items():
            ranked[name] = ranked.get(name, 0.0) + value
    order = sorted(ranked, key=lambda name: (-ranked[name], name))
    if not order:
        raise SystemExit("检验段没有可排序的持有贡献")
    dropped = order[0]
    excluded = frozenset({dropped})
    v6_s3, _logs_s3 = book(
        levels_a, levels_u, vote_a, vote_u, bond, cash, tags_a, tags_u, prior, "v6", COST, excluded)
    plain_s3, _plain_s3 = book(
        levels_a, levels_u, vote_a, vote_u, bond, cash, tags_a, tags_u, prior, "top", COST, excluded)
    s3 = criteria(v6_s3, plain_s3, k2a, benchmarks["BM-同仓位"], benchmarks["BM-主"])

    payload = {
        "cutoff": pd.Timestamp(CUTOFF).date().isoformat(),
        "path": "连续运行截出",
        "history": "2006-01-01 → 2015-12-31 的状态连续累积，判定只切 2011-01-01 → 2015-12-31",
        "cost_one_way": COST,
        "undefended": "前3、不设防守、单边 0.2%、每月末 60/40",
        "contribution": (
            "2011-01 至 2015-11 月末信号，下月价格收益的月末不晚于 2015-12-31；"
            "贡献 = 持有权重 × 下月价格收益，两名额加总后取最大的一个名字；"
            "v6 与不设防守都去掉这个名字"
        ),
        "S1": "两条腿和月末 60/40 再平衡都是单边 0.4%；不设防守同样；BM-主、K2A、BM-同仓位不动",
        "基准不随S移动": ["BM-主", "K2A", "BM-同仓位"],
        "主规则": base,
        "S1结果": s1,
        "S3结果": s3,
        "S3去掉": dropped,
        "S3贡献前8": [{"候选": name, "贡献": ranked[name]} for name in order[:8]],
        "K2A与主规则相同": s1["K2A年化除以回撤"] == base["K2A年化除以回撤"] and s3["K2A年化除以回撤"] == base["K2A年化除以回撤"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(OUT)
    print("dropped", dropped)
    print("premium", base["保费_百分点"])
    print("dd", base["最大回撤"])
    print("ratio", base["年化除以回撤"], base["K2A年化除以回撤"])
    print("excess_pp", base["对同仓位超额_百分点"])
    print("flags", base["判定"])


if __name__ == "__main__":
    main()
