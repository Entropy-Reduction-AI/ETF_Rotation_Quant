"""D37 S1：发布日之后才接指数，场内载体从上市日起按 5 日成交额过滤。

取不到正式发布日或登记来源的容器不拼接，研究序列保持冻结。
不改冻结文件。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pandas as pd

from src.v3.data.universe import containers as load_containers

from .universe import S1_BOND, S1_EXTRA

MIN_AMOUNT = 2_000_000.0
MEDIAN_DAYS = 5
MISSING = "取不到"


@dataclass(frozen=True)
class ListedFund:
    code: str
    list_date: pd.Timestamp


def _date(text: str) -> pd.Timestamp | None:
    raw = str(text or "").strip()
    if raw in {"", MISSING, "TBD"}:
        return None
    stamp = pd.Timestamp(raw)
    if pd.isna(stamp):
        return None
    return pd.Timestamp(stamp).normalize()


def listed_funds(container: dict) -> list[ListedFund]:
    """有交易所上市日的执行代码。没有上市日的场外基金不进 S1 载体。"""
    found = []
    for row in container.get("execution") or []:
        code = str(row.get("code") or "").strip()
        opened = _date(str(row.get("list_date") or ""))
        if not code or code in {MISSING, "TBD"} or opened is None:
            continue
        found.append(ListedFund(code, opened))
    return found


def first_list_date(container: dict) -> pd.Timestamp | None:
    funds = listed_funds(container)
    if not funds:
        return None
    return min(fund.list_date for fund in funds)


def rolling_amount_ok(amounts: pd.Series, list_date: pd.Timestamp, calendar: pd.DatetimeIndex) -> pd.Series:
    """上市日起可买。近 5 个自身交易日成交额中位数 < 200 万才排除；不满 5 天用已有天数。"""
    days = pd.DatetimeIndex(pd.to_datetime(calendar)).normalize()
    own = pd.Series(amounts, dtype=float).dropna().sort_index()
    own.index = pd.DatetimeIndex(pd.to_datetime(own.index)).normalize()
    own = own[own.index >= pd.Timestamp(list_date)]
    own = own[~own.index.duplicated(keep="last")]
    if own.empty:
        return pd.Series(False, index=days)
    median = own.rolling(MEDIAN_DAYS, min_periods=1).median()
    span = days.union(median.index).sort_values()
    filled = median.reindex(span).ffill().reindex(days)
    ok = filled.ge(MIN_AMOUNT).fillna(False)
    return ok & pd.Series(days >= pd.Timestamp(list_date), index=days)


def buyable_frame(calendar: pd.DatetimeIndex, funds: dict[str, list[tuple[ListedFund, pd.Series]]]) -> pd.DataFrame:
    """容器当天只要有一只场内基金过线就可买。"""
    days = pd.DatetimeIndex(pd.to_datetime(calendar)).normalize()
    columns = {}
    for name, rows in funds.items():
        if not rows:
            columns[name] = pd.Series(False, index=days)
            continue
        flag = pd.Series(False, index=days)
        for fund, amounts in rows:
            flag = flag | rolling_amount_ok(amounts, fund.list_date, days)
        columns[name] = flag
    if not columns:
        return pd.DataFrame(index=days)
    return pd.DataFrame(columns, index=days)


def splice_before_list(signal: pd.Series, index_returns: pd.Series, publish: pd.Timestamp,
                       list_date: pd.Timestamp | None) -> pd.Series:
    """只填上市日之前、正式发布日之后、原来是空的收益。已有数不覆盖。"""
    out = pd.Series(signal, dtype=float).copy()
    out.index = pd.DatetimeIndex(pd.to_datetime(out.index)).normalize()
    extra = pd.Series(index_returns, dtype=float).dropna().sort_index()
    extra.index = pd.DatetimeIndex(pd.to_datetime(extra.index)).normalize()
    extra = extra[extra.index >= pd.Timestamp(publish)]
    if list_date is not None:
        extra = extra[extra.index < pd.Timestamp(list_date)]
    aligned = extra.reindex(out.index)
    hole = out.isna() & aligned.notna()
    return out.where(~hole, aligned)


def returns_from_close(closes: pd.Series) -> pd.Series:
    level = _positive_level(closes)
    return level.pct_change()


def _positive_level(closes: pd.Series) -> pd.Series:
    level = pd.Series(closes, dtype=float).dropna().sort_index()
    level.index = pd.DatetimeIndex(pd.to_datetime(level.index)).normalize()
    level = level[level > 0]
    return level[~level.index.duplicated(keep="last")]


def series_truncated_at_listing(series_first: str, first_list: str, slack_days: int = 120) -> bool:
    """研究序列没有实质早于首只场内基金。没有序列、但有上市日，也算被上市日截断。

    基金净值常常比交易所上市日早几天到几十天。早于上市日不到 slack_days 的，
    仍当作从这只基金附近才开始，不是跟踪指数自己的长历史。
    """
    listed = str(first_list or "")[:10]
    if len(listed) < 10:
        return False
    started = str(series_first or "")[:10]
    if len(started) < 10:
        return True
    floor = (pd.Timestamp(listed) - pd.Timedelta(days=slack_days)).date().isoformat()
    return started >= floor


def calendar_index_returns(closes: pd.Series, calendar: pd.DatetimeIndex, fx: pd.Series | None = None,
                           stale_limit: int = 5) -> pd.Series:
    """价格指数对齐到上交所日历后再算收益。美元、港币点位先乘已登记汇率。

    走海外对齐：决策日只用严格早于当日的收盘，避免把美股收盘写进同一天的 A 股决策。
    """
    from src.v3.engine.prices import align_overseas

    level = _positive_level(closes)
    days = pd.DatetimeIndex(pd.to_datetime(calendar)).normalize()
    if fx is not None:
        rate = _positive_level(fx)
        rate = rate.reindex(level.index.union(rate.index)).sort_index().ffill().reindex(level.index)
        level = (level * rate).dropna()
    if level.empty:
        return pd.Series(dtype=float, index=days)
    frame = pd.DataFrame({"date": level.index, "close": level.to_numpy(dtype=float)})
    aligned, fresh, _gaps = align_overseas(frame, days, stale_limit)
    aligned = aligned.where(fresh.reindex(days).fillna(False))
    return aligned.pct_change()


def load_amounts(con: sqlite3.Connection, codes: list[str]) -> dict[str, pd.Series]:
    if not codes:
        return {}
    marks = ",".join("?" * len(codes))
    frame = pd.read_sql_query(
        f"SELECT code, date, amount FROM bars WHERE adj = 'raw' AND amount IS NOT NULL AND code IN ({marks})",
        con, params=tuple(codes),
    )
    out: dict[str, pd.Series] = {}
    if frame.empty:
        return out
    frame["date"] = pd.to_datetime(frame["date"])
    for code, block in frame.groupby("code", sort=False):
        series = pd.Series(block["amount"].to_numpy(dtype=float), index=pd.DatetimeIndex(block["date"]))
        series = series.sort_index()
        series = series[~series.index.duplicated(keep="last")]
        out[str(code)] = series
    return out


def load_closes(con: sqlite3.Connection, code: str) -> pd.Series:
    frame = pd.read_sql_query(
        "SELECT date, close FROM bars WHERE code = ? AND adj = 'raw' AND close > 0 ORDER BY date",
        con, params=(code,),
    )
    if frame.empty:
        return pd.Series(dtype=float)
    series = pd.Series(frame["close"].to_numpy(dtype=float), index=pd.DatetimeIndex(pd.to_datetime(frame["date"])))
    return series[~series.index.duplicated(keep="last")].sort_index()


def registry_rows(path) -> list[dict]:
    file = path
    if not file.is_file():
        return []
    frame = pd.read_csv(file, dtype=str).fillna("")
    return frame.to_dict(orient="records")


def s1_markets_from_classes(class_of: dict[str, str]) -> list[str]:
    return sorted(name for name, kind in class_of.items() if kind in S1_EXTRA and name != S1_BOND)


def apply_splices(signal: pd.DataFrame, registry: list[dict], closes_of, containers: dict[str, dict],
                  fx_of=None) -> tuple[pd.DataFrame, list[dict]]:
    """按登记表拼接。没有发布日或没有行情的保持原列，并记入缺口。

    currency 为 USD / HKD 时用已登记汇率换到人民币，再对齐到信号日历。
    LOCAL 只对齐、不换汇。空着或 CNY 的沿用点位自身的日期。
    """
    out = signal.copy()
    by_id = {str(row.get("container_id") or ""): row for row in registry}
    notes = []
    for name in out.columns:
        row = by_id.get(name)
        if row is None or str(row.get("status") or "") != "spliced":
            continue
        publish = _date(str(row.get("publish_date") or ""))
        code = str(row.get("bars_code") or "").strip()
        if publish is None or not code:
            notes.append({"container_id": name, "status": "frozen", "reason": "登记了拼接但没有发布日或代码"})
            continue
        closes = closes_of(code)
        if closes.empty:
            notes.append({"container_id": name, "status": "frozen", "reason": f"库里没有 {code}"})
            continue
        container = containers.get(name) or {}
        currency = str(row.get("currency") or "CNY").upper()
        if currency in {"USD", "HKD", "LOCAL"}:
            fx = None
            if currency == "USD":
                fx = fx_of("USDCNY") if fx_of is not None else None
            elif currency == "HKD":
                fx = fx_of("HKDCNY") if fx_of is not None else None
            extra = calendar_index_returns(closes, out.index, fx)
        else:
            extra = returns_from_close(closes)
        out[name] = splice_before_list(out[name], extra, publish, first_list_date(container))
        notes.append({
            "container_id": name, "status": "spliced", "publish_date": publish.date().isoformat(),
            "bars_code": code, "currency": currency, "reason": str(row.get("note") or row.get("reason") or ""),
        })
    return out, notes


def missing_report(class_of: dict[str, str], present: set[str], registry: list[dict], splice_notes: list[dict]) -> pd.DataFrame:
    """S1 新市场里，源或发布日没拿到的保持冻结规则。"""
    by_id = {str(row.get("container_id") or ""): row for row in registry}
    spliced = {row["container_id"] for row in splice_notes if row.get("status") == "spliced"}
    rows = []
    for name in s1_markets_from_classes(class_of):
        if name in spliced:
            continue
        if name not in present:
            rows.append({"container_id": name, "status": "frozen", "reason": "不在冻结研究池，没有可打分的序列"})
            continue
        row = by_id.get(name)
        if row is None:
            rows.append({"container_id": name, "status": "frozen", "reason": "没有登记到来源或指数正式发布日"})
            continue
        reason = str(row.get("reason") or row.get("note") or "取不到正式发布日或登记来源")
        rows.append({"container_id": name, "status": "frozen", "reason": reason})
    return pd.DataFrame(rows, columns=["container_id", "status", "reason"])


def container_map() -> dict[str, dict]:
    return {str(row.get("id") or ""): row for row in load_containers()}
