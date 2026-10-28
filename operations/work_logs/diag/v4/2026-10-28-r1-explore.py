"""v4-R1 数据探索。只描述，不跑组合。

结束日写死为 2015-12-31。排名用 v3.1 的 R / s / 现金过滤 / 排序（score.lookback_panel
与 pick_row 的同一顺序），不调用成交、持仓或净值。2016-01-01 之后的行情只用于
列数据缺陷（价格为 0、未复权拆分），不进入相关系数、跟踪差或排名。

没有命令行参数。不要把结束日改晚。
"""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.dividends import GAP_LIMIT
from src.v3.data.history import OFFICIAL
from src.v3.data.universe import containers as load_containers
from src.v3.engine.benchmark import _connect, _fx
from src.v3.engine.market import _research_level, _split_bars, _usd_level, load_market
from src.v3.engine.prices import signal_returns, total_return_close
from src.v3.engine.score import history_ok, lookback_panel, min_observations, pick_row
from src.v3.engine.spec import load_spec
from src.v3.engine.sessions import decision_dates
from src.v3.engine.universe import pool_members

END = pd.Timestamp("2015-12-31")
END_TEXT = "2015-12-31"
START_TEXT = "2006-01-01"
DB = ROOT / "data" / "market.sqlite"
OUT = ROOT / "results" / "v4" / "inventory"
LOOKBACKS = (20, 60, 120, 250)
NS = (3, 5, 8)
MARKETS = ("A股", "港股", "美股", "防守")
MARKET_OF = {
    "A股宽基": "A股",
    "A股行业": "A股",
    "A股红利": "A股",
    "港股": "港股",
    "美股宽基": "美股",
    "美股和全球主题": "美股",
    "商品": "防守",
    "债券": "防守",
}
# 已入库、作为新池容器。XLC 设计期没有 K 线，仍计入登记，可选为 0。
NEW_US = (
    ("us-xlb", "XLB", "材料"),
    ("us-xle", "XLE", "能源"),
    ("us-xlf", "XLF", "金融"),
    ("us-xli", "XLI", "工业"),
    ("us-xlk", "XLK", "信息科技"),
    ("us-xlp", "XLP", "必需消费"),
    ("us-xlu", "XLU", "公用事业"),
    ("us-xlv", "XLV", "医疗保健"),
    ("us-xly", "XLY", "可选消费"),
    ("us-xlre", "XLRE", "房地产"),
    ("us-xlc", "XLC", "通信服务"),
)
NEW_HK = (
    ("hk-hsf", "HSF", "恒生金融分类"),
    ("hk-hsu", "HSU", "恒生公用事业分类"),
    ("hk-hsp", "HSP", "恒生地产分类"),
    ("hk-hsc", "HSC", "恒生工商分类"),
)
BROAD_US = ("ndx100", "spx")
# 同一行业、库里实际有的对照。其余标普行业指数没有日线。
SECTOR_PAIRS = (("XLRE", "SP500-60", "Real Estate", "price_vs_price"),)
SPLIT_FACTORS = (2.0, 0.5, 3.0, 1.0 / 3.0, 4.0, 0.25, 1.5, 2.0 / 3.0, 10.0, 0.1)
GAP_LIST = 0.20
ROUNDTRIP = 0.15
ROUNDTRIP_NET = 0.03


def _die_on_args() -> None:
    if len(sys.argv) > 1:
        raise SystemExit("这个脚本没有参数。结束日写死为 2015-12-31。")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_end(index: pd.DatetimeIndex, label: str) -> None:
    if len(index) == 0:
        raise RuntimeError(f"{label} 没有日期")
    last = pd.Timestamp(index.max())
    if last > END:
        raise RuntimeError(f"{label} 含有 {last.date()}，晚于 {END.date()}")


def _data_ok(ret: pd.DataFrame, length: int) -> pd.DataFrame:
    """v3.1 参与排名的历史条件，不含现金过滤。"""
    values = ret.to_numpy(dtype=float)
    finite = np.isfinite(values) & (values > -1.0)
    finite_df = pd.DataFrame(finite, index=ret.index, columns=ret.columns)
    count = finite_df.astype(float).rolling(length, min_periods=1).sum()
    need = min_observations(length)
    return history_ok(finite_df, length) & count.ge(need) & finite_df


def _ordered(panel, day: pd.Timestamp, names: list[str], fresh: pd.DataFrame,
             sort_ids: dict[str, str]) -> list[str]:
    """与 pick_row 相同的资格和排序。不分配权重。"""
    total = panel.total.loc[day]
    score = panel.score.loc[day]
    ok = panel.ok.loc[day]
    gate = fresh.loc[day]
    ranked = []
    for name in names:
        if not bool(ok[name]) or not bool(gate[name]):
            continue
        ranked.append((float(score[name]), float(total[name]), sort_ids[name], name))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [item[3] for item in ranked]


