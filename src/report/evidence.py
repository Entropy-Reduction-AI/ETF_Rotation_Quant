"""基准、归因、代表性与数据时间线。只描述，不改规则。"""
from __future__ import annotations

import csv
import json
import math
import sqlite3
from pathlib import Path

import pandas as pd

from src.portfolio.config import load_config
from src.report.blend import monthly_rebalance
from src.report.charts import draw_nav, draw_timeline
from src.report.fx import cny_from_usd
from src.report.metrics import (
    cagr,
    decay_split,
    performance,
    versus,
    yearly_returns,
)
from src.research.prereg_v1.panel import read_table, validate_panel
from src.research.prereg_v2.engine import (
    A_SHARE,
    A_WEIGHT,
    DESIGN_END,
    OOS_END,
    OOS_START,
    OVERSEAS,
    cash_daily,
    equal_weight_returns,
    haven_total_return,
    load_haven,
    monthly_blend,
    summarize,
)

ROOT = Path(__file__).resolve().parents[2]
WINDOWS = (
    ("设计期", "2005-01-04", "2015-12-31"),
    ("样本外", "2016-01-04", "2026-09-30"),
    ("全程", "2005-01-04", "2026-09-30"),
)
SERIES_ORDER = (
    "策略组合",
    "A股部分",
    "BM-主",
    "BM-全市场",
    "H00300",
    "H00985",
    "SP500TR人民币",
    "XNDX人民币",
)
ANNUAL_ORDER = ("策略组合", "A股部分", "海外部分", "BM-主", "BM-全市场", "H00300", "H00985")
BACKFILL_SOURCE = "operations/reviews/2026-10-23-grok-pit-xcheck.md"
BACKFILL_ROWS = (
    ("发布前倒推：含回填，A股等权（月频设计期）", "+21.5% / −66.6%", "", "引用该复核，未重算"),
    ("发布前倒推：只用发布后，A股等权（月频设计期）", "+20.0% / −66.7%", "", "引用该复核，未重算"),
    ("发布前倒推：含回填，70/30（月频设计期）", "+22.7% / −29.5%", "", "引用该复核，未重算"),
    ("发布前倒推：只用发布后，70/30（月频设计期）", "+21.7% / −30.5%", "", "引用该复核，未重算"),
    ("发布前倒推：回填对年化的影响", "虚高约 1–1.5pp", "回撤几乎不变", "引用该复核的结论，未重算"),
)


class ReportError(RuntimeError):
    pass


