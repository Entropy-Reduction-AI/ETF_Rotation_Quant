"""Reviewer market panel for U-指数 / arm A (no src.v3.engine)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.report.fx import cny_from_usd

from operations.reviews.diag.v3.l2.cash import cash_returns
from operations.reviews.diag.v3.l2.prices import (
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
from operations.reviews.diag.v3.l2.spec_loader import Spec
from operations.reviews.diag.v3.l2.universe_rules import (
    execution_code,
    fee_for,
    parse_date,
    pool_members,
    research_code,
    signal_kinds,
)

ROOT = Path(__file__).resolve().parents[5]
GAP_LIMIT = 0.40


class RunnerError(RuntimeError):
    pass


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
    cost_multiplier: float = 1.0


def _connect(path: Path) -> sqlite3.Connection:
    if not Path(path).exists() or Path(path).stat().st_size < 1000:
        raise RunnerError(f"行情库不可读：{path}")
    uri = f"{Path(path).resolve().as_uri()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _calendar(con: sqlite3.Connection, end: str) -> pd.DatetimeIndex:
    frame = pd.read_sql_query(
        "SELECT date FROM calendar WHERE date <= ? ORDER BY date", con, params=(end,))
    return pd.DatetimeIndex(pd.to_datetime(frame["date"]))


def _fx(con: sqlite3.Connection, end: str) -> pd.Series:
    frame = pd.read_sql_query(
        "SELECT date, close, source FROM bars WHERE code = 'USDCNY' AND adj = 'raw' AND close > 0 "
        "AND date <= ? ORDER BY date",
        con, params=(end,))
    if frame.empty:
        raise RunnerError("bars 里没有 USDCNY")
    series = pd.Series(frame["close"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
    return series[~series.index.duplicated(keep="last")].sort_index()


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


def _research_level(code: str, source: str, bars: dict, divs: dict, calendar, fx, spec, publish):
    if code in USD_CODES:
        block = bars.get(code)
        if block is None or block.empty:
            return _empty_level(calendar)
        return _usd_level(block, fx, calendar, spec.stale_limit, publish)
    block = bars.get(code)
    if block is None or block.empty:
        return _empty_level(calendar)
    adjusted, gaps = total_return_close(block, divs.get(code, {}), GAP_LIMIT)
    adjusted = mask_publish(adjusted, publish)
    if source in OVERSEAS_SOURCES:
        ohlc = block.loc[:, ["date", "open", "close"]].copy()
        ohlc["date"] = pd.to_datetime(ohlc["date"])
        ohlc["close"] = adjusted.reindex(pd.DatetimeIndex(ohlc["date"])).to_numpy()
        ohlc = ohlc.dropna(subset=["close"])
        if publish is not None:
            ohlc = ohlc[ohlc["date"] >= publish]
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


def _nav_level(code: str | None, navs: dict, calendar, lag: int, publish):
    if not code or code not in navs:
        return _empty_level(calendar)
    events = navs[code]
    if publish is not None:
        events = events[events.index >= publish]
    level = lag_asof(events, calendar, lag)
    fresh = level.notna()
    return level, fresh, pd.DatetimeIndex([])


def load_containers_from_toml(path: Path) -> list[dict]:
    import tomllib

    with path.open("rb") as handle:
        raw = tomllib.load(handle)
    return list(raw.get("container", []))


def load_market_index_a(
    db: Path,
    containers: list[dict],
    end,
    spec: Spec,
    *,
    cost_multiplier: float = 1.0,
) -> Market:
    end_text = str(pd.Timestamp(end).date())
    members = pool_members(containers, "A", "index")
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
    signal = {spec.cash_id: cash}
    pnl = {spec.cash_id: cash}
    names = []
    fees = {spec.cash_id: spec.fee("现金")}
    sort_ids = {}
    liquid_cols = {}
    arm, pool = "A", "index"
    for container in members:
        if container.get("asset_class") == "现金":
            continue
        identity = str(container["id"])
        signal_kind, pnl_kind = signal_kinds(container, arm, pool)
        research = container.get("research") or {}
        publish = parse_date(research.get("publish_date"))
        code = research_code(container)
        traded = execution_code(container)

        def one(kind: str, *, lagged: bool):
            if kind == "research":
                return _research_level(
                    code or "", str(research.get("series_source") or ""),
                    bars, divs, calendar, fx, spec, publish)
            if kind == "price":
                return _price_level(traded, bars, divs, calendar, spec)
            if kind == "nav":
                return _nav_level(traded or code, navs, calendar, spec.nav_lag if lagged else 0, publish)
            raise RunnerError(kind)

        signal_level, signal_fresh, signal_gaps = one(signal_kind, lagged=True)
        signal[identity] = signal_returns(signal_level, signal_gaps).reindex(calendar)
        rank = signal_fresh.reindex(calendar).fillna(False).astype(bool)
        if pnl_kind == signal_kind and signal_kind != "nav":
            pnl[identity] = returns_from_level(signal_level).reindex(calendar)
        else:
            pnl_level, _price_fresh, _pnl_gaps = one(pnl_kind, lagged=False)
            pnl[identity] = returns_from_level(pnl_level).reindex(calendar)
        liquid_cols[identity] = rank
        names.append(identity)
        fees[identity] = fee_for(container, spec)
        sort_ids[identity] = identity
    signal_frame = pd.DataFrame(signal, index=calendar)
    pnl_frame = pd.DataFrame(pnl, index=calendar)
    liquidity = pd.DataFrame(liquid_cols, index=calendar) if liquid_cols else None
    return Market(
        dates=calendar,
        signal=signal_frame,
        pnl=pnl_frame,
        names=names,
        cash_id=spec.cash_id,
        sort_ids=sort_ids,
        fees=fees,
        liquidity=liquidity,
        cost_multiplier=cost_multiplier,
    )