def _load_bars(con: sqlite3.Connection, codes: list[str], end: str | None) -> dict[str, pd.DataFrame]:
    if not codes:
        return {}
    marks = ",".join("?" * len(codes))
    sql = (
        "SELECT code, date, open, high, low, close, volume FROM bars "
        f"WHERE adj = 'raw' AND code IN ({marks})"
    )
    params: list = list(codes)
    if end is not None:
        sql += " AND date <= ?"
        params.append(end)
    sql += " ORDER BY code, date"
    frame = pd.read_sql_query(sql, con, params=params)
    return _split_bars(frame)


def _dividend_yields(block: pd.DataFrame, events: pd.DataFrame) -> dict[pd.Timestamp, float]:
    if block is None or block.empty or events is None or events.empty:
        return {}
    close = pd.Series(block["close"].to_numpy(dtype=float), index=pd.DatetimeIndex(pd.to_datetime(block["date"])))
    close = close[np.isfinite(close.to_numpy(dtype=float)) & (close.to_numpy(dtype=float) > 0)]
    close = close[~close.index.duplicated(keep="last")].sort_index()
    out = {}
    for record in events.itertuples(index=False):
        day = pd.Timestamp(record.ex_date)
        amount = float(record.amount) if record.amount == record.amount else float("nan")
        if not (amount > 0):
            continue
        prev = close[close.index < day]
        if prev.empty:
            continue
        prev_close = float(prev.iloc[-1])
        if prev_close > amount:
            out[day] = amount / prev_close
    return out


def _signal_from_level(level: pd.Series, fresh: pd.Series, gaps: pd.DatetimeIndex,
                       calendar: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series]:
    series = signal_returns(level, gaps).reindex(calendar)
    flag = fresh.reindex(calendar).fillna(False).astype(bool)
    return series, flag


def _parity(market, bars: dict, divs: dict, calendar, fx, spec) -> None:
    """新序列走引擎里同一条对齐。先核对恒生、纳指、标普和引擎面板一致。"""
    checks = (
        ("hsi", "HSI", "tencent_hk_index"),
        ("ndx100", "XNDX", "nasdaq"),
        ("spx", "^SP500TR", "yahoo"),
    )
    for name, code, source in checks:
        level, fresh, gaps = _research_level(code, source, bars, divs, calendar, fx, spec, None)
        built, _flag = _signal_from_level(level, fresh, gaps, calendar)
        have = market.signal[name]
        if not built.index.equals(have.index):
            raise RuntimeError(f"{name} 日期没对齐")
        nan_mismatch = int((built.isna() != have.isna()).sum())
        both = built.notna() & have.notna()
        diff = float((built[both] - have[both]).abs().max()) if both.any() else 0.0
        if nan_mismatch or diff > 1e-8:
            raise RuntimeError(f"{name} 与引擎信号不一致 nan={nan_mismatch} max_abs={diff}")
        print(f"parity {name} ok max_abs={diff:.3e} finite={int(both.sum())}", flush=True)


def _cash_divs(con: sqlite3.Connection, end: str) -> dict[str, dict]:
    frame = pd.read_sql_query(
        "SELECT code, ex_date, amount, prev_close FROM cash_dividends WHERE ex_date <= ?",
        con, params=(end,))
    out: dict[str, dict] = {}
    if frame.empty:
        return out
    from src.v3.engine.prices import dividend_yields
    frame["ex_date"] = pd.to_datetime(frame["ex_date"])
    for code, block in frame.groupby("code", sort=False):
        out[str(code)] = dividend_yields(block)
    return out


def _build_new(calendar, fx, spec, bars: dict, events: pd.DataFrame, *, adjust_div: bool):
    signals = {}
    fresh = {}
    gap_days = {}
    for name, code, _label in NEW_US:
        block = bars.get(code)
        if block is None or block.empty:
            continue
        used = block
        if adjust_div:
            subset = events[(events["code"] == code) & (events["kind"] == "dividend")] if not events.empty else events
            yields = _dividend_yields(block, subset)
            adjusted, gaps = total_return_close(block, yields, GAP_LIMIT)
            gap_days[code] = [str(pd.Timestamp(day).date()) for day in gaps if pd.Timestamp(day) <= END]
            used = pd.DataFrame({
                "date": adjusted.index,
                "open": adjusted.to_numpy(dtype=float),
                "close": adjusted.to_numpy(dtype=float),
            })
        level, flag, _gaps = _usd_level(used, fx, calendar, spec.stale_limit, None)
        series, flag = _signal_from_level(level, flag, pd.DatetimeIndex([]), calendar)
        _assert_end(series.dropna().index, code)
        signals[name] = series
        fresh[name] = flag
    if adjust_div:
        return signals, fresh, gap_days
    for name, code, _label in NEW_HK:
        level, flag, gaps = _research_level(code, "tencent_hk_index", bars, {}, calendar, fx, spec, None)
        series, flag = _signal_from_level(level, flag, gaps, calendar)
        _assert_end(series.dropna().index, code)
        signals[name] = series
        fresh[name] = flag
    return signals, fresh, gap_days


