"""把设计期能算的数字收成一份复核用的字典。正式动作只在 `formal=True` 时对照 §7.3。"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .common import require_design_period
from .controls import criterion_2
from .drawdown import criterion_4, equity_weight, position_matched
from .eras import criterion_3
from .sharpe import criterion_5, trial_count
from .windows import criterion_1


def action_for(*, criterion_1: bool, criterion_2: bool, criterion_3: bool, criterion_4: bool,
               criterion_5: bool, formal: bool) -> dict:
    """§7.3。`formal=False` 时不把设计期数字当成通过与否。"""
    if not formal:
        return {
            "action": "未判定",
            "reason": "G3 之前设计期数字只作工程核对，不作通过与否。",
        }
    flags = (criterion_1, criterion_2, criterion_3, criterion_4, criterion_5)
    if all(flags):
        return {"action": "进入前向模拟盘", "reason": "①②③④⑤ 全部通过。真钱由 Owner 决定。"}
    if criterion_1 and criterion_3 and criterion_4 and not criterion_2:
        return {
            "action": "不作为轮动策略",
            "reason": "①③④ 通过、② 不通过。收益不是来自选择，是来自资产配置。",
        }
    if not criterion_1:
        return {"action": "关闭 v3", "reason": "① 不通过。"}
    if criterion_1 and criterion_2 and criterion_3 and criterion_4 and not criterion_5:
        return {
            "action": "进入前向模拟盘",
            "reason": "只有 ⑤ 不通过。标注证据弱，模拟盘期满前不上真钱。",
        }
    return {"action": "未列入 §7.3 的组合", "reason": "预注册没有给这个组合指定动作。"}


def plain(value):
    """时间戳改成日期字符串，元组键改成逗号分隔，便于复核时对照。"""
    if isinstance(value, dict):
        return {str(_key(key)): plain(item) for key, item in value.items()}
    if isinstance(value, pd.Series):
        return [{"date": plain(idx), "value": plain(item)} for idx, item in value.items()]
    if isinstance(value, np.ndarray):
        return [plain(item) for item in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return str(pd.Timestamp(value).date())
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return number
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _key(value):
    if isinstance(value, tuple):
        return ",".join(str(part) for part in value)
    return value


def evaluate_design(strategy, benchmark, calendar, *, targets=None, pnl=None, fees=None,
                    names=None, cash_id: str = "cash", eligible=None, n_trials: int = 1000,
                    seed: int | None = None, sr_variance: float | None = None,
                    ledger_path=None, cash=None, held=None, classes=None) -> dict:
    """设计期 ①③④，以及调用方给齐输入时的 ②⑤ 和仓位匹配。不判定通过。"""
    require_design_period(pd.Series(strategy).index)
    require_design_period(pd.Series(benchmark).index)
    report = {
        "period": "design",
        "end": "2015-12-31",
        "formal_pass": None,
        "action": action_for(
            criterion_1=False, criterion_2=False, criterion_3=False,
            criterion_4=False, criterion_5=False, formal=False),
        "criterion_1": plain(criterion_1(strategy, benchmark, calendar)),
        "criterion_3": plain(criterion_3(strategy, benchmark, calendar)),
        "criterion_4": plain(criterion_4(strategy, benchmark)),
        "criterion_2": None,
        "criterion_5": None,
        "position_matched": None,
        "trial_count": trial_count(ledger_path),
    }
    if targets is not None or pnl is not None or fees is not None:
        if targets is None or pnl is None or fees is None or names is None:
            raise ValueError("② 需要 targets、pnl、fees、names 一起给出")
        report["criterion_2"] = plain(criterion_2(
            strategy, pnl, targets, fees, names, cash_id, n_trials=n_trials, seed=seed,
            eligible=eligible))
    if sr_variance is not None:
        counted = trial_count(ledger_path)
        report["criterion_5"] = plain(criterion_5(
            strategy, n_trials=counted, sr_variance=sr_variance, cash=cash))
    if held is not None and classes is not None and cash is not None:
        weights = equity_weight(held, classes)
        report["position_matched"] = plain(position_matched(benchmark, cash, weights))
    return report
