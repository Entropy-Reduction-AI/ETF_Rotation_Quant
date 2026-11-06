"""D37 方案 B。第一层用 selection="all"，节奏仍是冻结规则。

只写 results/v51-diag/d37/<S0|S1>/<段>/B/。不改判据，不改 LOCK。
S0 设计期必须和 results/v5.1/robustness/S12 的成交一致，对不上就停。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.data import db as DB

from .diag_d37 import (
    INSPECT,
    OUT,
    ROOT,
    _cn_index,
    _norm,
    _s1_bundle,
    _signal_of,
    compare_exits,
    compare_frames,
    write_run,
    write_stats,
)
from .params import V51Error

S12 = ROOT / "results" / "v5.1" / "robustness" / "S12"


def plan_b_markets(held: pd.DataFrame, pnl: pd.DataFrame, state: pd.DataFrame, universe) -> tuple[pd.DataFrame, dict]:
    """每天持有几个市场，以及每个市场的平均仓位和贡献。"""
    member_of: dict[str, str] = {}
    for market in universe.markets:
        for name in market.members:
            member_of[name] = market.name
    labels = state["market"].fillna("").astype(str).replace({"nan": ""})
    counts = labels.map(lambda text: 0 if not text else text.count("|") + 1)
    returns = pnl.reindex(held.index)
    rows = []
    for market in universe.markets:
        members = [name for name in market.members if name in held.columns]
        if not members:
            rows.append({"market": market.name, "avg_weight": 0.0, "days_held": 0, "contribution": 0.0})
            continue
        weights = held[members].astype(float)
        total = weights.sum(axis=1)
        contrib = 0.0
        for name in members:
            if name not in returns.columns:
                continue
            contrib += float((weights[name] * returns[name].astype(float).fillna(0.0)).sum())
        rows.append({
            "market": market.name,
            "avg_weight": float(total.mean()) if len(total) else 0.0,
            "days_held": int((total > 1e-6).sum()),
            "contribution": contrib,
        })
    known = set(member_of)
    rest = [name for name in held.columns if name not in known]
    if rest:
        weights = held[rest].astype(float)
        total = weights.sum(axis=1)
        contrib = 0.0
        for name in rest:
            if name not in returns.columns:
                continue
            contrib += float((weights[name] * returns[name].astype(float).fillna(0.0)).sum())
        rows.append({
            "market": "防守或现金",
            "avg_weight": float(total.mean()) if len(total) else 0.0,
            "days_held": int((total > 1e-6).sum()),
            "contribution": contrib,
        })
    frame = pd.DataFrame(rows)
    summary = {
        "avg_markets_per_day": float(counts.mean()) if len(counts) else 0.0,
        "max_markets": int(counts.max()) if len(counts) else 0,
        "days": int(len(counts)),
    }
    return frame, summary


def _attach_plan_b(folder: Path, held: pd.DataFrame, pnl: pd.DataFrame, state: pd.DataFrame, universe) -> dict:
    table, summary = plan_b_markets(held, pnl, state, universe)
    table.to_csv(folder / "markets.csv", index=False, float_format="%.12g")
    path = folder / "stats.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["plan_b"] = summary
    payload["plan_b"]["markets"] = table.to_dict(orient="records")
    payload["selection"] = "all"
    payload["note"] = "方案 B，只报告，不计入任何过关判据。"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def compare_s12(folder: Path) -> list[str]:
    got = pd.read_csv(folder / "daily.csv", parse_dates=["date"], index_col="date")
    ref = pd.read_csv(S12 / "daily.csv", parse_dates=["date"], index_col="date")
    problems = compare_frames(got, ref, ["net", "gross", "nav", "cost", "buy", "sell"])
    got_exits = pd.read_csv(folder / "exits.csv")
    ref_exits = pd.read_csv(S12 / "exits.csv")
    problems.extend(compare_exits(got_exits, ref_exits))
    return [f"S12 {item}" for item in problems]


def _finish_cell(folder: Path, book, allocation, index, pnl, benchmark, segment: str, scope: str,
                 universe, extra: list[str]) -> None:
    daily = write_run(folder, book, allocation, index)
    held = pd.read_csv(folder / "held.csv", parse_dates=["date"], index_col="date")
    state = pd.read_csv(folder / "state.csv", parse_dates=["date"], index_col="date")
    exits = pd.read_csv(folder / "exits.csv")
    legs = pd.read_csv(folder / "legs.csv")
    write_stats(folder, daily, held, state, exits, pnl.reindex(index), benchmark, segment, scope, extra, legs)
    _attach_plan_b(folder, held, pnl.reindex(index), state, universe)
    decisions = allocation.decisions.copy()
    decisions.index.name = "date"
    decisions.to_csv(folder / "decisions.csv", float_format="%.12g")


def run_s0_design() -> list[str]:
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import benchmark_returns, prepare_market

    from .execute import universe_for

    spec = load_spec()
    print("方案 B 装中国设计期", flush=True)
    market = prepare_market("index", t4=False, allow_substitute=True, spec=spec, end="2015-12-31", allow_after=False)
    benchmark = benchmark_returns(end="2015-12-31", allow_after=False)
    signal = _signal_of(market)
    from .diag_d37 import _panel, _run_cn_version

    panel = _panel(signal, market.cash_id, False)
    universe = universe_for(market)
    book, allocation = _run_cn_version(
        market, spec, universe, signal, panel, None, "frozen", False, selection="all",
    )
    index = _cn_index(market, "设计期")
    folder = OUT / "S0" / "设计期" / "B"
    pnl = market.pnl.copy()
    pnl.index = _norm(pnl.index)
    view_book = book
    _finish_cell(folder, view_book, allocation, index, pnl, benchmark, "设计期", "S0", universe, [])
    return compare_s12(folder)


def run_s0_inspection() -> None:
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import benchmark_returns, prepare_market

    from .diag_d37 import _panel, _run_cn_version, _slice_book
    from .execute import universe_for

    spec = load_spec()
    print("方案 B 装中国检验段", flush=True)
    market = prepare_market("index", t4=False, allow_substitute=True, spec=spec, end=INSPECT[1], allow_after=True)
    benchmark = benchmark_returns(end=INSPECT[1], allow_after=True)
    signal = _signal_of(market)
    panel = _panel(signal, market.cash_id, True)
    universe = universe_for(market)
    book, allocation = _run_cn_version(
        market, spec, universe, signal, panel, None, "frozen", True, selection="all",
    )
    index = _cn_index(market, "检验段")
    view = _slice_book(book, index)
    folder = OUT / "S0" / "检验段" / "B"
    pnl = market.pnl.copy()
    pnl.index = _norm(pnl.index)
    _finish_cell(folder, view, allocation, index, pnl, benchmark, "检验段", "S0", universe, [])


def run_s1_inspection() -> None:
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import benchmark_returns, prepare_market

    from .diag_d37 import _panel, _run_cn_version, _slice_book

    spec = load_spec()
    print("方案 B 装 S1 检验段", flush=True)
    market = prepare_market("index", t4=False, allow_substitute=True, spec=spec, end=INSPECT[1], allow_after=True)
    benchmark = benchmark_returns(end=INSPECT[1], allow_after=True)
    con = DB.connect(DB.MARKET_DB, readonly=True)
    try:
        universe, signal, eligible, extra, _report, _notes = _s1_bundle(market, con)
    finally:
        con.close()
    panel = _panel(signal, market.cash_id, True)
    book, allocation = _run_cn_version(
        market, spec, universe, signal, panel, eligible, "frozen", True, selection="all",
    )
    index = _cn_index(market, "检验段")
    view = _slice_book(book, index)
    folder = OUT / "S1" / "检验段" / "B"
    pnl = market.pnl.copy()
    pnl.index = _norm(pnl.index)
    _finish_cell(folder, view, allocation, index, pnl, benchmark, "检验段", "S1", universe, extra)


def run_other() -> None:
    from .diag_d37 import _norm, write_run
    from .gpool import (
        benchmark_g,
        build_panels,
        check_registered,
        g_universe,
        load_adjclose,
        load_dtb3,
        raw_tickers,
        run_v51,
        spy_sessions,
        traded_names,
        window_slice,
    )
    from src.v4.r5.design import benchmark_returns

    print("方案 B 别的市场", flush=True)
    check_registered(raw_tickers())
    closes = {name: load_adjclose(name) for name in traded_names()}
    rates = load_dtb3()
    calendar = spy_sessions(closes["SPY"])
    prices, long_returns, _stale = build_panels(closes, calendar, rates)
    window = window_slice(long_returns)
    universe = g_universe()
    try:
        benchmark = benchmark_returns(end=INSPECT[1], allow_after=True)
    except Exception as exc:
        print(f"BM-主 没装上，别的市场逐年差改用 BM-G：{exc}", flush=True)
        benchmark = benchmark_g(window)["net"]
    allocation, book, _panel = run_v51(window, long_returns, prices, universe, cadence="frozen", selection="all")
    folder = OUT / "S0" / "别的市场" / "B"
    index = _norm(book.net.index)
    daily = write_run(folder, book, allocation, index)
    held = pd.read_csv(folder / "held.csv", parse_dates=["date"], index_col="date")
    state = pd.read_csv(folder / "state.csv", parse_dates=["date"], index_col="date")
    exits = pd.read_csv(folder / "exits.csv")
    legs = pd.read_csv(folder / "legs.csv")
    write_stats(folder, daily, held, state, exits, window.reindex(index), benchmark, "别的市场", "S0", [], legs)
    _attach_plan_b(folder, held, window.reindex(index), state, universe)
    (folder / "bm-g-note.txt").write_text(
        "逐年差对的是 BM-主。这一池自己的基准是 60% SPY + 40% IEF。方案 B 只报告。\n",
        encoding="utf-8",
    )


def main() -> int:
    problems = run_s0_design()
    note = OUT / "plan-b-s12.txt"
    if problems:
        text = "S0 设计期方案 B 和稳健性 S12 不一致，后面的方案 B 格子没有跑。\n" + "\n".join(problems) + "\n"
        note.write_text(text, encoding="utf-8")
        print(text, flush=True)
        return 2
    note.write_text("S0 设计期方案 B 与 results/v5.1/robustness/S12 的 net、gross、nav、cost、buy、sell 和 exits 一致。\n", encoding="utf-8")
    print("方案 B 设计期对上 S12", flush=True)
    run_other()
    run_s0_inspection()
    run_s1_inspection()
    print("方案 B 四格写完", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
