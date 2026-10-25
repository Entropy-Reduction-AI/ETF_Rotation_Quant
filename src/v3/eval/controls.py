"""§6② 随机对照。

零假设 B 的权重和 `src.v3.engine.control.null_b_targets` 是同一条规则：现金权重与策略相同，
其余资金在全池里无放回等权抽取 K 只，K 是权重大于 ε 的非现金容器个数。
零假设 A 把抽取范围收成决策日当天有资格的容器。有资格 = 任一回看期的绝对过滤通过，
并且流动性门（若有）也通过。成交日对应的决策日是上一个交易日。

名次：`percentile` = 年化不高于策略的对照次数 / 对照次数。前 10% 指 percentile ≥ 0.90。
两次对照各自从 `config/v3/arms.toml` 的种子重新起一个随机数流。默认 1,000 次。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.v3.engine.book import simulate
from src.v3.engine.control import null_b_targets
from src.v3.engine.score import lookback_panel
from src.v3.engine.spec import load_spec

from .common import EvalError, annualized_return, require_design_period

TOP_DECILE = 0.90


def percentile_rank(strategy_ann: float, null_anns) -> dict:
    """策略在对照年化里的位置。并列算作没有跑赢策略。"""
    nulls = np.asarray(null_anns, dtype=float)
    if nulls.ndim != 1 or len(nulls) == 0:
        raise EvalError("随机对照是空的")
    if not np.isfinite(strategy_ann) or not np.isfinite(nulls).all():
        raise EvalError("年化里有空值")
    n_better = int(np.sum(nulls > strategy_ann))
    n_worse = int(np.sum(nulls < strategy_ann))
    n_tie = int(len(nulls) - n_better - n_worse)
    percentile = (n_worse + n_tie) / len(nulls)
    return {
        "n_trials": int(len(nulls)),
        "n_better": n_better,
        "n_worse": n_worse,
        "n_tie": n_tie,
        "fraction_strictly_worse": n_worse / len(nulls),
        "percentile": float(percentile),
        "in_top_decile": bool(percentile >= TOP_DECILE),
        "rank_from_best": n_better + 1,
    }


def _summarize(strategy_ann: float, nulls: np.ndarray) -> dict:
    rank = percentile_rank(strategy_ann, nulls)
    rank["annualized"] = [float(value) for value in nulls]
    rank["median"] = float(np.median(nulls))
    return rank


def null_a_targets(targets: pd.DataFrame, names: list[str], cash_id: str, rng, eps: float,
                   eligible: pd.DataFrame) -> pd.DataFrame:
    """和零假设 B 同一条权重，池子换成当天有资格的容器。一个都没有资格时，这一天全部持有现金。"""
    pool = [name for name in names if name != cash_id]
    rows = []
    index = []
    gate = eligible.sort_index()
    for day, row in targets.sort_index().iterrows():
        stamp = pd.Timestamp(day)
        cash_weight = float(row.get(cash_id, 0.0))
        held = [name for name in pool if float(row.get(name, 0.0)) > eps]
        allowed = [name for name in pool if bool(gate.loc[stamp, name])]
        count = min(len(held), len(allowed))
        weights = {name: 0.0 for name in pool}
        if count == 0:
            weights[cash_id] = 1.0
        else:
            weights[cash_id] = cash_weight
            chosen = list(rng.choice(np.array(allowed, dtype=object), size=count, replace=False))
            each = (1.0 - cash_weight) / count
            for name in chosen:
                weights[name] = each
        rows.append([weights.get(name, 0.0) for name in [*pool, cash_id]])
        index.append(stamp)
    return pd.DataFrame(rows, index=pd.DatetimeIndex(index), columns=[*pool, cash_id])


def _annualized_paths(pnl, targets, fees, cash_id, names, *, n_trials: int, seed: int, eps: float,
                      eligible: pd.DataFrame | None, trade_eps: float, cost_multiplier: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = np.empty(n_trials, dtype=float)
    ordered = targets.sort_index()
    for i in range(n_trials):
        if eligible is None:
            drawn = null_b_targets(ordered, names, cash_id, rng, eps)
        else:
            drawn = null_a_targets(ordered, names, cash_id, rng, eps, eligible)
        book = simulate(
            pnl, drawn, fees, cash_id, trade_eps=trade_eps,
            cost_multiplier=cost_multiplier, allow_after=False)
        out[i] = annualized_return(book.net.to_numpy())
    return out


def eligibility(market, spec) -> pd.DataFrame:
    """每个交易日、每只非现金容器：任一回看期通过绝对过滤，流动性门也通过。"""
    names = list(market.names)
    ok = None
    for length in spec.lookbacks:
        panel = lookback_panel(market.signal, market.cash_id, length)
        flag = panel.ok[names].copy()
        if market.liquidity is not None:
            flag = flag & market.liquidity[names].astype(bool)
        ok = flag if ok is None else (ok | flag)
    return ok


def eligibility_on_targets(market, spec, targets: pd.DataFrame) -> pd.DataFrame:
    """成交日那一行用上一个交易日的资格。上一个交易日是 `to_execution` 的决策日。"""
    ok = eligibility(market, spec)
    dates = pd.DatetimeIndex(pd.to_datetime(market.dates)).sort_values()
    rows = []
    index = []
    for day in targets.sort_index().index:
        stamp = pd.Timestamp(day)
        pos = int(dates.searchsorted(stamp, side="left"))
        if pos >= len(dates) or pd.Timestamp(dates[pos]) != stamp or pos == 0:
            raise EvalError(f"{stamp.date()} 对不上一条由决策日推出来的成交日")
        decision = pd.Timestamp(dates[pos - 1])
        rows.append(ok.loc[decision].to_numpy(dtype=bool))
        index.append(stamp)
    return pd.DataFrame(rows, index=pd.DatetimeIndex(index), columns=ok.columns)


def criterion_2(strategy, pnl, targets, fees, names, cash_id, *, n_trials: int = 1000,
                seed: int | None = None, eps: float | None = None, eligible: pd.DataFrame | None = None,
                trade_eps: float | None = None, cost_multiplier: float = 1.0) -> dict:
    """策略全期年化相对 1,000 次零假设 B 的位置。给出资格表时同时报告零假设 A。"""
    spec = load_spec()
    if seed is None:
        seed = int(spec.seed)
    if eps is None:
        eps = float(spec.weight_eps)
    if trade_eps is None:
        trade_eps = float(spec.trade_eps)
    if n_trials < 1:
        raise EvalError("对照次数至少为 1")
    require_design_period(pd.Series(strategy).index)
    require_design_period(pnl.index)
    require_design_period(targets.index)
    if eligible is not None:
        require_design_period(eligible.index)
    aligned = pd.Series(strategy, dtype=float).reindex(pnl.index)
    if aligned.isna().any():
        raise EvalError("策略收益和行情日期对不齐")
    strategy_ann = annualized_return(aligned.to_numpy())
    null_b = _annualized_paths(
        pnl, targets, fees, cash_id, names, n_trials=n_trials, seed=seed, eps=eps,
        eligible=None, trade_eps=trade_eps, cost_multiplier=cost_multiplier)
    result = {
        "strategy_ann": strategy_ann,
        "seed": int(seed),
        "null_b": _summarize(strategy_ann, null_b),
        "null_a": None,
        "engineering_check": None,
        "formal_pass": None,
    }
    result["engineering_check"] = result["null_b"]["in_top_decile"]
    if eligible is not None:
        null_a = _annualized_paths(
            pnl, targets, fees, cash_id, names, n_trials=n_trials, seed=seed, eps=eps,
            eligible=eligible, trade_eps=trade_eps, cost_multiplier=cost_multiplier)
        result["null_a"] = _summarize(strategy_ann, null_a)
    return result
