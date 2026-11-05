"""D37 每个格子的统计。口径对齐 v51_turnover.py / v51_sells.py，不写签收目录。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.report.metrics import cagr, max_drawdown, yearly_returns

HORIZONS = (5, 20, 60)


def _years(index: pd.DatetimeIndex, segment: str) -> float:
    if segment == "设计期":
        return 10.0
    return max(len(index) / 252.0, 1e-9)


def performance(net: pd.Series, benchmark: pd.Series | None) -> dict:
    series = pd.Series(net, dtype=float).dropna().sort_index()
    depth = max_drawdown(series)
    out = {
        "ann": cagr(series),
        "max_drawdown": depth["max_drawdown"],
        "max_drawdown_peak": str(pd.Timestamp(depth["peak"]).date()),
        "max_drawdown_trough": str(pd.Timestamp(depth["trough"]).date()),
        "n": int(len(series)),
    }
    own = yearly_returns(series)
    yearly = []
    bench_yearly = {}
    if benchmark is not None:
        bench = pd.Series(benchmark, dtype=float).dropna().sort_index()
        bench_yearly = yearly_returns(bench)
    for year, value in own.items():
        other = bench_yearly.get(year)
        yearly.append({
            "year": int(year),
            "strategy": value,
            "benchmark": other,
            "excess": None if other is None else value - other,
        })
    out["yearly"] = yearly
    return out


def trade_cost(daily: pd.DataFrame, segment: str) -> dict:
    buy = daily["buy"].astype(float)
    sell = daily["sell"].astype(float)
    cost = daily["cost"].astype(float)
    turnover = buy + sell
    traded = turnover > 1e-3
    years = _years(pd.DatetimeIndex(daily.index), segment)
    return {
        "years": years,
        "trades_per_year": float(traded.sum() / years),
        "turnover_two_way_per_year": float(turnover.sum() / years),
        "cost_per_year": float(cost.sum() / years),
        "trades": int(traded.sum()),
        "turnover_two_way": float(turnover.sum()),
        "cost": float(cost.sum()),
    }


def _classes(path) -> dict[str, str]:
    frame = pd.read_csv(path)
    return dict(zip(frame["container_id"], frame["class"]))


def turnover_rows(held: pd.DataFrame, daily: pd.DataFrame, state: pd.DataFrame, exits: pd.DataFrame,
                  pnl: pd.DataFrame, classes: dict[str, str], segment: str) -> tuple[pd.DataFrame, dict]:
    """和 results/v5/report/v51_turnover.py 同一套分类和增值。"""
    defensive = {name for name, kind in classes.items() if kind in {"国债", "黄金", "现金"}} | {"cash"}
    columns = [name for name in held.columns]
    returns = pnl.reindex(index=held.index, columns=columns).fillna(0.0)
    logged = np.log1p(returns)
    cumulative = logged.cumsum()
    index = held.index
    prev = state.shift(1)
    market = state["market"].fillna("")
    previous = prev["market"].fillna("")
    kind = pd.Series("", index=index)
    kind[(market != "") & (previous == "")] = "整体进场"
    kind[(market == "") & (previous != "")] = "整体离场"
    kind[(market != "") & (previous != "") & (market != previous)] = "换市场"
    same = kind == ""
    risk = state["risk"].astype(float)
    prev_risk = prev["risk"].astype(float)
    kind[same & (risk > prev_risk)] = "加仓档"
    kind[same & (risk < prev_risk)] = "减仓档"
    same = kind == ""
    picks = state["picks"].fillna("")
    prev_picks = prev["picks"].fillna("")
    changed = same & (picks != prev_picks)
    if len(exits) and "t" in exits.columns:
        why = exits.groupby("t")["why"].agg(lambda values: "周度换掉" if (values == "周度换掉").any() else "单只离场")
        kind[changed] = why.reindex(index[changed]).fillna("换人（其他）").to_numpy()
    else:
        kind[changed] = "换人（其他）"
    defense = state["defense"].fillna("")
    prev_defense = prev["defense"].fillna("")
    kind[(kind == "") & (defense != prev_defense)] = "防守换品种"
    trade_kind = kind.shift(1).fillna("")
    turnover = daily["buy"].astype(float) + daily["sell"].astype(float)
    rows = []
    for i in np.where(turnover.to_numpy() > 1e-3)[0]:
        if i + 1 >= len(index):
            break
        stamp = index[i]
        delta = (held.iloc[i + 1] - held.iloc[i]).to_numpy(dtype=float)
        record = {
            "段": segment,
            "日期": pd.Timestamp(stamp).strftime("%Y-%m-%d"),
            "类别": trade_kind.iloc[i] or "其他",
            "换手": float(turnover.iloc[i]),
            "成本": float(daily["cost"].iloc[i]) * 100,
            "风险仓位变化": float(sum(delta[j] for j, name in enumerate(columns) if name not in defensive)),
        }
        for horizon in HORIZONS:
            stop = min(i + horizon, len(index) - 1)
            forward = np.expm1(cumulative.iloc[stop].to_numpy(dtype=float) - cumulative.iloc[i].to_numpy(dtype=float))
            record[f"VA{horizon}"] = float(np.dot(delta, forward)) * 100
        rows.append(record)
    frame = pd.DataFrame(rows)
    years = _years(pd.DatetimeIndex(index), segment)
    summary: dict = {}
    if frame.empty:
        summary["合计"] = {"每年次数": 0, "每年换手": 0, "每年成本": 0}
        return frame, summary
    for label, block in frame.groupby("类别"):
        summary[str(label)] = _turnover_block(block, years)
    summary["合计"] = _turnover_block(frame, years)
    return frame, summary


def _turnover_block(block: pd.DataFrame, years: float) -> dict:
    out = {
        "每年次数": round(len(block) / years, 1),
        "每年换手": round(float(block["换手"].sum()) / years, 1),
        "每年成本": round(float(block["成本"].sum()) / years, 2),
    }
    for horizon in HORIZONS:
        column = f"VA{horizon}"
        out[f"做对比例{horizon}"] = round(float((block[column] > 0).mean() * 100))
        out[f"每年增值{horizon}"] = round(float(block[column].sum()) / years, 2)
        out[f"扣成本后每笔为正{horizon}"] = round(float((block[column] > block["成本"]).mean() * 100))
    out["每笔成本bp"] = round(float(block["成本"].mean()) * 100, 1)
    out["每笔增值bp20"] = round(float(block["VA20"].mean()) * 100, 1)
    return out


def sell_rows(held: pd.DataFrame, daily: pd.DataFrame, state: pd.DataFrame, pnl: pd.DataFrame,
              classes: dict[str, str], segment: str) -> tuple[pd.DataFrame, dict]:
    """和 results/v5/report/v51_sells.py 同一套减仓价值。"""
    defensive = {name for name, kind in classes.items() if kind in {"国债", "黄金", "现金"}} | {"cash"}
    index = held.index
    pos = {day: i for i, day in enumerate(index)}
    weekly = set(pd.Series(index).groupby(pd.Series(index).dt.to_period("W")).max())
    columns = list(held.columns)
    risky = [name for name in columns if name not in defensive]
    logged = np.log1p(pnl.reindex(index=index, columns=columns).fillna(0.0))
    cumulative = logged.cumsum()
    risk = state["risk"].astype(float).where(state["market"].notna() & (state["market"].fillna("") != ""), 0.0)
    previous = risk.shift(1)
    downs = [day for day in index[1:] if risk.at[day] < previous.at[day] - 1e-9]
    ups = [day for day in index[1:] if risk.at[day] > previous.at[day] + 1e-9]
    rows = []
    for stamp in downs:
        i = pos[stamp] + 1
        if i + 1 >= len(index):
            continue
        delta = held.iloc[i + 1] - held.iloc[i]
        sold = (-delta[risky]).clip(lower=0)
        bought = delta[[name for name in columns if name in defensive]].clip(lower=0)
        if float(sold.sum()) < 1e-3:
            continue
        later = [day for day in ups if day > stamp]
        if later:
            stop = min(pos[later[0]] + 1, len(index) - 1)
        else:
            stop = len(index) - 1

        def gain(start: int, end: int) -> float:
            asset = np.expm1(cumulative.iloc[end][sold.index].to_numpy(dtype=float) - cumulative.iloc[start][sold.index].to_numpy(dtype=float))
            sleeve = np.expm1(cumulative.iloc[end][bought.index].to_numpy(dtype=float) - cumulative.iloc[start][bought.index].to_numpy(dtype=float))
            return (float(np.dot(sold.to_numpy(dtype=float), asset)) - float(np.dot(bought.to_numpy(dtype=float), sleeve))) * 100

        value = gain(i, stop)
        fridays = [day for day in sorted(weekly) if day >= stamp]
        friday_fill = min(pos[fridays[0]] + 1, len(index) - 1) if fridays else stop
        traded = float((daily["buy"] + daily["sell"]).iloc[i])
        cost_round = 2 * float(daily["cost"].iloc[i]) * 100 * min(1.0, float(sold.sum()) / max(1e-9, traded / 2))
        back_before_friday = bool(later and fridays and later[0] <= fridays[0])
        early = float("nan")
        if stamp not in weekly and not back_before_friday:
            early = -gain(i, friday_fill)
        rows.append({
            "段": segment,
            "状态日": pd.Timestamp(stamp).strftime("%Y-%m-%d"),
            "周中": stamp not in weekly,
            "整体离场": bool(risk.at[stamp] == 0),
            "卖出仓位": round(float(sold.sum()), 3),
            "回来天数": int((index[stop] - index[i]).days),
            "周五前回来": back_before_friday,
            "减仓价值": -value,
            "一来一回成本": cost_round,
            "比等到周五多赚": early,
            "年": pd.Timestamp(stamp).year,
        })
    frame = pd.DataFrame(rows)
    years = _years(pd.DatetimeIndex(index), segment)
    summary: dict = {}
    if frame.empty:
        return frame, summary
    summary["全部减仓"] = _sell_block(frame, years)
    for label, mask in (("周中减仓", frame["周中"]), ("周五减仓", ~frame["周中"])):
        summary[label] = _sell_block(frame[mask], years)
    for label, mask in (
        ("周中·整体离场（两条腿都断）", frame["周中"] & frame["整体离场"]),
        ("周中·降一档（一条腿断）", frame["周中"] & ~frame["整体离场"]),
        ("周中·周五前就加回", frame["周中"] & frame["周五前回来"]),
        ("周中·过了周五还在减", frame["周中"] & ~frame["周五前回来"]),
    ):
        summary[label] = _sell_block(frame[mask], years)
    early = frame[frame["周中"] & ~frame["周五前回来"]]["比等到周五多赚"].dropna()
    summary["周中提前减·比等到周五"] = {
        "笔数": int(len(early)),
        "提前减更好比例": None if early.empty else round(float((early > 0).mean() * 100)),
        "每笔bp": None if early.empty else round(float(early.mean()) * 100, 1),
        "每年": round(float(early.sum()) / years, 2) if len(early) else 0,
    }
    return frame, summary


def _sell_block(block: pd.DataFrame, years: float) -> dict:
    if block.empty:
        return {"笔数": 0, "每年笔数": 0}
    value = block["减仓价值"]
    net = value - block["一来一回成本"]
    return {
        "笔数": int(len(block)),
        "每年笔数": round(len(block) / years, 1),
        "减对比例": round(float((value > 0).mean() * 100)),
        "扣成本后减对": round(float((net > 0).mean() * 100)),
        "每笔价值bp": round(float(value.mean()) * 100, 1),
        "每笔成本bp": round(float(block["一来一回成本"].mean()) * 100, 1),
        "每笔净期望bp": round(float(net.mean()) * 100, 1),
        "每年净": round(float(net.sum()) / years, 2),
        "中位价值bp": round(float(value.median()) * 100, 1),
    }


def s1_participation(legs: pd.DataFrame, held: pd.DataFrame, pnl: pd.DataFrame, markets: list[str]) -> list[dict]:
    """新市场：第一次有得分、第一次持有、持有天数、权重乘收益的合计。"""
    rows = []
    score = legs.copy()
    if "date" in score.columns:
        score["date"] = pd.to_datetime(score["date"])
        score = score.set_index("date")
    for name in markets:
        block = score[score["market"] == name] if "market" in score.columns else score.iloc[0:0]
        defined = block["score"].dropna() if "score" in block.columns else pd.Series(dtype=float)
        weights = held[name] if name in held.columns else pd.Series(0.0, index=held.index)
        held_days = weights[weights > 1e-6]
        returns = pnl[name] if name in pnl.columns else pd.Series(0.0, index=held.index)
        aligned = returns.reindex(weights.index).fillna(0.0)
        rows.append({
            "market": name,
            "first_score": None if defined.empty else pd.Timestamp(defined.index[0]).date().isoformat(),
            "first_hold": None if held_days.empty else pd.Timestamp(held_days.index[0]).date().isoformat(),
            "days": int(len(held_days)),
            "contribution": float((weights.reindex(aligned.index).fillna(0.0) * aligned).sum()),
        })
    return rows
