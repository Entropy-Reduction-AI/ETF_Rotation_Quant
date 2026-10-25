"""§7.1 滚动前推，以及组合对称交叉验证的回测过拟合概率。

选择标准和引擎里的 B 臂相同：训练窗是扩张的，第一次用 2006-01 至 2010-12，用在 2011 年，
之后每年初把上一年加进去再选。IR 用 `src.v3.engine.arms.daily_ir`（超额均值 / 样本标准差 × √252）。
并列时保留 `keys` 里先出现的那一个。溢价参数要按 (W, θ) 从小到大放进 `keys`，这样并列会落到更小的那组。
本函数给出每年的选择和训练窗 IR，不把各年的独立净值串成一条假的 B 臂净值。
B 臂真正的持仓拼接在 `stitch_targets`，和引擎的 `select_b` 用同一条规则。

回测过拟合概率是 Bailey, Borwein, López de Prado and Zhu 的组合对称交叉验证：
把收益按时间切成偶数块（预注册写的全期是 2006–2026 的 16 块），
取全部 C(S, S/2) 种对半拆分。样本内夏普最高的候选，若样本外名次的
ω = rank / (N + 1) < 0.5，这一折记为过拟合。PBO 是这样的折数占比。
rank 从最差往最好数：1 + 严格更差的个数 + 0.5 ×（并列个数 − 1）。刚好落在中位不算过拟合。
样本内并列时取列顺序里更靠前的候选。长度除不尽块数时丢掉最早的行。

David H. Bailey, Jonathan M. Borwein, Marcos López de Prado and Qiji Jim Zhu,
"The Probability of Backtest Overfitting", Journal of Computational Finance 20(4), 2017.

带日期的收益晚于 2015-12-31 会拒绝。没有日期的数组只用于噪声检验，不是组合净值。
"""
from __future__ import annotations

import math
from itertools import combinations

import numpy as np
import pandas as pd

from src.v3.engine.arms import daily_ir

from .common import EvalError, require_design_period

PBO_BLOCKS = 16


def walk_forward(candidates: dict, benchmark, *, train_start: str, first_apply_year: int,
                 dates, keys: list | None = None) -> dict:
    """每年一个选择。`candidates` 的值是各候选自己的扣成本日收益。"""
    require_design_period(pd.Series(benchmark).index)
    require_design_period(dates)
    order = list(candidates) if keys is None else list(keys)
    missing = [key for key in order if key not in candidates]
    if missing:
        raise EvalError(f"候选里没有 {missing[0]}")
    for key in order:
        require_design_period(pd.Series(candidates[key]).index)
    span = pd.DatetimeIndex(pd.to_datetime(dates)).sort_values()
    if len(span) == 0:
        raise EvalError("没有交易日")
    start_year = int(pd.Timestamp(span.min()).year)
    end_year = int(pd.Timestamp(span.max()).year)
    floor = pd.Timestamp(train_start)
    bench = pd.Series(benchmark, dtype=float)
    years = []
    for year in range(start_year, end_year + 1):
        if year < first_apply_year:
            years.append({"year": year, "key": None, "ir": None, "ranking": []})
            continue
        train_end = pd.Timestamp(year=year - 1, month=12, day=31)
        ranking = []
        best_key = None
        best_ir = -math.inf
        for key in order:
            series = pd.Series(candidates[key], dtype=float)
            window = series[(series.index >= floor) & (series.index <= train_end)]
            score = daily_ir(window, bench)
            ranking.append({"key": key, "ir": None if score == -math.inf else float(score)})
            if score > best_ir:
                best_ir = score
                best_key = key
        if best_key is None or best_ir == -math.inf:
            years.append({"year": year, "key": None, "ir": None, "ranking": ranking})
            continue
        years.append({"year": year, "key": best_key, "ir": float(best_ir), "ranking": ranking})
    return {
        "years": years,
        "choices": {row["year"]: row["key"] for row in years},
    }


def premium_keys() -> tuple[tuple[int, float], ...]:
    """(W, θ) 按字典序。并列时 walk_forward 保留先出现的键，所以溢价参数用这个顺序。"""
    from src.v3.premium.rules import THETAS, WINDOWS
    return tuple((int(window), float(theta)) for window in WINDOWS for theta in THETAS)


