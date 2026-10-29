"""把 v4 开关接到已经装好的行情上。开关全关时不要调用。

不在这里跑组合。新列只是研究序列、费率和可交易掩码。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from src.v3.data.history import history_floor
from src.v3.engine.costs import leg_fee
from src.v3.engine.market import _split_bars, _usd_level, levels_from_returns
from src.v3.engine.prices import USD_CODES, returns_from_level, signal_returns
from src.v3.engine.universe import parse_date, research_code
from src.v4.engine.carriers import (
    build_candidates,
    choose_path,
    compound_level,
    has_investable_index,
    prints_for,
    spliced_portfolio,
    spliced_research,
    sse_calendar,
    stitch_fills,
)
from src.v4.engine.pool import HK_SECTORS, US_SECTORS, added_signals, bm_nav_level, load_mid
from src.v4.engine.pool import _hk_level


def _connect(path: Path) -> sqlite3.Connection:
    uri = f"{Path(path).resolve().as_uri()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _levels_for(signal: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    frame = pd.DataFrame({signal.name: signal, "cash": 0.0}, index=index)
    return levels_from_returns(frame, "cash")[signal.name]


def _reprice(market, con, containers: list[dict], spec, end: str) -> None:
    calendar = market.dates
    usd = load_mid(con, "USDCNY", end, filled=True)
    hkd = load_mid(con, "HKDCNY", end, filled=True)
    wanted = []
    for container in containers:
        identity = str(container.get("id") or "")
        if identity not in market.signal.columns:
            continue
        code = research_code(container) or ""
        source = str((container.get("research") or {}).get("series_source") or "")
        if code in USD_CODES or source == "tencent_hk_index":
            wanted.append(code)
    bars = {}
    if wanted:
        marks = ",".join("?" * len(set(wanted)))
        frame = pd.read_sql_query(
            "SELECT code, date, open, close FROM bars WHERE adj = 'raw' AND date <= ? "
            f"AND code IN ({marks})",
            con, params=[end, *sorted(set(wanted))])
        bars = _split_bars(frame)
    mode = getattr(market, "history_mode", "official")
    for container in containers:
        identity = str(container.get("id") or "")
        if identity not in market.signal.columns:
            continue
        code = research_code(container) or ""
        source = str((container.get("research") or {}).get("series_source") or "")
        floor = parse_date(history_floor(container, mode))
        if code in USD_CODES:
            block = bars.get(code)
            if block is None or block.empty:
                continue
            level, fresh, gaps = _usd_level(block, usd, calendar, spec.stale_limit, floor)
        elif source == "tencent_hk_index":
            # B0 / 旧池恒生：D 当天收盘 × D 当天或之前的港币中间价（D18-1）。
            level, fresh, gaps = _hk_level(code, bars, calendar, spec, hkd, same_day=True)
        else:
            continue
        asset = str(container.get("asset_class") or "")
        if market.fill_close is not None and (asset == "港股" or asset.startswith("美股")):
            market.fill_close[identity] = level.where(level > 0)
        market.signal[identity] = signal_returns(level, gaps).reindex(calendar)
        market.pnl[identity] = returns_from_level(level).reindex(calendar)
        series = market.signal[identity]
        series.name = identity
        market.levels[identity] = _levels_for(series, calendar)
        if market.liquidity is not None and identity in market.liquidity.columns:
            market.liquidity[identity] = (
                market.liquidity[identity].astype(bool)
                & fresh.reindex(calendar).fillna(False).astype(bool).to_numpy()
            )


def _add_pool(market, con, spec, end: str) -> None:
    signal, fresh = added_signals(
        con, market.dates, spec, end, adjusted=True, hk_fx=True, usd_filled=True)
    if market.asset_classes is None:
        market.asset_classes = {}
    for name in signal.columns:
        if name in market.signal.columns:
            continue
        column = signal[name]
        column.name = name
        market.signal[name] = column
        market.pnl[name] = column
        market.levels[name] = _levels_for(column, market.dates)
        market.names.append(name)
        kind = "美股行业" if name.startswith("us-") else "港股"
        carrier = "spdr" if name.startswith("us-") else ""
        market.fees[name] = leg_fee(kind, spec, carrier=carrier)
        market.sort_ids[name] = name
        market.asset_classes[name] = kind
        if market.fill_board is not None:
            market.fill_board[name] = "none"
        if market.fill_close is not None:
            market.fill_close[name] = pd.Series(dtype=float)
        if market.liquidity is not None:
            market.liquidity[name] = fresh[name]


def _grouped(con, containers, end: str, switches):
    calendar = sse_calendar(con, end)
    spdr = US_SECTORS if switches.t4_pool else ()
    grouped = build_candidates(con, containers, calendar, end, us_spdr=spdr)
    if not switches.allow_substitute:
        grouped = {
            key: [row for row in rows if row.tier != 3]
            for key, rows in grouped.items()
        }
    return grouped


def _splice_indexless(market, con, containers, spec, end: str, grouped) -> None:
    """没有可投资指数的容器，研究序列改成关联基金的日收益拼接。有指数的不动。

    收益比载体选定滞后一天：D 日记 D−1 的载体，新载体从 D+1 起进入这条序列。
    """
    for container in containers:
        identity = str(container.get("id") or "")
        if not identity or identity not in market.signal.columns:
            continue
        if has_investable_index(container):
            continue
        rows = grouped.get(identity) or []
        if not rows:
            continue
        series = spliced_research(con, rows, market.dates, end, nav_lag=int(spec.nav_lag))
        series = series.reindex(market.dates)
        if not bool(series.notna().any()):
            continue
        series.name = identity
        market.signal[identity] = series
        market.pnl[identity] = series
        market.levels[identity] = _levels_for(series, market.dates)
        if market.liquidity is not None and identity in market.liquidity.columns:
            market.liquidity[identity] = series.notna().fillna(False).to_numpy()


def _gate(market, con, containers, end: str, switches, grouped=None) -> None:
    if grouped is None:
        grouped = _grouped(con, containers, end, switches)
    hk_ids = {name for name, _code in HK_SECTORS}
    assets = {str(row.get("id") or ""): str(row.get("asset_class") or "") for row in containers}
    if market.fill_close is None:
        market.fill_close = {}
    if getattr(market, "fill_prev", None) is None:
        market.fill_prev = {}
    if getattr(market, "fill_board_by_day", None) is None:
        market.fill_board_by_day = {}
    for name, fill in stitch_fills(grouped, market.dates, prints_for(con, grouped, end), assets).items():
        market.fill_close[name] = fill.close
        market.fill_prev[name] = fill.prev
        market.fill_board_by_day[name] = fill.board
    for name in list(market.names):
        rows = grouped.get(name, [])
        path = choose_path(rows, market.dates)
        flags = []
        for choice, _day in zip(path, market.dates):
            if name in hk_ids:
                flags.append(False)
                continue
            flags.append(choice is not None)
        mask = pd.Series(flags, index=market.dates, dtype=bool)
        if market.liquidity is not None and name in market.liquidity.columns:
            market.liquidity[name] = market.liquidity[name].astype(bool) & mask.to_numpy()


def _replace_carrier_pnl(market, con, spec, end: str, grouped) -> None:
    """U-可交易的计价收益改成选定载体自己的日收益。排名用的信号不动。"""
    usd = load_mid(con, "USDCNY", end, filled=True)
    calendar = market.dates
    for name in list(market.names):
        if name == market.cash_id:
            continue
        rows = grouped.get(name) or []
        series = spliced_portfolio(
            con, rows, calendar, end,
            nav_lag=int(spec.nav_lag), usd=usd, stale_limit=int(spec.stale_limit))
        series = series.reindex(calendar)
        series.name = name
        market.pnl[name] = series
        if name in market.levels.columns:
            market.levels[name] = compound_level(series, calendar)


def apply_tradable_execution(market, switches, *, db, containers: list[dict], spec):
    """在已经装好的 U-指数研究序列上，改计价收益和可交易掩码。不改信号。"""
    end = str(pd.Timestamp(market.dates.max()).date())
    con = _connect(Path(db))
    try:
        grouped = _grouped(con, containers, end, switches)
        _gate(market, con, containers, end, switches, grouped)
        _replace_carrier_pnl(market, con, spec, end, grouped)
    finally:
        con.close()
    return market


def apply_market(market, switches, *, db, containers: list[dict], spec, pool: str = "index"):
    """按打开的开关改行情。全关时原样返回。"""
    if switches is None:
        return market
    if not (switches.t4_pool or switches.fx_v4 or switches.carriers or switches.t2_state_weights):
        return market
    end = str(pd.Timestamp(market.dates.max()).date())
    con = _connect(Path(db))
    try:
        if switches.t2_state_weights and getattr(market, "bm_nav", None) is None:
            market.bm_nav = bm_nav_level(con, market.dates, end)
        if switches.fx_v4:
            _reprice(market, con, containers, spec, end)
        if switches.t4_pool:
            _add_pool(market, con, spec, end)
        if switches.carriers:
            grouped = _grouped(con, containers, end, switches)
            _splice_indexless(market, con, containers, spec, end, grouped)
            if pool == "tradable":
                _gate(market, con, containers, end, switches, grouped)
                _replace_carrier_pnl(market, con, spec, end, grouped)
    finally:
        con.close()
    return market
