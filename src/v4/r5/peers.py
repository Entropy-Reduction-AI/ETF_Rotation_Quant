"""附表 A 在设计期的真实行情。信号用与 v4 相同的收盘时点和汇率。

U-指数用研究序列。U-可交易的月末判断和日收益都用选定载体自己的复权路径；
当天没有载体的那一腿拿现金。不接离场、溢价和 T1–T4。
日期晚于 2015-12-31 的序列直接拒绝。
"""
from __future__ import annotations

import pandas as pd

from src.v3.engine.benchmark import _calendar
from src.v3.engine.book import RunnerError
from src.v3.engine.limits import FillQuote, fill_board_for
from src.v3.engine.market import _raw_close, _research_level, _split_bars
from src.v3.engine.prices import dividend_yields
from src.v3.engine.spec import Spec
from src.v3.engine.universe import execution_code, research_code
from src.v3.data.history import OFFICIAL, history_floor
from src.v3.data.universe import containers as load_containers
from src.v3.engine.universe import parse_date
from src.v4.engine.carriers import (
    build_candidates,
    choose_path,
    compound_level,
    prints_for,
    spliced_portfolio,
    stitch_fills,
)
from src.v4.engine.pool import _hk_level, load_mid
from src.v4.peers import load_peer, run_peer
from src.v4.r5.design import (
    DESIGN_END,
    POOLS,
    _connect,
    cash_on,
    peer_params,
    read_net,
    require_design_index,
    run_dir,
    upsert_ledger,
    write_run,
)

A_SHARE = {"A股宽基", "A股行业", "A股红利"}


def _legs() -> list[str]:
    names = []
    for peer_id in ("A1", "A2"):
        for pool in POOLS:
            for leg in load_peer(peer_id, pool).legs:
                if leg.leg_id not in names:
                    names.append(leg.leg_id)
    return names


def _dividends(con, end: str) -> dict[str, dict]:
    frame = pd.read_sql_query(
        "SELECT code, ex_date, amount, prev_close FROM cash_dividends WHERE ex_date <= ?",
        con, params=(end,))
    out: dict[str, dict] = {}
    if frame.empty:
        return out
    frame["ex_date"] = pd.to_datetime(frame["ex_date"])
    for code, block in frame.groupby("code", sort=False):
        out[str(code)] = dividend_yields(block)
    return out


def _bars(con, codes: list[str], end: str) -> dict[str, pd.DataFrame]:
    marks = ",".join("?" * len(codes))
    frame = pd.read_sql_query(
        "SELECT code, date, open, close FROM bars WHERE adj = 'raw' AND date <= ? "
        f"AND code IN ({marks})",
        con, params=[end, *codes])
    return _split_bars(frame)


