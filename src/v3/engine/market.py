"""把登记表和行情库收成引擎用的收益面板。只读，SQL 的日期不超过调用方给出的结束日。"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.data.dividends import GAP_LIMIT
from src.report.fx import cny_from_usd

from .benchmark import _connect, _calendar, _fx, bm_main, cash_returns
from src.v3.data.history import OFFICIAL, history_floor

from .book import RunnerError
from .limits import fill_board_for
from .prices import (
    OVERSEAS_SOURCES,
    USD_CODES,
    align_overseas,
    align_same_day,
    dividend_yields,
    fresh_from_stale,
    lag_asof,
    mask_publish,
    returns_from_level,
    signal_returns,
    total_return_close,
)
from .spec import Spec
from .universe import (
    A_SHARE,
    execution_code,
    fee_for,
    parse_date,
    pool_members,
    research_code,
    signal_kinds,
)


@dataclass
class Market:
    dates: pd.DatetimeIndex
    signal: pd.DataFrame
    pnl: pd.DataFrame
    names: list[str]
    cash_id: str
    sort_ids: dict[str, str]
    fees: dict[str, float]
    liquidity: pd.DataFrame | None
    benchmark: pd.Series | None = None
    cost_multiplier: float = 1.0
    levels: pd.DataFrame | None = None
    history_mode: str = OFFICIAL
    premium_inputs: dict | None = None
    premium_ids: tuple = ()
    premium_panels: dict | None = None
    code_levels: dict | None = None
    code_returns: dict | None = None
    fill_close: dict | None = None
    fill_board: dict | None = None
    asset_classes: dict | None = None
    dividend_yield: pd.DataFrame | None = None
    bm_nav: pd.Series | None = None
    fill_board_by_day: dict | None = None
    fill_prev: dict | None = None


def levels_from_returns(pnl: pd.DataFrame, cash_id: str) -> pd.DataFrame:
    """没有行情库时，用收益倒推一条计价序列，供离场比较。无效收益不把价格打成 0。"""
    columns = {}
    for name in pnl.columns:
        if name == cash_id:
            columns[name] = pd.Series(1.0, index=pnl.index, dtype=float)
            continue
        current = 100.0
        values = []
        for raw in pnl[name].to_numpy(dtype=float):
            if math.isfinite(raw) and raw > -1.0:
                current *= 1.0 + float(raw)
                values.append(current)
            else:
                values.append(float("nan"))
        columns[name] = pd.Series(values, index=pnl.index, dtype=float)
    return pd.DataFrame(columns, index=pnl.index)


def market_from_returns(signal: pd.DataFrame, fees: dict[str, float], *, pnl: pd.DataFrame | None = None,
                        cash_id: str = "cash", sort_ids: dict[str, str] | None = None,
                        liquidity: pd.DataFrame | None = None, benchmark: pd.Series | None = None,
                        cost_multiplier: float = 1.0, levels: pd.DataFrame | None = None) -> Market:
    frame = signal.sort_index()
    mark = frame if pnl is None else pnl.reindex(frame.index)
    names = [name for name in frame.columns if name != cash_id]
    if cash_id not in frame.columns or cash_id not in mark.columns:
        raise RunnerError("收益面板缺现金列")
    if frame[cash_id].isna().any() or mark[cash_id].isna().any():
        raise RunnerError("现金收益有空值")
    return Market(
        dates=pd.DatetimeIndex(frame.index),
        signal=frame,
        pnl=mark,
        names=names,
        cash_id=cash_id,
        sort_ids=sort_ids or {name: name for name in names},
        fees=fees,
        liquidity=liquidity,
        benchmark=None if benchmark is None else benchmark.reindex(frame.index),
        cost_multiplier=cost_multiplier,
        levels=levels_from_returns(mark, cash_id) if levels is None else levels.reindex(frame.index),
    )


def _query(con: sqlite3.Connection, sql: str, codes: list[str], end: str) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame()
    frames = []
    for offset in range(0, len(codes), 400):
        chunk = codes[offset:offset + 400]
        marks = ",".join("?" * len(chunk))
        frames.append(pd.read_sql_query(sql.format(marks=marks), con, params=[end, *chunk]))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _split_bars(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out = {}
    if frame.empty:
        return out
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    for code, block in frame.groupby("code", sort=False):
        block = block.sort_values("date").drop_duplicates("date", keep="last")
        out[str(code)] = block.reset_index(drop=True)
    return out


def _split_nav(frame: pd.DataFrame) -> dict[str, pd.Series]:
    out = {}
    if frame.empty:
        return out
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    for code, block in frame.groupby("code", sort=False):
        series = pd.Series(block["unit_nav"].to_numpy(dtype=float), index=pd.DatetimeIndex(block["date"]))
        series = series[series > 0].sort_index()
        series = series[~series.index.duplicated(keep="last")]
        out[str(code)] = series
    return out


def _listing_day(list_date: pd.Timestamp | None, calendar: pd.DatetimeIndex, lag: int) -> pd.Timestamp | None:
    if list_date is None or lag <= 0:
        return None
    after = calendar[calendar > list_date]
    if len(after) < lag:
        return None
    return pd.Timestamp(after[lag - 1])


def _liquidity(amount: pd.Series, calendar: pd.DatetimeIndex, list_date: pd.Timestamp | None,
               first_bar: pd.Timestamp | None, spec: Spec) -> pd.Series:
    observed = amount.reindex(calendar)
    median = observed.rolling(spec.liquidity_window, min_periods=spec.liquidity_window).median()
    listed = list_date if list_date is not None else first_bar
    opened = _listing_day(listed, calendar, spec.tradable_list_lag)
    liquid = median[median >= spec.min_new_buy_amount]
    first_liquid = pd.Timestamp(liquid.index[0]) if len(liquid) else None
    if opened is None or first_liquid is None:
        return pd.Series(False, index=calendar)
    start = max(opened, first_liquid)
    ok = (calendar >= start) & median.ge(spec.min_new_buy_amount).fillna(False).to_numpy()
    return pd.Series(ok, index=calendar)


def index_pool_fill_close(pool: str, asset_class: str, research: pd.Series, traded: pd.Series) -> pd.Series:
    """U-指数的 A 股容器用研究序列收盘判断涨跌停。其余用成交工具自己的收盘。"""
    if pool == "index" and asset_class in A_SHARE:
        return research
    return traded


def _no_limit_asset(asset_class: str) -> bool:
    text = asset_class or ""
    return text == "港股" or text.startswith("美股")


def _raw_close(block: pd.DataFrame | None) -> pd.Series:
    """原始收盘，只留正的有限价。不前向填充，供涨跌停和停牌判断。"""
    if block is None or block.empty or "close" not in block.columns:
        return pd.Series(dtype=float)
    close = pd.Series(block["close"].to_numpy(dtype=float), index=pd.DatetimeIndex(block["date"]))
    close = close[~close.index.duplicated(keep="last")].sort_index()
    keep = [math.isfinite(value) and value > 0.0 for value in close.to_numpy(dtype=float)]
    return close.where(keep)


def _empty_level(calendar):
    level = pd.Series(float("nan"), index=calendar)
    return level, pd.Series(False, index=calendar), pd.DatetimeIndex([])


def _usd_level(block: pd.DataFrame, fx, calendar, stale_limit: int, publish):
    frame = block.loc[:, ["date", "open", "close"]].copy()
    frame["date"] = pd.to_datetime(frame["date"])
    if publish is not None:
        frame = frame[frame["date"] >= publish]
    if frame.empty:
        return _empty_level(calendar)
    frame["open"] = frame["open"].fillna(frame["close"])
    frame["high"] = frame["close"]
    frame["low"] = frame["close"]
    frame["volume"] = 0.0
    priced = cny_from_usd(frame, fx, calendar)
    if priced.empty:
        return _empty_level(calendar)
    dates = pd.DatetimeIndex(pd.to_datetime(priced["date"]))
    raw = pd.Series(priced["close_cny"].to_numpy(dtype=float), index=dates)
    fresh = fresh_from_stale(pd.Series(priced["stale"].to_numpy(dtype=int), index=dates), stale_limit)
    fresh = fresh & raw.notna()
    level = raw.ffill().reindex(calendar)
    fresh = fresh.reindex(calendar).fillna(False).astype(bool) & level.notna()
    return level, fresh, pd.DatetimeIndex([])


def _research_level(code: str, source: str, bars: dict, divs: dict, calendar, fx, spec, floor):
    """截断日之前的点位先抹掉，再向前填充，避免更早的收盘填进截断日之后。

    `floor` 在官方口径下是基日（可核实时），在发布日口径下是发布日。美股和全球主题还会再取上市日。
    """
    if code in USD_CODES:
        block = bars.get(code)
        if block is None or block.empty:
            return _empty_level(calendar)
        return _usd_level(block, fx, calendar, spec.stale_limit, floor)
    block = bars.get(code)
    if block is None or block.empty:
        return _empty_level(calendar)
    adjusted, gaps = total_return_close(block, divs.get(code, {}), GAP_LIMIT)
    adjusted = mask_publish(adjusted, floor)
    if source in OVERSEAS_SOURCES:
        ohlc = block.loc[:, ["date", "open", "close"]].copy()
        ohlc["date"] = pd.to_datetime(ohlc["date"])
        ohlc["close"] = adjusted.reindex(pd.DatetimeIndex(ohlc["date"])).to_numpy()
        ohlc = ohlc.dropna(subset=["close"])
        if floor is not None:
            ohlc = ohlc[ohlc["date"] >= floor]
        ohlc["open"] = ohlc["open"].fillna(ohlc["close"])
        ohlc["high"] = ohlc["close"]
        ohlc["low"] = ohlc["close"]
        ohlc["volume"] = 0.0
        return align_overseas(ohlc, calendar, spec.stale_limit, gaps)
    level, fresh = align_same_day(adjusted, calendar, spec.stale_limit)
    return level, fresh, gaps


def _price_level(code: str | None, bars: dict, divs: dict, calendar, spec):
    if not code or code not in bars:
        return _empty_level(calendar)
    adjusted, gaps = total_return_close(bars[code], divs.get(code, {}), GAP_LIMIT)
    level, fresh = align_same_day(adjusted, calendar, spec.stale_limit)
    return level, fresh, gaps


def _nav_level(code: str | None, navs: dict, calendar, lag: int, floor):
    """净值用 T−lag 已公布的最新值。没有净值则不可排名；有过净值之后沿用最近一笔。"""
    if not code or code not in navs:
        return _empty_level(calendar)
    events = navs[code]
    if floor is not None:
        events = events[events.index >= floor]
    level = lag_asof(events, calendar, lag)
    fresh = level.notna()
    return level, fresh, pd.DatetimeIndex([])


def load_market(db: Path, containers: list[dict], arm: str, pool: str, end, spec: Spec, *,
                cost_multiplier: float = 1.0, allow_after: bool = False,
                history_mode: str = OFFICIAL) -> Market:
    end_text = str(pd.Timestamp(end).date())
    members = pool_members(containers, arm, pool)
    con = _connect(Path(db))
    try:
        calendar = _calendar(con, end_text)
        codes = set()
        nav_codes = set()
        for container in members:
            if container.get("asset_class") == "现金":
                continue
            research = research_code(container)
            traded = execution_code(container)
            if research:
                codes.add(research)
            if traded:
                codes.add(traded)
                nav_codes.add(traded)
        bar_frame = _query(
            con,
            "SELECT code, date, open, close, amount FROM bars WHERE adj = 'raw' AND date <= ? "
            "AND code IN ({marks})",
            sorted(codes), end_text)
        nav_frame = _query(
            con,
            "SELECT code, date, unit_nav FROM fund_nav WHERE date <= ? AND unit_nav > 0 AND code IN ({marks})",
            sorted(nav_codes), end_text)
        dividends = pd.read_sql_query(
            "SELECT code, ex_date, amount, prev_close FROM cash_dividends WHERE ex_date <= ?",
            con, params=(end_text,))
        fx = _fx(con, end_text)
    finally:
        con.close()
    bars = _split_bars(bar_frame)
    navs = _split_nav(nav_frame)
    divs: dict[str, dict] = {}
    if not dividends.empty:
        dividends["ex_date"] = pd.to_datetime(dividends["ex_date"])
        for code, block in dividends.groupby("code", sort=False):
            divs[str(code)] = dividend_yields(block)
    cash = cash_returns(db, calendar, end_text, spec.cash_annual).reindex(calendar)
    if cash.isna().any():
        raise RunnerError("现金收益没有盖住交易日历")
    from src.v3.data.history import MODES
    from src.v3.premium.rules import subject_to_premium
    if history_mode not in MODES:
        raise RunnerError(f"未知的历史口径 {history_mode}")
    signal = {spec.cash_id: cash}
    pnl = {spec.cash_id: cash}
    levels = {spec.cash_id: pd.Series(1.0, index=calendar, dtype=float)}
    names = []
    fees = {spec.cash_id: spec.fee("现金")}
    sort_ids = {}
    liquid_cols = {}
    premium_inputs: dict = {}
    code_level_frames: dict = {}
    code_return_frames: dict = {}
    premium_ids: list[str] = []
    fill_close: dict[str, pd.Series] = {}
    fill_board: dict[str, str] = {}
    asset_classes: dict[str, str] = {}
    for container in members:
        if container.get("asset_class") == "现金":
            continue
        identity = str(container["id"])
        signal_kind, pnl_kind = signal_kinds(container, arm, pool)
        research = container.get("research") or {}
        floor = parse_date(history_floor(container, history_mode))
        code = research_code(container)
        traded = execution_code(container)
        executions = container.get("execution") or []
        track = str(executions[0].get("track") or "") if executions else ""
        asset = str(container.get("asset_class") or "")
        research_close = _raw_close(bars.get(code or ""))
        traded_close = _raw_close(bars.get(traded or ""))
        fill_close[identity] = index_pool_fill_close(pool, asset, research_close, traded_close)
        fill_board[identity] = fill_board_for(track, traded or "", asset)
        asset_classes[identity] = asset

        def one(kind: str, *, lagged: bool):
            if kind == "research":
                return _research_level(code or "", str(research.get("series_source") or ""),
                                       bars, divs, calendar, fx, spec, floor)
            if kind == "price":
                # 场内价只用 ETF 自己的行情。指数回溯不能虚构上市前成交。
                return _price_level(traded, bars, divs, calendar, spec)
            if kind == "nav":
                return _nav_level(traded or code, navs, calendar, spec.nav_lag if lagged else 0, floor)
            raise RunnerError(kind)

        signal_level, signal_fresh, signal_gaps = one(signal_kind, lagged=True)
        if pool == "index" and _no_limit_asset(asset):
            # 港股、美股没有涨跌停。有没有价看研究序列，不看后来才上市的场内 ETF。
            fill_close[identity] = signal_level.where(signal_level > 0)
        signal[identity] = signal_returns(signal_level, signal_gaps).reindex(calendar)
        rank = signal_fresh.reindex(calendar).fillna(False).astype(bool)
        if pnl_kind == signal_kind and signal_kind != "nav":
            pnl_level = signal_level
            pnl[identity] = returns_from_level(signal_level).reindex(calendar)
            price_fresh = signal_fresh
        else:
            pnl_level, price_fresh, _pnl_gaps = one(pnl_kind, lagged=False)
            pnl[identity] = returns_from_level(pnl_level).reindex(calendar)
        levels[identity] = pnl_level.reindex(calendar)
        if pool == "tradable" and subject_to_premium(container):
            premium_ids.append(identity)
            inputs = {}
            level_cols = {}
            ret_cols = {}
            for ex in container.get("execution") or []:
                traded_code = str(ex.get("code") or "")
                if traded_code in {"", "取不到", "TBD"}:
                    continue
                raw = bars.get(traded_code)
                if raw is not None and not raw.empty:
                    close = pd.Series(raw["close"].to_numpy(dtype=float), index=pd.DatetimeIndex(raw["date"]))
                    close = close[close > 0]
                    close = close[~close.index.duplicated(keep="last")].sort_index()
                else:
                    close = pd.Series(dtype=float)
                inputs[traded_code] = {"close": close, "nav": navs.get(traded_code, pd.Series(dtype=float))}
                code_level, _fresh, _gaps = _price_level(traded_code, bars, divs, calendar, spec)
                level_cols[traded_code] = code_level.reindex(calendar)
                ret_cols[traded_code] = returns_from_level(code_level).reindex(calendar)
            if inputs:
                premium_inputs[identity] = inputs
                code_level_frames[identity] = pd.DataFrame(level_cols, index=calendar)
                code_return_frames[identity] = pd.DataFrame(ret_cols, index=calendar)
        if pool == "tradable":
            rank = rank & price_fresh.reindex(calendar).fillna(False).astype(bool)
        liquid_cols[identity] = rank
        names.append(identity)
        fees[identity] = fee_for(container, spec)
        sort_ids[identity] = identity
        if pool == "tradable":
            block = bars.get(traded or "")
            amount = pd.Series(dtype=float)
            first_bar = None
            if block is not None and not block.empty:
                amount = pd.Series(block["amount"].to_numpy(dtype=float), index=pd.DatetimeIndex(block["date"]))
                amount = amount[~amount.index.duplicated(keep="last")].sort_index()
                first_bar = pd.Timestamp(amount.index[0])
            executions = container.get("execution") or []
            listed = parse_date(executions[0].get("list_date")) if executions else None
            liquid_cols[identity] = liquid_cols[identity] & _liquidity(
                amount, calendar, listed, first_bar, spec).reindex(calendar).fillna(False).astype(bool)
    signal_frame = pd.DataFrame(signal, index=calendar)
    pnl_frame = pd.DataFrame(pnl, index=calendar)
    liquidity = pd.DataFrame(liquid_cols, index=calendar) if liquid_cols else None
    benchmark = bm_main(db, end_text, allow_after=allow_after) if arm == "B" else None
    if benchmark is not None:
        benchmark = benchmark.reindex(calendar)
    return Market(
        dates=calendar,
        signal=signal_frame,
        pnl=pnl_frame,
        names=names,
        cash_id=spec.cash_id,
        sort_ids=sort_ids,
        fees=fees,
        liquidity=liquidity,
        benchmark=benchmark,
        cost_multiplier=cost_multiplier,
        levels=pd.DataFrame(levels, index=calendar),
        history_mode=history_mode,
        premium_inputs=premium_inputs or None,
        premium_ids=tuple(premium_ids),
        code_levels=code_level_frames or None,
        code_returns=code_return_frames or None,
        fill_close=fill_close,
        fill_board=fill_board,
        asset_classes=asset_classes,
    )
