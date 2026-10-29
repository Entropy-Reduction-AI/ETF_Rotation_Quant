"""U-可交易载体。开关关闭时不调用。

顺序是预注册第 2.2 版 §3.2：

1. 跟踪同一指数（或同一组）的场内 ETF、LOF，有后复权，并且满足 v3 §3.3 的可交易首日和当天流动性。
   可交易首日 = max(上市日后第 60 个上交所交易日, 首次「近 20 个自身交易日成交额中位数 ≥ 3000 万元」)。
   上市日取原始 K 线第一根正收盘，第 60 个交易日不含上市日当天。
   流动性是当天的条件：这一天对应的近 20 个自身交易日成交额中位数仍然 ≥ 3000 万元。
   同一档多只时，近 20 日成交额中位数高的优先，再按代码升序。不够 3000 万就看下一档（D16-1）。
   已持有的第 1 档只要还在这个可用名单里就留住（D19-2），不因别的基金成交额更高而换。
2. 跟踪同一指数的场外纯指数基金，含非增强的联接基金（D16-2）。增强型不用。
   成立日早的优先，再取第一笔净值早的，再按代码升序。
   没有可投资指数的容器：登记表 `maps_to` 已经指向该容器的场外基金同样放在这一档。
3. 已经决定的相近替身，只有 161211 和 510880。不把拒绝入库的指数升成替身。
   登记表顺序，再按代码升序。场内的同样要过第 1 档的流动性。
4. 美股行业才用美国的 SPDR，后复权。可用的后复权收盘严格早于 D。

都没有的那天，该容器不进 U-可交易排名。

没有可投资指数历史的容器，研究序列用当天这只基金自己的日收益往下接（§3.1）。
QDII 用 T−2 单位净值。换载体时接收益，不把两只基金的价格水平拼成一条。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.v3.engine.limits import board_of
from src.v3.engine.prices import lag_asof, returns_from_level
from src.v3.engine.universe import is_qdii
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
    board: str = "none"

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
    median: pd.Series
    board: str
    qdii: bool = False


def has_investable_index(container: dict) -> bool:
    """有可投资指数历史才用指数做研究序列。取不到代码或状态的容器改接基金日收益。"""
    research = container.get("research") or {}
    code = str(research.get("series_code") or "").strip()
    status = str(research.get("series_status") or "").strip()
    if code in {"", "取不到", "TBD"}:
        return False
    if status == "取不到":
        return False
    return True


def _marks_qdii(name: str, container: dict) -> bool:
    if is_qdii(container):
        return True
    return "QDII" in str(name or "").upper()


def _mask(calendar: pd.DatetimeIndex, predicate) -> pd.Series:
    flags = [bool(predicate(pd.Timestamp(day))) for day in calendar]
    return pd.Series(flags, index=calendar, dtype=bool)


def build_candidates(con: sqlite3.Connection, containers: list[dict], calendar: pd.DatetimeIndex,
                     end: str, *, us_spdr: tuple[tuple[str, str], ...] = ()) -> dict[str, list[_Candidate]]:
    """每个容器一串按档位排好的候选。`available` 是上交所交易日上的布尔序列。"""
    grouped: dict[str, list[_Candidate]] = {}
    by_id = {str(container.get("id") or ""): container for container in containers}
    etfs = _execution_etfs(containers)
    for identity, rows in etfs.items():
        container = by_id.get(identity, {})
        for row in rows:
            grouped.setdefault(identity, []).append(_etf_candidate(
                con, identity, row["code"], row["order"], calendar, end, tier=1, vehicle="etf",
                track=row["tracks"], qdii=_marks_qdii(row["name"], container)))
    _add_indexless_etfs(con, containers, grouped, calendar, end)
    for row in _listings(con):
        identity = str(row["maps_to"])
        track = str(row["tracked_index"] or "")
        container = by_id.get(identity, {})
        if int(row["enhanced"] or 0) == 1 or "增强" in str(row["name"] or ""):
            continue
        linked_without_index = bool(container) and not has_investable_index(container)
        if track not in index_names(identity) and not linked_without_index:
            continue
        nav_start = otc_nav_start(con, str(row["code"]), end)
        inception = str(row["inception"] or "")
        if nav_start is None or not inception:
            continue
        opened = max(pd.Timestamp(inception), nav_start)
        available = pd.Series(calendar >= opened, index=calendar)
        grouped.setdefault(identity, []).append(_Candidate(
            container=identity, code=str(row["code"]), vehicle="otc", tier=2,
            inception=inception, nav_start=str(nav_start.date()), order=0, available=available,
            median=pd.Series(dtype=float), board="none", qdii=_marks_qdii(row["name"], container)))
    for order, row in enumerate(SUBSTITUTES):
        identity = row["container"]
        if row["vehicle"] == "etf":
            grouped.setdefault(identity, []).append(_etf_candidate(
                con, identity, row["code"], order, calendar, end, tier=3, vehicle="near",
                track=row["tracks"]))
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
            inception=inception, nav_start=str(nav_start.date()), order=order, available=available,
            median=pd.Series(dtype=float), board="none"))
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
            available=pd.Series(flags, index=calendar, dtype=bool),
            median=pd.Series(dtype=float), board="none"))
    for identity, rows in grouped.items():
        rows.sort(key=lambda item: (item.tier, item.order, item.inception, item.nav_start, item.code))
        grouped[identity] = rows
    return grouped


def _add_indexless_etfs(con, containers: list[dict], grouped: dict[str, list[_Candidate]],
                        calendar: pd.DatetimeIndex, end: str) -> None:
    """没有指数历史的容器，执行层里的场内基金就是关联基金，不再要求跟踪标的对上指数名。"""
    for container in containers:
        if container.get("arm") not in {None, "main"}:
            continue
        if container.get("asset_class") == "现金":
            continue
        if has_investable_index(container):
            continue
        identity = str(container.get("id") or "")
        have = {item.code for item in grouped.get(identity, [])}
        order = len(grouped.get(identity, []))
        for row in container.get("execution") or []:
            code = str(row.get("code") or "")
            if code in {"", "取不到", "TBD"} or code in have:
                continue
            grouped.setdefault(identity, []).append(_etf_candidate(
                con, identity, code, order, calendar, end, tier=1, vehicle="etf",
                track=str(row.get("track") or ""), qdii=_marks_qdii(str(row.get("name") or ""), container)))
            have.add(code)
            order += 1


def _etf_candidate(con, identity, code, order, calendar, end, *, tier: int, vehicle: str,
                   track: str = "", qdii: bool = False) -> _Candidate:
    prints = raw_dates(con, code, end)
    median = amount_median(con, code, end)
    backward = hfq_dates(con, code, end)
    list_day = pd.Timestamp(prints[0]) if len(prints) else None
    opened = tradable_start(list_day, calendar, median)
    available = _mask(calendar, lambda day: etf_available(
        calendar, day, hfq=backward, prints=prints, median=median, opened=opened))
    return _Candidate(
        container=identity, code=code, vehicle=vehicle, tier=tier,
        inception="", nav_start="", order=order, available=available,
        median=median, board=board_of(track, code), qdii=qdii)


def _median_on(item: _Candidate, day: pd.Timestamp) -> float:
    series = item.median
    if series is None or len(series) == 0:
        return float("-inf")
    known = series.dropna()
    known = known[known.index <= pd.Timestamp(day)]
    if known.empty:
        return float("-inf")
    return float(known.iloc[-1])


def _kept_holding(candidates: list[_Candidate], day: pd.Timestamp,
                  held: CarrierChoice | None) -> CarrierChoice | None:
    """第 1 档仍在当天可用名单里就留住。名单含 3000 万资格；掉出去才允许换。"""
    if held is None:
        return None
    stamp = pd.Timestamp(day)
    for item in candidates:
        if item.tier != 1 or item.code != held.code or item.vehicle != held.vehicle:
            continue
        if stamp not in item.available.index or not bool(item.available.at[stamp]):
            continue
        return CarrierChoice(item.vehicle, item.code, item.board)
    return None


def choose_on(candidates: list[_Candidate], day: pd.Timestamp,
              held: CarrierChoice | None = None) -> CarrierChoice | None:
    """当天可用的最低一档。没有持仓时，第 1 档按成交额中位数、再按代码。

    已持有的第 1 档只要还满足 3000 万（仍在可用名单里）就留住，不因别的基金近 20 日
    成交额更高而换。失去资格、停牌或没有后复权时掉出名单，再按原规则重选。
    """
    kept = _kept_holding(candidates, day, held)
    if kept is not None:
        return kept
    stamp = pd.Timestamp(day)
    ready = []
    for item in candidates:
        if stamp not in item.available.index:
            continue
        if bool(item.available.at[stamp]):
            ready.append(item)
    if not ready:
        return None
    tier = min(item.tier for item in ready)
    pool = [item for item in ready if item.tier == tier]
    if tier == 1:
        pool.sort(key=lambda item: (-_median_on(item, stamp), item.code))
    elif tier == 2:
        pool.sort(key=lambda item: (item.inception or "9999-99-99", item.nav_start or "9999-99-99", item.code))
    else:
        pool.sort(key=lambda item: (item.order, item.code))
    winner = pool[0]
    return CarrierChoice(winner.vehicle, winner.code, winner.board)


def choices_on(grouped: dict[str, list[_Candidate]], day: pd.Timestamp,
               containers: list[str]) -> dict[str, CarrierChoice | None]:
    """单独一天、没有已持有载体。年末载体表用这个，不把路径依赖写进对照。"""
    return {identity: choose_on(grouped.get(identity, []), day) for identity in containers}


def choose_path(candidates: list[_Candidate], days) -> list[CarrierChoice | None]:
    """从第一天起递推。上一天选中的载体就是下一天的「已持有」。

    不看组合权重。研究序列要在排名之前定下来，不能等知道当天持不持仓再选基金。
    """
    held: CarrierChoice | None = None
    chosen: list[CarrierChoice | None] = []
    for day in days:
        choice = choose_on(candidates, pd.Timestamp(day), held=held)
        chosen.append(choice)
        held = choice
    return chosen


@dataclass(frozen=True)
class StitchedFill:
    """U-可交易当天载体的收盘、同一只的前收、以及涨跌停板块。"""

    close: pd.Series
    prev: pd.Series
    board: pd.Series


def _close_and_prev(series: pd.Series | None, day, *, strict_before: bool) -> tuple[float, float]:
    """A 股场内和场外用当天打印。美股 SPDR 用严格早于 D 的收盘。没有打印就是空。"""
    if series is None or len(series) == 0:
        return float("nan"), float("nan")
    stamp = pd.Timestamp(day).normalize()
    ordered = series.dropna().sort_index()
    if strict_before:
        known = ordered[ordered.index < stamp]
        if known.empty:
            return float("nan"), float("nan")
        close = float(known.iloc[-1])
        prev = float(known.iloc[-2]) if len(known) >= 2 else float("nan")
        return close, prev
    if stamp not in ordered.index:
        return float("nan"), float("nan")
    earlier = ordered[ordered.index < stamp]
    prev = float(earlier.iloc[-1]) if len(earlier) else float("nan")
    return float(ordered.loc[stamp]), prev


def stitch_fills(grouped: dict[str, list[_Candidate]], days, prints: dict[str, pd.Series],
                 assets: dict[str, str]) -> dict[str, StitchedFill]:
    """每个容器用路径上选中的载体自己的收盘。港股、美股容器不设涨跌停。"""
    index = pd.DatetimeIndex(pd.to_datetime(days))
    out: dict[str, StitchedFill] = {}
    for name, rows in grouped.items():
        asset = assets.get(name, "")
        no_band = asset == "港股" or str(asset).startswith("美股")
        closes = []
        prevs = []
        boards = []
        for day, choice in zip(index, choose_path(rows, index)):
            if choice is None:
                closes.append(np.nan)
                prevs.append(np.nan)
                boards.append("none")
                continue
            close, prev = _close_and_prev(
                prints.get(choice.code), day, strict_before=choice.vehicle == "spdr")
            closes.append(close)
            prevs.append(prev)
            boards.append("none" if no_band else choice.board)
        out[name] = StitchedFill(
            close=pd.Series(closes, index=index, dtype=float),
            prev=pd.Series(prevs, index=index, dtype=float),
            board=pd.Series(boards, index=index, dtype=object),
        )
    return out


def _positive_series(frame: pd.DataFrame) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    if frame.empty:
        return out
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    for code, block in frame.groupby("code", sort=False):
        series = pd.Series(block["close"].to_numpy(dtype=float), index=pd.DatetimeIndex(block["date"]))
        series = series[np.isfinite(series.to_numpy(dtype=float)) & (series > 0)]
        out[str(code)] = series[~series.index.duplicated(keep="last")].sort_index()
    return out


def prints_for(con: sqlite3.Connection, grouped: dict[str, list[_Candidate]], end: str) -> dict[str, pd.Series]:
    """场内用原始收盘，场外用复权净值，美股 SPDR 用后复权。"""
    raw_codes: list[str] = []
    nav_codes: list[str] = []
    back_codes: list[str] = []
    for rows in grouped.values():
        for row in rows:
            if row.vehicle == "spdr":
                back_codes.append(row.code)
            elif row.vehicle == "otc" or (row.vehicle == "near" and row.board == "none"):
                nav_codes.append(row.code)
            else:
                raw_codes.append(row.code)
    found: dict[str, pd.Series] = {}

    def pull(sql: str, codes: list[str]) -> None:
        if not codes:
            return
        marks = ",".join("?" * len(codes))
        frame = pd.read_sql_query(sql.format(marks=marks), con, params=[end, *codes])
        found.update(_positive_series(frame))

    pull(
        "SELECT code, date, close FROM bars WHERE adj = 'raw' AND close > 0 AND date <= ? "
        "AND code IN ({marks})",
        raw_codes)
    pull(
        "SELECT code, date, close FROM v4_series WHERE kind = 'otc_nav' AND close > 0 AND date <= ? "
        "AND code IN ({marks})",
        nav_codes)
    pull(
        "SELECT code, date, close FROM v4_series WHERE kind = 'backward' AND close > 0 AND date <= ? "
        "AND code IN ({marks})",
        back_codes)
    return found


def splice_returns(choices: list[CarrierChoice | None], days,
                   returns_by_code: dict[str, pd.Series]) -> pd.Series:
    """换载体那天用新基金自己的日收益。不用上一只的价格去除这一只的价格。"""
    index = pd.DatetimeIndex(pd.to_datetime(days))
    out = np.full(len(index), np.nan)
    for pos, (day, choice) in enumerate(zip(index, choices)):
        if choice is None:
            continue
        series = returns_by_code.get(choice.code)
        if series is None or series.empty:
            continue
        stamp = pd.Timestamp(day)
        if stamp not in series.index:
            continue
        value = series.loc[stamp]
        if hasattr(value, "iloc"):
            value = value.iloc[-1]
        if value == value:
            out[pos] = float(value)
    return pd.Series(out, index=index, dtype=float)


def _event_returns(level: pd.Series, calendar: pd.DatetimeIndex) -> pd.Series:
    """收益记在这只基金自己的打印日上，再对齐到上交所日历。缺日是空，不把价格填过去。"""
    if level is None or len(level) == 0:
        return pd.Series(np.nan, index=calendar, dtype=float)
    ordered = level.dropna().sort_index()
    ordered = ordered[~ordered.index.duplicated(keep="last")]
    values = ordered.to_numpy(dtype=float)
    ordered = ordered[np.isfinite(values) & (values > 0)]
    if ordered.empty:
        return pd.Series(np.nan, index=calendar, dtype=float)
    ret = ordered.astype(float) / ordered.astype(float).shift(1) - 1.0
    return ret.reindex(calendar)


def lagged_nav_returns(nav: pd.Series, calendar: pd.DatetimeIndex, lag: int) -> pd.Series:
    """QDII：决策日 T 的研究收益是 T−lag 单位净值水平自己的涨跌，不是场内收盘。"""
    level = lag_asof(nav, pd.DatetimeIndex(calendar), int(lag))
    return returns_from_level(level).reindex(calendar)


def _load_nav(con: sqlite3.Connection, code: str, end: str) -> pd.Series:
    frame = pd.read_sql_query(
        "SELECT date, unit_nav FROM fund_nav WHERE code = ? AND unit_nav > 0 AND date <= ? ORDER BY date",
        con, params=(code, end))
    if frame.empty:
        return pd.Series(dtype=float)
    series = pd.Series(frame["unit_nav"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
    return series[np.isfinite(series.to_numpy(dtype=float)) & (series > 0)].sort_index()


def _load_kind(con: sqlite3.Connection, code: str, kind: str, end: str) -> pd.Series:
    frame = pd.read_sql_query(
        "SELECT date, close FROM v4_series WHERE code = ? AND kind = ? AND close > 0 AND date <= ? ORDER BY date",
        con, params=(code, kind, end))
    if frame.empty:
        return pd.Series(dtype=float)
    series = pd.Series(frame["close"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
    return series[np.isfinite(series.to_numpy(dtype=float)) & (series > 0)].sort_index()


def research_return(con: sqlite3.Connection, item: _Candidate, calendar: pd.DatetimeIndex,
                    end: str, nav_lag: int) -> pd.Series:
    """一只关联基金自己的研究日收益。QDII 用 T−lag 净值，场内用后复权，场外用复权净值。"""
    if item.qdii:
        return lagged_nav_returns(_load_nav(con, item.code, end), calendar, nav_lag)
    if item.vehicle == "otc" or (item.vehicle == "near" and item.board == "none"):
        return _event_returns(_load_kind(con, item.code, "otc_nav", end), calendar)
    return _event_returns(_load_kind(con, item.code, "backward", end), calendar)


def spliced_research(con: sqlite3.Connection, rows: list[_Candidate], days, end: str, *,
                     nav_lag: int) -> pd.Series:
    """无指数容器的研究序列：按日用当天载体自己的收益接起来。"""
    calendar = pd.DatetimeIndex(pd.to_datetime(days))
    choices = choose_path(rows, calendar)
    returns: dict[str, pd.Series] = {}
    for item in rows:
        if item.code in returns:
            continue
        returns[item.code] = research_return(con, item, calendar, end, nav_lag)
    return splice_returns(choices, calendar, returns)
