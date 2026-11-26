"""正式一次性检验的独立复算。先写锁定文件，再允许对照 Dev。

检验段来自冻结稿 §5：2016-01-01 → 2026-09-30。
全段 2006-01-01 → 2026-09-30 只提供连续运行的状态，判定只切检验段、指数池。
判定成本单边 0.2%。不读 results/v6/oneshot 的判定数字。
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_d45 import A_SPEC, US_SPEC, bars_frame, build_levels, mix_monthly  # noqa: E402
from run_d47_health import complete_year_returns  # noqa: E402
from run_d48_health import k2a_book  # noqa: E402
from src.report.blend import monthly_rebalance  # noqa: E402
from src.report.metrics import cagr, max_drawdown, monthly_returns  # noqa: E402
from src.v4.r5.design import load_spec, prepare_market, reference_frame  # noqa: E402
from v6ind.d45_engine import US_TRIN, run_slot, trin_from_prices, votes  # noqa: E402
from v6ind.d45_french import us_prior  # noqa: E402
from v6ind.load import connect_readonly, load_fx  # noqa: E402

OUT = Path(__file__).resolve().parent / "output" / "d52-official-lock.json"
EXAM = ("2016-01-01", "2026-09-30")
EXAM_END = pd.Timestamp("2026-09-30")
COST = 0.002
COST_S1 = 0.004
FRENCH = ROOT / "results/v6/french-49-192607-199812"


def cap(index: pd.DatetimeIndex, what: str) -> None:
    if len(index) and pd.Timestamp(index.max()) > EXAM_END:
        raise SystemExit(f"{what} 晚于 2026-09-30：{pd.Timestamp(index.max()).date()}")


def french_frame() -> pd.DataFrame:
    def load(name: str) -> pd.DataFrame:
        frame = pd.read_csv(FRENCH / name)
        frame["yyyymm"] = frame["yyyymm"].astype(str)
        frame = frame[(frame["yyyymm"] >= "192607") & (frame["yyyymm"] <= "199812")]
        frame.index = pd.to_datetime(frame["yyyymm"], format="%Y%m") + pd.offsets.MonthEnd(0)
        frame = frame.drop(columns=["yyyymm"]).astype(float)
        return frame.where(lambda values: values > -99.0)

    returns = load("vw-monthly.csv") / 100.0
    firms = load("n-firms.csv")
    size = load("avg-firm-size.csv")
    cap_value = firms * size
    weights = cap_value.shift(1).div(cap_value.shift(1).sum(axis=1), axis=0)
    market = (weights * returns).sum(axis=1, min_count=1)
    returns = returns.loc["1953":]
    market = market.loc["1953":]
    return pd.concat([returns, market.rename("MKT")], axis=1)


def market_frame() -> pd.DataFrame:
    signal = prepare_market(
        "index", t4=False, allow_substitute=True, spec=load_spec(),
        end="2026-09-30", allow_after=True,
    ).signal
    frame = signal.loc[:EXAM_END]
    needed = ["csi300", "spx", "ndx100", "cgb-10y", "cash"]
    missing = [name for name in needed if name not in frame.columns]
    if missing:
        raise SystemExit(f"指数池缺列：{missing}")
    frame = frame[frame[["csi300", "spx", "ndx100"]].notna().all(axis=1)]
    cap(frame.index, "指数池")
    return frame


def benchmarks() -> dict[str, pd.Series]:
    parts = reference_frame(end="2026-09-30", allow_after=True).loc[:EXAM_END].dropna()
    cap(parts.index, "全收益基准")
    main, _weights = monthly_rebalance(parts, {"H00300": 0.70, "XNDX": 0.15, "SP500TR": 0.15})
    same, _weights = monthly_rebalance(parts, {"H00300": 0.40, "XNDX": 0.30, "SP500TR": 0.30})
    return {"BM-主": main, "BM-同仓位": same}


def votes_for(levels_a, amounts_a, levels_u, us_px, us_am):
    trin_columns = [name for name in levels_a.columns if name in US_TRIN or name.startswith("allshare-")
                    or name.startswith("theme-") or name in {"csi500", "csi1000", "chinext"}]
    vote_a = votes(levels_a, "csi300", trin_from_prices(levels_a[trin_columns], amounts_a[trin_columns], clip="expanding"))
    vote_u = votes(levels_u, "SPX", trin_from_prices(us_px, us_am, clip="expanding"))
    return vote_a, vote_u


def one(levels, parent, vote, bond, cash, tags, prior, mode: str, cost: float,
        exclude: frozenset[str] | None = None):
    series, _turn, log = run_slot(
        levels, parent, vote, bond, cash, tags, prior,
        mode=mode, cost=cost, exclude=exclude,
    )
    cap(series.index, mode)
    return series, log


def mix(levels_a, levels_u, vote_a, vote_u, bond, cash, tags_a, tags_u, prior,
        mode_a: str, mode_u: str, cost: float, exclude: frozenset[str] | None = None):
    left, log_a = one(levels_a, "csi300", vote_a, bond, cash, tags_a, None, mode_a, cost, exclude)
    right, log_u = one(levels_u, "SPX", vote_u, bond, cash, tags_u, prior, mode_u, cost, exclude)
    mixed = mix_monthly(left, right, cost)
    cap(mixed.index, "组合")
    return mixed, left, right, {"A股": log_a, "美股": log_u}


def precise(series: pd.Series) -> dict:
    block = series.loc[EXAM[0]:EXAM[1]].dropna()
    cap(block.index, "检验段")
    if block.index[0] < pd.Timestamp(EXAM[0]):
        raise SystemExit("检验段含有 2016-01-01 之前的收益")
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
    }


def premium_pp(undefended: pd.Series, strategy: pd.Series, benchmark: pd.Series) -> dict:
    return premium_pp_window(undefended, strategy, benchmark, 2016, 2026)


def premium_pp_window(undefended: pd.Series, strategy: pd.Series, benchmark: pd.Series,
                      first: int, last: int) -> dict:
    years = range(first, last + 1)
    bench = complete_year_returns(benchmark)
    plain = complete_year_returns(undefended)
    held = complete_year_returns(strategy)
    used = []
    for year in years:
        if year not in bench or year not in plain or year not in held:
            continue
        if bench[year] <= 0.0:
            continue
        used.append({
            "year": year,
            "bm_main": bench[year],
            "undefended": plain[year],
            "strategy": held[year],
            "gap_pp": (plain[year] - held[year]) * 100.0,
        })
    gap = float(np.mean([row["gap_pp"] for row in used])) if used else None
    return {"premium_pp": gap, "years": [row["year"] for row in used], "detail": used}


def criteria(strategy: pd.Series, undefended: pd.Series, k2a: pd.Series,
            bm_same: pd.Series, bm_main: pd.Series) -> dict:
    held = precise(strategy)
    plain = precise(undefended)
    bench = precise(k2a)
    same = precise(bm_same)
    prem = premium_pp(undefended, strategy, bm_main)
    excess = held["cagr"] * 100.0 - same["cagr"] * 100.0
    flags = {
        "①": held["max_drawdown"] >= -0.40,
        "②": prem["premium_pp"] is not None and prem["premium_pp"] <= 4.0,
        "③": held["ratio"] is not None and bench["ratio"] is not None and held["ratio"] > bench["ratio"],
        "④": excess >= 0.0,
    }
    return {
        "最大回撤": held["max_drawdown"],
        "年化": held["cagr"],
        "保费_百分点": prem["premium_pp"],
        "保费年份": prem["years"],
        "年化除以回撤": held["ratio"],
        "K2A年化除以回撤": bench["ratio"],
        "K2A年化": bench["cagr"],
        "K2A最大回撤": bench["max_drawdown"],
        "对同仓位超额_百分点": excess,
        "不设防守年化": plain["cagr"],
        "日数": held["days"],
        "起": held["first"],
        "止": held["last"],
        "判定": flags,
        "四条都过": all(flags.values()),
    }


def contributions(levels: pd.DataFrame, log: dict) -> dict[str, float]:
    stamps = sorted(log)
    total: dict[str, float] = {}
    start = pd.Timestamp(EXAM[0])
    for pos, stamp in enumerate(stamps[:-1]):
        nxt = stamps[pos + 1]
        if stamp < start or nxt > EXAM_END:
            continue
        for name, weight in (log[stamp].get("权重") or {}).items():
            if name not in levels.columns or weight == 0.0:
                continue
            left = float(levels.at[stamp, name])
            right = float(levels.at[nxt, name])
            if not np.isfinite(left) or not np.isfinite(right) or left == 0.0:
                continue
            total[name] = total.get(name, 0.0) + float(weight) * (right / left - 1.0)
    return total


def slot_t(cont: pd.Series, base: pd.Series) -> dict:
    diff = (monthly_returns(cont.loc[EXAM[0]:EXAM[1]]) - monthly_returns(base.loc[EXAM[0]:EXAM[1]])).dropna()
    count = int(len(diff))
    mean = float(diff.mean()) if count else None
    scale = float(diff.std(ddof=1)) if count > 1 else None
    t_value = None if not scale else mean / (scale / math.sqrt(count))
    return {"月数": count, "月均差": mean, "t": t_value}


def main() -> None:
    if not FRENCH.exists():
        raise SystemExit(f"缺少 French 面板 {FRENCH}")
    con = connect_readonly(ROOT / "data" / "market.sqlite")
    codes = sorted({row[1] for row in A_SPEC} | {row[1] for row in US_SPEC} | {
        "XLK", "XLV", "XLE", "XLY", "XLP", "XLF", "XLI", "XLB", "XLU",
    })
    from v6ind.load import load_fields
    raw = {}
    for code in codes:
        rows = load_fields(con, code, cutoff="2026-09-30")
        if not rows:
            raw[code] = pd.DataFrame(columns=["close", "volume", "amount"])
            continue
        frame = pd.DataFrame(rows, columns=["date", "close", "volume", "amount"])
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.set_index("date").sort_index()
        frame = frame[~frame.index.duplicated(keep="last")]
        frame = frame.loc[:EXAM_END]
        cap(frame.index, code)
        raw[code] = frame
    fx_rows = load_fx(con, cutoff="2026-09-30")
    con.close()
    fx = pd.Series([value for _day, value in fx_rows], index=pd.to_datetime([day for day, _value in fx_rows]))
    fx = fx[~fx.index.duplicated(keep="last")].sort_index().loc[:EXAM_END]
    cap(fx.index, "汇率")
    frame = market_frame()
    bond = frame["cgb-10y"].reindex(frame.index)
    cash = frame["cash"].reindex(frame.index)
    levels_a, amounts_a = build_levels(raw, A_SPEC, frame.index, None)
    levels_u, _amounts_u = build_levels(raw, US_SPEC, frame.index, fx)
    cap(levels_a.index, "A股面板")
    cap(levels_u.index, "美股面板")
    tags_a = {row[0]: row[3] for row in A_SPEC}
    tags_u = {row[0]: row[3] for row in US_SPEC}
    prior = us_prior(french_frame())
    us_prices, us_amounts = [], []
    for code in ("XLK", "XLV", "XLE", "XLY", "XLP", "XLF", "XLI", "XLB", "XLU"):
        close = raw[code]["close"]
        close = close[close > 0]
        close = close[~close.index.duplicated(keep="last")].sort_index().loc[:EXAM_END]
        cap(close.index, code)
        volume = raw[code]["volume"].reindex(close.index)
        us_prices.append(close.rename(code))
        us_amounts.append((close * volume).where(lambda values: values > 0).rename(code))
    us_px = pd.concat(us_prices, axis=1).sort_index()
    us_am = pd.concat(us_amounts, axis=1).reindex(us_px.index)
    vote_a, vote_u = votes_for(levels_a, amounts_a, levels_u, us_px, us_am)
    bench = benchmarks()
    k2a = k2a_book(frame)
    cap(k2a.index, "K2A")

    v6, a_v6, _u_v6, logs = mix(
        levels_a, levels_u, vote_a, vote_u, bond, cash, tags_a, tags_u, prior, "v6", "v6", COST)
    plain, _a_top, _u_top, _logs_top = mix(
        levels_a, levels_u, vote_a, vote_u, bond, cash, tags_a, tags_u, prior, "top", "top", COST)
    base = criteria(v6, plain, k2a, bench["BM-同仓位"], bench["BM-主"])
    rehearsal = premium_pp_window(plain, v6, bench["BM-主"], 2011, 2015)

    v6_s1, _a, _u, _logs_s1 = mix(
        levels_a, levels_u, vote_a, vote_u, bond, cash, tags_a, tags_u, prior, "v6", "v6", COST_S1)
    plain_s1, _a, _u, _logs_plain_s1 = mix(
        levels_a, levels_u, vote_a, vote_u, bond, cash, tags_a, tags_u, prior, "top", "top", COST_S1)
    s1 = criteria(v6_s1, plain_s1, k2a, bench["BM-同仓位"], bench["BM-主"])

    ranked: dict[str, float] = {}
    for sleeve, levels in (("A股", levels_a), ("美股", levels_u)):
        for name, value in contributions(levels, logs[sleeve]).items():
            ranked[name] = ranked.get(name, 0.0) + value
    order = sorted(ranked, key=lambda name: (-ranked[name], name))
    if not order:
        raise SystemExit("检验段没有可排序的持有贡献")
    dropped = order[0]
    excluded = frozenset({dropped})
    v6_s3, _a, _u, _logs_s3 = mix(
        levels_a, levels_u, vote_a, vote_u, bond, cash, tags_a, tags_u, prior,
        "v6", "v6", COST, excluded)
    plain_s3, _a, _u, _logs_plain_s3 = mix(
        levels_a, levels_u, vote_a, vote_u, bond, cash, tags_a, tags_u, prior,
        "top", "top", COST, excluded)
    s3 = criteria(v6_s3, plain_s3, k2a, bench["BM-同仓位"], bench["BM-主"])

    cont, a_cont, _u_cont, _logs_cont = mix(
        levels_a, levels_u, vote_a, vote_u, bond, cash, tags_a, tags_u, prior, "cont", "v6", COST)
    cont_plain, _a_plain, _u_plain, _logs_plain = mix(
        levels_a, levels_u, vote_a, vote_u, bond, cash, tags_a, tags_u, prior, "cont_plain", "top", COST)
    continuity = criteria(cont, cont_plain, k2a, bench["BM-同仓位"], bench["BM-主"])
    difference = slot_t(a_cont, a_v6)

    payload = {
        "path": "连续运行截出",
        "pool": "指数池",
        "检验段": {"start": EXAM[0], "end": EXAM[1]},
        "全段": "2006-01-01 → 2026-09-30 只累积状态，不进判定",
        "cost_one_way": COST,
        "undefended": "前3、不设防守、单边 0.2%、每月末 60/40",
        "continuity_undefended": "A 股连续性版前3不设防守，美股 12−1 前3不设防守，单边 0.2%",
        "主规则": base,
        "S1结果": s1,
        "S3结果": s3,
        "S3去掉": dropped,
        "S3贡献前8": [{"候选": name, "贡献": ranked[name]} for name in order[:8]],
        "连续性版": continuity,
        "A股名额月度差": difference,
        "K2A不随S移动": (
            s1["K2A年化除以回撤"] == base["K2A年化除以回撤"]
            and s3["K2A年化除以回撤"] == base["K2A年化除以回撤"]
        ),
        "设计期2011-15保费自检": rehearsal,
        "TRIN": "99% 上限用扩展分位，到当时为止；投票门槛仍是扩展的 1/3 与 2/3",
        "数据止于": str(frame.index.max().date()),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(OUT)
    print("premium", base["保费_百分点"], "years", base["保费年份"])
    print("dd", base["最大回撤"], "ratio", base["年化除以回撤"], "k2a", base["K2A年化除以回撤"])
    print("excess", base["对同仓位超额_百分点"], "flags", base["判定"])
    print("rehearsal_premium", rehearsal["premium_pp"], rehearsal["years"])
    print("cont", continuity["判定"], "t", difference)


if __name__ == "__main__":
    main()
