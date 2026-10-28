"""任意起点与四种市场状态。公式对齐 Owner 看板诊断脚本，不另起一套算法。

任意起点：`anystart.py`。每个月第一个交易日为起点，持有整年，年化是
`(净值终点 / 净值起点) ** (1/年数) - 1`。策略和基准用日收益累乘；
沪深300、标普500、纳指100 用人民币全收益点位（`lab2.py` 的美元 +1 日对齐）。

四种状态：`states.py`。沪深300 全收益月末价，过去 12 个月与当月涨跌。
拿现金 = 前一日现金权重 ×（0.02/252 − 基准日收益）。选标的 = 日超额 − 拿现金。
状态合计是日超额按月相加后再汇总，打印 1 位小数。跟涨、跟跌是月收益均值之比。

不计算 2015-12-31 之后的组合收益。现金日收益用诊断脚本里的常数 0.02/252，
不用 511880 的全收益。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from src.v3.engine.benchmark import bm_main
from src.v3.engine.book import DESIGN_END

DESIGN_START = "2006-01-05"
HORIZONS = (1, 2, 3, 5)
STATE_ORDER = ("牛市", "回调", "熊市", "反弹")
LEVEL_NAMES = ("沪深300", "标普500", "纳指100")
# states.py / reviewer_r3_scorecard.py 写死的现金日收益，不是避风港 ETF。
CASH_DAILY = 0.02 / 252
P1_RELATIVE = Path("results/v3/design-period/9b421c0294a8509e5283aa871034ff0e8ed66c75/P1")

# Reviewer 2026-10-28 `numbers_ok_with_notes`。状态超额是 states.py 的 1 位小数；
# 看板整数是对这些打印值四舍五入（0.6→1，29.9→30，94.9→95，−56.7→−57）。
REFERENCE = {
    "anystart_5y_win_pct": {"基准": 63, "纳指100": 32},
    "state_excess_pp": {"牛市": 0.6, "回调": 29.9, "熊市": 94.9, "反弹": -56.7},
    "state_excess_pp_board": {"牛市": 1, "回调": 30, "熊市": 95, "反弹": -57},
    "up_capture": 0.86,
    "down_capture": 0.52,
}


class ScorecardError(RuntimeError):
    pass


def refuse_portfolio_dates(index, *, what: str = "组合收益") -> None:
    """日期晚于设计期结束日就拒绝，避免算出 2016 年及之后的组合收益。"""
    stamps = pd.DatetimeIndex(pd.to_datetime(index))
    stamps = stamps[~stamps.isna()]
    if len(stamps) == 0:
        return
    last = pd.Timestamp(stamps.max())
    if last > DESIGN_END:
        raise ScorecardError(
            f"拒绝计算 {last.date()} 的{what}：晚于 {DESIGN_END.date()}。"
        )


def _end_stamp(end: str) -> pd.Timestamp:
    stamp = pd.Timestamp(end)
    if stamp > DESIGN_END:
        raise ScorecardError(
            f"拒绝结束日 {stamp.date()}：打分卡不计算晚于 {DESIGN_END.date()} 的组合收益。"
        )
    return stamp


def _read_column(path: Path, column: str) -> pd.Series:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    if column not in frame.columns:
        raise ScorecardError(f"{path} 没有列 {column}")
    series = frame[column].astype(float).sort_index()
    series = series[~series.index.duplicated(keep="last")]
    if series.empty:
        raise ScorecardError(f"{path} 的 {column} 是空的")
    if not np.isfinite(series.to_numpy(dtype=float)).all():
        raise ScorecardError(f"{path} 的 {column} 有空值或无穷")
    refuse_portfolio_dates(series.index, what=column)
    return series


def _connect(db: Path) -> sqlite3.Connection:
    path = Path(db)
    if not path.exists() or path.stat().st_size < 1000:
        raise ScorecardError(f"行情库不可读（若仍是 LFS 指针，先 git lfs pull）：{path}")
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def _closes(con: sqlite3.Connection, code: str, end: str) -> pd.Series:
    frame = pd.read_sql_query(
        "SELECT date, close FROM bars WHERE code = ? AND date <= ? ORDER BY date",
        con,
        params=(code, end),
    )
    if frame.empty:
        raise ScorecardError(f"bars 里没有 {code}（截至 {end}）")
    frame["date"] = pd.to_datetime(frame["date"])
    series = frame.set_index("date")["close"].astype(float)
    return series[~series.index.duplicated(keep="last")].sort_index()


def index_levels(db: Path, end: str) -> pd.DataFrame:
    """沪深300、标普500、纳指100 的人民币全收益点位，对齐方式与 lab2.py 相同。

    日历是沪深300 自 2005-01-01 到 `end`。美股先把日期 +1 天，再沿到 A 股交易日，
    乘当天或之前的美元兑人民币中间价。查询本身停在 `end`，不读更晚的行情。
    """
    end_text = str(_end_stamp(end).date())
    con = _connect(db)
    try:
        h00300 = _closes(con, "H00300", end_text)
        calendar = h00300.loc["2005-01-01":end_text].index
        fx = _closes(con, "USDCNY", end_text)
        raw = {"沪深300": h00300}

        def usd(code: str) -> pd.Series:
            series = _closes(con, code, end_text).copy()
            series.index = series.index + pd.Timedelta(days=1)
            shifted = series.reindex(calendar, method="ffill")
            rate = fx.reindex(calendar, method="ffill")
            return shifted * rate

        raw["纳指100"] = usd("XNDX")
        raw["标普500"] = usd("^SP500TR")
    finally:
        con.close()
    frame = pd.DataFrame({name: series.reindex(calendar, method="ffill") for name, series in raw.items()})
    for name, series in raw.items():
        first = series.dropna().index[0]
        frame.loc[frame.index < first, name] = np.nan
    frame = frame.mask(frame <= 0)
    for name in frame.columns:
        first = frame[name].first_valid_index()
        if first is not None:
            frame.loc[first:, name] = frame.loc[first:, name].ffill()
    return frame


def load_h00300(db: Path, end: str) -> pd.Series:
    """states.py 用的沪深300 全收益收盘：`date <= end` 的原始收盘，不做美元对齐。"""
    end_text = str(_end_stamp(end).date())
    con = _connect(db)
    try:
        return _closes(con, "H00300", end_text)
    finally:
        con.close()


def growth_nav(returns: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """缺日按 0 收益补上，再累乘。与 anystart.py 的 `nav` 相同。"""
    aligned = returns.reindex(index).fillna(0.0)
    return (1.0 + aligned).cumprod()


def level_nav(levels: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """点位先沿到评价日，再除以窗口第一天。与 anystart.py 的指数净值相同。"""
    aligned = levels.reindex(index).ffill()
    base = float(aligned.iloc[0])
    if not np.isfinite(base) or base == 0.0:
        raise ScorecardError("指数点位在窗口第一天没有正的价格")
    return aligned / base


def any_start(
    navs: dict[str, pd.Series],
    *,
    strategy: str = "E2",
    horizons: tuple[int, ...] = HORIZONS,
) -> dict[int, pd.DataFrame]:
    """每个月初持有 `horizons` 里的整年。终点超过最后一天就停止，与 anystart.py 的 break 相同。"""
    if strategy not in navs:
        raise ScorecardError(f"净值里没有策略列 {strategy}")
    index = pd.DatetimeIndex(navs[strategy].index).sort_values().unique()
    if len(index) == 0:
        raise ScorecardError("没有净值")
    refuse_portfolio_dates(index)
    starts = pd.Series(index, index=index).groupby([index.year, index.month]).first().values
    tables: dict[int, pd.DataFrame] = {}
    for years in horizons:
        rows = []
        for origin in starts:
            stop = pd.Timestamp(origin) + pd.DateOffset(years=int(years))
            if stop > index[-1]:
                break
            end = index[index <= stop][-1]
            rows.append({
                "start": origin,
                **{name: (nav.loc[end] / nav.loc[origin]) ** (1 / years) - 1 for name, nav in navs.items()},
            })
        if rows:
            tables[int(years)] = pd.DataFrame(rows).set_index("start")
        else:
            tables[int(years)] = pd.DataFrame(columns=list(navs))
    return tables


def any_start_summary(tables: dict[int, pd.DataFrame], *, strategy: str = "E2") -> pd.DataFrame:
    """跑赢占比用严格大于。百分比是 `round` 后的整数（与 Reviewer 的 pct 相同，.5 向偶数）。"""
    rows = []
    for years, frame in tables.items():
        for name in frame.columns:
            if name == strategy:
                continue
            excess = frame[strategy] - frame[name]
            filled = len(excess) > 0
            rate = float((excess > 0).mean()) if filled else None
            worst_at = excess.idxmin() if filled else pd.NaT
            rows.append({
                "years": int(years),
                "comparator": name,
                "n": int(len(frame)),
                "win_rate": rate,
                "win_pct": int(round(100 * rate)) if filled else None,
                "median_excess": float(excess.median()) if filled else None,
                "median_excess_pp": round(100 * float(excess.median()), 1) if filled else None,
                "worst_excess": float(excess.min()) if filled else None,
                "worst_excess_pp": round(100 * float(excess.min()), 1) if filled else None,
                "worst_start": None if not filled or pd.isna(worst_at) else pd.Timestamp(worst_at).date().isoformat(),
            })
    return pd.DataFrame(rows)


def label_state(slow: pd.Series, fast: pd.Series) -> pd.Series:
    """慢动量与快动量的四种状态。慢动量还没有值的月份留空。持平算向下那一支。"""
    labels = np.select(
        [(slow > 0) & (fast > 0), (slow > 0) & (fast <= 0), (slow <= 0) & (fast <= 0)],
        ["牛市", "回调", "熊市"],
        "反弹",
    )
    return pd.Series(labels, index=slow.index).where(slow.notna())


def classify_months(h00300: pd.Series) -> pd.Series:
    """月末收盘的 12 个月涨跌与当月涨跌。与 states.py 相同。"""
    month_end = h00300.sort_index().resample("ME").last()
    slow = month_end.pct_change(12)
    fast = month_end.pct_change(1)
    return label_state(slow, fast)


def cash_weight_on(held_cash: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """当天收益用上一行的现金权重。第一行没有上一行时记为 1。与 states.py 的 shift(1) 相同。"""
    return held_cash.sort_index().shift(1).reindex(index).fillna(1.0)


def state_frame(
    strategy: pd.Series,
    benchmark: pd.Series,
    cash_weight: pd.Series,
    states: pd.Series,
    *,
    cash_daily: float = CASH_DAILY,
) -> pd.DataFrame:
    """日超额拆成拿现金和选标的，再按月相加。月收益用各序列自己的日期，与 states.py 相同。"""
    refuse_portfolio_dates(strategy.index)
    refuse_portfolio_dates(benchmark.index)
    bench_on_strategy = benchmark.reindex(strategy.index).fillna(0.0)
    timing = cash_weight.reindex(strategy.index) * (cash_daily - bench_on_strategy)
    excess = strategy - bench_on_strategy
    daily = pd.DataFrame({
        "excess": excess,
        "timing": timing,
        "selection": excess - timing,
        "cash": cash_weight.reindex(strategy.index),
    })
    monthly = daily[["excess", "timing", "selection"]].resample("ME").sum()
    monthly["cash"] = daily["cash"].resample("ME").mean()
    monthly["state"] = states.reindex(monthly.index)
    monthly["strategy"] = (1.0 + strategy).resample("ME").prod() - 1.0
    monthly["benchmark"] = (1.0 + benchmark).resample("ME").prod() - 1.0
    return monthly


def state_table(monthly: pd.DataFrame) -> pd.DataFrame:
    """1 位小数与 states.py 的 `.round(1)` 相同。看板整数是对这一位小数再四舍五入。"""
    grouped = monthly.dropna(subset=["state"]).groupby("state")
    rows = []
    for name in STATE_ORDER:
        if name not in grouped.groups:
            continue
        block = grouped.get_group(name)
        excess_pp = round(100 * float(block["excess"].sum()), 1)
        rows.append({
            "state": name,
            "months": int(len(block)),
            "win_month_pct": round(100 * float((block["strategy"] > block["benchmark"]).mean()), 1),
            "cash_pp": round(100 * float(block["timing"].sum()), 1),
            "selection_pp": round(100 * float(block["selection"].sum()), 1),
            "excess_pp": excess_pp,
            "excess_pp_board": int(round(excess_pp)),
        })
    return pd.DataFrame(rows).set_index("state")


def capture_ratios(strategy: pd.Series, benchmark: pd.Series) -> dict[str, float | int]:
    """涨的月份：策略月收益均值 / 基准月收益均值。跌的月份同样。打印 2 位小数。"""
    refuse_portfolio_dates(strategy.index)
    refuse_portfolio_dates(benchmark.index)
    strategy_month = (1.0 + strategy).resample("ME").prod() - 1.0
    benchmark_month = (1.0 + benchmark).resample("ME").prod() - 1.0
    up = benchmark_month > 0
    down = benchmark_month < 0
    if int(up.sum()) == 0 or int(down.sum()) == 0:
        raise ScorecardError("跟涨或跟跌没有月份")
    up_ratio = float(strategy_month[up].mean() / benchmark_month[up].mean())
    down_ratio = float(strategy_month[down].mean() / benchmark_month[down].mean())
    return {
        "up_capture": round(up_ratio, 2),
        "down_capture": round(down_ratio, 2),
        "up_months": int(up.sum()),
        "down_months": int(down.sum()),
    }


def score_book(
    paths: Path,
    held: Path,
    db: Path,
    *,
    start: str = DESIGN_START,
    end: str = str(DESIGN_END.date()),
    name: str = "E2",
) -> dict:
    """读一份设计期成交收益和现金权重，对 BM-主 与三个人民币全收益指数出打分卡。"""
    end_stamp = _end_stamp(end)
    end_text = str(end_stamp.date())
    executed = _read_column(Path(paths), "executed")
    held_cash = _read_column(Path(held), "cash")
    window = executed.loc[start:end_text]
    if window.empty:
        raise ScorecardError(f"{start} 至 {end_text} 没有成交收益")
    benchmark = bm_main(Path(db), end_stamp).loc[start:end_text]
    levels = index_levels(Path(db), end_text)
    navs = {
        name: growth_nav(window, window.index),
        "基准": growth_nav(benchmark, window.index),
    }
    for level_name in LEVEL_NAMES:
        navs[level_name] = level_nav(levels[level_name], window.index)
    tables = any_start(navs, strategy=name)
    monthly = state_frame(
        window,
        benchmark,
        cash_weight_on(held_cash, window.index),
        classify_months(load_h00300(Path(db), end_text)),
    )
    return {
        "name": name,
        "start": str(pd.Timestamp(window.index[0]).date()),
        "end": str(pd.Timestamp(window.index[-1]).date()),
        "n_days": int(len(window)),
        "summary": any_start_summary(tables, strategy=name),
        "states": state_table(monthly),
        "capture": capture_ratios(window, benchmark),
    }


def acceptance(report: dict) -> dict:
    """对照 v3.1 P1 的参考数。状态超额比 1 位小数，不把看板整数当成另一套计算。"""
    summary = report["summary"]
    states = report["states"]
    capture = report["capture"]
    checks = []

    def add(name: str, got, want) -> None:
        checks.append({"name": name, "got": got, "want": want, "ok": got == want})

    five = summary[summary["years"] == 5]
    for label, want in REFERENCE["anystart_5y_win_pct"].items():
        got = five.loc[five["comparator"] == label, "win_pct"]
        add(f"5y_win_pct_{label}", None if got.empty else int(got.iloc[0]), want)
    for label, want in REFERENCE["state_excess_pp"].items():
        add(f"excess_pp_{label}", None if label not in states.index else float(states.loc[label, "excess_pp"]), want)
    for label, want in REFERENCE["state_excess_pp_board"].items():
        got = None if label not in states.index else int(states.loc[label, "excess_pp_board"])
        add(f"excess_board_{label}", got, want)
    add("up_capture", capture["up_capture"], REFERENCE["up_capture"])
    add("down_capture", capture["down_capture"], REFERENCE["down_capture"])
    return {"ok": all(item["ok"] for item in checks), "checks": checks}


def reference_scorecard(repo: Path, db: Path | None = None) -> dict:
    """v3.1 设计期 P1（正式引擎 E2）。只读已有 paths/held，不重跑组合。"""
    root = Path(repo)
    database = Path(db) if db is not None else root / "data" / "market.sqlite"
    book = root / P1_RELATIVE
    report = score_book(book / "paths.csv", book / "held.csv", database, name="E2")
    report["acceptance"] = acceptance(report)
    report["p1"] = str(book)
    return report


def payload(report: dict) -> dict:
    """可写入 JSON 的打分卡。DataFrame 变成记录。"""
    summary = report["summary"]
    states = report["states"].reset_index()
    body = {
        "name": report["name"],
        "start": report["start"],
        "end": report["end"],
        "n_days": report["n_days"],
        "any_start": summary.to_dict(orient="records"),
        "states": states.to_dict(orient="records"),
        "capture": report["capture"],
        "reference": REFERENCE,
    }
    if "acceptance" in report:
        body["acceptance"] = report["acceptance"]
    if "p1" in report:
        body["p1"] = report["p1"]
    return body