def _meta(members: list[dict]) -> dict[str, dict]:
    out = {}
    for row in members:
        if row.get("asset_class") == "现金":
            continue
        asset = str(row.get("asset_class"))
        if asset not in MARKET_OF:
            raise RuntimeError(f"没有市场映射：{row.get('id')} {asset}")
        out[str(row["id"])] = {
            "market": MARKET_OF[asset],
            "asset_class": asset,
            "label": str(row.get("name")),
            "origin": "old",
        }
    for name, code, label in NEW_US:
        out[name] = {"market": "美股", "asset_class": "v4美股行业ETF", "label": f"{label} {code}", "origin": "v4"}
    for name, code, label in NEW_HK:
        out[name] = {"market": "港股", "asset_class": "v4恒生分类指数", "label": f"{label} {code}", "origin": "v4"}
    return out


def _year_ends(days: pd.DatetimeIndex) -> dict[int, pd.Timestamp]:
    out = {}
    for day in days:
        if day.month == 12:
            out[int(day.year)] = pd.Timestamp(day)
    return out


def _write(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _coverage(meta, pools, fresh, signal, days, year_ends) -> list[dict]:
    rows = []
    ok20 = _data_ok(signal, 20)
    ok250 = _data_ok(signal, 250)
    for pool, names in pools.items():
        for year, year_end in year_ends.items():
            month_ends = [day for day in days if int(day.year) == year]
            for market in MARKETS:
                roster_names = [name for name in names if meta[name]["market"] == market]
                def count_on(day, gate):
                    total = 0
                    for name in roster_names:
                        if name not in signal.columns:
                            continue
                        if bool(fresh.at[day, name]) and bool(gate.at[day, name]):
                            total += 1
                    return total
                counts = [count_on(day, ok20) for day in month_ends]
                if pool == "new" and market == "美股" and year in {2006, 2015}:
                    print(
                        "month_us", pool, year,
                        [(pd.Timestamp(day).date().isoformat(), count) for day, count in zip(month_ends, counts)],
                        flush=True,
                    )
                rows.append({
                    "year": year,
                    "pool": pool,
                    "market": market,
                    "roster": len(roster_names),
                    "selectable_20": count_on(year_end, ok20),
                    "selectable_250": count_on(year_end, ok250),
                    "selectable_20_min": min(counts) if counts else 0,
                    "selectable_20_max": max(counts) if counts else 0,
                })
    return rows


def _name_rows(meta, pools, fresh, signal, year_ends) -> list[dict]:
    ok20 = _data_ok(signal, 20)
    ok250 = _data_ok(signal, 250)
    rows = []
    for pool, names in pools.items():
        for year, day in year_ends.items():
            for name in names:
                have = name in signal.columns
                rows.append({
                    "year": year,
                    "pool": pool,
                    "name": name,
                    "market": meta[name]["market"],
                    "asset_class": meta[name]["asset_class"],
                    "label": meta[name]["label"],
                    "selectable_20": int(have and bool(fresh.at[day, name]) and bool(ok20.at[day, name])),
                    "selectable_250": int(have and bool(fresh.at[day, name]) and bool(ok250.at[day, name])),
                })
    return rows


def _oracle(panel, day, names, fresh, sort_ids, cash_id: str) -> None:
    got = _ordered(panel, day, names, fresh, sort_ids)
    weights = pick_row(panel, day, 8, names, cash_id, sort_ids, fresh)
    selected = [name for name, weight in weights.items() if name != cash_id and weight > 0]
    # pick_row 只取前 n 个。这里用 n=8 核对顺序的前 8 名。
    if selected != got[:8]:
        raise RuntimeError(f"排名与 pick_row 不一致 {day.date()} engine={selected} local={got[:8]}")


def _structure(meta, pools, fresh_by_pool, signal_by_pool, days, spec):
    month_rows = []
    selections = []
    cap_acc = defaultdict(int)
    cap_hit = defaultdict(int)
    for pool, names in pools.items():
        signal = signal_by_pool[pool]
        fresh = fresh_by_pool[pool]
        frame = signal.loc[:, [*names, spec.cash_id]]
        _assert_end(frame.index, pool)
        panels = {length: lookback_panel(frame, spec.cash_id, length) for length in LOOKBACKS}
        sort_ids = {name: name for name in names}
        # 旧池 2012-06 的月末，核对一次排序实现。
        if pool == "old":
            probe = [day for day in days if day.year == 2012 and day.month == 6][0]
            _oracle(panels[60], probe, names, fresh, sort_ids, spec.cash_id)
            print(f"oracle pick_row {probe.date()} L=60 n=8 ok", flush=True)
        for day in days:
            for length, panel in panels.items():
                ordered = _ordered(panel, day, names, fresh, sort_ids)
                eligible = len(ordered)
                top8 = ordered[:8]
                both = int(all(name in top8[:2] for name in BROAD_US))
                cap_acc[(pool, int(day.year), length)] += 1
                cap_hit[(pool, int(day.year), length)] += both
                for rank, name in enumerate(top8, start=1):
                    selections.append({
                        "date": day.date().isoformat(),
                        "pool": pool,
                        "lookback": length,
                        "rank": rank,
                        "name": name,
                        "market": meta[name]["market"],
                    })
                counts = Counter(meta[name]["market"] for name in top8)
                for n in NS:
                    sliced = Counter(meta[name]["market"] for name in ordered[:n])
                    for market in MARKETS:
                        count = int(sliced.get(market, 0))
                        month_rows.append({
                            "date": day.date().isoformat(),
                            "year": int(day.year),
                            "pool": pool,
                            "lookback": length,
                            "n": n,
                            "market": market,
                            "count": count,
                            "share": count / n,
                            "eligible": eligible,
                        })
    cap_rows = []
    for (pool, year, length), months in sorted(cap_acc.items()):
        cap_rows.append({
            "year": year,
            "pool": pool,
            "lookback": length,
            "months": months,
            "both_broad_in_top2": cap_hit[(pool, year, length)],
            "rate": cap_hit[(pool, year, length)] / months,
        })
    return month_rows, selections, cap_rows


def _native_frame(con, code: str) -> pd.DataFrame:
    frame = pd.read_sql_query(
        "SELECT date, open, high, low, close FROM bars WHERE code = ? AND adj = 'raw' ORDER BY date",
        con, params=(code,))
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"])
    for column in ("open", "high", "low", "close"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _in_design(day) -> int:
    text = day if isinstance(day, str) else pd.Timestamp(day).date().isoformat()
    return int(START_TEXT <= str(text)[:10] <= END_TEXT)


def _quality(con, ranking_codes: set[str], split_events: pd.DataFrame) -> list[dict]:
    rows = []
    codes = [
        "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLRE", "XLC",
        "SP500-60", "HSF", "HSU", "HSP", "HSC", "HSFGTR", "HSUGTR", "HSPGTR", "HSCGTR",
        "HKDCNY", "HSI", "XNDX", "^SP500TR",
    ]
    zero = pd.read_sql_query(
        "SELECT code, date, close, source FROM bars WHERE adj = 'raw' AND (close <= 0 OR close IS NULL)",
        con)
    for record in zero.itertuples(index=False):
        day = str(record.date)
        rows.append({
            "code": record.code,
            "date": day,
            "kind": "close_le_0",
            "measure": record.close,
            "in_design_window": _in_design(day),
            "in_ranking_pool": int(str(record.code) in ranking_codes),
            "detail": f"source={record.source}。v3.1 主池研究代码里没有这 6 个中证代码。"
            if str(record.code).startswith("H") else f"source={record.source}",
        })
    split_on = {}
    if not split_events.empty:
        for record in split_events.itertuples(index=False):
            split_on.setdefault(str(record.code), []).append(record)
    for code in codes:
        frame = _native_frame(con, code)
        if frame.empty:
            rows.append({
                "code": code, "date": "", "kind": "no_bars", "measure": 0,
                "in_design_window": 0, "in_ranking_pool": int(code in ranking_codes),
                "detail": "设计期或全历史没有行情行",
            })
            continue
        dup = int(frame["date"].duplicated().sum())
        if dup:
            rows.append({
                "code": code, "date": "", "kind": "duplicate_date", "measure": dup,
                "in_design_window": 1, "in_ranking_pool": int(code in ranking_codes),
                "detail": "同一 code 有重复日期",
            })
        close = frame["close"]
        prev = close.shift(1)
        ret = close / prev - 1.0
        opened = frame["open"]
        gap = opened / prev - 1.0
        for pos in range(1, len(frame)):
            day = pd.Timestamp(frame["date"].iloc[pos])
            day_text = day.date().isoformat()
            change = float(ret.iloc[pos]) if np.isfinite(ret.iloc[pos]) else float("nan")
            opening = float(gap.iloc[pos]) if np.isfinite(gap.iloc[pos]) else float("nan")
            if np.isfinite(change) and abs(change) >= GAP_LIST:
                ratio = float(close.iloc[pos] / prev.iloc[pos])
                split_like = any(abs(ratio / factor - 1.0) <= 0.03 for factor in SPLIT_FACTORS)
                kind = "severe_gap" if abs(change) >= GAP_LIMIT else "large_gap"
                if split_like:
                    kind = "unhandled_split_candidate"
                rows.append({
                    "code": code,
                    "date": day_text,
                    "kind": kind,
                    "measure": round(change, 6),
                    "in_design_window": _in_design(day),
                    "in_ranking_pool": int(code in ranking_codes),
                    "detail": f"close/prev={ratio:.4f} open_gap={opening if np.isfinite(opening) else ''}",
                })
            elif np.isfinite(opening) and abs(opening) >= GAP_LIST and (not np.isfinite(change) or abs(change) < GAP_LIST):
                rows.append({
                    "code": code,
                    "date": day_text,
                    "kind": "large_open_gap",
                    "measure": round(opening, 6),
                    "in_design_window": _in_design(day),
                    "in_ranking_pool": int(code in ranking_codes),
                    "detail": "开盘相对前收的跳空。收盘涨跌没有过 20%。",
                })
        if len(frame) >= 3:
            change = ret.to_numpy(dtype=float)
            nxt = np.roll(change, -1)
            net = (1.0 + change) * (1.0 + nxt) - 1.0
            for pos in range(1, len(frame) - 1):
                if not np.isfinite(change[pos]) or not np.isfinite(nxt[pos]):
                    continue
                if abs(change[pos]) < ROUNDTRIP or change[pos] * nxt[pos] >= 0 or abs(net[pos]) >= ROUNDTRIP_NET:
                    continue
                day = pd.Timestamp(frame["date"].iloc[pos])
                rows.append({
                    "code": code,
                    "date": day.date().isoformat(),
                    "kind": "roundtrip_print",
                    "measure": round(float(change[pos]), 6),
                    "in_design_window": _in_design(day),
                    "in_ranking_pool": int(code in ranking_codes),
                    "detail": f"次日涨跌 {float(nxt[pos]):.4f}，两日合成 {float(net[pos]):.4f}。疑似坏点。",
                })
        for record in split_on.get(code, []):
            ex = pd.Timestamp(record.ex_date)
            after = frame[frame["date"] >= ex]
            before = frame[frame["date"] < ex]
            if after.empty or before.empty:
                observed = float("nan")
                used = ""
            else:
                observed = float(after["close"].iloc[0] / before["close"].iloc[-1])
                used = str(pd.Timestamp(after["date"].iloc[0]).date())
            expected = float(record.ratio_den) / float(record.ratio_num)
            if observed == observed and abs(observed / expected - 1.0) <= 0.05:
                kind = "split_visible_in_price"
                reading = "相邻收盘按拆分比例下跌，价格路径仍是未复权。"
            elif observed == observed and abs(observed - 1.0) <= 0.05:
                kind = "split_not_in_price"
                reading = "相邻收盘几乎没变。路径上看不到拆分缺口，不能再按 v4_event 复权一次。"
            else:
                kind = "split_price_mismatch"
                reading = "相邻收盘既不像未复权缺口，也不像已经复权。"
            rows.append({
                "code": code,
                "date": str(record.ex_date),
                "kind": kind,
                "measure": None if observed != observed else round(observed, 6),
                "in_design_window": _in_design(str(record.ex_date)),
                "in_ranking_pool": int(code in ranking_codes and _in_design(str(record.ex_date))),
                "detail": (
                    f"登记 {record.ratio}。未复权时期望收盘比约 {expected:.4f}，"
                    f"实际相邻收盘比 {observed if observed == observed else 'nan'}（K线日 {used}）。"
                    f"{reading} 该日不在 2006–2015，不进入本次排名。"
                ),
            })
    # 四个分类指数彼此差一天时列出来。
    dates = {code: set(pd.to_datetime(_native_frame(con, code)["date"]).dt.strftime("%Y-%m-%d"))
             for code in ("HSF", "HSU", "HSC")}
    if dates["HSF"] and dates["HSU"]:
        only = sorted(dates["HSF"] - dates["HSU"] - dates["HSC"])
        for day in only:
            rows.append({
                "code": "HSF", "date": day, "kind": "extra_session", "measure": 1,
                "in_design_window": _in_design(day), "in_ranking_pool": 1,
                "detail": "HSF 有这一天，HSU 和 HSC 没有。",
            })
    return rows


def _pair_stats(left: pd.Series, right: pd.Series) -> dict:
    joined = pd.concat([left.rename("l"), right.rename("r")], axis=1, sort=False).dropna()
    joined = joined[(joined.index <= END) & np.isfinite(joined["l"]) & np.isfinite(joined["r"])]
    joined = joined[(joined["l"] > -1.0) & (joined["r"] > -1.0)]
    n = int(len(joined))
    if n < 3:
        return {"n_days": n, "corr": "", "te_annual": "", "start": "", "end": ""}
    diff = joined["l"] - joined["r"]
    corr = float(joined["l"].corr(joined["r"]))
    te = float(diff.std(ddof=1) * np.sqrt(252.0))
    return {
        "n_days": n,
        "corr": round(corr, 6),
        "te_annual": round(te, 6),
        "start": joined.index.min().date().isoformat(),
        "end": joined.index.max().date().isoformat(),
    }


def _native_returns(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=float)
    close = pd.Series(frame["close"].to_numpy(dtype=float), index=pd.DatetimeIndex(frame["date"]))
    close = close[np.isfinite(close.to_numpy(dtype=float)) & (close.to_numpy(dtype=float) > 0)]
    close = close[~close.index.duplicated(keep="last")].sort_index()
    out = close.pct_change().iloc[1:]
    out = out[out.index <= END]
    return out


def _consistency(con) -> list[dict]:
    rows = []
    cache = {}

    def returns(code: str) -> pd.Series:
        if code not in cache:
            cache[code] = _native_returns(_native_frame(con, code))
        return cache[code]

    for etf, index, sector, basis in SECTOR_PAIRS:
        stats = _pair_stats(returns(etf), returns(index))
        rows.append({
            "pair_kind": "same_industry",
            "left_code": etf,
            "right_code": index,
            "sector": sector,
            "basis": basis,
            **stats,
            "note": "两边都是价格指数，不是全收益。XLRE 2015-10-08 才有 K 线，设计期重叠很短。Select Sector 有个股权重上限，官方行业指数没有。",
        })
    broad = returns("^SP500TR")
    for _name, code, label in NEW_US:
        if code == "XLC":
            continue
        stats = _pair_stats(returns(code), broad)
        rows.append({
            "pair_kind": "broad_sanity",
            "left_code": code,
            "right_code": "^SP500TR",
            "sector": label,
            "basis": "etf_price_vs_spx_total_return",
            **stats,
            "note": "不是同行业对照。标普行业指数没有日线时，用来看这条 ETF 价格收益是不是完全不像美股。",
        })
    hsi = returns("HSI")
    for _name, code, label in NEW_HK:
        stats = _pair_stats(returns(code), hsi)
        rows.append({
            "pair_kind": "hk_vs_hsi",
            "left_code": code,
            "right_code": "HSI",
            "sector": label,
            "basis": "price_vs_price_hkd",
            **stats,
            "note": "港币价格指数对恒生价格指数。不是 GICS 对照。",
        })
    return rows


def _yields(con, events: pd.DataFrame) -> list[dict]:
    rows = []
    if events.empty:
        return rows
    for _name, code, _label in NEW_US:
        subset = events[(events["code"] == code) & (events["kind"] == "dividend")].copy()
        if subset.empty:
            rows.append({
                "code": code, "n": 0, "sum_simple_yield": 0, "first_ex": "", "last_ex": "",
                "window": f"{START_TEXT}:{END_TEXT}",
            })
            continue
        subset["ex_date"] = pd.to_datetime(subset["ex_date"])
        window = subset[(subset["ex_date"] >= START_TEXT) & (subset["ex_date"] <= END)]
        block = _native_frame(con, code)
        block = block[block["date"] <= END]
        yields = _dividend_yields(block, window.rename(columns={}))
        # _dividend_yields 需要列 ex_date, amount。window 已有。
        rows.append({
            "code": code,
            "n": len(yields),
            "sum_simple_yield": round(float(sum(yields.values())), 6) if yields else 0,
            "first_ex": min(yields).date().isoformat() if yields else "",
            "last_ex": max(yields).date().isoformat() if yields else "",
            "window": f"{START_TEXT}:{END_TEXT}",
        })
    return rows


def _summary(coverage, month_rows, cap_rows, yields, consistency) -> dict:
    def sel(pool, year, market, field):
        for row in coverage:
            if row["pool"] == pool and row["year"] == year and row["market"] == market:
                return row[field]
        return None

    years = list(range(2006, 2016))
    coverage_view = []
    for pool in ("old", "new"):
        for year in years:
            item = {"pool": pool, "year": year}
            for market in MARKETS:
                item[market] = {
                    "roster": sel(pool, year, market, "roster"),
                    "selectable_20": sel(pool, year, market, "selectable_20"),
                    "selectable_250": sel(pool, year, market, "selectable_250"),
                    "min": sel(pool, year, market, "selectable_20_min"),
                    "max": sel(pool, year, market, "selectable_20_max"),
                }
            coverage_view.append(item)
    frame = pd.DataFrame(month_rows)
    headline = []
    grouped = frame.groupby(["pool", "year", "n", "market"], as_index=False)[["count", "share"]].mean()
    for record in grouped.itertuples(index=False):
        headline.append({
            "pool": record.pool,
            "year": int(record.year),
            "n": int(record.n),
            "market": record.market,
            "mean_count": round(float(record.count), 4),
            "mean_share": round(float(record.share), 4),
        })
    halves = []
    frame = frame.copy()
    frame["half"] = np.where(frame["year"] <= 2010, "2006-2010", "2011-2015")
    half_group = frame.groupby(["pool", "half", "n", "market"], as_index=False)[["count", "share"]].mean()
    for record in half_group.itertuples(index=False):
        halves.append({
            "pool": record.pool,
            "half": record.half,
            "n": int(record.n),
            "market": record.market,
            "mean_count": round(float(record.count), 4),
            "mean_share": round(float(record.share), 4),
        })
    return {
        "end": END_TEXT,
        "coverage": coverage_view,
        "headline": headline,
        "halves": halves,
        "us_broad_top2": cap_rows,
        "dividend_yield_sum": yields,
        "consistency": consistency,
    }


def main() -> None:
    _die_on_args()
    if not DB.exists() or DB.stat().st_size < 1000:
        raise SystemExit(f"行情库不可读：{DB}")
    digest = _sha256(DB)
    print(f"db_sha256 {digest}", flush=True)
    spec = load_spec()
    if pd.Timestamp(spec.design_end) != END:
        raise RuntimeError("arms.toml 的设计期结束日不是 2015-12-31")
    members = pool_members(load_containers(), "A", "index")
    meta = _meta(members)
    print("load_market", flush=True)
    market = load_market(DB, load_containers(), "A", "index", END_TEXT, spec, history_mode=OFFICIAL)
    _assert_end(market.dates, "calendar")
    if market.cash_id not in market.signal.columns:
        raise RuntimeError("没有现金列")
    old_names = [name for name in market.names if name in meta]
    con = _connect(DB)
    try:
        fx = _fx(con, END_TEXT)
        divs = _cash_divs(con, END_TEXT)
        codes = [code for _name, code, _label in (*NEW_US, *NEW_HK)]
        codes += ["HSI", "XNDX", "^SP500TR", "SP500-60"]
        bars = _load_bars(con, codes, END_TEXT)
        events = pd.read_sql_query(
            "SELECT code, kind, ex_date, amount, ratio_num, ratio_den, ratio FROM v4_event",
            con)
        _parity(market, bars, divs, market.dates, fx, spec)
        new_sig, new_fresh, _unused = _build_new(market.dates, fx, spec, bars, events, adjust_div=False)
        div_sig, div_flags, gap_days = _build_new(market.dates, fx, spec, bars, events, adjust_div=True)
        print("dividend_adjusted_gap_days", {key: value for key, value in gap_days.items() if value}, flush=True)
        ranking_codes = {code for _name, code, _label in (*NEW_US, *NEW_HK) if code != "XLC"}
        ranking_codes |= {"HSI", "XNDX", "^SP500TR"}
        quality = _quality(con, ranking_codes, events[events["kind"] == "split"] if not events.empty else events)
        consistency = _consistency(con)
        yields = _yields(con, events)
    finally:
        con.close()

    signal = market.signal.copy()
    fresh = market.liquidity.reindex(index=signal.index).fillna(False).astype(bool).copy()
    for name, series in new_sig.items():
        signal[name] = series.reindex(signal.index)
        fresh[name] = new_fresh[name].reindex(signal.index).fillna(False).astype(bool)
    div_signal = signal.copy()
    div_panel_fresh = fresh.copy()
    for name, series in div_sig.items():
        div_signal[name] = series.reindex(div_signal.index)
        div_panel_fresh[name] = div_flags[name].reindex(div_signal.index).fillna(False).astype(bool)
    _assert_end(signal.index, "signal")
    _assert_end(div_signal.index, "div_signal")

    ranked_new = [name for name, _code, _label in (*NEW_US, *NEW_HK) if name in new_sig]
    roster_new = old_names + [name for name, _code, _label in (*NEW_US, *NEW_HK)]
    pools = {"old": old_names, "new": roster_new}
    days = decision_dates(market.dates, "month")
    days = days[(days >= START_TEXT) & (days <= END)]
    if len(days) != 120:
        raise RuntimeError(f"月末决策日不是 120 个，而是 {len(days)}")
    year_ends = _year_ends(days)
    if set(year_ends) != set(range(2006, 2016)):
        raise RuntimeError(f"缺少年末：{sorted(year_ends)}")
    missing = [name for name in old_names + ranked_new if name not in fresh.columns]
    if missing:
        raise RuntimeError(f"fresh 缺列 {missing[:8]}")
    coverage = _coverage(meta, pools, fresh, signal, days, year_ends)
    names = _name_rows(meta, pools, fresh, signal, year_ends)
    signal_by_pool = {
        "old": signal,
        "new": signal,
        "new_plus_div": div_signal,
    }
    fresh_by_pool = {"old": fresh, "new": fresh, "new_plus_div": div_panel_fresh}
    struct_pools = {
        "old": old_names,
        "new": old_names + ranked_new,
        "new_plus_div": old_names + ranked_new,
    }
    print("rank", flush=True)
    month_rows, selections, cap_rows = _structure(meta, struct_pools, fresh_by_pool, signal_by_pool, days, spec)
    summary = _summary(coverage, month_rows, cap_rows, yields, consistency)
    rev = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    summary["db_sha256"] = digest
    summary["git_head"] = rev
    summary["months"] = 120
    summary["method"] = {
        "pool": "v3.1 U-指数 arm=A history=official",
        "lookbacks": list(LOOKBACKS),
        "rank": "s desc, R desc, id asc; R>cash; fresh stale_limit=5",
        "new_us": "未复权收盘 × USDCNY，D 用严格早于 D 的美股 K 线",
        "new_hk": "与恒生指数相同，腾讯价格指数，不乘 HKDCNY",
        "new_plus_div": "只把 v4_event 里 ≤2015-12-31 的现金分红按 total_return_close 加进 SPDR，再乘 USDCNY",
        "excluded": [
            "11 个标普行业全收益：没有日线",
            "SP500-60：核对序列，不进排名",
            "恒生综合行业 12 个：没有日线",
            "四个分类指数总收益：2021-04 起，不进设计期排名",
            "XLC：2018-06-19 起，登记但设计期可选为 0",
        ],
    }
    _write(OUT / "explore-coverage.csv", coverage, [
        "year", "pool", "market", "roster", "selectable_20", "selectable_250",
        "selectable_20_min", "selectable_20_max",
    ])
    _write(OUT / "explore-names.csv", names, [
        "year", "pool", "name", "market", "asset_class", "label", "selectable_20", "selectable_250",
    ])
    _write(OUT / "explore-structure-month.csv", month_rows, [
        "date", "year", "pool", "lookback", "n", "market", "count", "share", "eligible",
    ])
    _write(OUT / "explore-selections.csv", selections, [
        "date", "pool", "lookback", "rank", "name", "market",
    ])
    _write(OUT / "explore-us-broad-top2.csv", cap_rows, [
        "year", "pool", "lookback", "months", "both_broad_in_top2", "rate",
    ])
    _write(OUT / "explore-quality.csv", quality, [
        "code", "date", "kind", "measure", "in_design_window", "in_ranking_pool", "detail",
    ])
    _write(OUT / "explore-consistency.csv", consistency, [
        "pair_kind", "left_code", "right_code", "sector", "basis",
        "n_days", "corr", "te_annual", "start", "end", "note",
    ])
    _write(OUT / "explore-dividend-yield.csv", yields, [
        "code", "n", "sum_simple_yield", "first_ex", "last_ex", "window",
    ])
    (OUT / "explore-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if any(row["date"] > END_TEXT for row in month_rows):
        raise RuntimeError("排名用了设计期之后的日期")
    if any(row.get("end") and row["end"] > END_TEXT for row in consistency):
        raise RuntimeError("跟踪差用了设计期之后的日期")
    print(f"wrote {OUT}", flush=True)
    kinds = Counter((row["kind"], row["in_design_window"]) for row in quality)
    print("quality", dict(kinds), flush=True)
    for row in coverage:
        if row["pool"] in {"old", "new"} and row["year"] in {2006, 2008, 2011, 2015}:
            print("cov", row, flush=True)


if __name__ == "__main__":
    main()
