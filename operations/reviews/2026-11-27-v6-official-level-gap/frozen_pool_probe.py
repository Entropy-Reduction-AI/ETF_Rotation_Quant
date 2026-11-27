"""报告用的冻结池对照。不调用正式考试，不写判定文件。

两处相对附表 A 的差异：
- 半导体材料设备的参选起点是 2023-07-27，Dev 的拼接从库内第一根（2018-12-28）起。
- 科创50两边都没有。这里只在诊断里补上，并截断材料设备。
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(OUT))

from src.v6.guard import open_official_isolation  # noqa: E402
from src.v6.health import _benchmarks, _k2a  # noqa: E402
from src.v6.load import load_panels  # noqa: E402
from src.v6.oneshot_exam import COST, _variant  # noqa: E402
from src.v6.oneshot_prep import premium_pp  # noqa: E402
from src.v6.prior import us_prior  # noqa: E402
from src.v6.run_design import PANEL, TAGS, _a_daily, _us_daily  # noqa: E402
from src.v6.trin import clip_expanding, month_end_mean  # noqa: E402
from compare_paths import _rev_premium, _stats  # noqa: E402

EXAM = ("2016-01-01", "2026-09-30")
MATERIAL = "theme-中证半导体材料设备主题"
MATERIAL_START = pd.Timestamp("2023-07-27")
STAR = "star50"
STAR_START = pd.Timestamp("2020-07-23")
SIGNAL = pd.Timestamp("2019-12-31")


def _bars(code: str, start: pd.Timestamp) -> pd.DataFrame:
    con = sqlite3.connect(ROOT / "data" / "market.sqlite")
    try:
        frame = pd.read_sql_query(
            "select date, close, amount from bars where code=? and adj='raw' and close>0 "
            "and date<=? order by date",
            con,
            params=(code, "2026-09-30"),
        )
    finally:
        con.close()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.drop_duplicates("date", keep="last").set_index("date").sort_index()
    return frame.loc[start:]


def _align(series: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    out = series.reindex(index.union(series.index)).ffill().reindex(index)
    return out.where(out.index >= series.index[0])


def _blank(frame: pd.DataFrame, name: str, start: pd.Timestamp) -> None:
    if name in frame.columns:
        frame.loc[frame.index < start, name] = np.nan


def _criteria(book: dict, bm_main, bm_same, k2a) -> dict:
    held = _stats(book["净"])
    plain = _stats(book["不设防守"])
    same = _stats(bm_same)
    bench = _stats(k2a)
    prem = premium_pp(book["净"], book["不设防守"], bm_main, *EXAM)
    flags = {
        "①": held["max_drawdown"] >= -0.40,
        "②": prem <= 4.0,
        "③": held["ratio"] > bench["ratio"],
        "④": held["cagr"] * 100.0 - same["cagr"] * 100.0 >= 0.0,
    }
    return {
        "最大回撤": held["max_drawdown"],
        "年化": held["cagr"],
        "保费_百分点": prem,
        "保费明细": _rev_premium(book["不设防守"], book["净"], bm_main)["detail"],
        "年化除以回撤": held["ratio"],
        "K2A年化除以回撤": bench["ratio"],
        "对同仓位超额_百分点": held["cagr"] * 100.0 - same["cagr"] * 100.0,
        "判定": flags,
        "四条都过": all(flags.values()),
    }


def _rank(scores: dict, banned: set[str]) -> list[str]:
    tags = TAGS["a"]
    used: set[str] = set()
    picked = []
    for name, score in sorted(scores.items(), key=lambda item: (-item[1], item[0])):
        if name in banned or not np.isfinite(score):
            continue
        label = tags.get(name, "")
        if label and label in used:
            continue
        used.add(label)
        picked.append(name)
        if len(picked) == 3:
            break
    return picked


def _prepare(panels, *, delay_material: bool, add_star: bool) -> None:
    if delay_material:
        for key in ("A", "A_pub"):
            _blank(panels[key], MATERIAL, MATERIAL_START)
        amount = panels["amt"]
        if isinstance(amount, dict) and MATERIAL in amount:
            series = amount[MATERIAL]
            amount[MATERIAL] = series.where(series.index >= MATERIAL_START)
        elif isinstance(amount, pd.DataFrame) and MATERIAL in amount.columns:
            amount.loc[amount.index < MATERIAL_START, MATERIAL] = np.nan
    if add_star:
        bars = _bars("000688", STAR_START)
        level = _align(bars["close"].astype(float), panels["A"].index)
        amount = _align(bars["amount"].where(bars["amount"] > 0).astype(float), panels["A"].index)
        for key in ("A", "A_pub"):
            panels[key][STAR] = level.reindex(panels[key].index)
        if isinstance(panels["amt"], dict):
            panels["amt"][STAR] = amount
        else:
            panels["amt"][STAR] = amount.reindex(panels["amt"].index)
    panels["trin"]["csi300"] = month_end_mean(clip_expanding(_a_daily(panels)))
    panels["trin"]["SPX"] = month_end_mean(clip_expanding(_us_daily(panels)))


def _run(panels, prior) -> dict:
    return _variant(
        panels, prior, panels["votes"], panels["bond"], panels["cash"],
        n=3, cost=COST, lag=0, stress=2, exclude=None, weight_a=0.4,
    )


def main() -> None:
    open_official_isolation("2026-09-30", authorized=True)
    panels = load_panels()
    prior = us_prior(PANEL)
    starts = {}
    for name in (
        MATERIAL, "theme-中证新能源汽车", "theme-中证创新药产业", "theme-中证光伏产业",
        "theme-中证消费电子主题", "theme-中证全球中国教育主题人民币指数", STAR,
    ):
        if name not in panels["A"].columns:
            starts[name] = None
            continue
        first = panels["A"][name].first_valid_index()
        starts[name] = None if first is None else str(pd.Timestamp(first).date())

    official = _run(panels, prior)
    record = official["A记录"][SIGNAL]
    scores = {name: float(value) for name, value in record["分数"].items()}
    ranking = {
        "实际前3": _rank(scores, set()),
        "去掉材料设备后的前3": _rank(scores, {MATERIAL}),
        "新能源分数": scores.get("theme-中证新能源汽车"),
        "材料设备分数": scores.get(MATERIAL),
        "全指半导体分数": scores.get("theme-中证全指半导体产品与设备"),
        "前8": [
            {"name": name, "score": score}
            for name, score in sorted(scores.items(), key=lambda item: -item[1])[:8]
        ],
    }

    bm_main, bm_same = _benchmarks()
    k2a = _k2a(panels, True)

    def scenario(delay_material: bool, add_star: bool) -> dict:
        fresh = load_panels()
        _prepare(fresh, delay_material=delay_material, add_star=add_star)
        book = _run(fresh, prior)
        out = _criteria(book, bm_main, bm_same, k2a)
        day = book["A记录"].get(SIGNAL)
        out["2019-12-31持有"] = None if day is None else day.get("持有")
        material_first = fresh["A"][MATERIAL].first_valid_index()
        out["材料设备首个有效日"] = None if material_first is None else str(pd.Timestamp(material_first).date())
        if add_star:
            star_first = fresh["A"][STAR].first_valid_index()
            out["科创50首个有效日"] = None if star_first is None else str(pd.Timestamp(star_first).date())
        return out

    payload = {
        "说明": "诊断对照，不是正式考试，不改 verdict.json。",
        "首个有效日": starts,
        "2019-12-31排名": ranking,
        "只推迟材料设备": scenario(True, False),
        "冻结池_推迟材料设备并补科创50": scenario(True, True),
    }
    path = OUT / "frozen-pool-counterfactual.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({
        "starts": starts,
        "ranking": ranking,
        "delay_only_held": payload["只推迟材料设备"]["2019-12-31持有"],
        "delay_only": {k: payload["只推迟材料设备"][k] for k in ("最大回撤", "保费_百分点", "年化除以回撤", "对同仓位超额_百分点", "判定")},
        "frozen": {k: payload["冻结池_推迟材料设备并补科创50"][k] for k in ("最大回撤", "保费_百分点", "年化除以回撤", "对同仓位超额_百分点", "判定")},
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
