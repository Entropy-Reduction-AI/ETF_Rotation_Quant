"""两个崩盘窗口的月末名额持仓。只写 health-crash-positions.csv。

月份含首尾：2007-10 至 2009-06，2015-05 至 2015-12。
名额是冻结稿的 A 股、美股。三票是均线、宽度、TRIN，三票投票是这三票之和。
紧张是三票投票 ≥ 2。仓位是该名额内的比例，不是组合的 40/60。
"""

from __future__ import annotations

import json

import pandas as pd

from src.v6.engine import slot
from src.v6.guard import IsolationError, assert_not_after
from src.v6.health import COST, OUT
from src.v6.health_random import _plans
from src.v6.load import load_panels
from src.v6.prior import us_prior
from src.v6.run_design import FRENCH_SHA, PANEL, TAGS, _a_daily, _sha_file, _us_daily
from src.v6.trin import clip_expanding, month_end_mean

WINDOWS = (
    ("2007-10_2009-06", (2007, 10), (2009, 6)),
    ("2015-05_2015-12", (2015, 5), (2015, 12)),
)


def _in_window(day: pd.Timestamp, start: tuple[int, int], end: tuple[int, int]) -> bool:
    key = (day.year, day.month)
    return start <= key <= end


def _rows(levels, plans, votes_fn, parent: str, sleeve: str) -> list[dict]:
    columns = list(levels.columns)
    parts = {}
    for name in ("均线", "宽度", "TRIN"):
        series, _n = votes_fn(levels, parent, [name])
        parts[name] = series
    by_day = {plan["day"]: plan for plan in plans}
    rows = []
    for day, plan in by_day.items():
        for window, start, end in WINDOWS:
            if not _in_window(day, start, end):
                continue
            period = day.to_period("M")
            votes = [int(parts[name].get(period, 0)) for name in ("均线", "宽度", "TRIN")]
            held = [] if plan["fallback"] else [columns[i] for i in plan["v6"]]
            weights = [] if plan["fallback"] else [plan["frac"] / 3.0] * len(held)
            if plan["fallback"]:
                held = [columns[int(plan["pool"][0])]]
                weights = [1.0]
                stock = 1.0
            else:
                stock = plan["frac"] * len(held) / 3.0
            rest = 1.0 - stock
            bond = rest if plan["bond"] else 0.0
            cash = 0.0 if plan["bond"] else rest
            row = {
                "窗口": window,
                "月份": day.date().isoformat(),
                "名额": sleeve,
                "均线": votes[0],
                "宽度": votes[1],
                "TRIN": votes[2],
                "三票投票": sum(votes),
                "紧张": sum(votes) >= 2,
                "p": plan["p"],
                "股票仓位": stock,
                "国债仓位": bond,
                "现金仓位": cash,
            }
            for i in range(3):
                row[f"持有{i + 1}"] = held[i] if i < len(held) else ""
                row[f"权重{i + 1}"] = weights[i] if i < len(weights) else ""
            rows.append(row)
    return rows


def run() -> dict:
    panels = load_panels()
    opaque = __import__("pathlib").Path("/opt/cursor/artifacts/french-49/49_Industry_Portfolios.csv")
    if not opaque.exists() or _sha_file(opaque) != FRENCH_SHA or not PANEL.exists():
        raise IsolationError("美股起点经验不在已登记的面板上")
    prior = us_prior(PANEL)
    bond, cash = panels["bond"], panels["cash"]
    votes = panels["votes"]
    saved = {key: panels["trin"][key].copy() for key in ("csi300", "SPX")}
    panels["trin"]["csi300"] = month_end_mean(clip_expanding(_a_daily(panels)))
    panels["trin"]["SPX"] = month_end_mean(clip_expanding(_us_daily(panels)))
    try:
        a_plans = _plans(panels["A"], "csi300", None, TAGS["a"], votes, bond, cash)
        u_plans = _plans(panels["US"], "SPX", prior, TAGS["us"], votes, bond, cash)
        a_slot, _, a_log = slot(panels["A"], "csi300", 3, None, TAGS["a"], "v6", COST, votes, bond, cash)
        u_slot, _, u_log = slot(panels["US"], "SPX", 3, prior, TAGS["us"], "v6", COST, votes, bond, cash)
        assert_not_after(a_slot.index, "崩盘窗口")
        rows = _rows(panels["A"], a_plans, votes, "csi300", "A股")
        rows += _rows(panels["US"], u_plans, votes, "SPX", "美股")
        for row in rows:
            log = a_log if row["名额"] == "A股" else u_log
            rec = log[pd.Timestamp(row["月份"])]
            if int(rec["票数"]) != row["三票投票"] or bool(rec["紧张"]) != row["紧张"]:
                raise IsolationError(f"{row['月份']} {row['名额']} 与 v6 记录不一致")
            if abs(float(rec["p"]) - round(row["p"], 3)) > 1e-9:
                raise IsolationError(f"{row['月份']} {row['名额']} 的 p 与 v6 记录不一致")
    finally:
        panels["trin"]["csi300"] = saved["csi300"]
        panels["trin"]["SPX"] = saved["SPX"]
    frame = pd.DataFrame(rows)
    if frame.empty or frame["月份"].max() > "2015-12-31":
        raise IsolationError("崩盘窗口没有停在 2015-12-31")
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / "health-crash-positions.csv", index=False)
    return {"rows": int(len(frame)), "last": frame["月份"].max()}


def main() -> None:
    print(json.dumps(run(), ensure_ascii=False))


if __name__ == "__main__":
    main()
