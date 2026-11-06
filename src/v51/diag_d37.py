"""D37 诊断矩阵。只写 results/v51-diag/d37/，不改 LOCK，不改签收结果。

S0 V0 必须和签收文件逐位一致，对不上就停。
检验段只在 results/v5/LOCK-addendum-D37.md 已经在当前树上时才跑。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.data import db as DB
from src.data.db import git_head

from .allocate import CADENCES
from .diag_stats import performance, s1_participation, sell_rows, trade_cost, turnover_rows
from .params import V51Error
from .s1_scope import (
    apply_splices,
    buyable_frame,
    container_map,
    listed_funds,
    load_amounts,
    load_closes,
    missing_report,
    registry_rows,
)
from .universe import S1_EXTRA, universe_s1

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "v51-diag" / "d37"
ADDENDUM = ROOT / "results" / "v5" / "LOCK-addendum-D37.md"
CLASSES = ROOT / "config" / "v5" / "classes.csv"
VERSIONS = {
    "V0": "frozen",
    "V1": "weekly",
    "V2": "resonance",
    "V3": "daily",
    "V4": "resonance_daily",
}
DESIGN = ("2006-01-01", "2015-12-31")
INSPECT = ("2016-01-01", "2026-09-30")
OTHER = ("2003-07-01", "2026-09-30")


def _sha256(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspection_unlocked() -> bool:
    if not ADDENDUM.is_file():
        return False
    text = ADDENDUM.read_text(encoding="utf-8")
    return "2016-01-01" in text and "2026-09-30" in text and "D37" in text


def _db_ready() -> str:
    path = DB.MARKET_DB
    if not path.is_file() or path.stat().st_size < 1000:
        raise V51Error(f"行情库不可读：{path}")
    blob = path.read_bytes()[:80]
    if blob.startswith(b"version https://git-lfs.github.com/spec/v1"):
        raise V51Error("行情库还是 LFS 指针，先 git lfs pull --include=data/market.sqlite")
    return _sha256(path)


def _norm(index) -> pd.DatetimeIndex:
    days = pd.DatetimeIndex(pd.to_datetime(index)).normalize()
    if days.tz is not None:
        raise V51Error("日期不带时区")
    return days


def _write_frame(folder: Path, frame: pd.DataFrame, name: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    out.index.name = "date"
    out.to_csv(folder / name, float_format="%.12g")


def _daily_frame(book, allocation, index: pd.DatetimeIndex) -> pd.DataFrame:
    net = book.net.astype(float).reindex(index)
    daily = pd.DataFrame({
        "net": net,
        "gross": book.gross.astype(float).reindex(index),
        "nav": (1.0 + net).cumprod(),
        "cost": book.cost.astype(float).reindex(index),
        "buy": book.buy.astype(float).reindex(index),
        "sell": book.sell.astype(float).reindex(index),
    })
    state = allocation.state.copy()
    state.index = _norm(state.index)
    daily = daily.join(state.reindex(index))
    daily.index.name = "date"
    return daily


def _slice_book(book, index: pd.DatetimeIndex):
    """只留窗口内的成交结果。持仓用开盘前权重，和签收的 held 一样。"""
    class _View:
        pass
    view = _View()
    view.net = book.net.astype(float).reindex(index)
    view.gross = book.gross.astype(float).reindex(index)
    view.cost = book.cost.astype(float).reindex(index)
    view.buy = book.buy.astype(float).reindex(index)
    view.sell = book.sell.astype(float).reindex(index)
    held = book.held.copy()
    held.index = _norm(held.index)
    view.held = held.reindex(index)
    return view


def write_run(folder: Path, book, allocation, index: pd.DatetimeIndex) -> pd.DataFrame:
    daily = _daily_frame(book, allocation, index)
    _write_frame(folder, daily, "daily.csv")
    held = book.held.copy()
    held.index = _norm(held.index)
    _write_frame(folder, held.reindex(index), "held.csv")
    state = allocation.state.copy()
    state.index = _norm(state.index)
    _write_frame(folder, state.reindex(index), "state.csv")
    exits = allocation.exits.copy()
    if len(exits) and "t" in exits.columns:
        stamp = pd.to_datetime(exits["t"])
        exits = exits.loc[(stamp >= index.min()) & (stamp <= index.max())]
    exits.to_csv(folder / "exits.csv", index=False)
    legs = allocation.legs.copy() if allocation.legs is not None else pd.DataFrame()
    if len(legs):
        legs["date"] = pd.to_datetime(legs["date"])
        legs = legs.loc[(legs["date"] >= index.min()) & (legs["date"] <= index.max())]
    legs.to_csv(folder / "legs.csv", index=False, float_format="%.12g")
    return daily


def _text(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).replace({"nan": ""})


def _num_mismatch(got: pd.Series, signed: pd.Series, tol: float = 1e-8) -> str | None:
    left = pd.to_numeric(got, errors="coerce")
    right = pd.to_numeric(signed, errors="coerce")
    both_missing = left.isna() & right.isna()
    if not np.allclose(left.fillna(0.0), right.fillna(0.0), atol=tol, rtol=0.0, equal_nan=True):
        gap = (left.fillna(0.0) - right.fillna(0.0)).abs()
        gap = gap.where(~both_missing, 0.0)
        if float(gap.max()) <= tol:
            return None
        at = gap.idxmax()
        return f"max {float(gap.max()):.3g} @ {pd.Timestamp(at).date()} got {left.at[at]} signed {right.at[at]}"
    return None


def compare_frames(got: pd.DataFrame, signed: pd.DataFrame, columns: list[str]) -> list[str]:
    problems = []
    if not got.index.equals(signed.index):
        problems.append(f"日期 {len(got)}≠{len(signed)} {got.index.min()}→{got.index.max()} vs {signed.index.min()}→{signed.index.max()}")
        return problems
    for name in columns:
        if name not in got.columns or name not in signed.columns:
            problems.append(f"缺列 {name}")
            continue
        if name in {"market", "market_name", "defense", "picks", "blocked"}:
            if not _text(got[name]).equals(_text(signed[name])):
                bad = _text(got[name]) != _text(signed[name])
                stamp = pd.Timestamp(got.index[bad][0]).date()
                problems.append(f"{name} {int(bad.sum())} 行，例如 {stamp}")
            continue
        found = _num_mismatch(got[name], signed[name])
        if found:
            problems.append(f"{name} {found}")
    return problems


def compare_exits(got: pd.DataFrame, signed: pd.DataFrame) -> list[str]:
    def rows(frame: pd.DataFrame) -> list[tuple]:
        if frame.empty:
            return []
        out = frame.copy()
        out["t"] = pd.to_datetime(out["t"]).dt.strftime("%Y-%m-%d")
        return sorted(tuple(row) for row in out[["t", "id", "why"]].itertuples(index=False, name=None))
    left, right = rows(got), rows(signed)
    if left == right:
        return []
    mismatch = next(((a, b) for a, b in zip(left, right) if a != b), None)
    return [f"exits {len(left)}≠{len(right)} 首差 {mismatch}"]


def bitmatch_s0_v0(segment: str, folder: Path) -> list[str]:
    if segment == "设计期":
        signed = ROOT / "results" / "v5.1" / "design" / "index"
        got_daily = pd.read_csv(folder / "daily.csv", parse_dates=["date"], index_col="date")
        ref_daily = pd.read_csv(signed / "daily.csv", parse_dates=["date"], index_col="date")
        problems = compare_frames(
            got_daily, ref_daily,
            ["net", "gross", "nav", "cost", "buy", "sell", "market", "market_name", "risk", "defense", "picks", "blocked"],
        )
        got_held = pd.read_csv(folder / "held.csv", parse_dates=["date"], index_col="date")
        ref_held = pd.read_csv(signed / "held.csv", parse_dates=["date"], index_col="date")
        shared = [name for name in ref_held.columns if name in got_held.columns]
        problems.extend("held " + item for item in compare_frames(got_held, ref_held, shared))
        if list(got_held.columns) != list(ref_held.columns):
            problems.append("held 列顺序或名单和签收不一致")
        problems.extend(compare_exits(
            pd.read_csv(folder / "exits.csv"),
            pd.read_csv(signed / "exits.csv"),
        ))
        return [f"设计期 {item}" for item in problems]
    if segment == "别的市场":
        signed = ROOT / "results" / "v5.1" / "other-market" / "v51"
        got_daily = pd.read_csv(folder / "daily.csv", parse_dates=["date"], index_col="date")
        ref_daily = pd.read_csv(signed / "daily.csv", parse_dates=["date"], index_col="date")
        problems = compare_frames(
            got_daily, ref_daily,
            ["net", "gross", "nav", "cost", "buy", "sell", "market", "market_name", "risk", "defense", "picks", "blocked"],
        )
        got_held = pd.read_csv(folder / "held.csv", parse_dates=["date"], index_col="date")
        ref_held = pd.read_csv(signed / "held.csv", parse_dates=["date"], index_col="date")
        shared = [name for name in ref_held.columns if name in got_held.columns]
        problems.extend("held " + item for item in compare_frames(got_held, ref_held, shared))
        problems.extend(compare_exits(pd.read_csv(folder / "exits.csv"), pd.read_csv(signed / "exits.csv")))
        return [f"别的市场 {item}" for item in problems]
    signed = ROOT / "results" / "v5" / "oneshot" / "index" / "v5.1-对照"
    got_daily = pd.read_csv(folder / "daily.csv", parse_dates=["date"], index_col="date")
    ref_net = pd.read_csv(signed / "net.csv", parse_dates=["date"], index_col="date")
    problems = compare_frames(got_daily, ref_net, ["net", "nav", "gross", "cost", "buy", "sell"])
    ref_state = pd.read_csv(signed / "state.csv", parse_dates=["date"], index_col="date")
    problems.extend(compare_frames(
        got_daily, ref_state, ["market", "market_name", "risk", "defense", "picks", "blocked"],
    ))
    got_held = pd.read_csv(folder / "held.csv", parse_dates=["date"], index_col="date")
    ref_held = pd.read_csv(signed / "held.csv", parse_dates=["date"], index_col="date")
    shared = [name for name in ref_held.columns if name in got_held.columns]
    problems.extend("held " + item for item in compare_frames(got_held, ref_held, shared))
    if set(got_held.columns) != set(ref_held.columns):
        problems.append("held 列名单和签收不一致")
    problems.extend(compare_exits(pd.read_csv(folder / "exits.csv"), pd.read_csv(signed / "exits.csv")))
    return [f"检验段 {item}" for item in problems]


def _stats_window(daily: pd.DataFrame, held: pd.DataFrame, state: pd.DataFrame, segment: str):
    if segment == "设计期":
        start, end = DESIGN
        return daily.loc[start:end], held.loc[start:end], state.loc[start:end]
    return daily, held, state


def write_stats(folder: Path, daily: pd.DataFrame, held: pd.DataFrame, state: pd.DataFrame,
                exits: pd.DataFrame, pnl: pd.DataFrame, benchmark: pd.Series, segment: str,
                scope: str, extra_markets: list[str], legs: pd.DataFrame) -> dict:
    window_daily, window_held, window_state = _stats_window(daily, held, state, segment)
    classes = dict(zip(pd.read_csv(CLASSES)["container_id"], pd.read_csv(CLASSES)["class"]))
    numbers = performance(window_daily["net"], benchmark)
    numbers.update(trade_cost(window_daily, segment))
    trades, turnover = turnover_rows(
        window_held, window_daily, window_state, exits, pnl, classes, segment,
    )
    sells, sell_summary = sell_rows(window_held, window_daily, window_state, pnl, classes, segment)
    trades.to_csv(folder / "trades.csv", index=False, float_format="%.12g")
    sells.to_csv(folder / "sells.csv", index=False, float_format="%.12g")
    payload = {
        "scope": scope,
        "segment": segment,
        "performance": {key: value for key, value in numbers.items() if key != "yearly"},
        "yearly_vs_bm_main": numbers["yearly"],
        "turnover": turnover,
        "sells": sell_summary,
        "note": "诊断，不计入任何过关判据。",
    }
    if scope == "S1":
        payload["s1_markets"] = s1_participation(legs, window_held, pnl, extra_markets)
    (folder / "stats.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame(numbers["yearly"]).to_csv(folder / "yearly.csv", index=False, float_format="%.12g")
    return payload


def _signal_of(market) -> pd.DataFrame:
    signal = market.signal.copy()
    signal.index = _norm(signal.index)
    dates = _norm(market.dates)
    if not signal.index.equals(dates):
        raise V51Error("信号日历和成交日历不一致")
    return signal


def _s1_bundle(market, con):
    from .universe import class_lookup

    mapping = class_lookup(list(market.names), market.cash_id)
    universe = universe_s1([name for name in market.names if name != market.cash_id], mapping)
    containers = container_map()
    registry = registry_rows(OUT / "s1-index-registry.csv")
    signal, notes = apply_splices(
        _signal_of(market), registry, lambda code: load_closes(con, code), containers,
        fx_of=lambda code: load_closes(con, code),
    )
    codes: list[str] = []
    packed: dict[str, list] = {}
    members = [name for market_ in universe.markets for name in market_.members]
    for name in members:
        funds = listed_funds(containers.get(name) or {})
        packed[name] = [(fund, None) for fund in funds]
        codes.extend(fund.code for fund in funds)
    amounts = load_amounts(con, sorted(set(codes)))
    funds = {
        name: [(fund, amounts.get(fund.code, pd.Series(dtype=float))) for fund, _none in rows]
        for name, rows in packed.items()
    }
    eligible = buyable_frame(signal.index, funds)
    extra = [item.representative for item in universe.markets if mapping.get(item.representative) in S1_EXTRA]
    classes = dict(zip(pd.read_csv(CLASSES)["container_id"], pd.read_csv(CLASSES)["class"]))
    report = missing_report(classes, set(signal.columns), registry, notes)
    return universe, signal, eligible, extra, report, notes


def _panel(signal: pd.DataFrame, cash: str, allow_after: bool):
    from .readings import read_panel

    return read_panel(signal, cash, allow_after=allow_after)


def _run_cn_version(market, spec, universe, signal, panel, eligible, cadence: str, allow_after: bool,
                    selection: str = "market"):
    from .allocate import allocate
    from .execute import run_book
    from .readings import level_index

    allocation = allocate(
        panel.H.index, panel.H, panel.F, panel.E, universe,
        prices=level_index(signal), returns=signal, eligible=eligible,
        allow_after=allow_after, cadence=cadence, selection=selection,
    )
    missing = [name for name in allocation.decisions.columns if name not in market.pnl.columns]
    if missing:
        raise V51Error(f"决策有行情没有的列：{missing[:5]}")
    book = run_book(market, spec, allocation.decisions, allow_after=allow_after)
    return book, allocation


def _cn_index(market, segment: str) -> pd.DatetimeIndex:
    dates = _norm(market.dates)
    if segment == "设计期":
        return dates
    start, end = INSPECT
    return dates[(dates >= start) & (dates <= end)]


def _iso(stamp) -> str:
    if stamp is None or (isinstance(stamp, float) and np.isnan(stamp)):
        return ""
    try:
        if pd.isna(stamp):
            return ""
    except TypeError:
        pass
    return pd.Timestamp(stamp).date().isoformat()


def _first_valid(series: pd.Series) -> str:
    valid = series.dropna()
    if valid.empty:
        return ""
    return _iso(valid.index[0])


def _hold_start(held: pd.DataFrame, name: str) -> tuple[str, int]:
    if name not in held.columns:
        return "", 0
    weights = held[name].astype(float)
    days = weights[weights > 1e-6]
    if days.empty:
        return "", 0
    return _iso(days.index[0]), int(len(days))


def _day_gap(later: str, earlier: str) -> str:
    if not later or not earlier:
        return ""
    return str((pd.Timestamp(later) - pd.Timestamp(earlier)).days)


def write_s1_container_table(segment: str, pre_panel, post_panel, pre_held: pd.DataFrame,
                             post_held: pd.DataFrame, pnl: pd.DataFrame) -> None:
    """每只被考虑过的容器：拼接前后第一次能打分、第一次持有、持有天数和贡献。"""
    registry = registry_rows(OUT / "s1-index-registry.csv")
    if not registry:
        return
    rows = []
    for row in registry:
        name = str(row.get("container_id") or "")
        pre_score = _first_valid(pre_panel.H[name]) if name in pre_panel.H.columns else ""
        post_score = _first_valid(post_panel.H[name]) if name in post_panel.H.columns else ""
        pre_hold, _pre_days = _hold_start(pre_held, name)
        post_hold, post_days = _hold_start(post_held, name)
        weights = post_held[name].astype(float) if name in post_held.columns else pd.Series(dtype=float)
        returns = pnl[name].astype(float) if name in pnl.columns else pd.Series(dtype=float)
        aligned = returns.reindex(weights.index).fillna(0.0) if len(weights) else pd.Series(dtype=float)
        contribution = float((weights.reindex(aligned.index).fillna(0.0) * aligned).sum()) if len(weights) else 0.0
        rows.append({
            "container_id": name,
            "class": row.get("class") or "",
            "status": row.get("status") or "",
            "publish_date": row.get("publish_date") or "",
            "bars_code": row.get("bars_code") or "",
            "first_list": row.get("first_list") or "",
            "series_first": row.get("series_first") or "",
            "first_scoreable_pre": pre_score,
            "first_scoreable_post": post_score,
            "scoreable_earlier_days": _day_gap(pre_score, post_score),
            "first_hold_pre": pre_hold,
            "first_hold_post": post_hold,
            "hold_earlier_days": _day_gap(pre_hold, post_hold),
            "hold_days_post": post_days,
            "contribution_post": contribution,
            "reason": row.get("reason") or "",
        })
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / f"s1-container-effect-{segment}.csv", index=False, float_format="%.12g")


def write_otc_backfill_note(folder: Path) -> None:
    """当前库 S0 V0 相对签收 oneshot 的年化、回撤和换名天数。只作 OTC 续接的说明。"""
    stats = json.loads((folder / "stats.json").read_text(encoding="utf-8"))
    signed = json.loads((ROOT / "results" / "v5" / "oneshot" / "index" / "v5.1-对照" / "summary.json").read_text(encoding="utf-8"))
    got = pd.read_csv(folder / "daily.csv", parse_dates=["date"], index_col="date")
    ref = pd.read_csv(ROOT / "results" / "v5" / "oneshot" / "index" / "v5.1-对照" / "state.csv", parse_dates=["date"], index_col="date")
    shared = got.index.intersection(ref.index)
    picks = (_text(got.loc[shared, "picks"]) != _text(ref.loc[shared, "picks"])).sum()
    market = (_text(got.loc[shared, "market"]) != _text(ref.loc[shared, "market"])).sum()
    ann = float(stats["performance"]["ann"])
    mdd = float(stats["performance"]["max_drawdown"])
    lines = [
        "当前库 S0 V0 检验段没有逐位对上签收的 v5.1-对照。",
        "签收库是 167d4e39。用那份库的临时副本重跑，S0 V0 检验段与签收 net 逐日差为 0。",
        "差异来自签收之后的场外净值续接，不是节奏开关。这一段后面的版本改以当前库的 S0 V0 为对照，不改签收结论。",
        f"年化：当前 {ann:.6f}，签收 {float(signed['cagr']):.6f}，差 {ann - float(signed['cagr']):.6f}",
        f"最大回撤：当前 {mdd:.6f}，签收 {float(signed['max_drawdown']):.6f}，差 {mdd - float(signed['max_drawdown']):.6f}",
        f"名字不同的天数（picks）：{int(picks)}",
        f"市场不同的天数：{int(market)}",
    ]
    (OUT / "inspection-v0-note.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_cn(segment: str, versions: list[str], scopes: list[str], *, bitmatch: bool) -> list[str]:
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import benchmark_returns, prepare_market

    if segment == "检验段" and not inspection_unlocked():
        raise V51Error("检验段还没解锁：当前树上没有 LOCK-addendum-D37")
    allow_after = segment == "检验段"
    end = INSPECT[1] if allow_after else DESIGN[1]
    spec = load_spec()
    print(f"装中国 {segment} 到 {end}", flush=True)
    market = prepare_market("index", t4=False, allow_substitute=True, spec=spec, end=end, allow_after=allow_after)
    benchmark = benchmark_returns(end=end, allow_after=allow_after)
    index = _cn_index(market, segment)
    problems: list[str] = []
    con = None
    s1 = None
    if "S1" in scopes:
        import sqlite3
        con = sqlite3.connect(DB.MARKET_DB)
        s1 = _s1_bundle(market, con)
        s1[4].to_csv(OUT / "s1-missing-sources.csv", index=False)
        (OUT / "s1-splice-notes.json").write_text(json.dumps(s1[5], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    from .execute import universe_for

    frozen_universe = universe_for(market)
    signal = _signal_of(market)
    panels = {"S0": _panel(signal, market.cash_id, allow_after)}
    if s1 is not None:
        panels["S1"] = _panel(s1[1], market.cash_id, allow_after)
    for scope in scopes:
        for version in versions:
            if scope == "S0" and version != "V0" and bitmatch:
                continue
            cadence = VERSIONS[version]
            print(f"{scope} {segment} {version}", flush=True)
            if scope == "S0":
                book, allocation = _run_cn_version(
                    market, spec, frozen_universe, signal, panels["S0"], None, cadence, allow_after,
                )
                extra: list[str] = []
            else:
                assert s1 is not None
                book, allocation = _run_cn_version(
                    market, spec, s1[0], s1[1], panels["S1"], s1[2], cadence, allow_after,
                )
                extra = s1[3]
            view = _slice_book(book, index)
            folder = OUT / scope / segment / version
            daily = write_run(folder, view, allocation, index)
            held = pd.read_csv(folder / "held.csv", parse_dates=["date"], index_col="date")
            state = pd.read_csv(folder / "state.csv", parse_dates=["date"], index_col="date")
            exits = pd.read_csv(folder / "exits.csv")
            legs = pd.read_csv(folder / "legs.csv")
            pnl = market.pnl.copy()
            pnl.index = _norm(pnl.index)
            write_stats(folder, daily, held, state, exits, pnl.reindex(index), benchmark, segment, scope, extra, legs)
            if scope == "S0" and version == "V0":
                found = bitmatch_s0_v0(segment, folder)
                problems.extend(found)
                if found:
                    print("S0 V0 对不上签收，停止这一段后面的版本", flush=True)
                    break
    if s1 is not None and "V0" in versions and (OUT / "S1" / segment / "V0" / "held.csv").is_file():
        print(f"S1 {segment} 拼接前 V0，只为对照第一次持有", flush=True)
        pre_book, _pre_allocation = _run_cn_version(
            market, spec, s1[0], signal, panels["S0"], s1[2], "frozen", allow_after,
        )
        pre_held = _slice_book(pre_book, index).held
        post_held = pd.read_csv(OUT / "S1" / segment / "V0" / "held.csv", parse_dates=["date"], index_col="date")
        pnl = market.pnl.copy()
        pnl.index = _norm(pnl.index)
        write_s1_container_table(segment, panels["S0"], panels["S1"], pre_held, post_held, pnl.reindex(index))
    if con is not None:
        con.close()
    return problems


def run_other(versions: list[str], *, bitmatch: bool) -> list[str]:
    from .gpool import (
        CASH,
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

    print("核对别的市场行情", flush=True)
    check_registered(raw_tickers())
    closes = {name: load_adjclose(name) for name in traded_names()}
    rates = load_dtb3()
    calendar = spy_sessions(closes["SPY"])
    prices, long_returns, _stale = build_panels(closes, calendar, rates)
    window = window_slice(long_returns)
    universe = g_universe()
    benchmark = benchmark_g(window)["net"]
    try:
        bm_main = benchmark_returns(end=INSPECT[1], allow_after=True)
    except Exception as exc:
        print(f"BM-主 没装上，别的市场逐年差改用 BM-G：{exc}", flush=True)
        bm_main = benchmark
    problems = []
    for version in versions:
        if version != "V0" and bitmatch:
            continue
        print(f"S0 别的市场 {version}", flush=True)
        allocation, book, _panel = run_v51(window, long_returns, prices, universe, cadence=VERSIONS[version])
        folder = OUT / "S0" / "别的市场" / version
        index = _norm(book.net.index)
        daily = write_run(folder, book, allocation, index)
        held = pd.read_csv(folder / "held.csv", parse_dates=["date"], index_col="date")
        state = pd.read_csv(folder / "state.csv", parse_dates=["date"], index_col="date")
        exits = pd.read_csv(folder / "exits.csv")
        legs = pd.read_csv(folder / "legs.csv")
        write_stats(
            folder, daily, held, state, exits, window.reindex(index), bm_main, "别的市场", "S0", [], legs,
        )
        (folder / "bm-g-note.txt").write_text(
            "逐年差对的是 BM-主。这一池自己的基准是 60% SPY + 40% IEF，年化见 stats 外不另作过关。\n",
            encoding="utf-8",
        )
        if version == "V0":
            found = bitmatch_s0_v0("别的市场", folder)
            problems.extend(found)
            if found:
                break
        del allocation, book
    return problems


def run_matrix(scopes: list[str], segments: list[str], versions: list[str], *, allow_v0_diff: bool = False) -> dict:
    if set(versions) - set(VERSIONS):
        raise V51Error(f"版本只能是 {list(VERSIONS)}")
    if "S1" in scopes and "别的市场" in segments and segments == ["别的市场"] and scopes == ["S1"]:
        raise V51Error("别的市场只跑 S0")
    OUT.mkdir(parents=True, exist_ok=True)
    digest = ""
    if any(item != "别的市场" for item in segments) or "S1" in scopes:
        digest = _db_ready()
    ordered = [item for item in ("设计期", "别的市场", "检验段") if item in segments]
    # 先把三个 S0 V0 对完，再跑其余版本。
    v0_problems: list[str] = []
    for segment in ordered:
        if segment == "别的市场":
            v0_problems.extend(run_other(["V0"], bitmatch=True))
        else:
            v0_problems.extend(run_cn(segment, ["V0"], ["S0"], bitmatch=True))
    manifest = {
        "diagnostic": "D37",
        "counts_toward_gate": False,
        "lock_addendum": str(ADDENDUM.relative_to(ROOT)) if inspection_unlocked() else None,
        "inspection_unlocked": inspection_unlocked(),
        "db_sha256": digest,
        "git_sha": git_head() or "",
        "cadence": CADENCES,
        "s0_v0_segments_checked": ordered,
        "s0_v0_bitmatch": v0_problems or "ok",
        "allow_v0_diff": allow_v0_diff,
        "s1_pnl": "打分用拼接后的研究序列；持有收益仍是冻结的指数池计价。可买日按场内 ETF/LOF 上市当日起、5 日成交额中位数。美元和港币价格指数先乘已登记汇率，再按海外对齐放到上交所日历。",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if v0_problems:
        (OUT / "s0-v0-mismatch.txt").write_text("\n".join(v0_problems) + "\n", encoding="utf-8")
        if not allow_v0_diff:
            raise V51Error("S0 V0 和签收结果不一致：\n" + "\n".join(v0_problems))
        inspected = OUT / "S0" / "检验段" / "V0"
        if (inspected / "stats.json").is_file():
            write_otc_backfill_note(inspected)
    for segment in ordered:
        if segment == "别的市场":
            pending = [item for item in versions if item != "V0"]
            if pending and "S0" in scopes:
                run_other(pending, bitmatch=False)
            continue
        if "S1" in scopes:
            run_cn(segment, list(versions), ["S1"], bitmatch=False)
        pending = [item for item in versions if item != "V0"]
        if pending and "S0" in scopes:
            run_cn(segment, pending, ["S0"], bitmatch=False)
    manifest["cells_written"] = True
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="D37 v5.1 节奏诊断")
    parser.add_argument("--scope", default="all", choices=["S0", "S1", "all"])
    parser.add_argument("--segment", default="all", choices=["设计期", "别的市场", "检验段", "all"])
    parser.add_argument("--version", default="all", choices=["V0", "V1", "V2", "V3", "V4", "all"])
    parser.add_argument("--allow-v0-diff", action="store_true")
    args = parser.parse_args(argv)
    scopes = ["S0", "S1"] if args.scope == "all" else [args.scope]
    segments = ["设计期", "别的市场", "检验段"] if args.segment == "all" else [args.segment]
    if "S1" in scopes and "别的市场" in segments and args.segment == "别的市场":
        raise V51Error("别的市场只跑 S0")
    if "别的市场" in segments and "S1" in scopes and args.segment == "all":
        pass
    versions = list(VERSIONS) if args.version == "all" else [args.version]
    if "检验段" in segments and not inspection_unlocked():
        raise V51Error("检验段还没解锁")
    # 别的市场不跑 S1。全量时把 S1 限制在中国两段，由 run_matrix 负责。
    summary = run_matrix(
        scopes, [item for item in segments if not (item == "别的市场" and scopes == ["S1"])], versions,
        allow_v0_diff=args.allow_v0_diff,
    )
    print(json.dumps({"bitmatch": summary["s0_v0_bitmatch"], "db": summary["db_sha256"]}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
