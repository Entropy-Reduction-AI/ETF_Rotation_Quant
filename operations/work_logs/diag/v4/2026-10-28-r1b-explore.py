"""v4-R1b 数据探索。只描述，不算组合收益。

结束日写死为 2015-12-31。没有命令行参数。
不读取 2016-01-01 之后的价格来计算收益、跟踪差、名额或 IC。
后复权序列里 2016 年以后的公司行为，对两条都落在设计期内的价格比会约掉，
所以设计期内的收益不含 2016 年以后的分红或拆分。

名额的原始口径沿用 R1 第 4 节（v3.1 的 R / s / 现金过滤）。
IC 沿用 Orchestrator 的价格比、秩相关和 2% 现金门槛。
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.v3.data.universe import containers as load_containers
from src.v3.engine.benchmark import _fx
from src.v3.engine.market import _research_level, _usd_level, load_market
from src.v3.engine.score import lookback_panel
from src.v3.engine.spec import load_spec
from src.v3.engine.universe import research_code
from src.v3.data.history import OFFICIAL

END = pd.Timestamp("2015-12-31")
END_TEXT = "2015-12-31"
START_TEXT = "2006-01-01"
DB = ROOT / "data" / "market.sqlite"
OUT = ROOT / "results" / "v4" / "inventory"
EXPECTED_SHA = "af4c5a376d084cd6254187c1107c6179d0cfd9647c008bff84b4c26f52045b78"
LOOKBACKS_IC = (5, 10, 20, 40, 60, 90, 120, 180, 250)
BLEND_LENGTHS = (20, 60, 120, 250)
FORWARD = 20
CASH_ANNUAL = 0.02
BASELINE_IC = {"20": 0.093, "60": 0.028, "120": -0.004, "250": 0.049, "blend": 0.069}

# R1 所说的 14 个 A 股容器。创业板指没有研究序列，科创50 从 2019 年起，都不在这 14 个里。
A14 = (
    "csi300", "csi500", "csi1000",
    "allshare-energy", "allshare-materials", "allshare-industrials",
    "allshare-discretionary", "allshare-staples", "allshare-healthcare",
    "allshare-financials-re", "allshare-it", "allshare-communication",
    "allshare-utilities", "csi-dividend",
)
A14_NAME = {
    "csi300": "沪深300", "csi500": "中证500", "csi1000": "中证1000",
    "allshare-energy": "中证全指能源", "allshare-materials": "中证全指原材料",
    "allshare-industrials": "中证全指工业", "allshare-discretionary": "中证全指可选消费",
    "allshare-staples": "中证全指主要消费", "allshare-healthcare": "中证全指医药卫生",
    "allshare-financials-re": "中证全指金融地产", "allshare-it": "中证全指信息技术",
    "allshare-communication": "中证全指通信服务", "allshare-utilities": "中证全指公用事业",
    "csi-dividend": "中证红利",
}
# 概况页上的跟踪标的 → 容器。名称必须全称一致，不用简称猜测。
EXACT_TRACK = {
    "沪深300指数": "csi300",
    "中证500指数": "csi500",
    "中证1000指数": "csi1000",
    "中证红利指数": "csi-dividend",
    "中证全指能源指数": "allshare-energy",
    "中证全指原材料指数": "allshare-materials",
    "中证全指工业指数": "allshare-industrials",
    "中证全指可选消费指数": "allshare-discretionary",
    "中证全指主要消费指数": "allshare-staples",
    "中证全指医药卫生指数": "allshare-healthcare",
    "中证全指金融地产指数": "allshare-financials-re",
    "中证全指信息技术指数": "allshare-it",
    "中证全指通信服务指数": "allshare-communication",
    "中证全指公用事业指数": "allshare-utilities",
}
# 库里有日线的是全收益指数。价格指数 000300 等没有入库。
TRACKED_RESEARCH = {
    "沪深300指数": "H00300",
    "中证500指数": "H00905",
    "中证红利指数": "H00922",
}
CONTAINER_RESEARCH = {
    "csi300": "H00300",
    "csi500": "H00905",
    "csi-dividend": "H00922",
    "allshare-financials-re": "H00992",
}
SEVENTEEN = {
    "H00300", "H00905", "H00852", "H00922",
    "H00986", "H00987", "H00988", "H00989", "H00990", "H00991", "H00992",
    "H00993", "H00994", "H00995", "HSI", "XNDX", "^SP500TR",
}
LAB2_A = {
    "H00300": "沪深300", "H00905": "中证500", "H00852": "中证1000", "H00922": "中证红利",
    "H00986": "能源", "H00987": "原材料", "H00988": "工业", "H00989": "可选消费",
    "H00990": "主要消费", "H00991": "医药", "H00992": "金融地产", "H00993": "信息技术",
    "H00994": "通信", "H00995": "公用事业",
}


def _die_on_args() -> None:
    if len(sys.argv) > 1:
        raise SystemExit("这个脚本没有参数。结束日写死为 2015-12-31。")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_r1():
    path = ROOT / "operations/work_logs/diag/v4/2026-10-28-r1-explore.py"
    spec = importlib.util.spec_from_file_location("r1_explore", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _assert_not_after(dates, label: str) -> None:
    if len(dates) == 0:
        return
    last = pd.Timestamp(max(pd.Timestamp(day) for day in dates))
    if last > END:
        raise RuntimeError(f"{label} 含有 {last.date()}，晚于 {END.date()}")


def _cash_threshold(length: int) -> float:
    return (1.0 + CASH_ANNUAL / 252.0) ** length - 1.0


def _first_positive(con: sqlite3.Connection, code: str) -> str:
    row = con.execute(
        "SELECT MIN(date) FROM bars WHERE code=? AND adj='raw' AND close>0",
        (code,),
    ).fetchone()
    return "" if row is None or row[0] is None else str(row[0])


def _series_close(con: sqlite3.Connection, sql: str, params: tuple) -> pd.Series:
    frame = pd.read_sql_query(sql, con, params=params)
    if frame.empty:
        return pd.Series(dtype=float)
    frame["date"] = pd.to_datetime(frame["date"])
    close = pd.to_numeric(frame["close"], errors="coerce")
    series = pd.Series(close.to_numpy(dtype=float), index=pd.DatetimeIndex(frame["date"]))
    series = series[np.isfinite(series.to_numpy(dtype=float)) & (series.to_numpy(dtype=float) > 0)]
    series = series[~series.index.duplicated(keep="last")].sort_index()
    series = series[series.index <= END]
    _assert_not_after(series.index, "close")
    return series


def _daily_returns(close: pd.Series) -> pd.Series:
    if close.empty:
        return close
    out = close.pct_change().iloc[1:]
    out = out[np.isfinite(out.to_numpy(dtype=float)) & (out.to_numpy(dtype=float) > -1.0)]
    _assert_not_after(out.index, "return")
    return out


def _pair_stats(left: pd.Series, right: pd.Series) -> dict:
    joined = pd.concat([left.rename("l"), right.rename("r")], axis=1, sort=False).dropna()
    joined = joined[(joined.index <= END) & np.isfinite(joined["l"]) & np.isfinite(joined["r"])]
    joined = joined[(joined["l"] > -1.0) & (joined["r"] > -1.0)]
    n = int(len(joined))
    if n < 3:
        return {"n_days": n, "corr": "", "te_annual": "", "bias_annual": "", "start": "", "end": ""}
    diff = joined["l"] - joined["r"]
    return {
        "n_days": n,
        "corr": round(float(joined["l"].corr(joined["r"])), 6),
        "te_annual": round(float(diff.std(ddof=1) * np.sqrt(252.0)), 6),
        "bias_annual": round(float(diff.mean() * 252.0), 6),
        "start": joined.index.min().date().isoformat(),
        "end": joined.index.max().date().isoformat(),
    }


def _coverage(con: sqlite3.Connection, containers: list[dict], year_ends: dict[int, pd.Timestamp]):
    exact = []
    mismatched = []
    for container in containers:
        for execution in container.get("execution") or []:
            track = str(execution.get("track") or "")
            code = str(execution.get("code") or "")
            first = _first_positive(con, code)
            item = {
                "container_id": str(container.get("id")),
                "code": code,
                "name": str(execution.get("name") or ""),
                "track": track,
                "list_date": str(execution.get("list_date") or ""),
                "first_bar": first,
            }
            if track in EXACT_TRACK and EXACT_TRACK[track] == container.get("id"):
                exact.append(item)
            elif str(container.get("id")) in A14:
                mismatched.append(item)
    listings = pd.read_sql_query(
        "SELECT code, name, maps_to, tracked_index, inception, enhanced, note FROM v4_listing",
        con,
    )
    first_nav = dict(con.execute(
        "SELECT code, MIN(date) FROM v4_series WHERE kind='otc_nav' AND close>0 GROUP BY code"
    ))
    detail = []
    summary = []
    for year, year_end in year_ends.items():
        counts = {"etf": 0, "otc_only": 0, "neither": 0}
        for container_id in A14:
            etfs = []
            for item in exact:
                if item["container_id"] != container_id or not item["first_bar"]:
                    continue
                if item["first_bar"] <= year_end.date().isoformat():
                    etfs.append(item)
            funds = []
            for record in listings.itertuples(index=False):
                if record.maps_to != container_id:
                    continue
                started = str(record.inception or "")
                nav = str(first_nav.get(record.code) or "")
                if started and started <= year_end.date().isoformat() and nav and nav <= year_end.date().isoformat():
                    funds.append(record)
            if etfs:
                bucket = "etf"
            elif funds:
                bucket = "otc_only"
            else:
                bucket = "neither"
            counts[bucket] += 1
            notes = []
            if any(record.tracked_index not in EXACT_TRACK for record in funds):
                notes.append("场外基金跟踪的是相近指数，不是这个容器的指数。")
            if container_id == "csi-dividend":
                notes.append("510880 跟踪上证红利，不计入中证红利的场内 ETF。")
            detail.append({
                "year": year,
                "container_id": container_id,
                "container_name": A14_NAME[container_id],
                "bucket": bucket,
                "etf_codes": " ".join(item["code"] for item in etfs),
                "etf_first": min((item["first_bar"] for item in etfs), default=""),
                "otc_codes": " ".join(str(record.code) for record in funds),
                "otc_n": len(funds),
                "otc_near": int(any(str(record.tracked_index) not in EXACT_TRACK for record in funds)),
                "note": "".join(notes),
            })
        if sum(counts.values()) != 14:
            raise RuntimeError(f"{year} 覆盖不是 14 个容器：{counts}")
        summary.append({"year": year, **counts, "containers": 14})
    return detail, summary, exact, mismatched


def _tracking(con: sqlite3.Connection) -> list[dict]:
    listings = pd.read_sql_query(
        "SELECT code, name, maps_to, tracked_index, inception, enhanced, note FROM v4_listing ORDER BY maps_to, code",
        con,
    )
    cache: dict[str, pd.Series] = {}

    def index_returns(code: str) -> pd.Series:
        if code not in cache:
            close = _series_close(
                con,
                "SELECT date, close FROM bars WHERE code=? AND adj='raw' AND date<=? AND close>0 ORDER BY date",
                (code, END_TEXT),
            )
            cache[code] = _daily_returns(close)
        return cache[code]

    rows = []
    for record in listings.itertuples(index=False):
        fund_close = _series_close(
            con,
            "SELECT date, close FROM v4_series WHERE code=? AND kind='otc_nav' AND date<=? AND close>0 ORDER BY date",
            (record.code, END_TEXT),
        )
        fund = _daily_returns(fund_close)
        tracked = str(record.tracked_index)
        research = TRACKED_RESEARCH.get(tracked, "")
        container_code = CONTAINER_RESEARCH.get(str(record.maps_to), "")
        if research:
            stats = _pair_stats(fund, index_returns(research))
            basis = "tracked_name_but_total_return_series"
        else:
            stats = {"n_days": 0, "corr": "", "te_annual": "", "bias_annual": "", "start": "", "end": ""}
            basis = "tracked_index_not_in_db"
        near_stats = {"n_days": "", "corr": "", "te_annual": "", "bias_annual": "", "start": "", "end": ""}
        if container_code and container_code != research:
            near_stats = _pair_stats(fund, index_returns(container_code))
        if stats.get("end") and stats["end"] > END_TEXT:
            raise RuntimeError("跟踪差用了设计期之后的日期")
        rows.append({
            "code": record.code,
            "name": record.name,
            "maps_to": record.maps_to,
            "tracked_index": tracked,
            "enhanced": int(record.enhanced),
            "feeder": int("联接" in str(record.note)),
            "inception": record.inception,
            "index_code": research,
            "index_basis": basis,
            **{f"tracked_{key}" if key != "n_days" else "n_days": value for key, value in stats.items()},
            "near_index_code": container_code if container_code != research else "",
            "near_te_annual": near_stats.get("te_annual", ""),
            "near_corr": near_stats.get("corr", ""),
            "near_n_days": near_stats.get("n_days", ""),
            "note": record.note,
        })
    return rows


def _backward_frame(con: sqlite3.Connection, code: str) -> pd.DataFrame:
    frame = pd.read_sql_query(
        "SELECT date, open, close FROM v4_series WHERE code=? AND kind='backward' AND date<=? ORDER BY date",
        con,
        params=(code, END_TEXT),
    )
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"])
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["open"] = pd.to_numeric(frame["open"], errors="coerce")
    frame = frame[frame["close"] > 0]
    _assert_not_after(frame["date"], f"{code} backward")
    return frame


def _level_to_signal(level: pd.Series, fresh: pd.Series, calendar: pd.DatetimeIndex):
    from src.v3.engine.prices import signal_returns
    series = signal_returns(level, pd.DatetimeIndex([])).reindex(calendar)
    flag = fresh.reindex(calendar).fillna(False).astype(bool)
    finite = series.dropna()
    if len(finite) and pd.Timestamp(finite.index.max()) > END:
        raise RuntimeError("信号晚于设计期")
    return series, flag


def _build_adjusted_us(con, calendar, fx, spec, r1):
    signals = {}
    fresh = {}
    levels = {}
    excluded = []
    for name, code, label in r1.NEW_US:
        exists = con.execute(
            "SELECT MIN(date), COUNT(*) FROM v4_series WHERE code=? AND kind='backward'",
            (code,),
        ).fetchone()
        block = _backward_frame(con, code)
        if block.empty:
            reason = "no_backward_series" if not exists or not exists[1] else "backward_exists_but_no_design_period_print"
            excluded.append({
                "code": code,
                "name": name,
                "role": "pool_etf",
                "reason": reason,
                "first_date": "" if not exists or exists[0] is None else str(exists[0]),
                "in_paired_rank": 0,
            })
            continue
        level, flag, _gaps = _usd_level(block, fx, calendar, spec.stale_limit, None)
        series, flag = _level_to_signal(level, flag, calendar)
        if int(series.notna().sum()) == 0:
            excluded.append({
                "code": code,
                "name": name,
                "role": "pool_etf",
                "reason": "backward_exists_but_no_design_period_print",
                "first_date": pd.Timestamp(block["date"].iloc[0]).date().isoformat(),
                "in_paired_rank": 0,
            })
            continue
        signals[name] = series
        fresh[name] = flag
        levels[name] = level.reindex(calendar)
        excluded.append({
            "code": code,
            "name": name,
            "role": "pool_etf",
            "reason": "has_backward_used",
            "first_date": pd.Timestamp(block["date"].iloc[0]).date().isoformat(),
            "in_paired_rank": 1,
        })
    return signals, fresh, levels, excluded


def _outside_missing_adj(con: sqlite3.Connection) -> list[dict]:
    rows = []
    have = {row[0] for row in con.execute("SELECT DISTINCT code FROM v4_series WHERE kind='backward'")}
    query = con.execute(
        "SELECT code, MIN(date), MAX(date), COUNT(*) FROM bars "
        "WHERE adj='raw' AND source='tencent_etf' GROUP BY code ORDER BY code"
    )
    for code, first, last, count in query:
        if code in have:
            continue
        rows.append({
            "code": code,
            "name": "",
            "role": "outside_pool",
            "reason": "no_backward_series",
            "first_date": first,
            "last_date": last,
            "rows": count,
            "in_design_period": int(str(first) <= END_TEXT),
            "in_paired_rank": 0,
        })
    return rows


def _annual_shares(month_rows: list[dict], pool: str) -> pd.DataFrame:
    frame = pd.DataFrame(month_rows)
    frame = frame[frame["pool"] == pool]
    grouped = frame.groupby(["year", "n", "market"], as_index=False)["share"].mean()
    return grouped


def _check_raw_against_r1(month_rows: list[dict]) -> None:
    saved = pd.read_csv(OUT / "explore-structure-month.csv")
    saved = saved[saved["pool"] == "new"]
    mine = pd.DataFrame(month_rows)
    mine = mine[mine["pool"] == "raw"]
    keys = ["date", "lookback", "n", "market"]
    merged = saved.merge(mine, on=keys, how="outer", indicator=True)
    if not (merged["_merge"] == "both").all():
        missing = merged[merged["_merge"] != "both"].head(8)
        raise RuntimeError(f"原始口径和 R1 名额表对不齐\n{missing.to_string(index=False)}")
    if not (merged["count_x"] == merged["count_y"]).all():
        bad = merged[merged["count_x"] != merged["count_y"]].head(8)
        raise RuntimeError(f"原始口径名额和 R1 不一致\n{bad.to_string(index=False)}")
    print(f"raw shares match R1 month file rows={len(merged)}", flush=True)


def _share_diff(month_rows: list[dict]) -> list[dict]:
    raw = _annual_shares(month_rows, "raw").rename(columns={"share": "raw_share"})
    adj = _annual_shares(month_rows, "adj").rename(columns={"share": "adj_share"})
    merged = raw.merge(adj, on=["year", "n", "market"], how="outer")
    rows = []
    for record in merged.itertuples(index=False):
        raw_share = float(record.raw_share)
        adj_share = float(record.adj_share)
        rows.append({
            "year": int(record.year),
            "n": int(record.n),
            "market": record.market,
            "raw_share": round(raw_share, 6),
            "adj_share": round(adj_share, 6),
            "diff_share": round(adj_share - raw_share, 6),
        })
    return rows


def _half_diff(month_rows: list[dict]) -> list[dict]:
    frame = pd.DataFrame(month_rows)
    frame = frame[frame["pool"].isin(["raw", "adj"])]
    frame["half"] = np.where(frame["year"] <= 2010, "2006-2010", "2011-2015")
    grouped = frame.groupby(["pool", "half", "n", "market"], as_index=False)["share"].mean()
    raw = grouped[grouped["pool"] == "raw"].rename(columns={"share": "raw_share"})
    adj = grouped[grouped["pool"] == "adj"].rename(columns={"share": "adj_share"})
    merged = raw.merge(adj, on=["half", "n", "market"])
    rows = []
    for record in merged.itertuples(index=False):
        rows.append({
            "half": record.half,
            "n": int(record.n),
            "market": record.market,
            "raw_share": round(float(record.raw_share), 6),
            "adj_share": round(float(record.adj_share), 6),
            "diff_share": round(float(record.adj_share) - float(record.raw_share), 6),
        })
    return rows


def _rank_ic(levels: pd.DataFrame) -> pd.DataFrame:
    """Orchestrator ic.py 的截面 Rank IC。未来 20 日停在样本最后一天之内。"""
    frame = levels.sort_index()
    frame = frame[frame.index <= END]
    _assert_not_after(frame.index, "ic levels")
    returns = frame.pct_change()
    month_end = frame.index.to_series().groupby(frame.index.to_period("M")).last()
    dates = [pd.Timestamp(day) for day in month_end.to_numpy() if pd.Timestamp(day) >= pd.Timestamp(START_TEXT)]
    rows = []
    for day in dates:
        k = int(frame.index.get_loc(day))
        if k + FORWARD >= len(frame) or k < 250:
            continue
        if pd.Timestamp(frame.index[k + FORWARD]) > END or pd.Timestamp(frame.index[k]) > END:
            raise RuntimeError("IC 的未来收益离开了设计期")
        forward = frame.iloc[k + FORWARD] / frame.iloc[k] - 1.0
        row: dict = {"date": day}
        blend = []
        for length in LOOKBACKS_IC:
            if k < length:
                row[str(length)] = np.nan
                row[f"n_{length}"] = 0
                continue
            window_return = frame.iloc[k] / frame.iloc[k - length] - 1.0
            scale = returns.iloc[k - length + 1:k + 1].std(ddof=1) * np.sqrt(length)
            score = window_return / scale
            ok = score.notna() & forward.notna() & np.isfinite(score.to_numpy(dtype=float)) & np.isfinite(
                forward.to_numpy(dtype=float))
            row[f"n_{length}"] = int(ok.sum())
            row[str(length)] = (
                float(score[ok].rank().corr(forward[ok].rank())) if int(ok.sum()) >= 2 else np.nan
            )
            if length in BLEND_LENGTHS:
                blend.append(score.rank())
        blended = pd.concat(blend, axis=1).mean(axis=1)
        ok = blended.notna() & forward.notna()
        row["n_blend"] = int(ok.sum())
        row["blend"] = float(blended[ok].rank().corr(forward[ok].rank())) if int(ok.sum()) >= 2 else np.nan
        rows.append(row)
    out = pd.DataFrame(rows).set_index("date")
    _assert_not_after(out.index, "ic dates")
    return out


def _beat_cash(levels: pd.DataFrame) -> list[dict]:
    """过了平坦 2% 现金门槛的名字，之后 20 日平均收益减去没过的。"""
    frame = levels.sort_index()
    frame = frame[frame.index <= END]
    month_end = frame.index.to_series().groupby(frame.index.to_period("M")).last()
    dates = [pd.Timestamp(day) for day in month_end.to_numpy() if pd.Timestamp(day) >= pd.Timestamp(START_TEXT)]
    rows = []
    for length in LOOKBACKS_IC:
        diffs = []
        hits = []
        for day in dates:
            k = int(frame.index.get_loc(day))
            if k < length or k + FORWARD >= len(frame):
                continue
            if pd.Timestamp(frame.index[k + FORWARD]) > END:
                raise RuntimeError("门槛检验离开了设计期")
            past = frame.iloc[k] / frame.iloc[k - length] - 1.0
            forward = frame.iloc[k + FORWARD] / frame.iloc[k] - 1.0
            ok = past.notna() & forward.notna()
            passed = past[ok] > _cash_threshold(length)
            if int(passed.sum()) > 0 and int((~passed).sum()) > 0:
                diffs.append(float(forward[ok][passed].mean() - forward[ok][~passed].mean()))
            hits.append(float(((forward[ok] > _cash_threshold(FORWARD)) == passed).mean()))
        diff = np.asarray(diffs, dtype=float)
        rows.append({
            "length": length,
            "spread_pct": round(float(diff.mean() * 100.0), 4) if len(diff) else "",
            "t": round(float(diff.mean() / diff.std(ddof=1) * np.sqrt(len(diff))), 4) if len(diff) > 2 else "",
            "hit": round(float(np.mean(hits) * 100.0), 4) if hits else "",
            "n_months": int(len(diff)),
        })
    return rows


def _ic_summary(ic: pd.DataFrame) -> list[dict]:
    rows = []
    columns = [str(length) for length in LOOKBACKS_IC] + ["blend"]
    for column in columns:
        series = ic[column].dropna()
        yearly = ic[column].groupby(ic.index.year).mean()
        t_value = float(series.mean() / series.std(ddof=1) * np.sqrt(series.count())) if series.count() > 2 else np.nan
        count_col = "n_blend" if column == "blend" else f"n_{column}"
        mean_names = float(ic[count_col].mean()) if count_col in ic.columns else float("nan")
        rows.append({
            "length": column,
            "mean_ic": round(float(series.mean()), 6),
            "t": round(t_value, 4),
            "pos_frac": round(float((series > 0).mean()), 4),
            "n_months": int(series.count()),
            "mean_names": round(mean_names, 2),
            "half_2006_2010": round(float(ic.loc["2006":"2010", column].mean()), 6),
            "half_2011_2015": round(float(ic.loc["2011":"2015", column].mean()), 6),
            "year_autocorr": round(float(yearly.autocorr()), 4) if yearly.count() > 3 else "",
        })
    return rows


def _ic_contrast(summary_rows: list[dict]) -> dict:
    by_length = {row["length"]: row["mean_ic"] for row in summary_rows}
    out = {}
    for key, baseline in BASELINE_IC.items():
        got = float(by_length[key])
        out[key] = {
            "new_pool": round(got, 6),
            "baseline_rounded": baseline,
            "rounded_3dp": round(got, 3),
            "minus_baseline": round(got - baseline, 6),
        }
    return out


def _lab2_levels(con: sqlite3.Connection) -> pd.DataFrame:
    """照 Orchestrator lab2.py 重建 17 个指数的价格，用来核对 IC 函数。"""

    def closes(code: str) -> pd.Series:
        frame = pd.read_sql_query(
            "SELECT date, close FROM bars WHERE code=? ORDER BY date",
            con,
            params=(code,),
        )
        frame["date"] = pd.to_datetime(frame["date"])
        series = pd.Series(pd.to_numeric(frame["close"], errors="coerce").to_numpy(dtype=float),
                           index=pd.DatetimeIndex(frame["date"]))
        series = series[~series.index.duplicated(keep="last")].sort_index()
        return series

    calendar = closes("H00300").loc["2005-01-01":END_TEXT].index
    fx = closes("USDCNY")
    levels = {}
    for code, name in LAB2_A.items():
        levels[name] = closes(code)
    def usd(series: pd.Series) -> pd.Series:
        shifted = series.copy()
        shifted.index = shifted.index + pd.Timedelta(days=1)
        shifted = shifted.reindex(calendar, method="ffill")
        rate = fx.reindex(calendar, method="ffill")
        return shifted * rate
    levels["恒生指数"] = usd(closes("HSI"))
    levels["纳指100"] = usd(closes("XNDX"))
    levels["标普500"] = usd(closes("^SP500TR"))
    frame = pd.DataFrame({name: series.reindex(calendar, method="ffill") for name, series in levels.items()})
    for name, series in levels.items():
        first = series.dropna()
        first = first[first > 0]
        if first.empty:
            continue
        frame.loc[frame.index < first.index[0], name] = np.nan
    frame = frame.mask(frame <= 0)
    for name in frame.columns:
        first = frame[name].first_valid_index()
        if first is not None:
            frame.loc[first:, name] = frame.loc[first:, name].ffill()
    frame = frame[frame.index <= END]
    _assert_not_after(frame.index, "lab2")
    return frame


def _engine_levels(market, extra_levels: dict[str, pd.Series], extra_fresh: dict[str, pd.Series],
                   ids: list[str]) -> pd.DataFrame:
    frame = market.levels.reindex(columns=[name for name in ids if name in market.levels.columns]).copy()
    fresh = market.liquidity.reindex(index=frame.index).copy()
    for name, level in extra_levels.items():
        if name not in ids:
            continue
        frame[name] = level.reindex(frame.index)
        fresh[name] = extra_fresh[name].reindex(frame.index).fillna(False).astype(bool)
    keep = [name for name in ids if name in frame.columns]
    frame = frame.loc[:, keep]
    fresh = fresh.reindex(columns=keep).fillna(False).astype(bool)
    masked = frame.where(fresh)
    masked = masked[masked.index <= END]
    _assert_not_after(masked.index, "engine levels")
    return masked


def _seventeen_ids(members: list[dict]) -> list[str]:
    found = []
    for member in members:
        code = research_code(member)
        if code in SEVENTEEN:
            found.append(str(member["id"]))
    if len(found) != 17:
        raise RuntimeError(f"17 个指数对到了 {len(found)} 个容器：{found}")
    return found


def _dump_ic(panel: str, ic: pd.DataFrame, summary: list[dict], beat: list[dict], yearly_rows: list[dict]):
    for row in summary:
        row["panel"] = panel
    for row in beat:
        row["panel"] = panel
    yearly = ic.groupby(ic.index.year).mean(numeric_only=True)
    for year, record in yearly.iterrows():
        for column in [str(length) for length in LOOKBACKS_IC] + ["blend"]:
            value = record.get(column, np.nan)
            yearly_rows.append({
                "panel": panel,
                "year": int(year),
                "length": column,
                "mean_ic": "" if pd.isna(value) else round(float(value), 6),
            })
    return summary, beat


def main() -> None:
    _die_on_args()
    if not DB.exists():
        raise SystemExit(f"行情库不可读：{DB}")
    digest = _sha256(DB)
    print(f"db_sha256 {digest}", flush=True)
    if digest != EXPECTED_SHA:
        raise SystemExit(f"SHA256 不一致。期望 {EXPECTED_SHA}，实际 {digest}")
    r1 = _load_r1()
    spec = load_spec()
    if pd.Timestamp(spec.design_end) != END:
        raise RuntimeError("设计期结束日不是 2015-12-31")
    if abs(float(spec.cash_annual) - CASH_ANNUAL) > 1e-12:
        raise RuntimeError("现金年利率不是 2%")
    containers = load_containers()
    market = load_market(DB, containers, "A", "index", END_TEXT, spec, history_mode=OFFICIAL)
    _assert_not_after(market.dates, "calendar")
    r1_mod_members = r1.pool_members(load_containers(), "A", "index")
    meta = r1._meta(r1_mod_members)
    con = r1._connect(DB)
    try:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"integrity_check {integrity}")
        fx = _fx(con, END_TEXT)
        codes = [code for _name, code, _label in (*r1.NEW_US, *r1.NEW_HK)]
        codes += ["HSI", "XNDX", "^SP500TR"]
        bars = r1._load_bars(con, codes, END_TEXT)
        raw_sig, raw_fresh, _unused = r1._build_new(
            market.dates, fx, spec, bars, pd.DataFrame(), adjust_div=False)
        adj_sig, adj_fresh, adj_levels, adj_notes = _build_adjusted_us(con, market.dates, fx, spec, r1)
        hk_levels = {}
        for name, code, _label in r1.NEW_HK:
            level, _flag, _gaps = _research_level(
                code, "tencent_hk_index", bars, {}, market.dates, fx, spec, None)
            hk_levels[name] = level.reindex(market.dates)
        year_ends = {}
        days = r1.decision_dates(market.dates, "month")
        days = days[(days >= START_TEXT) & (days <= END)]
        if len(days) != 120:
            raise RuntimeError(f"月末决策日不是 120 个，而是 {len(days)}")
        for day in days:
            if day.month == 12:
                year_ends[int(day.year)] = pd.Timestamp(day)
        detail, summary, exact, mismatched = _coverage(con, containers, year_ends)
        tracking = _tracking(con)
        outside = _outside_missing_adj(con)
        seventeen = _seventeen_ids(r1_mod_members)
        lab2 = _lab2_levels(con)
    finally:
        con.close()

    signal = market.signal.copy()
    fresh = market.liquidity.reindex(index=signal.index).fillna(False).astype(bool).copy()
    for name, series in raw_sig.items():
        signal[name] = series.reindex(signal.index)
        fresh[name] = raw_fresh[name].reindex(signal.index).fillna(False).astype(bool)
    adj_signal = signal.copy()
    adj_panel_fresh = fresh.copy()
    for name, series in adj_sig.items():
        adj_signal[name] = series.reindex(adj_signal.index)
        adj_panel_fresh[name] = adj_fresh[name].reindex(adj_signal.index).fillna(False).astype(bool)
    ranked = [name for name, _code, _label in (*r1.NEW_US, *r1.NEW_HK) if name in raw_sig]
    missing_adj = [name for name in ranked if name.startswith("us-") and name not in adj_sig]
    if missing_adj:
        raise RuntimeError(f"新池美股 ETF 缺后复权，拒绝用原始收盘代替：{missing_adj}")
    old_names = [name for name in market.names if name in meta]
    pools = {
        "raw": old_names + ranked,
        "adj": old_names + ranked,
        "adj_only_with_backward": [name for name in ranked if name in adj_sig],
    }
    print("rank", flush=True)
    month_rows, _selections, _caps = r1._structure(
        meta,
        pools,
        {"raw": fresh, "adj": adj_panel_fresh, "adj_only_with_backward": adj_panel_fresh},
        {"raw": signal, "adj": adj_signal, "adj_only_with_backward": adj_signal},
        days,
        spec,
    )
    _check_raw_against_r1(month_rows)
    share_rows = _share_diff(month_rows)
    half_rows = _half_diff(month_rows)
    max_abs = max(abs(row["diff_share"]) for row in share_rows)

    extra_levels = dict(adj_levels)
    extra_levels.update(hk_levels)
    extra_fresh = {name: flag for name, flag in raw_fresh.items() if not str(name).startswith("us-")}
    extra_fresh.update(adj_fresh)
    new_ids = old_names + ranked
    new_levels = _engine_levels(market, extra_levels, extra_fresh, new_ids)
    engine_17 = _engine_levels(market, {}, {}, seventeen)
    panels = {
        "lab2_17": _rank_ic(lab2),
        "engine_17": _rank_ic(engine_17),
        "new_pool": _rank_ic(new_levels),
    }
    summary_rows = []
    beat_rows = []
    yearly_rows = []
    panel_summary = {}
    level_panels = {"lab2_17": lab2, "engine_17": engine_17, "new_pool": new_levels}
    for label, ic in panels.items():
        ic_rows = _ic_summary(ic)
        beat = _beat_cash(level_panels[label])
        _dump_ic(label, ic, ic_rows, beat, yearly_rows)
        summary_rows.extend(ic_rows)
        beat_rows.extend(beat)
        panel_summary[label] = ic_rows
        print(label, {row["length"]: row["mean_ic"] for row in ic_rows if row["length"] in {"20", "60", "120", "250", "blend"}}, flush=True)

    lab2_rounded = {
        row["length"]: round(row["mean_ic"], 3)
        for row in panel_summary["lab2_17"]
        if row["length"] in BASELINE_IC
    }
    lab2_match = lab2_rounded == BASELINE_IC
    print(f"lab2_17 rounded match baseline: {lab2_match} got={lab2_rounded}", flush=True)

    index_held = []
    for name in old_names + [item[0] for item in r1.NEW_HK]:
        index_held.append({
            "code": "",
            "name": name,
            "role": "pool_research_series",
            "reason": "not_an_etf_held_on_research_series",
            "first_date": "",
            "in_paired_rank": 1,
        })
    exclusion = adj_notes + index_held + outside

    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    pure = [row for row in tracking if row["enhanced"] == 0 and row["tracked_te_annual"] != ""]
    enhanced = [row for row in tracking if row["enhanced"] == 1 and row["tracked_te_annual"] != ""]
    payload = {
        "db_sha256": digest,
        "sha_matches_dev": True,
        "git_head": head,
        "integrity": "ok",
        "coverage_by_year": summary,
        "tracking_median_pure": None if not pure else round(float(np.median([row["tracked_te_annual"] for row in pure])), 6),
        "tracking_median_enhanced": None if not enhanced else round(float(np.median([row["tracked_te_annual"] for row in enhanced])), 6),
        "share_max_abs_diff": round(max_abs, 6),
        "adj_pool_membership_equals_raw": missing_adj == [],
        "outside_pool_without_backward": len(outside),
        "lab2_match_baseline_3dp": lab2_match,
        "lab2_rounded": lab2_rounded,
        "new_pool_vs_baseline": _ic_contrast(panel_summary["new_pool"]),
        "engine_17_vs_baseline": _ic_contrast(panel_summary["engine_17"]),
        "ic_months": {label: int(frame.shape[0]) for label, frame in panels.items()},
        "new_pool_names": new_ids,
        "method": {
            "end": END_TEXT,
            "coverage": "14 个 A 股容器。场内 ETF 只算跟踪标的全称一致、且第一根正收盘不晚于该年末的。510880 跟踪上证红利，不算中证红利。",
            "tracking": "基金复权净值对库里的全收益指数。年化跟踪差是日收益差的标准差乘 sqrt(252)，与 R1 相同。价格指数没有入库。",
            "shares": "R1 第 4 节。后复权口径只把有 backward 的美股 ETF 换成后复权，再走同一条美元中间价对齐。指数没有后复权序列，不把原始收盘写成后复权。",
            "ic": "得分是 L 日价格比除以日收益标准差乘 sqrt(L)。Rank IC 对之后 20 个交易日。四个平均是 20/60/120/250 得分排名的平均。现金门槛是 (1+0.02/252)^L-1。",
            "fx": "美股用 bars 里 2006-01-04 起的 USDCNY，和 R1 相同。港股不乘 HKDCNY。",
        },
    }
    _write(OUT / "r1b-otc-coverage-detail.csv", detail, [
        "year", "container_id", "container_name", "bucket", "etf_codes", "etf_first",
        "otc_codes", "otc_n", "otc_near", "note",
    ])
    _write(OUT / "r1b-otc-coverage-year.csv", summary, ["year", "etf", "otc_only", "neither", "containers"])
    _write(OUT / "r1b-otc-tracking.csv", tracking, [
        "code", "name", "maps_to", "tracked_index", "enhanced", "feeder", "inception",
        "index_code", "index_basis", "n_days", "tracked_corr", "tracked_te_annual", "tracked_bias_annual",
        "tracked_start", "tracked_end", "near_index_code", "near_te_annual", "near_corr", "near_n_days", "note",
    ])
    _write(OUT / "r1b-share-month.csv", month_rows, [
        "date", "year", "pool", "lookback", "n", "market", "count", "share", "eligible",
    ])
    _write(OUT / "r1b-share-diff-year.csv", share_rows, [
        "year", "n", "market", "raw_share", "adj_share", "diff_share",
    ])
    _write(OUT / "r1b-share-diff-half.csv", half_rows, [
        "half", "n", "market", "raw_share", "adj_share", "diff_share",
    ])
    _write(OUT / "r1b-adj-exclusion.csv", exclusion, [
        "code", "name", "role", "reason", "first_date", "last_date", "rows",
        "in_design_period", "in_paired_rank",
    ])
    def _paired(frame: pd.DataFrame, left: str, right: str) -> dict:
        gap = (frame[left] - frame[right]).dropna()
        return {
            "mean": round(float(gap.mean()), 6),
            "t": round(float(gap.mean() / gap.std(ddof=1) * np.sqrt(len(gap))), 4),
            "n": int(len(gap)),
        }

    payload["ic_gap"] = {
        "lab2_17_20_minus_blend": _paired(panels["lab2_17"], "20", "blend"),
        "lab2_17_20_minus_120": _paired(panels["lab2_17"], "20", "120"),
        "new_pool_20_minus_blend": _paired(panels["new_pool"], "20", "blend"),
        "new_pool_20_minus_120": _paired(panels["new_pool"], "20", "120"),
    }
    _write(OUT / "r1b-ic-summary.csv", summary_rows, [
        "panel", "length", "mean_ic", "t", "pos_frac", "n_months", "mean_names",
        "half_2006_2010", "half_2011_2015", "year_autocorr",
    ])
    _write(OUT / "r1b-ic-year.csv", yearly_rows, ["panel", "year", "length", "mean_ic"])
    _write(OUT / "r1b-ic-beat-cash.csv", beat_rows, [
        "panel", "length", "spread_pct", "t", "hit", "n_months",
    ])
    (OUT / "r1b-summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("coverage", summary, flush=True)
    print(f"share max abs diff {max_abs:.6f}", flush=True)
    print(f"outside without backward {len(outside)} mismatched execution {len(mismatched)} exact etf rows {len(exact)}", flush=True)
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
