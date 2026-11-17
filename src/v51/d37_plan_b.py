"""D37 方案 B。第一层用 selection="all"，节奏仍是冻结规则。

只写 results/v51-diag/d37/<S0|S1>/<段>/B/。不改判据，不改 LOCK。
S0 设计期的净值路径已经接受：run_book 与 S12 差在创业板跌停，不重跑，也不改数字去贴齐。
中国格子成交走 run_book。别的市场与同段 V0 一样走 gpool.run_v51 的 simulate（该池没有涨跌停）。
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
    _db_ready,
    _norm,
    _s1_bundle,
    _sha256,
    _signal_of,
    compare_exits,
    compare_frames,
    write_run,
    write_stats,
)
from .params import V51Error

S12 = ROOT / "results" / "v5.1" / "robustness" / "S12"
EXPECTED_DB = "d0b947d90b444eb1d874a04df6bcb1974cbea4422b489f214a56c0a658abf0d9"
# 年化、回撤、笔数、成本。笔数和成本同时给出合计和每年，与 V0–V4 的 stats 同一套字段。
VS_V0 = (
    ("ann", "年化"),
    ("max_drawdown", "最大回撤"),
    ("trades", "笔数"),
    ("trades_per_year", "每年笔数"),
    ("cost", "成本"),
    ("cost_per_year", "每年成本"),
)
KEPT_DESIGN = (
    "daily.csv", "held.csv", "state.csv", "decisions.csv", "exits.csv",
    "legs.csv", "trades.csv", "sells.csv", "yearly.csv", "markets.csv",
)


def market_counts(state: pd.DataFrame) -> pd.Series:
    """state['market'] 用 | 串起当天同时持有的市场。空着就是 0 个。"""
    labels = state["market"].fillna("").astype(str).replace({"nan": ""})
    return labels.map(lambda text: 0 if not text else text.count("|") + 1).astype(int)


def vs_rows(got: dict, base: dict) -> list[dict]:
    """同一段方案 B 减 V0。got、base 都是 stats['performance']。"""
    rows = []
    for key, label in VS_V0:
        b = float(got[key])
        v = float(base[key])
        rows.append({"metric": key, "label": label, "B": b, "V0": v, "B_minus_V0": b - v})
    return rows


def _write_market_days(folder: Path, histogram: dict[str, int], n_days: int) -> None:
    rows = []
    for key in sorted(histogram, key=lambda item: int(item)):
        got = int(histogram[key])
        rows.append({
            "n_markets": int(key),
            "days": got,
            "share": (got / n_days) if n_days else 0.0,
        })
    pd.DataFrame(rows).to_csv(folder / "market_days.csv", index=False, float_format="%.12g")


def _write_vs_v0(folder: Path, payload: dict) -> None:
    v0_path = folder.parent / "V0" / "stats.json"
    if not v0_path.is_file():
        raise V51Error(f"没有同段 V0：{v0_path}")
    base = json.loads(v0_path.read_text(encoding="utf-8"))
    rows = vs_rows(payload["performance"], base["performance"])
    pd.DataFrame(rows).to_csv(folder / "vs-v0.csv", index=False, float_format="%.12g")
    payload["vs_v0"] = rows


def _histogram(counts: pd.Series) -> dict[str, int]:
    if counts.empty:
        return {"0": 0}
    highest = int(counts.max())
    return {str(n): int((counts == n).sum()) for n in range(highest + 1)}


def plan_b_markets(held: pd.DataFrame, pnl: pd.DataFrame, state: pd.DataFrame, universe) -> tuple[pd.DataFrame, dict]:
    """每天持有几个市场，以及每个市场的平均仓位和贡献。"""
    member_of: dict[str, str] = {}
    for market in universe.markets:
        for name in market.members:
            member_of[name] = market.name
    counts = market_counts(state)
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
        "market_days": _histogram(counts),
    }
    return frame, summary


def _attach_plan_b(folder: Path, held: pd.DataFrame, pnl: pd.DataFrame, state: pd.DataFrame, universe, *,
                   execution: str, db_sha256: str, nav_path: str) -> dict:
    table, summary = plan_b_markets(held, pnl, state, universe)
    histogram = summary.pop("market_days")
    table.to_csv(folder / "markets.csv", index=False, float_format="%.12g")
    _write_market_days(folder, histogram, int(summary["days"]))
    path = folder / "stats.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["plan_b"] = summary
    payload["plan_b"]["markets"] = table.to_dict(orient="records")
    payload["plan_b"]["market_days"] = histogram
    payload["selection"] = "all"
    payload["execution"] = execution
    payload["db_sha256"] = db_sha256
    payload["nav_path"] = nav_path
    payload["note"] = "方案 B，只报告，不计入任何过关判据。"
    _write_vs_v0(folder, payload)
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
                 universe, extra: list[str], *, execution: str, db_sha256: str) -> None:
    daily = write_run(folder, book, allocation, index)
    held = pd.read_csv(folder / "held.csv", parse_dates=["date"], index_col="date")
    state = pd.read_csv(folder / "state.csv", parse_dates=["date"], index_col="date")
    exits = pd.read_csv(folder / "exits.csv")
    legs = pd.read_csv(folder / "legs.csv")
    write_stats(folder, daily, held, state, exits, pnl.reindex(index), benchmark, segment, scope, extra, legs)
    _attach_plan_b(
        folder, held, pnl.reindex(index), state, universe,
        execution=execution, db_sha256=db_sha256, nav_path="this-run",
    )
    decisions = allocation.decisions.copy()
    decisions.index.name = "date"
    decisions.to_csv(folder / "decisions.csv", float_format="%.12g")


def run_s0_design(*, overwrite: bool = False) -> list[str]:
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import benchmark_returns, prepare_market

    from .execute import universe_for

    folder = OUT / "S0" / "设计期" / "B"
    if (folder / "daily.csv").is_file() and not overwrite:
        raise V51Error("S0 设计期 B 已有接受的净值路径，不重跑")
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
    digest = _require_db()
    _finish_cell(
        folder, view_book, allocation, index, pnl, benchmark, "设计期", "S0", universe, [],
        execution="run_book", db_sha256=digest,
    )
    return compare_s12(folder)


def run_s0_inspection(db_sha256: str) -> None:
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
    _finish_cell(
        folder, view, allocation, index, pnl, benchmark, "检验段", "S0", universe, [],
        execution="run_book", db_sha256=db_sha256,
    )


def run_s1_inspection(db_sha256: str) -> None:
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
    _finish_cell(
        folder, view, allocation, index, pnl, benchmark, "检验段", "S1", universe, extra,
        execution="run_book", db_sha256=db_sha256,
    )


def run_other(db_sha256: str) -> None:
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
    _attach_plan_b(
        folder, held, window.reindex(index), state, universe,
        execution="gpool.simulate", db_sha256=db_sha256, nav_path="this-run",
    )
    decisions = allocation.decisions.copy()
    decisions.index.name = "date"
    decisions.to_csv(folder / "decisions.csv", float_format="%.12g")
    (folder / "bm-g-note.txt").write_text(
        "逐年差对的是 BM-主。这一池自己的基准是 60% SPY + 40% IEF。\n"
        "成交入口与同段 V0 相同，是 gpool.run_v51 的 simulate，没有涨跌停。方案 B 只报告。\n",
        encoding="utf-8",
    )


def _require_acceptance() -> None:
    note = OUT / "plan-b-s12.txt"
    text = note.read_text(encoding="utf-8") if note.is_file() else ""
    if "Owner 接受 run_book" not in text:
        raise V51Error("plan-b-s12.txt 还没写明 Owner 接受 run_book")


def _require_db() -> str:
    digest = _db_ready()
    if digest != EXPECTED_DB:
        raise V51Error(f"行情库不是当前库 {EXPECTED_DB}，实际 {digest}")
    return digest


def supplement_kept_design(db_sha256: str) -> None:
    """给已接受的 S0 设计期 B 补分布和与 V0 的对照。不改净值文件。"""
    folder = OUT / "S0" / "设计期" / "B"
    missing = [name for name in KEPT_DESIGN if not (folder / name).is_file()]
    if missing:
        raise V51Error(f"设计期 B 缺文件：{missing}")
    before = {name: _sha256(folder / name) for name in KEPT_DESIGN}
    state = pd.read_csv(folder / "state.csv", parse_dates=["date"], index_col="date")
    counts = market_counts(state)
    path = folder / "stats.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    stored = payload["plan_b"]
    avg = float(counts.mean()) if len(counts) else 0.0
    if abs(avg - float(stored["avg_markets_per_day"])) > 1e-12:
        raise V51Error("持有市场数的均值和已接受的 plan_b 对不上，没有改净值")
    if int(counts.max() if len(counts) else 0) != int(stored["max_markets"]):
        raise V51Error("持有市场数的最大值和已接受的 plan_b 对不上，没有改净值")
    if int(len(counts)) != int(stored["days"]):
        raise V51Error("天数和已接受的 plan_b 对不上，没有改净值")
    from .diag_d37 import DESIGN

    start, end = DESIGN
    window_state = state.loc[start:end]
    window_counts = market_counts(window_state)
    histogram = _histogram(window_counts)
    _write_market_days(folder, histogram, int(len(window_counts)))
    # 已接受的 avg / days / markets.csv 含 2005 年 242 天满仓现金。分布改按设计期窗口，那两个数不改。
    stored["market_days"] = histogram
    stored["market_days_window"] = {"start": start, "end": end, "days": int(len(window_counts))}
    stored["avg_markets_in_window"] = float(window_counts.mean()) if len(window_counts) else 0.0
    warmup = int(len(counts) - len(window_counts))
    stored["warmup_days_before_window"] = warmup
    n_full = int(stored["days"])
    n_win = int(len(window_counts))
    daily = pd.read_csv(folder / "daily.csv", parse_dates=["date"], index_col="date")
    pre_gross = float(daily.loc[:pd.Timestamp(start) - pd.Timedelta(days=1), "gross"].sum())
    for row in stored["markets"]:
        if row["market"] == "防守或现金":
            row["window_avg_weight"] = (float(row["avg_weight"]) * n_full - warmup) / n_win
            row["window_days_held"] = int(row["days_held"]) - warmup
            row["window_contribution"] = float(row["contribution"]) - pre_gross
        else:
            row["window_avg_weight"] = float(row["avg_weight"]) * n_full / n_win
            row["window_days_held"] = int(row["days_held"])
            row["window_contribution"] = float(row["contribution"])
    pd.DataFrame([
        {
            "market": row["market"],
            "avg_weight": row["window_avg_weight"],
            "days_held": row["window_days_held"],
            "contribution": row["window_contribution"],
        }
        for row in stored["markets"]
    ]).to_csv(folder / "markets-window.csv", index=False, float_format="%.12g")
    stored["window_note"] = (
        "market_days、avg_markets_in_window、window_* 和 markets-window.csv 是 2006-01-01→2015-12-31，与年化同一窗口。"
        "avg_markets_per_day、days 和 markets.csv 仍是含 2005 年 242 天满仓现金的已接受数字，没有改。"
        "风险市场这 242 天权重为 0，所以窗口贡献等于原贡献；防守贡献减去这 242 天的组合毛收益。"
    )
    payload["execution"] = "run_book"
    payload["db_sha256"] = db_sha256
    payload["nav_path"] = "kept"
    _write_vs_v0(folder, payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    changed = [name for name in KEPT_DESIGN if _sha256(folder / name) != before[name]]
    if changed:
        raise V51Error(f"设计期净值文件被改了：{changed}")


def _write_manifest(db_sha256: str) -> None:
    cells = []
    for scope, segment in (("S0", "设计期"), ("S0", "别的市场"), ("S0", "检验段"), ("S1", "检验段")):
        folder = OUT / scope / segment / "B"
        stats = json.loads((folder / "stats.json").read_text(encoding="utf-8"))
        perf = stats["performance"]
        cells.append({
            "scope": scope,
            "segment": segment,
            "execution": stats.get("execution"),
            "nav_path": stats.get("nav_path"),
            "ann": perf["ann"],
            "max_drawdown": perf["max_drawdown"],
            "trades": perf["trades"],
            "trades_per_year": perf["trades_per_year"],
            "cost": perf["cost"],
            "cost_per_year": perf["cost_per_year"],
        })
    payload = {
        "diagnostic": "D37-r5",
        "counts_toward_gate": False,
        "selection": "all",
        "cadence": "frozen",
        "db_sha256": db_sha256,
        "design_nav": "kept",
        "cells": cells,
    }
    (OUT / "plan-b-round5.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )


def main() -> int:
    _require_acceptance()
    digest = _require_db()
    print(f"方案 B 行情库 {digest}", flush=True)
    supplement_kept_design(digest)
    print("方案 B 设计期净值保持原路径，已补分布和 V0 对照", flush=True)
    run_other(digest)
    run_s0_inspection(digest)
    run_s1_inspection(digest)
    _write_manifest(digest)
    print("方案 B 其余三格写完", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