def _num(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _date(value) -> str:
    if value is None or value == "":
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    return str(pd.Timestamp(text).date())


def _slice(series: pd.Series, start: str, end: str) -> pd.Series:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    out = series.loc[(series.index >= start_ts) & (series.index <= end_ts)].dropna()
    out.name = "ret"
    return out.astype(float)


def _level_returns(level: pd.Series) -> pd.Series:
    clean = level.sort_index().astype(float)
    clean = clean[~clean.index.duplicated(keep="last")]
    returns = clean.pct_change().iloc[1:].dropna()
    returns.name = "ret"
    return returns.astype(float)


def _read_closes(con: sqlite3.Connection, code: str, calendar: pd.DatetimeIndex) -> pd.Series:
    frame = pd.read_sql_query(
        "SELECT date, close FROM bars WHERE code = ? AND adj = 'raw' AND close > 0 ORDER BY date",
        con, params=(code,))
    if frame.empty:
        raise ReportError(f"bars 里没有 {code}")
    series = pd.Series(frame["close"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
    series = series[~series.index.duplicated(keep="last")].sort_index()
    return series.loc[series.index.isin(calendar)]


def _read_ohlc(con: sqlite3.Connection, code: str) -> pd.DataFrame:
    frame = pd.read_sql_query(
        "SELECT date, open, high, low, close, volume FROM bars WHERE code = ? AND adj = 'raw' AND close > 0 ORDER BY date",
        con, params=(code,))
    if frame.empty:
        raise ReportError(f"bars 里没有 {code}")
    frame["date"] = pd.to_datetime(frame["date"])
    for column in ("open", "high", "low"):
        frame[column] = frame[column].fillna(frame["close"])
    frame["volume"] = frame["volume"].fillna(0.0)
    return frame


def _empty_summary(net: pd.Series) -> dict:
    empty = pd.Series(0.0, index=net.index)
    return summarize(net, empty, empty)


def reconcile(panel: pd.DataFrame) -> dict:
    """原口径：面板里的美元序列。纳指是 NDX 价格指数，标普是面板里的那条。"""
    asset = equal_weight_returns(panel, A_SHARE, OOS_END)
    overseas = equal_weight_returns(panel, OVERSEAS, OOS_END).reindex(asset.index)
    if overseas.isna().any():
        raise ReportError("对账时海外腿没有盖住 A 股腿")
    design_a = asset.loc[:DESIGN_END]
    design_o = overseas.loc[:DESIGN_END]
    oos_a = asset.loc[OOS_START:]
    oos_o = overseas.loc[OOS_START:]
    design_port = _empty_summary(monthly_blend(design_a, design_o, A_WEIGHT))
    oos_port = _empty_summary(monthly_blend(oos_a, oos_o, A_WEIGHT))
    oos_sleeve = _empty_summary(oos_a)
    got = {
        "a_share_oos_cagr": round(oos_sleeve["cagr"] * 100, 2),
        "a_share_oos_drawdown": round(oos_sleeve["max_drawdown"] * 100, 2),
        "portfolio_oos_cagr": round(oos_port["cagr"] * 100, 2),
        "portfolio_oos_drawdown": round(oos_port["max_drawdown"] * 100, 1),
        "portfolio_design_cagr": round(design_port["cagr"] * 100, 1),
        "portfolio_design_drawdown": round(design_port["max_drawdown"] * 100, 1),
    }
    expected = {
        "a_share_oos_cagr": 3.05,
        "a_share_oos_drawdown": -35.75,
        "portfolio_oos_cagr": 7.75,
        "portfolio_oos_drawdown": -26.3,
        "portfolio_design_cagr": 18.9,
        "portfolio_design_drawdown": -61.1,
    }
    gaps = {key: got[key] - expected[key] for key in expected if got[key] != expected[key]}
    if gaps:
        raise ReportError(f"对账未过 0.01pp：{gaps}；得到 {got}")
    return {
        "definition": "美元；纳指为面板 NDX 价格指数；标普为面板现有序列。A 股为 16 个研究序列日等权。组合为 §5 monthly_blend。",
        "printed": expected,
        "rounded": got,
        "exact": {
            "a_share_oos_cagr": oos_sleeve["cagr"],
            "a_share_oos_drawdown": oos_sleeve["max_drawdown"],
            "portfolio_oos_cagr": oos_port["cagr"],
            "portfolio_oos_drawdown": oos_port["max_drawdown"],
            "portfolio_design_cagr": design_port["cagr"],
            "portfolio_design_drawdown": design_port["max_drawdown"],
        },
    }


def _overseas_sleeve(frames: list[pd.DataFrame]) -> pd.Series:
    parts = []
    for frame in frames:
        index = pd.to_datetime(frame["date"])
        level = pd.Series(frame["close_cny"].to_numpy(dtype=float), index=index)
        hole = pd.Series(pd.to_numeric(frame["data_hole"]).to_numpy(dtype=int), index=index)
        returns = level.pct_change().where(hole.eq(0))
        parts.append(returns)
    merged = pd.concat(parts, axis=1)
    averaged = merged.mean(axis=1, skipna=True)
    first = averaged.first_valid_index()
    if first is None:
        raise ReportError("人民币海外腿没有收益")
    return averaged.loc[first:].fillna(0.0).astype(float)


def _calendar(con: sqlite3.Connection) -> pd.DatetimeIndex:
    frame = pd.read_sql_query(
        "SELECT date FROM calendar WHERE date <= ? ORDER BY date", con, params=("2026-09-30",))
    return pd.DatetimeIndex(pd.to_datetime(frame["date"]))


def _fx(con: sqlite3.Connection) -> pd.Series:
    frame = pd.read_sql_query(
        "SELECT date, close, source FROM bars WHERE code = 'USDCNY' AND adj = 'raw' AND close > 0 ORDER BY date",
        con)
    if frame.empty:
        raise ReportError("bars 里没有 USDCNY")
    sources = set(frame["source"])
    if sources != {"chinamoney"}:
        raise ReportError(f"USDCNY 来源不是 chinamoney：{sources}")
    series = pd.Series(frame["close"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
    return series[~series.index.duplicated(keep="last")].sort_index()


def _container_returns(panel: pd.DataFrame) -> pd.DataFrame:
    frame = panel.loc[pd.to_datetime(panel["date"]) <= OOS_END].copy()
    frame["date"] = pd.to_datetime(frame["date"])
    prices = frame.pivot(index="date", columns="container", values="close").sort_index()
    hole = frame.pivot(index="date", columns="container", values="data_hole").reindex_like(prices)
    columns = list(A_SHARE)
    return prices[columns].where(hole[columns].eq(0)).pct_change()


def _coverage(con: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT c.container, c.series_code, c.price_only, c.route_used, c.exec_code
          FROM coverage c
          JOIN (SELECT theme_id, MAX(run_id) AS run_id FROM coverage GROUP BY theme_id) latest
            ON c.theme_id = latest.theme_id AND c.run_id = latest.run_id
        """
    ).fetchall()
    return {row["container"]: row for row in rows}


def _launch_table() -> dict[str, dict[str, str]]:
    path = ROOT / "incoming" / "grok-pit-20261022" / "index_launch.csv"
    out = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            out[row["index_code"]] = row
    return out


def _list_dates() -> dict[str, str]:
    path = ROOT / "results" / "inventory" / "execution-2026-09-30.csv"
    out = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("role") == "primary" and row.get("first_date"):
                out[row["code"]] = row["first_date"]
    return out


def _first_real(panel: pd.DataFrame, name: str) -> pd.Timestamp:
    dates = pd.to_datetime(panel.loc[(panel["container"] == name) & (panel["data_hole"] == 0), "date"])
    if dates.empty:
        raise ReportError(f"面板里没有 {name} 的 data_hole==0")
    return pd.Timestamp(dates.min())


def _universe_rows(panel, frames, coverage, launch, listed, cfg) -> list[dict]:
    books = {book.container: book for book in cfg.funds}
    rows = []
    for name in A_SHARE:
        info = coverage[name]
        code = info["series_code"]
        card = launch.get(code, {})
        book = books[name]
        rows.append({
            "name": name,
            "series_code": code,
            "kind": "全收益" if info["price_only"] == "False" else "价格",
            "start": _first_real(panel, name),
            "base_date": _date(card.get("base_date")),
            "publish": _date(card.get("launch_date")),
            "etf": book.primary,
            "list_date": _date(listed.get(book.primary)),
            "source": info["route_used"],
            "end": pd.Timestamp("2026-09-30"),
        })
    extra = (
        ("纳指100", "XNDX", "全收益", frames["XNDX"], "^XNDX", "513100", "nasdaq"),
        ("标普500", "^SP500TR", "全收益", frames["SP500TR"], "^SP500TR", "513500", "yahoo"),
    )
    for name, code, kind, frame, launch_code, etf, source in extra:
        hole = pd.to_numeric(frame["data_hole"])
        dates = pd.to_datetime(frame.loc[hole.eq(0), "date"])
        card = launch.get(launch_code, {})
        rows.append({
            "name": name,
            "series_code": code,
            "kind": kind,
            "start": pd.Timestamp(dates.min()),
            "base_date": _date(card.get("base_date")),
            "publish": _date(card.get("launch_date")),
            "etf": etf,
            "list_date": _date(listed.get(etf)),
            "source": source,
            "end": pd.Timestamp("2026-09-30"),
        })
    rows.append({
        "name": "货币ETF",
        "series_code": "511880",
        "kind": "全收益（收盘加现金分红）",
        "start": pd.Timestamp("2013-07-12"),
        "base_date": "",
        "publish": "",
        "etf": "511880",
        "list_date": _date(listed.get("511880")),
        "source": "tencent_etf",
        "end": pd.Timestamp("2026-09-30"),
    })
    return rows


def _investable(rows: list[dict], calendar: pd.DatetimeIndex, cfg) -> pd.DataFrame:
    books = {book.container: book for book in cfg.funds}
    first_listed = {}
    for row in rows:
        if row["name"] not in books:
            continue
        dates = []
        if row["list_date"]:
            dates.append(pd.Timestamp(row["list_date"]))
        for alternate in books[row["name"]].alternates:
            dates.append(pd.Timestamp(alternate.list_date))
        first_listed[row["name"]] = min(dates) if dates else None
    month_end = calendar.to_series().groupby(calendar.to_period("M")).max()
    records = []
    for day in month_end:
        count = sum(1 for listed_on in first_listed.values() if listed_on is not None and listed_on <= day)
        records.append({"month_end": str(pd.Timestamp(day).date()), "investable_count": count})
    return pd.DataFrame(records)


def _benchmark_rows(series: dict[str, pd.Series], benchmark: pd.Series, rf: pd.Series) -> list[dict]:
    rows = []
    for window, start, end in WINDOWS:
        bench = _slice(benchmark, start, end)
        for name in SERIES_ORDER:
            block = _slice(series[name], start, end)
            if len(block) < 2 or len(bench) < 2:
                raise ReportError(f"{name} {window} 不足两个交易日")
            row = {"series": name, "window": window, **performance(block, rf)}
            relative = versus(block, bench)
            overlap = pd.concat([block.rename("left"), bench.rename("right")], axis=1).dropna()
            row.update(relative)
            row["relative_start"] = str(pd.Timestamp(overlap.index[0]).date())
            row["relative_end"] = str(pd.Timestamp(overlap.index[-1]).date())
            for key, value in list(row.items()):
                if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                    row[key] = None
            rows.append(row)
    return rows


def _annual(series: dict[str, pd.Series]) -> list[dict]:
    yearly = {name: yearly_returns(series[name].dropna()) for name in ANNUAL_ORDER}
    years = range(2005, 2027)
    rows = []
    for year in years:
        row = {"year": year}
        for name in ANNUAL_ORDER:
            row[name] = yearly[name].get(year)
        rows.append(row)
    return rows


def _attribution(panel_returns: pd.DataFrame, sleeves: dict[str, pd.Series], weights: pd.DataFrame,
                 h00300: pd.Series) -> list[dict]:
    oos = panel_returns.loc[(panel_returns.index >= OOS_START) & (panel_returns.index <= OOS_END), list(A_SHARE)]
    count = oos.notna().sum(axis=1).replace(0, pd.NA)
    contribution = oos.div(count, axis=0)
    years = len(_slice(sleeves["A股部分"], "2016-01-04", "2026-09-30")) / 252
    rows = []
    h_oos = _slice(h00300, "2016-01-04", "2026-09-30")
    for name in A_SHARE:
        own = oos[name].dropna()
        overlap = pd.concat([own.rename("left"), h_oos.rename("right")], axis=1).dropna()
        total = float(contribution[name].sum(min_count=1))
        rows.append({
            "level": "容器",
            "name": name,
            "cagr": cagr(own),
            "monthly_contribution_sum": total,
            "annualized_arithmetic_contribution": total / years,
            "excess_vs_h00300": cagr(overlap["left"]) - cagr(overlap["right"]),
        })
    port = _slice(sleeves["策略组合"], "2016-01-04", "2026-09-30")
    port_years = len(port) / 252
    aligned = weights.reindex(port.index)
    for label, column in (("A股部分", "A股部分"), ("海外部分", "海外部分")):
        daily = aligned[column] * sleeves[column].reindex(port.index)
        total = float(daily.sum())
        rows.append({
            "level": "组合",
            "name": label,
            "cagr": cagr(_slice(sleeves[column], "2016-01-04", "2026-09-30")),
            "monthly_contribution_sum": total,
            "annualized_arithmetic_contribution": total / port_years,
            "excess_vs_h00300": None,
        })
    return rows


def _decay(a_share: pd.Series, benchmark: pd.Series) -> list[dict]:
    design = pd.concat([
        _slice(a_share, "2005-01-04", "2015-12-31").rename("a"),
        _slice(benchmark, "2005-01-04", "2015-12-31").rename("b"),
    ], axis=1).dropna()
    oos = pd.concat([
        _slice(a_share, "2016-01-04", "2026-09-30").rename("a"),
        _slice(benchmark, "2016-01-04", "2026-09-30").rename("b"),
    ], axis=1).dropna()
    split = decay_split(cagr(design["a"]), cagr(oos["a"]), cagr(design["b"]), cagr(oos["b"]))
    note = (
        f"A股与 BM-主 的重叠日期：设计期 {pd.Timestamp(design.index[0]).date()}→{pd.Timestamp(design.index[-1]).date()}，"
        f"样本外 {pd.Timestamp(oos.index[0]).date()}→{pd.Timestamp(oos.index[-1]).date()}。"
    )
    rows = [
        {"item": "A股部分年化", "design": split["a_design"], "oos": split["a_oos"],
         "change": split["a_oos"] - split["a_design"], "note": note},
        {"item": "BM-主年化", "design": split["benchmark_design"], "oos": split["benchmark_oos"],
         "change": split["decay_benchmark"], "note": note},
        {"item": "A股相对BM-主超额", "design": split["excess_design"], "oos": split["excess_oos"],
         "change": split["decay_relative"], "note": note},
        {"item": "衰减合计", "design": split["a_design"], "oos": split["a_oos"],
         "change": split["decay_total"], "note": "等于基准自身的变化加相对基准的变化"},
        {"item": "其中：基准自身的变化", "design": split["benchmark_design"], "oos": split["benchmark_oos"],
         "change": split["decay_benchmark"], "note": ""},
        {"item": "其中：A股部分相对基准的变化", "design": split["excess_design"], "oos": split["excess_oos"],
         "change": split["decay_relative"], "note": ""},
    ]
    for item, design_text, oos_text, quote_note in BACKFILL_ROWS:
        rows.append({
            "item": item, "design": design_text, "oos": oos_text, "change": "",
            "note": f"{quote_note}。来源 {BACKFILL_SOURCE}",
        })
    return rows


def _representativeness(a_share: pd.Series, market: pd.Series) -> dict:
    out = {"industry_coverage": None, "industry_note": "中证一级行业权重未取到，这一项跳过。见 UNAVAILABLE.md。"}
    windows = {}
    for window, start, end in WINDOWS:
        left = _slice(a_share, start, end)
        right = _slice(market, start, end)
        relative = versus(left, right)
        both = pd.concat([left.rename("a"), right.rename("b")], axis=1).dropna()
        yearly = {}
        for year in sorted(set(both.index.year)):
            block = both.loc[both.index.year == year]
            yearly[str(year)] = float((1.0 + block["a"]).prod() - 1.0) - float((1.0 + block["b"]).prod() - 1.0)
        windows[window] = {
            **{key: _num(value) for key, value in relative.items()},
            "start": str(pd.Timestamp(both.index[0]).date()),
            "end": str(pd.Timestamp(both.index[-1]).date()),
            "yearly_excess": yearly,
        }
    out["versus_h00985"] = windows
    return out


def _write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if row.get(key) is None else row.get(key) for key in columns})


def _json_ready(value):
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, float):
        return _num(value)
    return value


def write_evidence(panel_path: Path, market_db: Path, out_dir: Path, asset_dir: Path) -> None:
    panel = validate_panel(read_table(panel_path, "panel"))
    checked = reconcile(panel)
    uri = f"{Path(market_db).resolve().as_uri()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        calendar = _calendar(con)
        fx = _fx(con)
        h00300 = _level_returns(_read_closes(con, "H00300", calendar))
        h00985 = _level_returns(_read_closes(con, "H00985", calendar))
        price_all = _level_returns(_read_closes(con, "000985", calendar))
        xndx = cny_from_usd(_read_ohlc(con, "XNDX"), fx, calendar)
        spx = cny_from_usd(_read_ohlc(con, "^SP500TR"), fx, calendar)
        coverage = _coverage(con)
        haven_closes, dividends = load_haven(market_db, "511880", OOS_END)
    finally:
        con.close()
    xndx_ret = _level_returns(pd.Series(xndx["close_cny"].to_numpy(dtype=float), index=pd.to_datetime(xndx["date"])))
    sp_ret = _level_returns(pd.Series(spx["close_cny"].to_numpy(dtype=float), index=pd.to_datetime(spx["date"])))
    overseas = _overseas_sleeve([xndx, spx])
    a_share = equal_weight_returns(panel, A_SHARE, OOS_END)
    a_share.index = pd.to_datetime(a_share.index)
    common = a_share.index.intersection(overseas.dropna().index)
    blended = monthly_blend(a_share.loc[common], overseas.loc[common], A_WEIGHT)
    check_frame = pd.DataFrame({"A股部分": a_share.loc[common], "海外部分": overseas.loc[common]})
    rebuilt, weights = monthly_rebalance(check_frame, {"A股部分": A_WEIGHT, "海外部分": 1.0 - A_WEIGHT})
    if float((rebuilt - blended).abs().max()) > 1e-12:
        raise ReportError("三资产月初再平衡在两资产情形下与 monthly_blend 不一致")
    parts = pd.concat([h00300.rename("H00300"), xndx_ret.rename("XNDX"), sp_ret.rename("SP500TR")], axis=1).dropna()
    broad = pd.concat([h00985.rename("H00985"), xndx_ret.rename("XNDX"), sp_ret.rename("SP500TR")], axis=1).dropna()
    bm_main, _bm_weights = monthly_rebalance(parts, {"H00300": 0.70, "XNDX": 0.15, "SP500TR": 0.15})
    bm_all, _broad_weights = monthly_rebalance(broad, {"H00985": 0.70, "XNDX": 0.15, "SP500TR": 0.15})
    series = {
        "策略组合": blended,
        "A股部分": a_share,
        "海外部分": overseas,
        "BM-主": bm_main,
        "BM-全市场": bm_all,
        "H00300": h00300,
        "H00985": h00985,
        "SP500TR人民币": sp_ret,
        "XNDX人民币": xndx_ret,
    }
    rf = haven_total_return(haven_closes, dividends, calendar, cash_daily())
    rf.index = pd.to_datetime(rf.index)
    benchmark_rows = _benchmark_rows(series, bm_main, rf)
    annual_rows = _annual(series)
    attr_rows = _attribution(_container_returns(panel), series, weights, h00300)
    decay_rows = _decay(a_share, bm_main)
    cfg = load_config()
    universe = _universe_rows(panel, {"XNDX": xndx, "SP500TR": spx}, coverage, _launch_table(), _list_dates(), cfg)
    investable = _investable(universe, calendar, cfg)
    overlap = pd.concat([price_all.rename("price"), h00985.rename("tr")], axis=1).dropna()
    cross = {
        "price_code": "000985",
        "total_return_code": "H00985",
        "daily_return_corr": float(overlap["price"].corr(overlap["tr"])),
        "price_cagr": cagr(overlap["price"]),
        "total_return_cagr": cagr(overlap["tr"]),
        "start": str(pd.Timestamp(overlap.index[0]).date()),
        "end": str(pd.Timestamp(overlap.index[-1]).date()),
        "n": int(len(overlap)),
    }
    payload = {
        "benchmark_fixed": "2026-10",
        "benchmark_note": "基准定于 2026-10，晚于 v2 样本外运行。",
        "standard": "GIPS Guidance Statement on Benchmarks：全收益、与策略配置一致；混合基准披露成分、权重和再平衡，并逐年列基准收益。国内 QDII 合同口径：513100 为纳斯达克100经汇率调整后的总收益，513500 为标普500经估值汇率调整、以人民币计价。",
        "fees": "全部按指数层面计算，不扣管理费。",
        "risk_free": "无风险利率用 511880 真实日收益；511880 上市前按年化 2%。",
        "construction": {
            "a_share": "16 个容器的研究序列，data_hole==0 的当日收益等权。这是 v2 §5 里 A 股腿的函数。",
            "portfolio": "monthly_blend：A 股腿 70% + 海外两指数人民币全收益的日等权 30%，每月第一个交易日回到目标权重。",
            "bm_main": "70% H00300 + 15% XNDX人民币 + 15% SP500TR人民币，每月第一根收益回到这个权重，月内漂移。三个成分之间不另做日频再平衡。",
            "bm_broad": "A 股部分换成 H00985，权重和再平衡与 BM-主相同。",
            "fx": "A 股交易日 D 取日期严格早于 D 的美元收盘，再乘 D 当天或之前最近一个人民币中间价。",
        },
        "fx": {
            "source": "chinamoney",
            "code": "USDCNY",
            "first": str(fx.index.min().date()),
            "last": str(fx.index.max().date()),
            "note": "中国外汇交易中心历史接口在 2005 年返回 0 行，序列从 2006-01-04 起。没有改用 FRED，也没有把 2005 年按固定汇率补上。",
        },
        "xndx": {
            "source": "nasdaq",
            "url": "https://indexes.nasdaqomx.com/Index/ExportHistory/XNDX",
            "first_native": "2005-01-04",
            "note": "Nasdaq quote API 对 XNDX 返回 Symbol not exists。官方 History 导出有 2005-01-04 起的指数点位。Yahoo ^XNDX 图表没有返回历史序列。",
        },
        "cross_check_000985": cross,
        "reconciliation": checked,
        "rows": _json_ready(benchmark_rows),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "benchmark.json").write_text(json.dumps(_json_ready(payload), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    _write_csv(out_dir / "benchmark.csv", benchmark_rows, [
        "series", "window", "start", "end", "n", "cagr", "ann_vol", "max_drawdown",
        "max_drawdown_peak", "max_drawdown_trough", "sharpe", "calmar",
        "excess_cagr", "tracking_error", "information_ratio", "beta", "monthly_corr",
        "relative_start", "relative_end",
    ])
    _write_csv(out_dir / "annual.csv", annual_rows, ["year", *ANNUAL_ORDER])
    _write_csv(out_dir / "attribution.csv", attr_rows, [
        "level", "name", "cagr", "monthly_contribution_sum", "annualized_arithmetic_contribution", "excess_vs_h00300",
    ])
    _write_csv(out_dir / "decay.csv", decay_rows, ["item", "design", "oos", "change", "note"])
    _write_csv(out_dir / "universe.csv", [
        {
            "容器": row["name"],
            "研究序列代码": row["series_code"],
            "全收益或价格": row["kind"],
            "数据起点": str(pd.Timestamp(row["start"]).date()),
            "基日": row["base_date"],
            "发布日": row["publish"],
            "主执行ETF": row["etf"],
            "ETF上市日": row["list_date"],
            "数据来源": row["source"],
        }
        for row in universe
    ], ["容器", "研究序列代码", "全收益或价格", "数据起点", "基日", "发布日", "主执行ETF", "ETF上市日", "数据来源"])
    (out_dir / "representativeness.json").write_text(
        json.dumps(_json_ready(_representativeness(a_share, h00985)), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    _write_csv(out_dir / "investable.csv", investable.to_dict("records"), ["month_end", "investable_count"])
    draw_nav(asset_dir / "nav-vs-benchmark.png", [
        ("策略组合", series["策略组合"]),
        ("BM-主", series["BM-主"]),
        ("沪深300全收益", series["H00300"]),
    ])
    draw_timeline(
        asset_dir / "data-timeline.png",
        universe,
        pd.Series(investable["investable_count"].to_numpy(), index=pd.to_datetime(investable["month_end"])),
    )
    unavailable = out_dir / "UNAVAILABLE.md"
    if not unavailable.exists():
        unavailable.write_text("# 未取得的数据\n\n行业权重见本任务取数记录。\n", encoding="utf-8")