def research_panel(spec: Spec) -> dict:
    """五条腿的研究序列，已经换成人民币并对齐到上交所交易日。"""
    containers = load_containers()
    by_id = {str(row.get("id") or ""): row for row in containers}
    names = _legs()
    missing = [name for name in names if name not in by_id]
    if missing:
        raise RunnerError(f"附表 A 的容器不在登记表里：{missing}")
    con = _connect()
    try:
        calendar = _calendar(con, DESIGN_END)
        usd = load_mid(con, "USDCNY", DESIGN_END, filled=True)
        hkd = load_mid(con, "HKDCNY", DESIGN_END, filled=True)
        codes = []
        for name in names:
            code = research_code(by_id[name])
            if not code:
                raise RunnerError(f"{name} 没有研究序列")
            codes.append(code)
        bars = _bars(con, codes, DESIGN_END)
        divs = _dividends(con, DESIGN_END)
        levels = {}
        quotes = {}
        for name in names:
            container = by_id[name]
            code = research_code(container) or ""
            asset = str(container.get("asset_class") or "")
            source = str((container.get("research") or {}).get("series_source") or "")
            floor = parse_date(history_floor(container, OFFICIAL))
            if asset == "港股" or source == "tencent_hk_index":
                level, fresh, _gaps = _hk_level(code, bars, calendar, spec, hkd, same_day=True)
            else:
                level, fresh, _gaps = _research_level(
                    code, source, bars, divs, calendar, usd, spec, floor)
            level = level.reindex(calendar)
            fresh = fresh.reindex(calendar).fillna(False).astype(bool)
            levels[name] = level
            executions = container.get("execution") or []
            track = str(executions[0].get("track") or "") if executions else ""
            traded = execution_code(container) or ""
            board = fill_board_for(track, traded, asset)
            if asset in A_SHARE:
                close = _raw_close(bars.get(code))
            else:
                close = level.where(fresh)
            quotes[name] = FillQuote(close=close, board=board)
        grouped = {name: [] for name in names}
        built = build_candidates(con, containers, calendar, DESIGN_END)
        for name in names:
            grouped[name] = built.get(name) or []
        assets = {name: str(by_id[name].get("asset_class") or "") for name in names}
        prints = prints_for(con, grouped, DESIGN_END)
        fills = stitch_fills(grouped, calendar, prints, assets)
        tradable_levels = {}
        for name in names:
            series = spliced_portfolio(
                con, grouped[name], calendar, DESIGN_END,
                nav_lag=int(spec.nav_lag), usd=usd, stale_limit=int(spec.stale_limit))
            tradable_levels[name] = compound_level(series, pd.DatetimeIndex(calendar))
    finally:
        con.close()
    level_frame = pd.DataFrame(levels, index=calendar)
    require_design_index(level_frame.index, what="同行收盘")
    mask = {}
    traded_quotes = {}
    for name, fill in fills.items():
        path = choose_path(grouped[name], calendar)
        mask[name] = [choice is not None for choice in path]
        traded_quotes[name] = FillQuote(
            close=fill.close, board="none", board_by_day=fill.board, prev_close=fill.prev)
    return {
        "levels": level_frame,
        "calendar": pd.DatetimeIndex(calendar),
        "cash": cash_on(calendar, spec),
        "index_quotes": quotes,
        "tradable_quotes": traded_quotes,
        "carriers": pd.DataFrame(mask, index=calendar),
        "tradable_levels": pd.DataFrame(tradable_levels, index=calendar),
    }


def _summary(peer_id: str, pool: str, net: pd.Series) -> dict:
    from src.report.metrics import cagr, max_drawdown
    return {
        "case": peer_id,
        "pool": pool,
        "kind": "peer",
        "cagr": cagr(net),
        "max_drawdown": max_drawdown(net)["max_drawdown"],
        "exit_module": False,
        "premium_module": False,
        "t1_turn": False,
        "t2_state_weights": False,
        "t3_refill": False,
        "t4_pool": False,
    }


def run_peers(spec: Spec, *, resume: bool = True) -> None:
    panel = None
    for peer_id in ("A1", "A2"):
        for pool in POOLS:
            folder = run_dir(peer_id, pool)
            if resume and (folder / "net.csv").exists():
                read_net(peer_id, pool)
                from src.v4.r5.design import _same_job, ledger_rows
                if not any(_same_job(row, arm=peer_id, pool=pool) for row in ledger_rows()):
                    upsert_ledger(peer_params(peer_id, pool))
                continue
            if panel is None:
                print("装载附表 A 的研究序列", flush=True)
                panel = research_panel(spec)
            peer = load_peer(peer_id, pool)
            carriers = panel["carriers"] if pool == "tradable" else None
            quotes = panel["tradable_quotes"] if pool == "tradable" else panel["index_quotes"]
            levels = panel["tradable_levels"] if pool == "tradable" else panel["levels"]
            result = run_peer(
                peer, panel["calendar"], levels,
                cash=panel["cash"], carriers=carriers, quotes=quotes, calendar_closed=True)
            net = result.net.astype(float)
            require_design_index(net.index, what=f"{peer_id}/{pool}")
            write_run(peer_id, pool, net, _summary(peer_id, pool, net))
            upsert_ledger(peer_params(peer_id, pool))
            print(
                f"peer {peer_id} {pool} {net.index[0].date()}→{net.index[-1].date()} n={len(net)}",
                flush=True,
            )