def stitch_targets(frames: dict, choices: dict) -> pd.DataFrame:
    """把选中候选的成交目标按公历年拼起来。没有选择的年份不产生目标，账本保持现金。"""
    columns = None
    for frame in frames.values():
        columns = list(frame.columns)
        break
    parts = []
    for year in sorted(choices):
        key = choices[year]
        if key is None:
            continue
        targets = frames[key]
        if columns is None:
            columns = list(targets.columns)
        part = targets[targets.index.year == year]
        if len(part):
            parts.append(part)
    if not parts:
        return pd.DataFrame(columns=columns or [])
    out = pd.concat(parts).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    require_design_period(out.index)
    return out


def _as_matrix(returns, benchmark):
    if isinstance(returns, pd.DataFrame):
        require_design_period(returns.index)
        frame = returns.astype(float).sort_index()
        if benchmark is None:
            if frame.isna().any().any():
                raise EvalError("过拟合概率不接受空值")
            values = frame.to_numpy(dtype=float)
        else:
            bench = pd.Series(benchmark, dtype=float).reindex(frame.index)
            require_design_period(bench.index)
            if bench.isna().any() or frame.isna().any().any():
                raise EvalError("过拟合概率不接受空值")
            values = frame.to_numpy(dtype=float) - bench.to_numpy(dtype=float)[:, None]
        names = [str(column) for column in frame.columns]
        return values, names
    values = np.asarray(returns, dtype=float)
    if values.ndim != 2:
        raise EvalError("候选收益必须是二维的")
    if not np.isfinite(values).all():
        raise EvalError("过拟合概率不接受空值")
    if benchmark is not None:
        bench = np.asarray(benchmark, dtype=float)
        if bench.shape != (values.shape[0],):
            raise EvalError("基准长度和候选不一致")
        if not np.isfinite(bench).all():
            raise EvalError("过拟合概率不接受空值")
        values = values - bench[:, None]
    names = [str(i) for i in range(values.shape[1])]
    return values, names


def _sharpe_rows(sum_: np.ndarray, sumsq: np.ndarray, count: int) -> np.ndarray:
    mean = sum_ / count
    var = (sumsq - (sum_ ** 2) / count) / (count - 1)
    std = np.sqrt(np.maximum(var, 0.0))
    sharpe = np.zeros(mean.shape, dtype=float)
    positive = std > 0.0
    sharpe[positive] = mean[positive] / std[positive]
    sharpe[~positive & (mean > 0.0)] = np.inf
    sharpe[~positive & (mean < 0.0)] = -np.inf
    return sharpe


def cscv_pbo(returns, n_blocks: int = PBO_BLOCKS, benchmark=None) -> dict:
    """组合对称交叉验证。返回过拟合折数的占比。"""
    if n_blocks < 2 or n_blocks % 2 != 0:
        raise EvalError("组合对称交叉验证的块数必须是不小于 2 的偶数")
    values, names = _as_matrix(returns, benchmark)
    rows, cols = values.shape
    if cols < 1:
        raise EvalError("没有候选")
    usable = (rows // n_blocks) * n_blocks
    block = usable // n_blocks
    half = n_blocks // 2
    if block * half < 2:
        raise EvalError("每一折的样本短于 2，算不出标准差")
    trimmed = values[rows - usable:]
    shaped = trimmed.reshape(n_blocks, block, cols)
    block_sum = shaped.sum(axis=1)
    block_sumsq = np.square(shaped).sum(axis=1)
    combos = np.array(list(combinations(range(n_blocks), half)), dtype=int)
    is_sum = block_sum[combos].sum(axis=1)
    is_sumsq = block_sumsq[combos].sum(axis=1)
    total_sum = block_sum.sum(axis=0)
    total_sumsq = block_sumsq.sum(axis=0)
    count = block * half
    is_sharpe = _sharpe_rows(is_sum, is_sumsq, count)
    oos_sharpe = _sharpe_rows(total_sum - is_sum, total_sumsq - is_sumsq, count)
    selected = np.argmax(is_sharpe, axis=1)
    chosen = oos_sharpe[np.arange(len(combos)), selected]
    worse = np.sum(oos_sharpe < chosen[:, None], axis=1)
    tied = np.sum(oos_sharpe == chosen[:, None], axis=1)
    rank = 1.0 + worse + 0.5 * (tied - 1.0)
    omega = rank / (cols + 1)
    overfit = omega < 0.5
    return {
        "pbo": float(overfit.mean()),
        "n_splits": int(len(combos)),
        "n_blocks": int(n_blocks),
        "n_candidates": int(cols),
        "block_length": int(block),
        "dropped_rows": int(rows - usable),
        "not_above_half": bool(float(overfit.mean()) <= 0.5),
        "candidates": names,
        "formal_pass": None,
    }
