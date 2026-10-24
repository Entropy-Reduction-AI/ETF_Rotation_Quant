"""§6② 零假设 B 的权重。只服务引擎测试，不在这里做 1,000 次正式对照。"""
from __future__ import annotations

import numpy as np
import pandas as pd


def null_b_targets(targets: pd.DataFrame, names: list[str], cash_id: str, rng, eps: float) -> pd.DataFrame:
    """每个执行日保持策略的现金权重，其余资金在全池里无放回等权抽取同样个数的容器。"""
    pool = [name for name in names if name != cash_id]
    rows = []
    index = []
    for day, row in targets.iterrows():
        cash_weight = float(row.get(cash_id, 0.0))
        held = [name for name in pool if float(row.get(name, 0.0)) > eps]
        count = min(len(held), len(pool))
        weights = {name: 0.0 for name in pool}
        weights[cash_id] = cash_weight
        if count:
            chosen = list(rng.choice(np.array(pool, dtype=object), size=count, replace=False))
            each = (1.0 - cash_weight) / count
            for name in chosen:
                weights[name] = each
        rows.append([weights.get(name, 0.0) for name in [*pool, cash_id]])
        index.append(pd.Timestamp(day))
    return pd.DataFrame(rows, index=pd.DatetimeIndex(index), columns=[*pool, cash_id])
