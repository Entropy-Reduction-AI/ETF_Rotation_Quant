"""官方窗口水平差的诊断重放。

只重放主规则的两条路径，写出本目录的对照表。
不调用 oneshot_exam.execute / main，不写 results/v6/oneshot，不写 Reviewer 锁文件。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
IND = ROOT / "operations" / "reviews" / "v6-independent-design"
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(IND))

from src.report.metrics import cagr, max_drawdown, yearly_returns  # noqa: E402
from src.v6.guard import open_official_isolation  # noqa: E402
from src.v6.health import _benchmarks, _k2a  # noqa: E402
from src.v6.load import load_panels  # noqa: E402
from src.v6.oneshot_exam import COST, _variant  # noqa: E402
from src.v6.oneshot_prep import premium_pp  # noqa: E402
from src.v6.prior import us_prior as dev_prior  # noqa: E402
from src.v6.run_design import PANEL, TAGS, _a_daily, _us_daily  # noqa: E402
from src.v6.trin import clip_expanding, month_end_mean  # noqa: E402
from run_d45 import A_SPEC, US_SPEC, build_levels, mix_monthly  # noqa: E402
from run_d47_health import complete_year_returns  # noqa: E402
from run_d48_health import k2a_book  # noqa: E402
from v6ind.d45_engine import US_TRIN, run_slot, trin_from_prices, votes  # noqa: E402
from v6ind.d45_french import us_prior as rev_prior  # noqa: E402
from v6ind.load import connect_readonly, load_fields, load_fx  # noqa: E402

EXAM = ("2016-01-01", "2026-09-30")
EXAM_END = pd.Timestamp("2026-09-30")
TOL = 1e-8
FORBIDDEN = (
    ROOT / "results" / "v6" / "oneshot",
    IND / "output" / "d52-official-lock.json",
    IND / "output" / "d51-rehearsal-lock.json",
)


def _guard_write(path: Path) -> None:
    resolved = path.resolve()
    for blocked in FORBIDDEN:
        if resolved == blocked.resolve() or blocked.resolve() in resolved.parents:
            raise SystemExit(f"拒绝写入 {resolved}")
    if OUT.resolve() not in resolved.parents and resolved != OUT.resolve():
        raise SystemExit(f"只写诊断目录：{resolved}")


def _write_json(name: str, payload: dict) -> None:
    path = OUT / name
    _guard_write(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _write_csv(name: str, frame: pd.DataFrame) -> None:
    path = OUT / name
    _guard_write(path)
    frame.to_csv(path, index=False)


def _cap(index: pd.DatetimeIndex, what: str) -> None:
    if len(index) and pd.Timestamp(index.max()) > EXAM_END:
        raise SystemExit(f"{what} 晚于 2026-09-30：{pd.Timestamp(index.max()).date()}")


def _french() -> pd.DataFrame:
    def load(name: str) -> pd.DataFrame:
        frame = pd.read_csv(ROOT / "results" / "v6" / "french-49-192607-199812" / name)
        frame["yyyymm"] = frame["yyyymm"].astype(str)
        frame = frame[(frame["yyyymm"] >= "192607") & (frame["yyyymm"] <= "199812")]
        frame.index = pd.to_datetime(frame["yyyymm"], format="%Y%m") + pd.offsets.MonthEnd(0)
        return frame.drop(columns=["yyyymm"]).astype(float).where(lambda values: values > -99.0)

    returns = load("vw-monthly.csv") / 100.0
    firms = load("n-firms.csv")
    size = load("avg-firm-size.csv")
    cap = firms * size
    weights = cap.shift(1).div(cap.shift(1).sum(axis=1), axis=0)
    market = (weights * returns).sum(axis=1, min_count=1)
    returns = returns.loc["1953":]
    market = market.loc["1953":]
    return pd.concat([returns, market.rename("MKT")], axis=1)


def _reviewer_market() -> pd.DataFrame:
    from src.v4.r5.design import load_spec, prepare_market

    signal = prepare_market(
        "index", t4=False, allow_substitute=True, spec=load_spec(),
        end="2026-09-30", allow_after=True,
    ).signal
    frame = signal.loc[:EXAM_END]
    frame = frame[frame[["csi300", "spx", "ndx100"]].notna().all(axis=1)]
    _cap(frame.index, "Reviewer 指数池")
    return frame


def _reviewer_benchmarks() -> dict[str, pd.Series]:
    from src.report.blend import monthly_rebalance
    from src.v4.r5.design import reference_frame

    parts = reference_frame(end="2026-09-30", allow_after=True).loc[:EXAM_END].dropna()
    _cap(parts.index, "Reviewer 全收益基准")
    main, _weights = monthly_rebalance(parts, {"H00300": 0.70, "XNDX": 0.15, "SP500TR": 0.15})
    same, _weights = monthly_rebalance(parts, {"H00300": 0.40, "XNDX": 0.30, "SP500TR": 0.30})
    return {"BM-主": main, "BM-同仓位": same}


def _stats(series: pd.Series) -> dict:
    block = series.loc[EXAM[0]:EXAM[1]].dropna()
    depth = float(max_drawdown(block)["max_drawdown"])
    growth = float(cagr(block))
    return {
        "days": int(len(block)),
        "first": str(block.index[0].date()),
        "last": str(block.index[-1].date()),
        "cagr": growth,
        "max_drawdown": depth,
        "ratio": None if depth == 0.0 else growth / abs(depth),
    }


def _rev_premium(undefended: pd.Series, strategy: pd.Series, benchmark: pd.Series) -> dict:
    bench = complete_year_returns(benchmark)
    plain = complete_year_returns(undefended)
    held = complete_year_returns(strategy)
    used = []
    for year in range(2016, 2027):
        if year not in bench or year not in plain or year not in held or bench[year] <= 0.0:
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


def _signal_rows(log: dict, sleeve: str, side: str) -> list[dict]:
    rows = []
    for stamp, record in sorted(log.items()):
        scores = record.get("分数") or {}
        if side == "dev":
            eligible = list(record.get("可参选名单") or [])
            position = record.get("股票仓位")
            bond = record.get("国债在均线上方")
        else:
            eligible = list(scores)
            position = record.get("股票仓位")
            bond = record.get("国债")
        held = list(record.get("持有") or [])
        rows.append({
            "month": str(pd.Timestamp(stamp).to_period("M")),
            "date": pd.Timestamp(stamp).date().isoformat(),
            "sleeve": sleeve,
            "side": side,
            "held": "|".join(held),
            "n_held": len(held),
            "position": position,
            "votes": record.get("票数"),
            "stress": record.get("紧张"),
            "p": record.get("p"),
            "gate": record.get("母指数跌破均线"),
            "eligible_n": record.get("可参选"),
            "eligible": "|".join(sorted(eligible)),
            "bond": bond,
            "weights": json.dumps(record.get("权重") or {}, ensure_ascii=False),
            "scores": json.dumps({name: scores.get(name) for name in held}, ensure_ascii=False),
        })
    return rows


def run_reviewer() -> dict:
    con = connect_readonly(ROOT / "data" / "market.sqlite")
    codes = sorted({row[1] for row in A_SPEC} | {row[1] for row in US_SPEC} | {
        "XLK", "XLV", "XLE", "XLY", "XLP", "XLF", "XLI", "XLB", "XLU",
    })
    raw = {}
    for code in codes:
        rows = load_fields(con, code, cutoff="2026-09-30")
        if not rows:
            raw[code] = pd.DataFrame(columns=["close", "volume", "amount"])
            continue
        frame = pd.DataFrame(rows, columns=["date", "close", "volume", "amount"])
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.set_index("date").sort_index()
        frame = frame[~frame.index.duplicated(keep="last")].loc[:EXAM_END]
        _cap(frame.index, code)
        raw[code] = frame
    fx_rows = load_fx(con, cutoff="2026-09-30")
    con.close()
    fx = pd.Series(
        [value for _day, value in fx_rows],
        index=pd.to_datetime([day for day, _value in fx_rows]),
    )
    fx = fx[~fx.index.duplicated(keep="last")].sort_index().loc[:EXAM_END]
    _cap(fx.index, "汇率")
    market = _reviewer_market()
    bond = market["cgb-10y"].reindex(market.index)
    cash = market["cash"].reindex(market.index)
    levels_a, amounts_a = build_levels(raw, A_SPEC, market.index, None)
    levels_u, _amounts_u = build_levels(raw, US_SPEC, market.index, fx)
    _cap(levels_a.index, "Reviewer A股")
    _cap(levels_u.index, "Reviewer 美股")
    tags_a = {row[0]: row[3] for row in A_SPEC}
    tags_u = {row[0]: row[3] for row in US_SPEC}
    prior = rev_prior(_french())
    us_prices, us_amounts = [], []
    for code in ("XLK", "XLV", "XLE", "XLY", "XLP", "XLF", "XLI", "XLB", "XLU"):
        close = raw[code]["close"]
        close = close[close > 0]
        close = close[~close.index.duplicated(keep="last")].sort_index().loc[:EXAM_END]
        volume = raw[code]["volume"].reindex(close.index)
        us_prices.append(close.rename(code))
        us_amounts.append((close * volume).where(lambda values: values > 0).rename(code))
    us_px = pd.concat(us_prices, axis=1).sort_index()
    us_am = pd.concat(us_amounts, axis=1).reindex(us_px.index)
    trin_columns = [name for name in levels_a.columns if name in US_TRIN or name.startswith("allshare-")
                    or name.startswith("theme-") or name in {"csi500", "csi1000", "chinext"}]
    vote_a = votes(levels_a, "csi300", trin_from_prices(levels_a[trin_columns], amounts_a[trin_columns], clip="expanding"))
    vote_u = votes(levels_u, "SPX", trin_from_prices(us_px, us_am, clip="expanding"))

    def one(levels, parent, vote, tags, mode: str):
        series, _turn, log = run_slot(
            levels, parent, vote, bond, cash, tags, prior if parent == "SPX" else None,
            mode=mode, cost=COST,
        )
        _cap(series.index, mode)
        return series, log

    a_v6, log_a = one(levels_a, "csi300", vote_a, tags_a, "v6")
    u_v6, log_u = one(levels_u, "SPX", vote_u, tags_u, "v6")
    a_top, log_a_top = one(levels_a, "csi300", vote_a, tags_a, "top")
    u_top, log_u_top = one(levels_u, "SPX", vote_u, tags_u, "top")
    v6 = mix_monthly(a_v6, u_v6, COST)
    top = mix_monthly(a_top, u_top, COST)
    bench = _reviewer_benchmarks()
    k2a = k2a_book(market)
    held = _stats(v6)
    same = _stats(bench["BM-同仓位"])
    prem = _rev_premium(top, v6, bench["BM-主"])
    summary = {
        "最大回撤": held["max_drawdown"],
        "年化": held["cagr"],
        "保费_百分点": prem["premium_pp"],
        "保费年份": prem["years"],
        "保费明细": prem["detail"],
        "年化除以回撤": held["ratio"],
        "对同仓位超额_百分点": held["cagr"] * 100.0 - same["cagr"] * 100.0,
        "不设防守年化": _stats(top)["cagr"],
        "K2A": _stats(k2a),
        "BM同仓位": same,
        "日数": held["days"],
        "起": held["first"],
        "止": held["last"],
        "列_A": list(levels_a.columns),
        "列_美": list(levels_u.columns),
        "起点经验条数": len(prior),
    }
    daily = pd.DataFrame({
        "date": v6.index,
        "v6": v6.to_numpy(),
        "不设防守": top.reindex(v6.index).to_numpy(),
        "A": a_v6.reindex(v6.index).to_numpy(),
        "美": u_v6.reindex(v6.index).to_numpy(),
        "A不设防守": a_top.reindex(v6.index).to_numpy(),
        "美不设防守": u_top.reindex(v6.index).to_numpy(),
        "BM主": bench["BM-主"].reindex(v6.index).to_numpy(),
        "BM同仓位": bench["BM-同仓位"].reindex(v6.index).to_numpy(),
        "K2A": k2a.reindex(v6.index).to_numpy(),
        "bond": bond.reindex(v6.index).to_numpy(),
        "cash": cash.reindex(v6.index).to_numpy(),
    })
    signals = (
        _signal_rows(log_a, "A", "rev") + _signal_rows(log_u, "美", "rev")
        + _signal_rows(log_a_top, "A不设防守", "rev") + _signal_rows(log_u_top, "美不设防守", "rev")
    )
    levels = {"A": levels_a, "美": levels_u}
    return {"summary": summary, "daily": daily, "signals": pd.DataFrame(signals), "levels": levels, "prior": prior}


def run_dev() -> dict:
    panels = load_panels()
    panels["trin"]["csi300"] = month_end_mean(clip_expanding(_a_daily(panels)))
    panels["trin"]["SPX"] = month_end_mean(clip_expanding(_us_daily(panels)))
    prior = dev_prior(PANEL)
    base = _variant(
        panels, prior, panels["votes"], panels["bond"], panels["cash"],
        n=3, cost=COST, lag=0, stress=2, exclude=None, weight_a=0.4,
    )
    bm_main, bm_same = _benchmarks()
    k2a = _k2a(panels, True)
    official = pd.read_csv(ROOT / "results" / "v6" / "oneshot" / "returns-daily.csv", parse_dates=["date"])
    official = official.set_index("date").sort_index()
    v6 = base["净"]
    top = base["不设防守"]
    joined = pd.concat([
        v6.rename("replay"),
        official["v6"].rename("official"),
    ], axis=1, join="inner")
    gap = (joined["replay"] - joined["official"]).abs()
    top_joined = pd.concat([
        top.rename("replay"),
        official["不设防守"].rename("official"),
    ], axis=1, join="inner")
    top_gap = (top_joined["replay"] - top_joined["official"]).abs()
    match = {
        "v6_max_abs": float(gap.max()) if len(gap) else None,
        "v6_days": int(len(joined)),
        "undefended_max_abs": float(top_gap.max()) if len(top_gap) else None,
        "matches_official_v6": bool(len(gap) and float(gap.max()) < 1e-9),
        "matches_official_undefended": bool(len(top_gap) and float(top_gap.max()) < 1e-9),
    }
    held = _stats(v6)
    same = _stats(bm_same)
    prem = premium_pp(v6, top, bm_main, *EXAM)
    summary = {
        "最大回撤": held["max_drawdown"],
        "年化": held["cagr"],
        "保费_百分点": prem,
        "年化除以回撤": held["ratio"],
        "对同仓位超额_百分点": held["cagr"] * 100.0 - same["cagr"] * 100.0,
        "不设防守年化": _stats(top)["cagr"],
        "K2A": _stats(k2a),
        "BM同仓位": same,
        "日数": held["days"],
        "起": held["first"],
        "止": held["last"],
        "列_A": list(panels["A"].columns),
        "列_美": list(panels["US"].columns),
        "起点经验条数": len(prior),
        "与交卷日收益": match,
        "交卷保费公式_重放": prem,
        "Reviewer保费公式_打在Dev序列上": _rev_premium(top, v6, bm_main),
    }
    daily = pd.DataFrame({
        "date": v6.index,
        "v6": v6.to_numpy(),
        "不设防守": top.reindex(v6.index).to_numpy(),
        "A": base["A"].reindex(v6.index).to_numpy(),
        "美": base["美"].reindex(v6.index).to_numpy(),
        "BM主": bm_main.reindex(v6.index).to_numpy(),
        "BM同仓位": bm_same.reindex(v6.index).to_numpy(),
        "K2A": k2a.reindex(v6.index).to_numpy(),
        "bond": panels["bond"].reindex(v6.index).to_numpy(),
        "cash": panels["cash"].reindex(v6.index).to_numpy(),
    })
    # 不设防守的名额序列不在 _variant 的顶层。保费对照只用组合。名额对照用 v6 的两条腿。
    signals = _signal_rows(base["A记录"], "A", "dev") + _signal_rows(base["美记录"], "美", "dev")
    levels = {"A": panels["A"], "美": panels["US"]}
    return {"summary": summary, "daily": daily, "signals": pd.DataFrame(signals), "levels": levels, "prior": prior}


def _month_returns(series: pd.Series) -> pd.Series:
    clean = series.dropna()
    out = (1.0 + clean).groupby(clean.index.to_period("M")).prod() - 1.0
    out.index = out.index.astype(str)
    return out


def _first_day(left: pd.Series, right: pd.Series) -> dict:
    joined = pd.concat([left.rename("dev"), right.rename("rev")], axis=1)
    both = joined.dropna()
    diff = (both["dev"] - both["rev"]).abs()
    hit = diff[diff > TOL]
    only_dev = joined.index.difference(right.dropna().index)
    only_rev = joined.index.difference(left.dropna().index)
    return {
        "only_dev_days": int(len(only_dev)),
        "only_rev_days": int(len(only_rev)),
        "first_only_dev": None if len(only_dev) == 0 else str(pd.Timestamp(only_dev.min()).date()),
        "first_only_rev": None if len(only_rev) == 0 else str(pd.Timestamp(only_rev.min()).date()),
        "overlap_days": int(len(both)),
        "first_diff_day": None if hit.empty else str(hit.index[0].date()),
        "first_diff_abs": None if hit.empty else float(diff.loc[hit.index[0]]),
        "dev": None if hit.empty else float(both.loc[hit.index[0], "dev"]),
        "rev": None if hit.empty else float(both.loc[hit.index[0], "rev"]),
    }


def _level_first(dev_levels: pd.DataFrame, rev_levels: pd.DataFrame) -> list[dict]:
    rows = []
    shared = [name for name in dev_levels.columns if name in rev_levels.columns]
    for name in shared:
        left = dev_levels[name].pct_change()
        right = rev_levels[name].pct_change()
        both = pd.concat([left.rename("dev"), right.rename("rev")], axis=1).dropna()
        if both.empty:
            rows.append({"name": name, "first_diff": None, "overlap": 0})
            continue
        gap = (both["dev"] - both["rev"]).abs()
        hit = gap[gap > 1e-6]
        rows.append({
            "name": name,
            "overlap": int(len(both)),
            "first_diff": None if hit.empty else str(hit.index[0].date()),
            "dev": None if hit.empty else float(both.loc[hit.index[0], "dev"]),
            "rev": None if hit.empty else float(both.loc[hit.index[0], "rev"]),
            "dev_first": None if dev_levels[name].first_valid_index() is None else str(pd.Timestamp(dev_levels[name].first_valid_index()).date()),
            "rev_first": None if rev_levels[name].first_valid_index() is None else str(pd.Timestamp(rev_levels[name].first_valid_index()).date()),
        })
    rows.sort(key=lambda row: (row["first_diff"] is None, row["first_diff"] or ""))
    return rows


def _active_signal(signals: pd.DataFrame, sleeve: str, day: pd.Timestamp) -> pd.Series | None:
    block = signals[(signals["sleeve"] == sleeve) & (signals["date"] < day.date().isoformat())]
    if block.empty:
        return None
    return block.sort_values("date").iloc[-1]


def _explain_day(dev: dict, rev: dict, day: str, sleeve: str) -> dict:
    stamp = pd.Timestamp(day)
    dev_sig = _active_signal(dev["signals"], sleeve, stamp)
    rev_sig = _active_signal(rev["signals"], sleeve, stamp)
    level_key = "A" if sleeve == "A" else "美"
    held_dev = [] if dev_sig is None else [name for name in str(dev_sig["held"]).split("|") if name]
    held_rev = [] if rev_sig is None else [name for name in str(rev_sig["held"]).split("|") if name]
    names = sorted(set(held_dev) | set(held_rev))
    prices = []
    for name in names:
        if name not in dev["levels"][level_key].columns or name not in rev["levels"][level_key].columns:
            prices.append({"name": name, "missing": True})
            continue
        left = dev["levels"][level_key][name].pct_change()
        right = rev["levels"][level_key][name].pct_change()
        prices.append({
            "name": name,
            "dev": None if stamp not in left.index or pd.isna(left.loc[stamp]) else float(left.loc[stamp]),
            "rev": None if stamp not in right.index or pd.isna(right.loc[stamp]) else float(right.loc[stamp]),
            "held_dev": name in held_dev,
            "held_rev": name in held_rev,
        })
    elig_dev = set() if dev_sig is None else set(filter(None, str(dev_sig["eligible"]).split("|")))
    elig_rev = set() if rev_sig is None else set(filter(None, str(rev_sig["eligible"]).split("|")))
    return {
        "sleeve": sleeve,
        "signal_dev": None if dev_sig is None else dev_sig.to_dict(),
        "signal_rev": None if rev_sig is None else rev_sig.to_dict(),
        "held_only_dev": sorted(set(held_dev) - set(held_rev)),
        "held_only_rev": sorted(set(held_rev) - set(held_dev)),
        "eligible_only_dev": sorted(elig_dev - elig_rev)[:20],
        "eligible_only_rev": sorted(elig_rev - elig_dev)[:20],
        "eligible_count_diff": None if dev_sig is None or rev_sig is None else int(dev_sig["eligible_n"]) - int(rev_sig["eligible_n"]),
        "prices": prices,
    }


def compare(dev: dict, rev: dict) -> dict:
    daily_rows = []
    books = ["v6", "不设防守", "A", "美", "BM主", "BM同仓位", "K2A", "bond", "cash"]
    first = {}
    for name in books:
        left = dev["daily"].set_index("date")[name]
        right = rev["daily"].set_index("date")[name]
        info = _first_day(left, right)
        info["book"] = name
        first[name] = info
        dev_m = _month_returns(left)
        rev_m = _month_returns(right)
        both = pd.concat([dev_m.rename("dev"), rev_m.rename("rev")], axis=1)
        both["book"] = name
        both["month"] = both.index
        daily_rows.append(both.reset_index(drop=True))
    months = pd.concat(daily_rows, ignore_index=True)
    months["diff"] = months["dev"] - months["rev"]
    _write_csv("month-returns.csv", months)

    year_rows = []
    for name in ["v6", "不设防守", "A", "美", "BM主", "BM同仓位", "K2A"]:
        dev_y = yearly_returns(dev["daily"].set_index("date")[name].loc[EXAM[0]:EXAM[1]])
        rev_y = yearly_returns(rev["daily"].set_index("date")[name].loc[EXAM[0]:EXAM[1]])
        years = sorted(set(dev_y) | set(rev_y))
        for year in years:
            year_rows.append({
                "book": name,
                "year": year,
                "dev": dev_y.get(year),
                "rev": rev_y.get(year),
                "diff_pp": None if year not in dev_y or year not in rev_y else (dev_y[year] - rev_y[year]) * 100.0,
            })
    _write_csv("year-slot.csv", pd.DataFrame(year_rows))

    level_rows = []
    for sleeve in ("A", "美"):
        found = _level_first(dev["levels"][sleeve], rev["levels"][sleeve])
        for row in found:
            row["sleeve"] = sleeve
            level_rows.append(row)
    _write_csv("level-first-diff.csv", pd.DataFrame(level_rows))

    dev_sig = dev["signals"]
    rev_sig = rev["signals"]
    held_rows = []
    for sleeve in ("A", "美"):
        left = dev_sig[dev_sig["sleeve"] == sleeve].set_index("month")
        right = rev_sig[rev_sig["sleeve"] == sleeve].set_index("month")
        for month in sorted(set(left.index) | set(right.index)):
            if month < "2016-01" or month > "2026-09":
                continue
            lrow = left.loc[month] if month in left.index else None
            rrow = right.loc[month] if month in right.index else None
            if isinstance(lrow, pd.DataFrame):
                lrow = lrow.iloc[-1]
            if isinstance(rrow, pd.DataFrame):
                rrow = rrow.iloc[-1]
            held_rows.append({
                "month": month,
                "sleeve": sleeve,
                "dev_held": None if lrow is None else lrow["held"],
                "rev_held": None if rrow is None else rrow["held"],
                "same_held": None if lrow is None or rrow is None else lrow["held"] == rrow["held"],
                "dev_votes": None if lrow is None else lrow["votes"],
                "rev_votes": None if rrow is None else rrow["votes"],
                "dev_p": None if lrow is None else lrow["p"],
                "rev_p": None if rrow is None else rrow["p"],
                "dev_position": None if lrow is None else lrow["position"],
                "rev_position": None if rrow is None else rrow["position"],
                "dev_eligible_n": None if lrow is None else lrow["eligible_n"],
                "rev_eligible_n": None if rrow is None else rrow["eligible_n"],
                "dev_gate": None if lrow is None else lrow["gate"],
                "rev_gate": None if rrow is None else rrow["gate"],
            })
    held = pd.DataFrame(held_rows)
    _write_csv("slot-signals.csv", held)

    v6_day = first["v6"]["first_diff_day"]
    explain = None
    if v6_day:
        explain = {
            "day": v6_day,
            "A": _explain_day(dev, rev, v6_day, "A"),
            "美": _explain_day(dev, rev, v6_day, "美"),
            "sleeve_first": {name: first[name] for name in ("A", "美", "不设防守", "BM主", "BM同仓位", "K2A")},
        }
    prior_gap = None
    if len(dev["prior"]) == len(rev["prior"]):
        prior_gap = float(np.max(np.abs(np.asarray(dev["prior"]) - np.asarray(rev["prior"]))))
    payload = {
        "dev_matches_submitted_daily": dev["summary"]["与交卷日收益"],
        "dev_summary": {key: value for key, value in dev["summary"].items() if key != "与交卷日收益"},
        "rev_summary": rev["summary"],
        "first_diff": first,
        "columns_only_dev_A": sorted(set(dev["summary"]["列_A"]) - set(rev["summary"]["列_A"])),
        "columns_only_rev_A": sorted(set(rev["summary"]["列_A"]) - set(dev["summary"]["列_A"])),
        "columns_only_dev_US": sorted(set(dev["summary"]["列_美"]) - set(rev["summary"]["列_美"])),
        "columns_only_rev_US": sorted(set(rev["summary"]["列_美"]) - set(dev["summary"]["列_美"])),
        "prior_len_dev": len(dev["prior"]),
        "prior_len_rev": len(rev["prior"]),
        "prior_max_abs": prior_gap,
        "explain": explain,
        "held_mismatch_months": held.loc[held["same_held"] == False, ["month", "sleeve", "dev_held", "rev_held"]].to_dict("records")[:30],
    }
    _write_json("comparison.json", payload)
    return payload


def main() -> None:
    open_official_isolation("2026-09-30", authorized=True)
    rev = run_reviewer()
    dev = run_dev()
    _write_json("reviewer-summary.json", rev["summary"])
    _write_json("dev-summary.json", dev["summary"])
    _write_csv("reviewer-signals.csv", rev["signals"])
    _write_csv("dev-signals.csv", dev["signals"])
    payload = compare(dev, rev)
    print(json.dumps({
        "dev_match": payload["dev_matches_submitted_daily"],
        "dev_mdd": payload["dev_summary"]["最大回撤"],
        "rev_mdd": payload["rev_summary"]["最大回撤"],
        "dev_premium": payload["dev_summary"]["保费_百分点"],
        "rev_premium": payload["rev_summary"]["保费_百分点"],
        "dev_excess": payload["dev_summary"]["对同仓位超额_百分点"],
        "rev_excess": payload["rev_summary"]["对同仓位超额_百分点"],
        "first_v6": payload["first_diff"]["v6"],
        "first_A": payload["first_diff"]["A"]["first_diff_day"],
        "first_US": payload["first_diff"]["美"]["first_diff_day"],
        "prior_max_abs": payload["prior_max_abs"],
        "only_dev_A": payload["columns_only_dev_A"],
        "only_rev_A": payload["columns_only_rev_A"],
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
