"""v5.1 R6：§7.2 G 池，设计期只跑一次。

规则数字沿用冻结的 v5.1。池子换成美国、发达市场（美国以外）、新兴市场，
代表是 SPY、EFA、EEM。不使用中国序列，不跑 2016 年以后的中国组合，
不跑 §7.1 的稳健性，不写 LOCK，不打标签。

    .venv/bin/python -m src.v51 gpool

价格是 `results/v5/other-market/raw/` 里已登记的 Yahoo `adjclose`。
这是分红调整后的价格，不是官方全收益指数。日历是 SPY 有收盘的日子。
现金是 DTB3，日收益 = 利率 ÷ 100 × 间隔自然日 ÷ 360；当天没有数就沿用
不晚于当天的最近一个值。成交在下一个 G 日收盘，没有涨跌停，每腿 0.1%。

信号可以用窗口之前已经有的收盘。账上的持仓从 2003-07-01 的现金算起，
不把窗口之前的持仓带进来。
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src.data.db import git_head
from src.report.metrics import cagr, calmar, max_drawdown, yearly_returns
from src.v3.engine.book import drift, leg_cost, simulate, to_execution
from src.v3.engine.ledger import COLUMNS, canonical_params
from src.v3.engine.sessions import decision_dates
from src.v4.peers.signals import trailing_cash_return, trailing_price_return
from src.v4.r5.design import series_sha256

from .controls import _quantile, rankable_names
from .design import LEDGER, _refuse_ledger, _rows
from .hold import N_SIMS, SEED, decision_frame, draw_names, execution_positions
from .params import V51Error
from .universe import Market, Universe

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "results" / "v5" / "other-market" / "raw"
OUT = ROOT / "results" / "v5.1" / "other-market"
GATE = ROOT / "results" / "v5.1" / "design" / "gate-draft.csv"
DESIGN_MANIFEST = ROOT / "results" / "v5.1" / "design" / "manifest.json"
TAIPEI = ZoneInfo("Asia/Taipei")

WINDOW_START = "2003-07-01"
WINDOW_END = "2026-09-30"
H1_END = "2014-12-31"
H2_START = "2015-01-01"
SEGMENTS = (
    ("full", WINDOW_START, WINDOW_END),
    ("h1", WINDOW_START, H1_END),
    ("h2", H2_START, WINDOW_END),
)
LEG = 0.001
STALE_LIMIT = 5
CASH = "cash"
BOND = "IEF"
GOLD = "GLD"
TRADE_EPS = 1e-12
# 预注册表的书写顺序。9 只 Select Sector SPDR 不含后来分拆的 XLRE、XLC。
US = (
    "SPY", "QQQ", "IWM",
    "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY",
    "XLRE", "XLC",
)
DEVELOPED = ("EFA", "VGK", "FEZ", "EWG", "EWU", "EWQ", "EWJ")
EMERGING = ("EEM", "EWZ", "FXI", "EWH", "INDA")
CHINA_IDS = {"csi300", "hsi", "spx", "cgb-10y", "gold"}
RUNNER = "dev"
SEGMENT = "other-market"


def g_universe() -> Universe:
    """第一层就是表的前三行。国债和黄金只作防守，不进第一层。"""
    universe = Universe((
        Market("美国", "SPY", US),
        Market("发达市场", "EFA", DEVELOPED),
        Market("新兴市场", "EEM", EMERGING),
    ), bond=BOND, gold=GOLD, cash=CASH)
    names = traded_names()
    if CHINA_IDS & set(names):
        raise V51Error("G 池不使用中国序列")
    if len(names) != len(set(names)):
        raise V51Error("G 池容器重复")
    if BOND in names[:-2] or GOLD in names[:-2]:
        raise V51Error("防守容器不能同时出现在第一层")
    return universe


def traded_names() -> list[str]:
    """三个市场的成员，加上 IEF、GLD。现金不在这里。"""
    return [*US, *DEVELOPED, *EMERGING, BOND, GOLD]


def raw_tickers() -> list[str]:
    return [*traded_names(), "DTB3"]


def _num(value: float) -> str:
    return format(float(value), ".16g")


def load_adjclose(ticker: str) -> pd.Series:
    """登记过的分红调整收盘。缺文件或仍是 LFS 指针时直接拒绝。"""
    path = RAW / f"{ticker}.csv"
    if not path.is_file():
        raise V51Error(f"缺少 {path}")
    blob = path.read_bytes()
    if blob.startswith(b"version https://git-lfs.github.com/spec/v1"):
        raise V51Error(f"{ticker} 还是 LFS 指针，先 git lfs pull")
    frame = pd.read_csv(path, parse_dates=["date"])
    if "adjclose" not in frame.columns:
        raise V51Error(f"{ticker} 没有 adjclose")
    series = pd.Series(frame["adjclose"].to_numpy(dtype=float), index=pd.DatetimeIndex(frame["date"]).normalize())
    series = series[np.isfinite(series.to_numpy(dtype=float)) & (series.to_numpy(dtype=float) > 0.0)]
    series = series.sort_index()
    series = series[~series.index.duplicated(keep="last")]
    if series.empty:
        raise V51Error(f"{ticker} 没有可用的 adjclose")
    return series


def load_dtb3() -> pd.Series:
    """H.15 三个月国库券贴现收益率，单位是百分数。缺值和占位负数丢掉。"""
    path = RAW / "DTB3.csv"
    if not path.is_file():
        raise V51Error(f"缺少 {path}")
    blob = path.read_bytes()
    if blob.startswith(b"version https://git-lfs.github.com/spec/v1"):
        raise V51Error("DTB3 还是 LFS 指针，先 git lfs pull")
    frame = pd.read_csv(path, parse_dates=["date"], na_values=[".", ""])
    series = pd.Series(frame["DTB3"].to_numpy(dtype=float), index=pd.DatetimeIndex(frame["date"]).normalize())
    keep = np.isfinite(series.to_numpy(dtype=float)) & (series.to_numpy(dtype=float) > -100.0)
    series = series[keep].sort_index()
    series = series[~series.index.duplicated(keep="last")]
    if series.empty:
        raise V51Error("DTB3 没有可用的值")
    return series


def registered_sha256() -> dict[str, str]:
    manifest = pd.read_csv(RAW / "manifest.csv")
    return {str(row.ticker): str(row.sha256) for row in manifest.itertuples(index=False)}


def check_registered(tickers: list[str]) -> dict[str, str]:
    """用到的文件必须和普查清单上的 SHA256 一致。"""
    listed = registered_sha256()
    found = {}
    for ticker in tickers:
        path = RAW / f"{ticker}.csv"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if ticker not in listed or listed[ticker] != digest:
            raise V51Error(f"{ticker} 的 SHA256 和 results/v5/other-market/raw/manifest.csv 不一致")
        found[ticker] = digest
    return found


def cash_returns(calendar: pd.DatetimeIndex, rates: pd.Series, previous: pd.Timestamp | None) -> pd.Series:
    """G 日 t 的现金收益 = DTB3(t′) / 100 × d / 360。

    t′ 是不晚于 t 的最近一个有值日（当天有数用当天，没有就沿用）。
    d 是上一个 G 日到 t 的自然日数。序列第一天没有上一个 G 日时，d = 1。
    """
    dates = pd.DatetimeIndex(pd.to_datetime(calendar)).normalize()
    if dates.tz is not None or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise V51Error("G 日历要按时间唯一排好")
    if len(dates) == 0:
        raise V51Error("G 日历是空的")
    quote = pd.Series(rates, dtype=float).dropna().sort_index()
    quote = quote[~quote.index.duplicated(keep="last")]
    if quote.empty:
        raise V51Error("DTB3 没有可用的值")
    pos = quote.index.searchsorted(dates, side="right") - 1
    if int(np.min(pos)) < 0:
        raise V51Error("DTB3 没有盖住 G 日历的起点")
    rate = quote.to_numpy(dtype=float)[pos] / 100.0
    gap = np.array(dates.to_series().diff().dt.days.to_numpy(dtype=float), dtype=float, copy=True)
    if previous is None:
        gap[0] = 1.0
    else:
        gap[0] = float((pd.Timestamp(dates[0]) - pd.Timestamp(previous).normalize()).days)
    if np.any(gap <= 0.0) or not np.isfinite(gap).all() or not np.isfinite(rate).all():
        raise V51Error("现金日收益算不出来")
    return pd.Series(rate * gap / 360.0, index=dates, dtype=float, name=CASH)


def spy_sessions(spy: pd.Series) -> pd.DatetimeIndex:
    series = spy.sort_index().loc[:WINDOW_END]
    dates = pd.DatetimeIndex(series.index).normalize()
    if dates.has_duplicates or not dates.is_monotonic_increasing or len(dates) == 0:
        raise V51Error("SPY 日历不唯一")
    if pd.Timestamp(dates.max()) < pd.Timestamp(WINDOW_END):
        raise V51Error("SPY 没有覆盖到 2026-09-30")
    if dates.searchsorted(pd.Timestamp(WINDOW_START)) >= len(dates):
        raise V51Error("窗口里没有 SPY 交易日")
    return dates


def build_panels(closes: dict[str, pd.Series], calendar: pd.DatetimeIndex, rates: pd.Series
                 ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """原始收盘、用于排名的日收益、以及连续五个 G 日没有成交的天数。

    缺价日沿用最近收盘，所以中间一两天的收益是 0。最近五个 G 日都没有打印时，
    收益改成空值，这一天退出排名。硬闸门用原始收盘，缺打印的日子不更新高点。
    """
    raw = {}
    returns = {}
    stale = {}
    for name in traded_names():
        if name not in closes:
            raise V51Error(f"G 池缺少 {name}")
        native = closes[name].reindex(calendar)
        observed = native.notna()
        level = native.ffill()
        recent = observed.astype(float).rolling(STALE_LIMIT, min_periods=1).sum()
        fresh = recent.gt(0) & level.notna()
        change = level.pct_change()
        returns[name] = change.where(fresh)
        raw[name] = native
        stale[name] = int((level.notna() & ~fresh).sum())
    returns[CASH] = cash_returns(calendar, rates, None)
    raw[CASH] = pd.Series(np.nan, index=calendar, dtype=float)
    return pd.DataFrame(raw, index=calendar), pd.DataFrame(returns, index=calendar), stale


def window_slice(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.loc[WINDOW_START:WINDOW_END]
    if out.empty:
        raise V51Error("窗口里没有行")
    if pd.Timestamp(out.index.min()) < pd.Timestamp(WINDOW_START):
        raise V51Error("窗口切片早于 2003-07-01")
    if pd.Timestamp(out.index.max()) > pd.Timestamp(WINDOW_END):
        raise V51Error("窗口切片晚于 2026-09-30")
    return out


def fees_for(columns: list[str]) -> dict[str, float]:
    return {name: LEG for name in columns}


def _score_block(case: str, segment: str, start: str, end: str, strategy: pd.Series, benchmark: pd.Series) -> dict:
    left = strategy.loc[start:end].astype(float)
    right = benchmark.loc[start:end].astype(float)
    if left.empty or right.empty:
        raise V51Error(f"{case} {segment} 没有日收益")
    if not np.isfinite(left.to_numpy(dtype=float)).all() or not np.isfinite(right.to_numpy(dtype=float)).all():
        raise V51Error(f"{case} {segment} 的日收益有空值")
    depth_s = max_drawdown(left)
    depth_b = max_drawdown(right)
    return {
        "case": case,
        "segment": segment,
        "start": str(pd.Timestamp(left.index[0]).date()),
        "end": str(pd.Timestamp(left.index[-1]).date()),
        "n": int(len(left)),
        "n_benchmark": int(len(right)),
        "cagr": cagr(left),
        "max_drawdown": depth_s["max_drawdown"],
        "max_drawdown_peak": str(pd.Timestamp(depth_s["peak"]).date()),
        "max_drawdown_trough": str(pd.Timestamp(depth_s["trough"]).date()),
        "calmar": calmar(left),
        "bm_cagr": cagr(right),
        "bm_max_drawdown": depth_b["max_drawdown"],
        "bm_calmar": calmar(right),
    }


def run_v51(window_returns: pd.DataFrame, long_returns: pd.DataFrame, prices: pd.DataFrame, universe: Universe,
            cadence: str = "frozen"):
    """冻结规则。读数看得到窗口之前的收盘；持仓从窗口第一天的现金走起。

    `cadence` 默认 frozen。别的值只给 D37，不写本目录的签收结果。
    """
    from .allocate import allocate
    from .readings import read_panel

    panel = read_panel(long_returns, CASH, allow_after=True)
    allocation = allocate(
        window_returns.index, panel.H, panel.F, panel.E, universe,
        prices=prices.reindex(window_returns.index), returns=window_returns,
        allow_after=True, cadence=cadence,
    )
    missing = [name for name in allocation.decisions.columns if name not in window_returns.columns]
    if missing:
        raise V51Error(f"v5.1 的决策有行情没有的列：{missing[:5]}")
    book = simulate(
        window_returns, to_execution(allocation.decisions, window_returns.index),
        fees_for(list(window_returns.columns)), CASH,
        trade_eps=TRADE_EPS, allow_after=True,
    )
    return allocation, book, panel


def run_e2(long_returns: pd.DataFrame, window_returns: pd.DataFrame, prices: pd.DataFrame):
    """E2 式：N ∈ {3, 5, 8} × 周、月，六路平均，10% 离场。成交按 G 池，不打开涨跌停和溢价。"""
    from src.v3.engine.arms import execute
    from src.v3.engine.market import market_from_returns
    from src.v3.engine.spec import load_spec
    from src.v3.engine.switches import EngineSwitches

    spec = load_spec()
    if spec.candidates() != (
        (3, "week"), (3, "month"), (5, "week"), (5, "month"), (8, "week"), (8, "month"),
    ):
        raise V51Error("E2 的六路和 v3 写死的候选集不一致")
    levels = prices.reindex(window_returns.index)
    market = market_from_returns(
        window_returns, fees_for(list(window_returns.columns)),
        cash_id=CASH, levels=levels,
    )
    market.signal = long_returns.loc[:, window_returns.columns]
    if CASH not in market.signal.columns or market.signal[CASH].isna().any():
        raise V51Error("E2 的长历史缺现金")
    book = execute(market, spec, "A", allow_after=True, switches=EngineSwitches())
    if len(book.paths) != 6:
        raise V51Error(f"E2 应该是六路，实际 {len(book.paths)}")
    return book


def _marked(level: pd.Series, day) -> bool:
    stamp = pd.Timestamp(day)
    if stamp not in level.index:
        return False
    value = level.loc[stamp]
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return bool(np.isfinite(number) and number > 0.0)


def a1_weights(levels: pd.DataFrame, cash: pd.Series, month_ends, day) -> dict[str, float]:
    """SPY 的 12 个月收益不高于现金则全仓 IEF；否则全仓 SPY、EFA 里 12 个月收益更高的一只。

    两条相等时持有先写到的 SPY。历史不够、或该持有的那只没有收盘时，拿现金。
    """
    cash_book = {"SPY": 0.0, "EFA": 0.0, "IEF": 0.0, CASH: 1.0}
    equity = trailing_price_return(levels["SPY"], month_ends, day, 12)
    hurdle = trailing_cash_return(cash, month_ends, day, 12)
    if equity is None or hurdle is None:
        return cash_book
    if not equity > hurdle:
        if not _marked(levels["IEF"], day):
            return cash_book
        return {"SPY": 0.0, "EFA": 0.0, "IEF": 1.0, CASH: 0.0}
    other = trailing_price_return(levels["EFA"], month_ends, day, 12)
    if other is None:
        return cash_book
    chosen = "EFA" if other > equity else "SPY"
    if not _marked(levels[chosen], day):
        return cash_book
    weights = {"SPY": 0.0, "EFA": 0.0, "IEF": 0.0, CASH: 0.0}
    weights[chosen] = 1.0
    return weights


def a1_decisions(levels: pd.DataFrame, cash: pd.Series, calendar: pd.DatetimeIndex,
                 window: pd.DatetimeIndex) -> pd.DataFrame:
    """月末决策只用窗口内的月末。12 个月的比较可以落到窗口之前的月末收盘。"""
    ends = decision_dates(calendar, "month")
    columns = ["SPY", "EFA", "IEF", CASH]
    rows = []
    index = []
    first = pd.Timestamp(window.min())
    last = pd.Timestamp(window.max())
    for day in ends:
        stamp = pd.Timestamp(day)
        if stamp < first or stamp > last:
            continue
        weights = a1_weights(levels, cash, ends, stamp)
        rows.append([weights[name] for name in columns])
        index.append(stamp)
    if not rows:
        raise V51Error("A1 没有决策日")
    return pd.DataFrame(rows, index=pd.DatetimeIndex(index), columns=columns)


def run_a1(levels: pd.DataFrame, cash: pd.Series, calendar: pd.DatetimeIndex, window_returns: pd.DataFrame):
    decisions = a1_decisions(levels, cash, calendar, window_returns.index)
    book = simulate(
        window_returns, to_execution(decisions, window_returns.index),
        fees_for(list(window_returns.columns)), CASH,
        trade_eps=TRADE_EPS, allow_after=True,
    )
    book.decisions = decisions
    return book


def benchmark_g(returns: pd.DataFrame) -> pd.DataFrame:
    """60% SPY + 40% IEF。每月第一个 G 日开盘前回到目标，当天按目标拿收益，并付换仓的腿成本。

    窗口第一天已经按目标建仓，不另收一笔开仓费。
    """
    if "SPY" not in returns.columns or BOND not in returns.columns:
        raise V51Error("基准 G 缺 SPY 或 IEF")
    target = {"SPY": 0.60, BOND: 0.40}
    held = dict(target)
    fee = fees_for(["SPY", BOND])
    prev = None
    rows = []
    for day, row in returns.iterrows():
        stamp = pd.Timestamp(day)
        period = stamp.to_period("M")
        cost = 0.0
        buy = 0.0
        sell = 0.0
        if prev is not None and period != prev:
            cost, buy, sell = leg_cost(held, target, fee, TRADE_EPS)
            held = dict(target)
        spy = float(row["SPY"])
        ief = float(row[BOND])
        if not np.isfinite(spy) or not np.isfinite(ief):
            raise V51Error(f"基准 G 在 {stamp.date()} 没有 SPY 或 IEF 的收益")
        gain, drifted = drift(held, {"SPY": spy, BOND: ief})
        rows.append({
            "net": gain - cost,
            "gross": gain,
            "cost": cost,
            "buy": buy,
            "sell": sell,
            "SPY": held["SPY"],
            BOND: held[BOND],
        })
        held = drifted
        prev = period
    frame = pd.DataFrame(rows, index=returns.index)
    frame.index.name = "date"
    return frame


def g_single_name_nets(returns: pd.DataFrame, decisions: pd.DatetimeIndex, picks: list[list[str]]) -> np.ndarray:
    """每月末一只满仓，下一 G 日收盘换。没有涨跌停。换仓两边各付 0.1%。"""
    from src.v3.engine.book import assert_window

    frame = returns.copy()
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index)).normalize()
    assert_window(frame.index, True)
    if CASH not in frame.columns:
        raise V51Error("收益里没有现金列")
    columns = list(frame.columns)
    if any(len(row) != len(decisions) for row in picks):
        raise V51Error("每次模拟的决定个数要和决策日一致")
    positions = execution_positions(frame.index, decisions)
    keep = positions >= 0
    if len(positions[keep]) != len(set(positions[keep].tolist())):
        raise V51Error("两个决策日落到了同一个成交日")
    codes = {name: i for i, name in enumerate(columns)}
    unknown = sorted({name for row in picks for name in row if name not in codes})
    if unknown:
        raise V51Error(f"随机抽到了收益里没有的容器：{unknown[:5]}")
    exec_pos = positions[keep]
    desired = np.empty((len(picks), int(keep.sum())), dtype=np.int16)
    for i, row in enumerate(picks):
        kept = [name for name, use in zip(row, keep) if use]
        desired[i] = [codes[name] for name in kept]
    values = frame.to_numpy(dtype=float)
    values = np.where(np.isfinite(values), values, 0.0)
    cash_i = np.int16(codes[CASH])
    hold = np.full(len(picks), cash_i, dtype=np.int16)
    gross = np.zeros((len(picks), len(frame)), dtype=float)
    cost = np.zeros((len(picks), len(frame)), dtype=float)
    exec_at = {int(pos): i for i, pos in enumerate(exec_pos)}
    both = 2.0 * LEG
    for t in range(len(frame)):
        gross[:, t] = values[t, hold]
        if t not in exec_at:
            continue
        target = desired[:, exec_at[t]]
        change = target != hold
        if not change.any():
            continue
        cost[change, t] = both
        hold[change] = target[change]
    return gross - cost


def _distribution(matrix: np.ndarray, dates: pd.DatetimeIndex) -> pd.DataFrame:
    series = pd.Series(matrix[0], index=dates)
    growth = np.cumprod(1.0 + matrix, axis=1)
    years = matrix.shape[1] / 252.0
    annual = growth[:, -1] ** (1.0 / years) - 1.0
    drawdown = growth / np.maximum.accumulate(growth, axis=1) - 1.0
    depth = drawdown.min(axis=1)
    ratio = annual / np.abs(depth)
    if abs(float(annual[0]) - cagr(series)) > 1e-12:
        raise V51Error("R0 年化和 metrics.cagr 不一致")
    if abs(float(depth[0]) - max_drawdown(series)["max_drawdown"]) > 1e-12:
        raise V51Error("R0 回撤和 metrics.max_drawdown 不一致")
    if abs(float(ratio[0]) - calmar(series)) > 1e-12:
        raise V51Error("R0 Calmar 和 metrics.calmar 不一致")
    return pd.DataFrame({"sim": np.arange(len(annual)), "cagr": annual, "max_drawdown": depth, "calmar": ratio})


def _check_one(returns: pd.DataFrame, decisions: pd.DatetimeIndex, picks: list[str], nets: np.ndarray, row: int) -> None:
    frame = decision_frame(list(returns.columns), CASH, decisions, picks)
    book = simulate(
        returns, to_execution(frame, returns.index), fees_for(list(returns.columns)), CASH,
        trade_eps=TRADE_EPS, allow_after=True,
    )
    gap = float(np.max(np.abs(book.net.to_numpy(dtype=float) - nets[row])))
    if gap > 1e-8:
        raise V51Error(f"G 池 R0 快速成交和逐笔成交不一致（模拟 {row}，最大差 {gap:.3g}）")


def run_r0(panel, universe: Universe, window_returns: pd.DataFrame, folder: Path) -> dict:
    dates = pd.DatetimeIndex(window_returns.index).normalize()
    months = decision_dates(dates, "month")
    if months.empty:
        raise V51Error("G 池 R0 没有月末")
    roster = [rankable_names(panel, universe, day, None) for day in months]
    print(f"G 池 R0 抽 {N_SIMS} 次，月末 {len(months)} 个", flush=True)
    picks = draw_names(roster, n=N_SIMS, seed=SEED, cash_id=CASH)
    nets = g_single_name_nets(window_returns, months, picks)
    _check_one(window_returns, months, picks[0], nets, 0)
    _check_one(window_returns, months, picks[1], nets, 1)
    sims = _distribution(nets, dates)
    if int(sims["cagr"].isna().sum()) or int(sims["calmar"].isna().sum()):
        raise V51Error("G 池 R0 有模拟没有年化或 Calmar")
    stats = {
        "pool": "G",
        "n": N_SIMS,
        "seed": SEED,
        "cagr_median": float(sims["cagr"].median()),
        "cagr_p95": _quantile(sims["cagr"], 0.95),
        "calmar_median": float(sims["calmar"].median()),
        "calmar_p95": _quantile(sims["calmar"], 0.95),
        "max_drawdown_median": float(sims["max_drawdown"].median()),
        "months": int(len(months)),
        "eligible_mean": float(np.mean([len(names) for names in roster])),
    }
    if stats["eligible_mean"] <= 0.0:
        raise V51Error("G 池 R0 没有任何月份有可排名的容器")
    folder.mkdir(parents=True, exist_ok=True)
    sims.to_csv(folder / "sims.csv", index=False, float_format="%.16g")
    pd.DataFrame([{
        "date": pd.Timestamp(day).date().isoformat(),
        "n": len(names),
        "names": "|".join(names),
    } for day, names in zip(months, roster)]).to_csv(folder / "eligibility.csv", index=False)
    pd.DataFrame({
        "date": [pd.Timestamp(day).date().isoformat() for day in months],
        "name": picks[0],
    }).to_csv(folder / "draws-0.csv", index=False)
    pd.DataFrame([stats]).to_csv(folder / "summary.csv", index=False, float_format="%.16g")
    print(
        f"G 池 R0 年化中位 {stats['cagr_median']:.4f} Calmar95 {stats['calmar_p95']:.4f}",
        flush=True,
    )
    return stats


def apply_g_results(rows: list[dict], *, calmar_value: float, calmar_hurdle: float,
                    cagr_value: float, cagr_hurdle: float, n: int, seed: int) -> list[dict]:
    """只改 §6.3 第 5 条和入围注记。第 6 条保持原样。不把整张表写成入围。"""
    out = [dict(row) for row in rows]
    calmar_ok = bool(np.isfinite(calmar_value) and np.isfinite(calmar_hurdle) and calmar_value > calmar_hurdle)
    cagr_ok = bool(np.isfinite(cagr_value) and np.isfinite(cagr_hurdle) and cagr_value > cagr_hurdle)
    seen = {"calmar": False, "cagr": False}
    for row in out:
        if row.get("item") != "5" or row.get("pool") != "G":
            continue
        if row.get("metric") == "calmar":
            row["strategy"] = _num(calmar_value)
            row["benchmark"] = _num(calmar_hurdle)
            row["status"] = "通过" if calmar_ok else "未通过"
            row["note"] = f"G 的 R0 {n} 次；种子 {seed}；高于 95 分位"
            seen["calmar"] = True
        elif row.get("metric") == "cagr":
            row["strategy"] = _num(cagr_value)
            row["benchmark"] = _num(cagr_hurdle)
            row["status"] = "通过" if cagr_ok else "未通过"
            row["note"] = f"基准 G 年化 {_num(cagr_hurdle)}；区间 {WINDOW_START} → {WINDOW_END}"
            seen["cagr"] = True
    if not seen["calmar"] or not seen["cagr"]:
        raise V51Error("过关表没有 §6.3 第 5 条的两行")
    scored = [row["status"] for row in out if row["status"] in {"通过", "未通过"}]
    pending = [row["status"] for row in out if str(row.get("status", "")).startswith("待")]
    for row in out:
        if row.get("item") != "入围":
            continue
        if pending or any(status != "通过" for status in scored):
            row["status"] = "未完成"
            row["note"] = (
                f"第 5 条已写入 G 池：年化÷最大回撤{'通过' if calmar_ok else '未通过'}，"
                f"十年以上年化{'通过' if cagr_ok else '未通过'}。"
                "第 6 条仍未通过。稳健性未跑。这张表不是入围结论"
            )
        else:
            row["status"] = "通过"
            row["note"] = "§6.3 已列条目全部通过"
    return out


def _patch_gate(path: Path, **kwargs) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = apply_g_results(list(reader), **kwargs)
    if not fields:
        raise V51Error("过关表没有表头")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _mark_design_manifest() -> None:
    if not DESIGN_MANIFEST.is_file():
        return
    payload = json.loads(DESIGN_MANIFEST.read_text(encoding="utf-8"))
    payload["excluded"] = ["R1", "robustness"]
    payload["r6"] = "results/v5.1/other-market"
    DESIGN_MANIFEST.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _base_params(case: str) -> dict:
    from .params import Params

    frozen = Params()
    universe = g_universe()
    return {
        "rules": "v5.1",
        "case": case,
        "kind": SEGMENT,
        "pool": "G",
        "start": WINDOW_START,
        "end": WINDOW_END,
        "h1_end": H1_END,
        "h2_start": H2_START,
        "prices": "yahoo adjclose",
        "price_disclosure": "分红调整后的价格，不是官方全收益指数",
        "calendar": "SPY",
        "cash": "DTB3",
        "cash_daycount": "ACT/360",
        "cost_per_leg": LEG,
        "fill": "next G close",
        "limits": False,
        "premium": False,
        "china_pnl": False,
        "robustness": False,
        "layer1": [market.name for market in universe.markets],
        "representative": {market.name: market.representative for market in universe.markets},
        "members": {market.name: list(market.members) for market in universe.markets},
        "bond": universe.bond,
        "gold": universe.gold,
        "frontier": frozen.frontier,
        "noise_band": frozen.noise_band,
        "top_n": frozen.top_n,
        "hard_stop": frozen.hard_stop,
        "breadth_min": frozen.breadth_min,
        "slow_gap": frozen.slow_gap,
        "long_min_days": frozen.long_min_days,
        "sigma_window": frozen.sigma_window,
        "quantile_min": frozen.quantile_min,
        "rulers": list(frozen.rulers),
    }


def record_g(params: dict, path: Path = LEDGER, *, runner: str = RUNNER) -> None:
    """同一臂、同一段只留一行。不碰设计期和 R5 对照，不写 LOCK。"""
    _refuse_ledger(path)
    if params.get("kind") != SEGMENT or params.get("pool") != "G":
        raise V51Error("别的市场账本只收 G 池")
    if params.get("china_pnl") or params.get("robustness"):
        raise V51Error("这一行不能登记中国 2016 年以后的收益或稳健性")
    arm = str(params["case"])
    fresh = {
        "run_at": datetime.now(TAIPEI).isoformat(timespec="seconds"),
        "git_sha": git_head() or "",
        "arm": arm,
        "params": canonical_params(params),
        "segment": SEGMENT,
        "runner": runner,
    }
    kept = []
    newline = "\n"
    if path.exists() and b"\r\n" in path.read_bytes():
        newline = "\r\n"
    for row in _rows(path):
        try:
            old = json.loads(row.get("params") or "{}")
        except json.JSONDecodeError:
            kept.append(row)
            continue
        if row.get("arm") == arm and row.get("segment") == SEGMENT and old.get("pool") == "G" and old.get("kind") == SEGMENT:
            continue
        kept.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator=newline)
        writer.writeheader()
        writer.writerows(kept)
        writer.writerow(fresh)


def _write_run(folder: Path, book, decisions: pd.DataFrame | None, exits: pd.DataFrame | None,
               state: pd.DataFrame | None) -> pd.Series:
    net = book.net.astype(float).sort_index()
    net.index = pd.DatetimeIndex(pd.to_datetime(net.index)).normalize()
    if pd.Timestamp(net.index.min()) < pd.Timestamp(WINDOW_START) or pd.Timestamp(net.index.max()) > pd.Timestamp(WINDOW_END):
        raise V51Error("写出的净值超出 G 池区间")
    if not np.isfinite(net.to_numpy(dtype=float)).all():
        raise V51Error("日收益有空值")
    folder.mkdir(parents=True, exist_ok=True)
    daily = pd.DataFrame({
        "net": net,
        "gross": book.gross.reindex(net.index).astype(float),
        "nav": (1.0 + net).cumprod(),
        "cost": book.cost.reindex(net.index).astype(float),
        "buy": book.buy.reindex(net.index).astype(float),
        "sell": book.sell.reindex(net.index).astype(float),
    })
    if state is not None:
        aligned = state.copy()
        aligned.index = pd.DatetimeIndex(pd.to_datetime(aligned.index)).normalize()
        daily = daily.join(aligned.reindex(net.index))
    daily.index.name = "date"
    daily.to_csv(folder / "daily.csv", float_format="%.12g")
    if decisions is not None:
        frame = decisions.copy()
        frame.index.name = "date"
        frame.to_csv(folder / "decisions.csv", float_format="%.12g")
    if exits is not None:
        exits.to_csv(folder / "exits.csv", index=False)
    held = book.held.copy()
    held.index = pd.DatetimeIndex(pd.to_datetime(held.index)).normalize()
    held.index.name = "date"
    held.to_csv(folder / "held.csv", float_format="%.12g")
    years = [{"year": year, "return": value} for year, value in yearly_returns(net).items()]
    pd.DataFrame(years).to_csv(folder / "yearly.csv", index=False)
    (folder / "net-sha256.txt").write_text(series_sha256(net) + "\n", encoding="utf-8")
    return net


def run_gpool(*, ledger: Path = LEDGER, out: Path = OUT, gate: Path = GATE) -> dict:
    """G 池整套只跑这一次：v5.1、E2 式、A1、基准 G、R0。"""
    _refuse_ledger(ledger)
    if not gate.is_file():
        raise V51Error("还没有设计期过关表")
    universe = g_universe()
    print("核对已登记的行情文件", flush=True)
    digests = check_registered(raw_tickers())
    closes = {name: load_adjclose(name) for name in traded_names()}
    rates = load_dtb3()
    calendar = spy_sessions(closes["SPY"])
    print(f"G 日历 {calendar.min().date()} → {calendar.max().date()}，{len(calendar)} 天", flush=True)
    prices, long_returns, stale = build_panels(closes, calendar, rates)
    window_returns = window_slice(long_returns)
    if window_returns[CASH].isna().any():
        raise V51Error("窗口里的现金收益有空值")
    if window_returns["SPY"].isna().any():
        raise V51Error("窗口里的 SPY 收益有空值")
    print("v5.1 读数与成交", flush=True)
    allocation, v51_book, panel = run_v51(window_returns, long_returns, prices, universe)
    print("E2 式", flush=True)
    e2_book = run_e2(long_returns, window_returns, prices)
    print("A1", flush=True)
    a1_book = run_a1(prices, long_returns[CASH], calendar, window_returns)
    print("基准 G", flush=True)
    bench = benchmark_g(window_returns)
    bench_net = bench["net"].astype(float)
    blocks = []
    nets = {
        "v5.1": _write_run(out / "v51", v51_book, allocation.decisions, allocation.exits, allocation.state),
        "E2式": _write_run(out / "e2", e2_book, e2_book.decisions, e2_book.exits, None),
        "A1": _write_run(out / "a1", a1_book, a1_book.decisions, getattr(a1_book, "exits", None), None),
    }
    for case, series in nets.items():
        for segment, start, end in SEGMENTS:
            blocks.append(_score_block(case, segment, start, end, series, bench_net))
    for segment, start, end in SEGMENTS:
        row = _score_block("BM-G", segment, start, end, bench_net, bench_net)
        blocks.append(row)
    r0 = run_r0(panel, universe, window_returns, out / "r0")
    full = next(row for row in blocks if row["case"] == "v5.1" and row["segment"] == "full")
    if abs(full["bm_cagr"] - cagr(bench_net)) > 1e-12:
        raise V51Error("基准 G 的年化对不齐")
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(blocks).to_csv(out / "summary.csv", index=False, float_format="%.16g")
    bench.to_csv(out / "benchmark.csv", float_format="%.12g")
    payloads = [
        _base_params("v5.1"),
        {**_base_params("E2式"), "engine": "v3.1 A", "paths": "3/5/8 × week/month", "exit_drawdown": 0.10},
        {**_base_params("A1"), "rule": "SPY 12m vs cash; else higher of SPY and EFA; else IEF", "lookback_months": 12},
        {**_base_params("R0"), "n": N_SIMS, "seed": SEED, "decision": "month",
         "eligibility": "layer1 members with H F E", "hold": "one full"},
    ]
    protocol = {
        "rules": "v5.1",
        "pool": "G",
        "window": [WINDOW_START, WINDOW_END],
        "segments": {"h1": [WINDOW_START, H1_END], "h2": [H2_START, WINDOW_END]},
        "signal": "窗口之前已有的 adjclose 只用于读数和 12 个月收益；持仓从窗口第一天的现金起算",
        "prices": "Yahoo adjclose。分红调整后的价格，不是官方全收益指数。",
        "calendar": "SPY 有收盘的日子",
        "cash": "DTB3 ÷ 100 × 距上一个 G 日的自然日数 ÷ 360；不晚于当天的最近一个值",
        "cost_per_leg": LEG,
        "fill": "下一 G 日收盘；没有涨跌停；不用 QDII 溢价",
        "stale_limit": STALE_LIMIT,
        "stale_days": stale,
        "raw_sha256": digests,
        "git_sha": git_head() or "",
        "v51_full": {"cagr": full["cagr"], "max_drawdown": full["max_drawdown"], "calmar": full["calmar"]},
        "benchmark_full": {"cagr": full["bm_cagr"], "calmar": full["bm_calmar"]},
        "r0": r0,
        "gate5": {
            "calmar_pass": bool(full["calmar"] > r0["calmar_p95"]),
            "cagr_pass": bool(full["cagr"] > full["bm_cagr"]),
        },
        "china_pnl": False,
        "robustness": False,
        "lock": False,
    }
    (out / "manifest.json").write_text(
        json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out / "params.json").write_text(
        json.dumps(payloads, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _patch_gate(
        gate,
        calmar_value=full["calmar"],
        calmar_hurdle=r0["calmar_p95"],
        cagr_value=full["cagr"],
        cagr_hurdle=full["bm_cagr"],
        n=r0["n"],
        seed=r0["seed"],
    )
    _mark_design_manifest()
    for payload in payloads:
        record_g(payload, ledger)
    print(
        f"v5.1 年化 {full['cagr']:.4f} Calmar {full['calmar']:.4f}；"
        f"基准 G {full['bm_cagr']:.4f}；R0 Calmar95 {r0['calmar_p95']:.4f}",
        flush=True,
    )
    return {"full": full, "r0": r0, "stale_days": stale}
