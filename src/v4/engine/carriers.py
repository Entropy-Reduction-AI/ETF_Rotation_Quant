"""U-可交易载体。开关关闭时不调用。

顺序是预注册草案 §3.2 的字面，和载体表同一读法：

1. 跟踪同一指数的场内 ETF，有后复权，并且满足 v3 §3.3 的可交易首日和当天流动性。
   可交易首日 = max(上市日后第 60 个上交所交易日, 首次「近 20 个自身交易日成交额中位数 ≥ 3000 万元」)。
   上市日取原始 K 线第一根正收盘，第 60 个交易日不含上市日当天。
   流动性是当天的条件：这一天对应的近 20 个自身交易日成交额中位数仍然 ≥ 3000 万元。
2. 跟踪同一指数的场外纯指数基金。增强型不用。草案没有把「联接」排除出这一档，
   非增强且跟踪同一指数的联接放在第 2 档。
3. 已经决定的相近替身，只有 161211 和 510880。不把拒绝入库的指数升成替身。
4. 美股行业才用美国的 SPDR，后复权。

同一档有多只场外基金时，取成立日最早的，再取净值起点最早的，再取代码最小的。
场内同一档按登记表里的先后。都没有的那天，该容器不进 U-可交易排名。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pandas as pd

from src.v4.data.r1b import EXACT_INDEX

# 14 个 A 股容器之外，执行层跟踪标的就是容器自己的指数。
OWN_TRACK = {
    "chinext": frozenset({"创业板指数(价格)", "创业板指数"}),
    "star50": frozenset({"上证科创板50成份指数"}),
}

# D15-2、D15-3。载体表只承认这两只，不扩大。
SUBSTITUTES = (
    {"code": "161211", "container": "allshare-financials-re", "vehicle": "otc", "tracks": "沪深300金融地产指数"},
    {"code": "510880", "container": "csi-dividend", "vehicle": "etf", "tracks": "上证红利指数"},
)

MIN_AMOUNT = 30_000_000.0
LIQUID_WINDOW = 20
LIST_LAG = 60
STALE_DAYS = 5
# 和载体表一样：H00300 的 2005-01-01 是周六，交易日从 2005-01-04 起。
CALENDAR_FROM = "2005-01-04"


@dataclass(frozen=True)
class CarrierChoice:
    vehicle: str
    code: str

    @property
    def label(self) -> str:
        return f"{self.vehicle}:{self.code}"


def index_names(container_id: str) -> frozenset[str]:
    names = {text for text, owner in EXACT_INDEX.items() if owner == container_id}
    names.update(OWN_TRACK.get(container_id, ()))
    return frozenset(names)


def sse_calendar(con: sqlite3.Connection, end: str) -> pd.DatetimeIndex:
    """载体表用的交易日：H00300 正收盘，并且是周一至周五。"""
    frame = pd.read_sql_query(
        "SELECT date FROM bars WHERE code = 'H00300' AND adj = 'raw' AND close > 0 "
        "AND date >= ? AND date <= ? ORDER BY date",
        con, params=(CALENDAR_FROM, end))
    if frame.empty:
        return pd.DatetimeIndex([])
    days = pd.DatetimeIndex(pd.to_datetime(frame["date"]))
    return days[days.day_of_week < 5]


def _positive_dates(con: sqlite3.Connection, sql: str, code: str, end: str) -> pd.DatetimeIndex:
    frame = pd.read_sql_query(sql, con, params=(code, end))
    if frame.empty:
        return pd.DatetimeIndex([])
    return pd.DatetimeIndex(pd.to_datetime(frame["date"]))


def hfq_dates(con: sqlite3.Connection, code: str, end: str) -> pd.DatetimeIndex:
    return _positive_dates(
        con,
        "SELECT date FROM v4_series WHERE code = ? AND kind = 'backward' AND close > 0 AND date <= ? ORDER BY date",
        code, end)


def raw_dates(con: sqlite3.Connection, code: str, end: str) -> pd.DatetimeIndex:
    return _positive_dates(
        con,
        "SELECT date FROM bars WHERE code = ? AND adj = 'raw' AND close > 0 AND date <= ? ORDER BY date",
        code, end)


def amount_median(con: sqlite3.Connection, code: str, end: str) -> pd.Series:
    """近 20 个自身交易日的成交额中位数。空值不进窗口，也不当成 0。"""
    frame = pd.read_sql_query(
        "SELECT date, amount FROM bars WHERE code = ? AND adj = 'raw' AND date <= ? ORDER BY date",
        con, params=(code, end))
    if frame.empty:
        return pd.Series(dtype=float)
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.dropna(subset=["amount"]).drop_duplicates("date", keep="last")
    series = pd.Series(frame["amount"].to_numpy(dtype=float), index=pd.DatetimeIndex(frame["date"]))
    series = series.sort_index()
    return series.rolling(LIQUID_WINDOW, min_periods=LIQUID_WINDOW).median()


def nth_session_after(list_day: pd.Timestamp, calendar: pd.DatetimeIndex, lag: int = LIST_LAG) -> pd.Timestamp | None:
    after = calendar[calendar > pd.Timestamp(list_day)]
    if len(after) < lag:
        return None
    return pd.Timestamp(after[lag - 1])


def tradable_start(list_day: pd.Timestamp | None, calendar: pd.DatetimeIndex, median: pd.Series) -> pd.Timestamp | None:
    if list_day is None or median.empty:
        return None
    opened = nth_session_after(list_day, calendar)
    hit = median[median >= MIN_AMOUNT]
    if opened is None or hit.empty:
        return None
    return max(opened, pd.Timestamp(hit.index[0]))


def _session_pos(calendar: pd.DatetimeIndex, day: pd.Timestamp) -> int:
    return int(calendar.searchsorted(pd.Timestamp(day), side="right")) - 1


def _within_stale(calendar: pd.DatetimeIndex, day: pd.Timestamp, last_print: pd.Timestamp) -> bool:
    """最近 5 个上交所交易日（含当天）里有自身正收盘。"""
    pos = _session_pos(calendar, day)
    if pos < 0:
        return False
    start = calendar[max(0, pos - (STALE_DAYS - 1))]
    return pd.Timestamp(last_print) >= pd.Timestamp(start)


def etf_available(calendar: pd.DatetimeIndex, day: pd.Timestamp, *, hfq: pd.DatetimeIndex,
                  prints: pd.DatetimeIndex, median: pd.Series, opened: pd.Timestamp | None) -> bool:
    """后复权已开始，5 日内有正收盘，已过可交易首日，并且当天的 20 日成交额中位数仍 ≥ 3000 万。"""
    stamp = pd.Timestamp(day)
    if opened is None or stamp < opened:
        return False
    if len(hfq) == 0 or hfq[hfq <= stamp].empty:
        return False
    if len(prints) == 0:
        return False
    last_print = prints[prints <= stamp]
    if last_print.empty or not _within_stale(calendar, stamp, pd.Timestamp(last_print[-1])):
        return False
    if median.empty:
        return False
    known = median.dropna()
    known = known[known.index <= stamp]
    if known.empty or not _within_stale(calendar, stamp, pd.Timestamp(known.index[-1])):
        return False
    return float(known.iloc[-1]) >= MIN_AMOUNT


def otc_nav_start(con: sqlite3.Connection, code: str, end: str) -> pd.Timestamp | None:
    row = con.execute(
        "SELECT MIN(date) FROM v4_series WHERE code = ? AND kind = 'otc_nav' AND close > 0 AND date <= ?",
        (code, end)).fetchone()
    if row is None or row[0] is None:
        return None
    return pd.Timestamp(row[0])


def _listings(con: sqlite3.Connection) -> list[dict]:
    rows = con.execute(
        "SELECT code, name, maps_to, tracked_index, inception, enhanced FROM v4_listing ORDER BY code"
    ).fetchall()
    return [dict(row) if hasattr(row, "keys") else {
        "code": row[0], "name": row[1], "maps_to": row[2], "tracked_index": row[3],
        "inception": row[4], "enhanced": row[5],
    } for row in rows]


def _execution_etfs(containers: list[dict]) -> dict[str, list[dict]]:
    """arm=main 的执行层里，跟踪标的全称和容器指数一致的场内 ETF。510880 对不上，不会进这里。"""
    out: dict[str, list[dict]] = {}
    for container in containers:
        if container.get("arm") not in {None, "main"}:
            continue
        if container.get("asset_class") == "现金":
            continue
        identity = str(container.get("id") or "")
        names = index_names(identity)
        if not names:
            continue
        order = 0
        for row in container.get("execution") or []:
            code = str(row.get("code") or "")
            track = str(row.get("track") or "")
            if code in {"", "取不到", "TBD"} or track not in names:
                continue
            out.setdefault(identity, []).append({
                "code": code,
                "name": str(row.get("name") or ""),
                "order": order,
                "tracks": track,
            })
            order += 1
    return out


@dataclass(frozen=True)
class _Candidate:
    container: str
    code: str
    vehicle: str
    tier: int
    inception: str
    nav_start: str
    order: int
    available: pd.Series


def _mask(calendar: pd.DatetimeIndex, predicate) -> pd.Series:
    flags = [bool(predicate(pd.Timestamp(day))) for day in calendar]
    return pd.Series(flags, index=calendar, dtype=bool)


def build_candidates(con: sqlite3.Connection, containers: list[dict], calendar: pd.DatetimeIndex,
                     end: str, *, us_spdr: tuple[tuple[str, str], ...] = ()) -> dict[str, list[_Candidate]]:
    """每个容器一串按档位排好的候选。`available` 是上交所交易日上的布尔序列。"""
    grouped: dict[str, list[_Candidate]] = {}
    etfs = _execution_etfs(containers)
    for identity, rows in etfs.items():
        for row in rows:
            grouped.setdefault(identity, []).append(_etf_candidate(
                con, identity, row["code"], row["order"], calendar, end, tier=1, vehicle="etf"))
    for row in _listings(con):
        identity = str(row["maps_to"])
        track = str(row["tracked_index"] or "")
        if int(row["enhanced"] or 0) == 1 or "增强" in str(row["name"] or ""):
            continue
        if track not in index_names(identity):
            continue
        nav_start = otc_nav_start(con, str(row["code"]), end)
        inception = str(row["inception"] or "")
        if nav_start is None or not inception:
            continue
        opened = max(pd.Timestamp(inception), nav_start)
        available = pd.Series(calendar >= opened, index=calendar)
        grouped.setdefault(identity, []).append(_Candidate(
            container=identity, code=str(row["code"]), vehicle="otc", tier=2,
            inception=inception, nav_start=str(nav_start.date()), order=0, available=available))
    for row in SUBSTITUTES:
        identity = row["container"]
        if row["vehicle"] == "etf":
            grouped.setdefault(identity, []).append(_etf_candidate(
                con, identity, row["code"], 0, calendar, end, tier=3, vehicle="near"))
            continue
        nav_start = otc_nav_start(con, row["code"], end)
        inception = str(nav_start.date()) if nav_start is not None else ""
        # 161211 的成立日和净值起点都是 2010-04-09。成立日以净值起点和登记为准，取较晚的一天。
        listed = next((item for item in _listings(con) if item["code"] == row["code"]), None)
        if listed is not None and listed.get("inception"):
            inception = str(listed["inception"])
        if nav_start is None or not inception:
            continue
        opened = max(pd.Timestamp(inception), nav_start)
        available = pd.Series(calendar >= opened, index=calendar)
        grouped.setdefault(identity, []).append(_Candidate(
            container=identity, code=row["code"], vehicle="near", tier=3,
            inception=inception, nav_start=str(nav_start.date()), order=0, available=available))
    for identity, code in us_spdr:
        dates = hfq_dates(con, code, end)
        if len(dates) == 0:
            continue
        # 美股收盘严格早于上交所交易日 D，才算这一天用得上后复权。
        flags = []
        for day in calendar:
            earlier = dates[dates < pd.Timestamp(day)]
            flags.append(len(earlier) > 0)
        grouped.setdefault(identity, []).append(_Candidate(
            container=identity, code=code, vehicle="spdr", tier=4,
            inception="", nav_start="", order=0,
            available=pd.Series(flags, index=calendar, dtype=bool)))
    for identity, rows in grouped.items():
        rows.sort(key=lambda item: (item.tier, item.order, item.inception, item.nav_start, item.code))
        grouped[identity] = rows
    return grouped


def _etf_candidate(con, identity, code, order, calendar, end, *, tier: int, vehicle: str) -> _Candidate:
    prints = raw_dates(con, code, end)
    median = amount_median(con, code, end)
    backward = hfq_dates(con, code, end)
    list_day = pd.Timestamp(prints[0]) if len(prints) else None
    opened = tradable_start(list_day, calendar, median)
    available = _mask(calendar, lambda day: etf_available(
        calendar, day, hfq=backward, prints=prints, median=median, opened=opened))
    return _Candidate(
        container=identity, code=code, vehicle=vehicle, tier=tier,
        inception="", nav_start="", order=order, available=available)


def choose_on(candidates: list[_Candidate], day: pd.Timestamp) -> CarrierChoice | None:
    stamp = pd.Timestamp(day)
    for item in candidates:
        if stamp not in item.available.index:
            continue
        if bool(item.available.at[stamp]):
            return CarrierChoice(item.vehicle, item.code)
    return None


def choices_on(grouped: dict[str, list[_Candidate]], day: pd.Timestamp,
               containers: list[str]) -> dict[str, CarrierChoice | None]:
    return {identity: choose_on(grouped.get(identity, []), day) for identity in containers}
