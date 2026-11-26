"""D48 设计期体检输入。每月再平衡是主结果。不覆盖 d47-health.json。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_d45 import OFFICIAL, SEG, mix_monthly  # noqa: E402
from run_d47_health import (  # noqa: E402
    A_SPEC,
    US_SPEC,
    bars_frame,
    build_levels,
    current_allocation,
    k2a_book,
    leaders_same,
    line_table,
    load_fx,
    load_market,
    premium,
    require_cutoff,
    signed_peer,
    sleeve_books,
    total_return_benchmarks,
    window_stats,
)
from v6ind.d45_engine import CUTOFF  # noqa: E402
from v6ind.d45_french import us_prior, value_weighted_market  # noqa: E402
from v6ind.load import connect_readonly  # noqa: E402

OUT = Path(__file__).resolve().parent / "output" / "d48-health.json"
PRIOR = Path(__file__).resolve().parent / "output" / "d47-health.json"
PERIODS = SEG


def k2a_every_21(frame: pd.DataFrame) -> pd.Series:
    """参照：沿用合成路径的每 21 根一个月。波动仍每 5 个交易日。净值先记账、再扣成本，与 sim.run 相同。"""
    simple = np.column_stack([
        frame["csi300"].astype(float).fillna(0.0).to_numpy(),
        ((frame["ndx100"] + frame["spx"]) / 2.0).astype(float).fillna(0.0).to_numpy(),
    ])
    bond = frame["cgb-10y"].to_numpy(dtype=float)
    cash = frame["cash"].fillna(0.0).to_numpy(dtype=float)
    haven = np.where(np.isfinite(bond), np.nan_to_num(bond, nan=0.0), cash)
    log_ret = np.log1p(simple)
    level = np.exp(np.cumsum(log_ret, axis=0))
    step, week, year = 21, 5, 252
    cost = 0.001
    on = np.ones(2)
    frac = np.ones(2)
    held = np.array([0.5, 0.5, 0.0])
    nav = 1.0
    recorded = np.empty(len(frame))
    for today in range(len(frame)):
        gain = 1.0 + held[0] * simple[today, 0] + held[1] * simple[today, 1] + held[2] * haven[today]
        held = np.array([
            held[0] * (1.0 + simple[today, 0]),
            held[1] * (1.0 + simple[today, 1]),
            held[2] * (1.0 + haven[today]),
        ]) / gain
        nav *= gain
        recorded[today] = nav
        month_end = (today + 1) % step == 0
        week_end = (today + 1) % week == 0
        new_on = on.copy()
        new_frac = frac.copy()
        if month_end and today >= 10 * step:
            closes = level[today - 9 * step:today + 1:step]
            new_on = (level[today] >= closes.mean(axis=0)).astype(float)
        if week_end and today >= year:
            long_vol = log_ret[today - year + 1:today + 1].std(axis=0)
            short_vol = log_ret[today - 20 + 1:today + 1].std(axis=0)
            proposed = np.minimum(1.0, long_vol / np.maximum(short_vol, 1e-9))
            new_frac = np.where(np.abs(proposed - frac) >= 0.10, proposed, frac)
        new_on = new_on.copy()
        new_on[1] = 1.0
        new_frac = new_frac.copy()
        new_frac[1] = 1.0
        target = np.array([0.5 * new_on[0] * new_frac[0], 0.5, 0.0])
        target[2] = 1.0 - target[0] - target[1]
        trade = month_end or new_on[0] != on[0] or abs(float(new_frac[0] - frac[0])) > 1e-12
        if trade:
            nav *= 1.0 - cost * float(np.abs(target - held).sum())
            held = target
        on, frac = new_on, new_frac
    return pd.Series(recorded, index=frame.index).pct_change().fillna(0.0)


def ratio(stats: dict) -> float:
    return round(stats["annual_pct"] / abs(stats["maxdd_pct"]), 6)


def last_p(log: dict) -> dict:
    days = [day for day in log if day <= CUTOFF]
    if not days:
        return {}
    day = max(days)
    return {"date": day.strftime("%Y-%m-%d"), "p": log[day]["p"], "leaders": log[day].get("领头者")}


def forecast_block(books: dict, bench: dict, prem: dict) -> dict:
    out = {}
    for label, window in PERIODS.items():
        us_top = window_stats(books["top"]["us"], *window)["annual_pct"]
        us_ew = window_stats(books["ew"]["us"], *window)["annual_pct"]
        spx = window_stats(books["spx"], *window)["annual_pct"]
        a_top = window_stats(books["top"]["a"], *window)["annual_pct"]
        a_ew = window_stats(books["ew"]["a"], *window)["annual_pct"]
        csi = window_stats(books["csi300"], *window)["annual_pct"]
        main = us_top - spx
        alloc = window_stats(bench["BM-同仓位"], *window)["annual_pct"] - window_stats(bench["BM-主"], *window)["annual_pct"]
        gate = prem[label]["premium_pp"]
        out[label] = {
            "美股挑选": {
                "名额内": round(main, 6),
                "组合贡献": round(main * 0.6, 6),
                "前3减同名额等权": round(us_top - us_ew, 6),
                "同名额等权减SPX": round(us_ew - spx, 6),
            },
            "A股挑选": {"名额内": round(a_top - a_ew, 6), "组合贡献": round((a_top - a_ew) * 0.4, 6)},
            "A股等权倾斜": {"名额内": round(a_ew - csi, 6), "组合贡献": round((a_ew - csi) * 0.4, 6)},
            "防守保费": {"判据②": gate, "预测行": None if gate is None else round(-gate, 6)},
            "美股60%仓位差": {"组合贡献": round(alloc, 6)},
        }
    return out


def changed(old, new, path: str) -> list:
    if isinstance(old, dict) and isinstance(new, dict):
        rows = []
        for key in sorted(set(old) | set(new)):
            rows.extend(changed(old.get(key), new.get(key), f"{path}.{key}"))
        return rows
    if old != new:
        return [{"path": path, "d47": old, "d48": new}]
    return []


def main() -> None:
    if not OFFICIAL.exists():
        raise SystemExit(f"缺少已允许的 French 文件 {OFFICIAL}")
    if not PRIOR.exists():
        raise SystemExit("缺少上一轮锁定文件")
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
    k2a_month = k2a_book(frame)
    k2a_21 = k2a_every_21(frame)
    peers = {
        "A1": signed_peer(ROOT / "results/v4/r5/design/A1/index/net.csv"),
        "A2": signed_peer(ROOT / "results/v4/r5/design/A2/index/net.csv"),
    }
    try:
        current = current_allocation()
    except Exception as exc:  # noqa: BLE001 — 这一项停下，不造权重
        current = {"status": "stopped", "reason": str(exc)}
    clips = {}
    for clip in ("full", "expanding"):
        books, logs = sleeve_books(
            levels_a, amounts_a, levels_u, us_px, us_am, bond, cash, tags_a, tags_u, prior, clip)
        if not leaders_same(logs["cont"]["a"], logs["cont_ref"]["a"]):
            raise SystemExit(f"{clip}：A 股过滤版的把握领头者和未过滤名单不一致")
        v6 = mix_monthly(books["v6"]["a"], books["v6"]["us"], 0.002)
        undefended = mix_monthly(books["top_net"]["a"], books["top_net"]["us"], 0.002)
        continuity = mix_monthly(books["cont"]["a"], books["v6"]["us"], 0.002)
        reference = mix_monthly(books["cont_ref"]["a"], books["v6"]["us"], 0.002)
        daily = books["v6"]["book"]
        prem = {label: premium(undefended, v6, benchmarks["BM-主"], *window) for label, window in PERIODS.items()}
        gates = {}
        for label, window in PERIODS.items():
            v6_stats = window_stats(v6, *window)
            month_stats = window_stats(k2a_month, *window)
            step_stats = window_stats(k2a_21, *window)
            same = window_stats(benchmarks["BM-同仓位"], *window)
            gates[label] = {
                "v6_annual_pct": v6_stats["annual_pct"],
                "v6_maxdd_pct": v6_stats["maxdd_pct"],
                "v6_ratio": ratio(v6_stats),
                "defense_premium_pp": prem[label]["premium_pp"],
                "forecast_premium_pp": None if prem[label]["premium_pp"] is None else round(-prem[label]["premium_pp"], 6),
                "defense_premium_years": prem[label]["years"],
                "k2a_month_annual_pct": month_stats["annual_pct"],
                "k2a_month_maxdd_pct": month_stats["maxdd_pct"],
                "k2a_month_ratio": ratio(month_stats),
                "k2a_21_annual_pct": step_stats["annual_pct"],
                "k2a_21_maxdd_pct": step_stats["maxdd_pct"],
                "k2a_21_ratio": ratio(step_stats),
                "v6_minus_bm_same_pp": round(v6_stats["annual_pct"] - same["annual_pct"], 6),
            }
        lines = line_table({
            "v6": v6,
            "连续性版": continuity,
            "连续性版未过滤参照": reference,
            "A1": peers["A1"],
            "A2": peers["A2"],
            "K2A真实月末": k2a_month,
            "K2A每21根": k2a_21,
            "BM-主": benchmarks["BM-主"],
            "BM-同仓位": benchmarks["BM-同仓位"],
            "每日固定对照": daily,
        })
        if current.get("status") == "ok":
            lines["现行配置"] = current["lines"]
        clips[clip] = {
            "gates": gates,
            "lines": lines,
            "forecast": forecast_block(books, benchmarks, prem),
            "continuity": {
                "a_slot": "cont",
                "us_slot": "v6",
                "mix": "month_end_60_40",
                "p_from_unfiltered_a_leaders": True,
                "leaders_match_unfiltered_a": True,
                "filtered_last_p": last_p(logs["cont"]["a"]),
                "unfiltered_last_p": last_p(logs["cont_ref"]["a"]),
            },
        }
    old = json.loads(PRIOR.read_text(encoding="utf-8"))
    stable = {}
    for clip in ("full", "expanding"):
        old_lines = old["clips"][clip]["lines"]
        new_lines = clips[clip]["lines"]
        rows = []
        for name in ("A1", "A2", "BM-主", "BM-同仓位", "现行配置"):
            rows.extend(changed(old_lines[name], new_lines[name], f"{clip}.{name}"))
        old_fc = old["clips"][clip]["forecast"]
        new_fc = clips[clip]["forecast"]
        for label in PERIODS:
            for item in ("A股挑选", "A股等权倾斜"):
                rows.extend(changed(old_fc[label][item], new_fc[label][item], f"{clip}.{label}.{item}"))
            rows.extend(changed(
                old_fc[label]["美股60%仓位差"]["组合贡献"],
                new_fc[label]["美股60%仓位差"]["组合贡献"],
                f"{clip}.{label}.美股60%仓位差",
            ))
        stable[clip] = rows
    payload = {
        "cutoff": "2015-12-31",
        "rule": "D48：每月末 60/40 再平衡；连续性版只改 A 股名额；K2A 主值为真实月末，每 21 根为参照；波动每 5 个交易日",
        "not_acceptance": "每日固定 60/40 只放在「每日固定对照」，不作为判据或 Dev 缺陷",
        "current_allocation": {key: value for key, value in current.items() if key != "lines"},
        "clips": clips,
        "unchanged_versus_d47": stable,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
