"""D47 设计期体检输入。先写出自己的数字。不读 Dev 的 health-*。

四条闸门只报告数值。连续性版的把握 p 用未过滤的领头者。
现行配置走 package(end=2015-12-31) → indicators.build → daily_book，阀门关闭。
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import traceback
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_d45 import A_SPEC, OFFICIAL, SEG, US_SPEC, US_TRIN, bars_frame, build_levels  # noqa: E402
from src.report.blend import monthly_rebalance  # noqa: E402
from src.report.metrics import cagr, max_drawdown  # noqa: E402
from src.v4.r5.design import DESIGN_END, reference_frame  # noqa: E402
from v6ind.d45_engine import CUTOFF, run_slot, trin_from_prices, votes  # noqa: E402
from v6ind.d45_french import us_prior, value_weighted_market  # noqa: E402
from v6ind.load import connect_readonly, load_fx  # noqa: E402

OUT = Path(__file__).resolve().parent / "output" / "d47-health.json"
PERIODS = SEG


def digest(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def require_cutoff(index: pd.DatetimeIndex, what: str) -> None:
    if len(index) and pd.Timestamp(index.max()) > CUTOFF:
        raise SystemExit(f"{what} 晚于 2015-12-31：{pd.Timestamp(index.max()).date()}")


def mix_daily(left: pd.Series, right: pd.Series, left_weight: float = 0.4) -> pd.Series:
    return left_weight * left + (1.0 - left_weight) * right


def window_stats(series: pd.Series, start: str, end: str) -> dict:
    block = series.loc[start:end].dropna()
    require_cutoff(block.index, "窗口")
    return {
        "annual_pct": round(cagr(block) * 100.0, 6),
        "maxdd_pct": round(max_drawdown(block)["max_drawdown"] * 100.0, 6),
        "days": int(len(block)),
        "first": str(block.index[0].date()),
        "last": str(block.index[-1].date()),
    }


def complete_year_returns(series: pd.Series) -> dict[int, float]:
    """自然年首尾净值之比。上一年 12 月和这一年 12 月都有收盘才算完整年。"""
    clean = series.dropna().sort_index()
    nav = (1.0 + clean).cumprod()
    last = nav.groupby(nav.index.year).tail(1)
    points = list(last.items())
    out = {}
    for (prev_day, prev_nav), (day, value) in zip(points, points[1:]):
        if int(day.year) != int(prev_day.year) + 1:
            continue
        if prev_day.month != 12 or day.month != 12:
            continue
        out[int(day.year)] = float(value / prev_nav - 1.0)
    return out


def premium(undefended: pd.Series, strategy: pd.Series, benchmark: pd.Series, start: str, end: str) -> dict:
    years = range(int(start[:4]), int(end[:4]) + 1)
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
            "bm_main_pct": round(bench[year] * 100.0, 6),
            "undefended_pct": round(plain[year] * 100.0, 6),
            "v6_pct": round(held[year] * 100.0, 6),
            "gap_pp": round((plain[year] - held[year]) * 100.0, 6),
        })
    gap = float(np.mean([row["gap_pp"] for row in used])) if used else None
    return {"premium_pp": None if gap is None else round(gap, 6), "years": used}


def load_market():
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import Markets

    signal = Markets(load_spec()).get("index", t4=False, allow_substitute=True).signal
    require_cutoff(signal.index, "市场信号")
    frame = signal.loc[:DESIGN_END]
    frame = frame[frame[["csi300", "spx", "ndx100"]].notna().all(axis=1)]
    return frame


def total_return_benchmarks() -> dict[str, pd.Series]:
    parts = reference_frame(end=DESIGN_END).dropna()
    require_cutoff(parts.index, "全收益基准")
    main, _weights = monthly_rebalance(parts, {"H00300": 0.70, "XNDX": 0.15, "SP500TR": 0.15})
    same, _weights = monthly_rebalance(parts, {"H00300": 0.40, "XNDX": 0.30, "SP500TR": 0.30})
    return {"BM-主": main, "BM-同仓位": same}


def k2a_book(frame: pd.DataFrame) -> pd.Series:
    """D39-3：只给 A 股腿上 K2，美股 50% 一直持有。月末用真实日历，波动每 5 个交易日看一次。"""
    a = frame["csi300"].astype(float)
    us = ((frame["ndx100"] + frame["spx"]) / 2.0).astype(float)
    bond = frame["cgb-10y"].astype(float)
    cash = frame["cash"].fillna(0.0).astype(float)
    index = frame.index
    price_a = np.exp(np.log1p(a.fillna(0.0)).cumsum())
    month_end = np.r_[index.month.to_numpy()[1:] != index.month.to_numpy()[:-1], True]
    ends = list(index[month_end])
    end_pos = {stamp: pos for pos, stamp in enumerate(ends)}
    cost = 0.001
    held = np.array([0.5, 0.5, 0.0])
    on_a, frac_a = 1.0, 1.0
    out = np.zeros(len(index))
    bond_values = bond.to_numpy(dtype=float)
    cash_values = cash.to_numpy(dtype=float)
    a_values = a.fillna(0.0).to_numpy(dtype=float)
    u_values = us.fillna(0.0).to_numpy(dtype=float)
    log_a = np.log1p(a_values)
    for today, stamp in enumerate(index):
        haven = bond_values[today] if np.isfinite(bond_values[today]) else cash_values[today]
        gain = float(held[0] * a_values[today] + held[1] * u_values[today] + held[2] * haven)
        out[today] = gain
        gross = 1.0 + gain
        held = held * np.array([1.0 + a_values[today], 1.0 + u_values[today], 1.0 + haven]) / gross
        new_on, new_frac = on_a, frac_a
        if month_end[today] and end_pos[stamp] >= 9:
            pts = price_a.loc[ends[end_pos[stamp] - 9:end_pos[stamp] + 1]]
            new_on = 1.0 if float(price_a.loc[stamp]) >= float(pts.mean()) else 0.0
        if (today + 1) % 5 == 0 and today >= 251:
            long = float(np.std(log_a[today - 251:today + 1]))
            short = float(np.std(log_a[today - 19:today + 1]))
            proposed = min(1.0, long / max(short, 1e-9))
            if abs(proposed - frac_a) >= 0.10:
                new_frac = proposed
        target_a = 0.5 * new_on * new_frac
        target = np.array([target_a, 0.5, 1.0 - target_a - 0.5])
        if month_end[today] or new_on != on_a or new_frac != frac_a:
            traded = float(np.abs(target - held).sum())
            out[today] = (1.0 + gain) * (1.0 - cost * traded) - 1.0
            held = target
            on_a, frac_a = new_on, new_frac
    return pd.Series(out, index=index)


def signed_peer(path: Path) -> pd.Series:
    """v4 设计期 `net.csv` 的 net 列是日收益，不是净值。"""
    frame = pd.read_csv(path, parse_dates=["date"])
    if frame["date"].max() > CUTOFF:
        raise SystemExit(f"{path} 含有 2015-12-31 之后的日期")
    series = frame.set_index("date")["net"].astype(float).sort_index()
    series = series[~series.index.duplicated(keep="last")].dropna()
    if (series <= -1.0).any():
        raise SystemExit(f"{path} 有小于等于 -100% 的日收益")
    return series


def sleeve_books(levels_a, amounts_a, levels_u, us_px, us_am, bond, cash, tags_a, tags_u, prior, clip: str):
    trin_columns = [name for name in levels_a.columns if name in US_TRIN or name.startswith("allshare-")
                    or name.startswith("theme-") or name in {"csi500", "csi1000", "chinext"}]
    vote_a = votes(levels_a, "csi300", trin_from_prices(levels_a[trin_columns], amounts_a[trin_columns], clip=clip))
    vote_u = votes(levels_u, "SPX", trin_from_prices(us_px, us_am, clip=clip))
    books = {}
    logs = {}
    for mode, cost in (("ew", 0.0), ("top", 0.0), ("top_net", 0.002), ("v6", 0.002),
                       ("cont", 0.002), ("cont_ref", 0.002)):
        slot_mode = "top" if mode == "top_net" else mode
        a_ret, _turn, a_log = run_slot(levels_a, "csi300", vote_a, bond, cash, tags_a, None,
                                       mode=slot_mode, cost=cost)
        u_ret, _turn, u_log = run_slot(levels_u, "SPX", vote_u, bond, cash, tags_u, prior,
                                       mode=slot_mode, cost=cost)
        books[mode] = {"a": a_ret, "us": u_ret, "book": mix_daily(a_ret, u_ret)}
        logs[mode] = {"a": a_log, "us": u_log}
    books["spx"] = levels_u["SPX"].pct_change().fillna(0.0)
    books["csi300"] = levels_a["csi300"].pct_change().fillna(0.0)
    return books, logs


def forecast_block(books: dict, bench: dict, prem: dict) -> dict:
    out = {}
    for label, window in PERIODS.items():
        us_slot = window_stats(books["top"]["us"], *window)["annual_pct"] - window_stats(books["spx"], *window)["annual_pct"]
        a_slot = window_stats(books["top"]["a"], *window)["annual_pct"] - window_stats(books["ew"]["a"], *window)["annual_pct"]
        tilt_slot = window_stats(books["ew"]["a"], *window)["annual_pct"] - window_stats(books["csi300"], *window)["annual_pct"]
        alloc = window_stats(bench["BM-同仓位"], *window)["annual_pct"] - window_stats(bench["BM-主"], *window)["annual_pct"]
        out[label] = {
            "美股挑选": {"名额内": round(us_slot, 6), "组合贡献": round(us_slot * 0.6, 6)},
            "A股挑选": {"名额内": round(a_slot, 6), "组合贡献": round(a_slot * 0.4, 6)},
            "A股等权倾斜": {"名额内": round(tilt_slot, 6), "组合贡献": round(tilt_slot * 0.4, 6)},
            "防守保费": {"名额内": None, "组合贡献": prem[label]["premium_pp"]},
            "美股60%仓位差": {"名额内": None, "组合贡献": round(alloc, 6)},
        }
    return out


def line_table(series_map: dict[str, pd.Series]) -> dict:
    return {name: {label: window_stats(series, *window) for label, window in PERIODS.items()}
            for name, series in series_map.items()}


def leaders_same(filtered: dict, reference: dict) -> bool:
    if filtered.keys() != reference.keys():
        return False
    return all(filtered[day].get("领头者") == reference[day].get("领头者") for day in filtered)


def current_allocation() -> dict:
    from src.data import runner
    from src.indicators.build import build
    from src.portfolio.config import load_config
    from src.portfolio.replicate import _haven_returns, daily_book, load_haven_closes

    end = date(2015, 12, 31)
    root = Path("/tmp/v6-d47-pkg")
    root.mkdir(parents=True, exist_ok=True)
    package = runner.package(end, pkg_root=root, force=True, log=print)
    con = sqlite3.connect(f"{package.resolve().as_uri()}?mode=ro", uri=True)
    try:
        bar_max, bar_after = con.execute(
            "SELECT MAX(date), SUM(date > '2015-12-31') FROM bars").fetchone()
        cal_max, cal_after = con.execute(
            "SELECT MAX(date), SUM(date > '2015-12-31') FROM calendar").fetchone()
    finally:
        con.close()
    note = {
        "package": str(package),
        "bar_max": bar_max,
        "bars_after_cutoff": int(bar_after or 0),
        "calendar_max": cal_max,
        "calendar_dates_after_cutoff": int(cal_after or 0),
        "calendar_note": "calendar 复制的是日期。晚于截止日的行只在这里计数，不读价格。",
    }
    if int(bar_after or 0) > 0:
        note["status"] = "stopped"
        note["reason"] = "数据包里有 2015-12-31 之后的行情行"
        return note
    panel = build(package, out=root / "panel-2015-12-31.sqlite", log=print)
    cfg = load_config()
    if cfg.valve_enabled:
        note["status"] = "stopped"
        note["reason"] = "config/portfolio.toml 的阀门不是关闭"
        return note
    uri = f"{panel.resolve().as_uri()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        panel_max, panel_after = con.execute(
            "SELECT MAX(date), SUM(date > '2015-12-31') FROM panel").fetchone()
        prices = pd.read_sql_query(
            "SELECT date, container, close, data_hole FROM panel WHERE date <= '2015-12-31'", con)
    finally:
        con.close()
    note["panel_max"] = panel_max
    note["panel_rows_after_cutoff"] = int(panel_after or 0)
    if int(panel_after or 0) > 0:
        note["status"] = "stopped"
        note["reason"] = "面板里有 2015-12-31 之后的行"
        return note
    prices["date"] = pd.to_datetime(prices["date"])
    prices = prices.loc[prices["data_hole"] == 0]
    wide = prices.pivot(index="date", columns="container", values="close").sort_index()
    require_cutoff(wide.index, "现行配置面板")
    missing = [name for name in list(cfg.a_share) + list(cfg.overseas) if name not in wide.columns]
    if missing:
        note["status"] = "stopped"
        note["reason"] = f"面板缺容器：{missing}"
        note["panel_containers"] = sorted(map(str, wide.columns))
        return note
    state = pd.Series(1, index=wide.groupby(wide.index.to_period("M")).tail(1).index)
    haven = load_haven_closes(ROOT / "data" / "market.sqlite", cfg.haven_code, pd.Timestamp(end))
    if haven is not None and len(haven) and haven.index.max() > CUTOFF:
        note["status"] = "stopped"
        note["reason"] = "511880 读入超过截止日"
        return note
    daily = daily_book(wide, state, cfg, _haven_returns(wide.index, haven, cfg.cash_daily))
    require_cutoff(daily.index, "现行配置日收益")
    note["status"] = "ok"
    note["valve"] = "off"
    note["cost_one_way"] = cfg.cost_one_way
    note["lines"] = {label: window_stats(daily, *window) for label, window in PERIODS.items()}
    return note


def main() -> None:
    if not OFFICIAL.exists():
        raise SystemExit(f"缺少已允许的 French 文件 {OFFICIAL}")
    con = connect_readonly(ROOT / "data" / "market.sqlite")
    codes = sorted({row[1] for row in A_SPEC} | {row[0] for row in US_SPEC})
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
    tags_a = {row[0]: row[3] for row in A_SPEC}
    tags_u = {row[0]: row[3] for row in US_SPEC}
    prior = us_prior(value_weighted_market(OFFICIAL.read_text(errors="replace")))
    us_prices, us_amounts = [], []
    for code in ("XLK", "XLV", "XLE", "XLY", "XLP", "XLF", "XLI", "XLB", "XLU"):
        close = raw[code]["close"]
        close = close[close > 0]
        close = close[~close.index.duplicated(keep="last")].sort_index()
        volume = raw[code]["volume"].reindex(close.index)
        us_prices.append(close.rename(code))
        us_amounts.append((close * volume).where(lambda values: values > 0).rename(code))
    us_px = pd.concat(us_prices, axis=1).sort_index()
    us_am = pd.concat(us_amounts, axis=1).reindex(us_px.index)
    benchmarks = total_return_benchmarks()
    k2a = k2a_book(frame)
    peers = {
        "A1": signed_peer(ROOT / "results/v4/r5/design/A1/index/net.csv"),
        "A2": signed_peer(ROOT / "results/v4/r5/design/A2/index/net.csv"),
    }
    try:
        current = current_allocation()
    except Exception as exc:  # noqa: BLE001 — 这一项停下，不造权重
        current = {"status": "stopped", "reason": str(exc), "trace": traceback.format_exc().splitlines()[-8:]}
    clips = {}
    for clip in ("full", "expanding"):
        books, logs = sleeve_books(levels_a, amounts_a, levels_u, us_px, us_am, bond, cash,
                                   tags_a, tags_u, prior, clip)
        same = leaders_same(logs["cont"]["a"], logs["cont_ref"]["a"]) and leaders_same(
            logs["cont"]["us"], logs["cont_ref"]["us"])
        if not same:
            raise SystemExit(f"{clip} 连续性版的把握领头者和未过滤参照不一致")
        prem = {label: premium(books["top_net"]["book"], books["v6"]["book"], benchmarks["BM-主"], *window)
                for label, window in PERIODS.items()}
        gates = {}
        for label, window in PERIODS.items():
            v6 = window_stats(books["v6"]["book"], *window)
            enhanced = window_stats(k2a, *window)
            same_alloc = window_stats(benchmarks["BM-同仓位"], *window)
            gates[label] = {
                "v6_net_maxdd_pct": v6["maxdd_pct"],
                "defense_premium_pp": prem[label]["premium_pp"],
                "defense_premium_years": prem[label]["years"],
                "v6_annual_pct": v6["annual_pct"],
                "v6_maxdd_pct": v6["maxdd_pct"],
                "k2a_annual_pct": enhanced["annual_pct"],
                "k2a_maxdd_pct": enhanced["maxdd_pct"],
                "v6_minus_bm_same_pp": round(v6["annual_pct"] - same_alloc["annual_pct"], 6),
            }
        lines = {
            "v6": books["v6"]["book"],
            "连续性版": books["cont"]["book"],
            "连续性版未过滤参照": books["cont_ref"]["book"],
            "A1": peers["A1"],
            "A2": peers["A2"],
            "K2A": k2a,
            "BM-主": benchmarks["BM-主"],
            "BM-同仓位": benchmarks["BM-同仓位"],
        }
        if current.get("status") == "ok":
            lines["现行配置"] = None
        table = line_table({name: series for name, series in lines.items() if series is not None})
        if current.get("status") == "ok":
            table["现行配置"] = current["lines"]
        clips[clip] = {
            "gates": gates,
            "lines": table,
            "forecast": forecast_block(books, benchmarks, prem),
            "continuity_p_uses_unfiltered_leaders": same,
        }
    payload = {
        "cutoff": "2015-12-31",
        "rule": "A_BF；T−12；每日固定 60/40；单边 0.2%；全收益基准月初再平衡；两种 TRIN 都保留",
        "k2a": "A 股腿为指数池 csi300，美股腿为 ndx100 与 spx 的当日平均，权重 50/50；月末 10 个月均线，252/20 日波动，带宽 10 个点，单边 0.1%",
        "forecast_definition": "美股挑选=前3不设防守名额年化−SPX；A股挑选=前3−等权；等权倾斜=等权−沪深300；只对这两类挑选和倾斜乘 0.6/0.4；保费和仓位差不乘",
        "current_allocation": {key: value for key, value in current.items() if key != "lines"},
        "clips": clips,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(digest(json.loads(OUT.read_text(encoding="utf-8"))))
    print(OUT)


if __name__ == "__main__":
    main()
