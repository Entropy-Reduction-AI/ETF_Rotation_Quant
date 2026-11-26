"""一次性检验脚本。窗口只有一对常数。

现在这对常数是预演：检验段 2011-01→2015-12，全段 2006-01→2015-12。
正式考试把 ACTIVE 改成 OFFICIAL（2016-01→2026-09，全段到 2026-09）并另行授权。
本文件的正式入口在未授权时拒绝。预演不读 2015-12-31 之后的行情，不计试验。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.report.blend import monthly_rebalance
from src.report.metrics import cagr, max_drawdown, monthly_returns
from src.v4.r5.design import reference_frame
from src.v6.engine import benchmark, mix_monthly, slot
from src.v6.guard import DESIGN_END_TEXT, IsolationError, assert_not_after
from src.v6.health import (
    A1_SHA,
    A2_SHA,
    COST,
    _benchmarks,
    _k2a,
    _read_peer,
)
from src.v6.health_random import (
    SEED,
    TRIALS,
    _draw,
    _plans,
    _simulate,
    _v6_picks,
    _window_rows,
)
from src.v6.load import load_panels
from src.v6.oneshot_prep import (
    BLOCKS,
    EIGHT_LINES,
    HOLD_DAYS,
    SpanBook,
    any_start,
    eight_line_table,
    evaluate,
    month_regime,
    official_verdict,
    pick_detail,
    regime_table,
    run_exam,
    select_judgment,
    six_blocks,
    sleeve_split,
    stress_detail,
)
from src.v6.portfolio_design import design_book
from src.v6.prior import us_prior
from src.v6.run_design import FRENCH_SHA, PANEL, TAGS, _a_daily, _sha_file, _us_daily
from src.v6.trin import clip_expanding, month_end_mean

ROOT = Path(__file__).resolve().parents[2]
REHEARSAL_OUT = ROOT / "results" / "v6" / "rehearsal"
FRENCH_CANDIDATES = (
    Path("/opt/cursor/artifacts/french-49/49_Industry_Portfolios.csv"),
    ROOT / "operations/reviews/diag/49_Industry_Portfolios.csv",
)


@dataclass(frozen=True)
class Windows:
    """唯一的窗口开关。正式考试只改 ACTIVE 指向 OFFICIAL。"""

    name: str
    exam_start: str
    exam_end: str
    full_start: str
    full_end: str


REHEARSAL = Windows("预演", "2011-01-01", "2015-12-31", "2006-01-01", "2015-12-31")
OFFICIAL = Windows("正式", "2016-01-01", "2026-09-30", "2006-01-01", "2026-09-30")
ACTIVE = REHEARSAL
OFFICIAL_AUTHORIZED = False
# D51-3：S6 的同仓位基准跟着改成 50/25/25。BM-主和 K2A 不改。
S6_SAME_WEIGHTS = {"H00300": 0.50, "XNDX": 0.25, "SP500TR": 0.25}
SIGNED_PREMIUM = 1.383910856278514
PREMIUM_TOLERANCE = 0.01


def extend_plan(end: str) -> dict:
    """接到 2026-09 的步骤。不读行情。"""
    return {
        "end": end,
        "读行情": False,
        "步骤": [
            "把 ACTIVE 从 REHEARSAL 改成 OFFICIAL",
            "OFFICIAL_AUTHORIZED 由另行授权的那一次运行打开",
            "装载日期放宽到该次窗口终点，SQL 仍必须自带 date<=",
            "A1、A2 用设计期账本接检验段账本，重叠日逐日一致才衔接",
            "现行配置的 package 终点改成该次窗口终点",
        ],
    }


def refuse_market_after_design(end: str) -> None:
    if end > DESIGN_END_TEXT:
        raise IsolationError(f"不读 {end}。本预演的行情封顶是 {DESIGN_END_TEXT}。")


def _cap(series: pd.Series, what: str, end: str) -> pd.Series:
    if series is None or series.empty:
        raise IsolationError(f"{what} 是空的")
    assert_not_after(series.index, what)
    if pd.Timestamp(series.index.max()) > pd.Timestamp(end):
        raise IsolationError(f"{what} 晚于 {end}")
    return series


def _mix(a: pd.Series, u: pd.Series, cost: float, weight_a: float) -> pd.Series:
    return mix_monthly(a, u, cost, weight_a)


def _sleeve(levels, parent, prior, tags, votes, bond, cash, mode, cost, n, lag, stress, exclude):
    series, _turnover, log = slot(
        levels, parent, n, prior, tags, mode, cost, votes, bond, cash,
        signal_lag=lag, stress_votes=stress, exclude=exclude,
    )
    assert_not_after(series.index, mode)
    return series, log


def control_spec(code: str, spec: dict) -> dict:
    """D51-2。改 v6 自身设定时，不设防守做同样的改动。S8 只改防守门槛，对照保持主规则。"""
    if code == "S8":
        return {"n": 3, "cost": COST, "lag": 0, "stress": 2, "exclude": None, "weight_a": 0.4}
    return {
        "n": spec["n"], "cost": spec["cost"], "lag": spec["lag"], "stress": spec["stress"],
        "exclude": spec["exclude"], "weight_a": spec["weight_a"],
    }


def _variant(panels, prior, votes, bond, cash, *, n, cost, lag, stress, exclude, weight_a, plain=None):
    plain = plain or {"n": n, "cost": cost, "lag": lag, "stress": stress, "exclude": exclude, "weight_a": weight_a}
    a, log_a = _sleeve(panels["A"], "csi300", None, TAGS["a"], votes, bond, cash, "v6", cost, n, lag, stress, exclude)
    u, log_u = _sleeve(panels["US"], "SPX", prior, TAGS["us"], votes, bond, cash, "v6", cost, n, lag, stress, exclude)
    a_top, _ = _sleeve(
        panels["A"], "csi300", None, TAGS["a"], votes, bond, cash, "top",
        plain["cost"], plain["n"], plain["lag"], plain["stress"], plain["exclude"],
    )
    u_top, _ = _sleeve(
        panels["US"], "SPX", prior, TAGS["us"], votes, bond, cash, "top",
        plain["cost"], plain["n"], plain["lag"], plain["stress"], plain["exclude"],
    )
    net = _mix(a, u, cost, weight_a)
    undefended = _mix(a_top, u_top, plain["cost"], plain["weight_a"])
    return {"净": net, "不设防守": undefended, "A": a, "美": u, "A记录": log_a, "美记录": log_u}


def _zero_cost_blocks(panels, prior, votes, bond, cash):
    """D49 的毛收益。成本为 0，名额仍是前 3，每月 60/40。"""
    a_top, _ = _sleeve(panels["A"], "csi300", None, TAGS["a"], votes, bond, cash, "top", 0.0, 3, 0, 2, None)
    u_top, _ = _sleeve(panels["US"], "SPX", prior, TAGS["us"], votes, bond, cash, "top", 0.0, 3, 0, 2, None)
    a_ew, _ = _sleeve(panels["A"], "csi300", None, TAGS["a"], votes, bond, cash, "ew", 0.0, 3, 0, 2, None)
    u_ew, _ = _sleeve(panels["US"], "SPX", prior, TAGS["us"], votes, bond, cash, "ew", 0.0, 3, 0, 2, None)
    a_gross, _ = _sleeve(panels["A"], "csi300", None, TAGS["a"], votes, bond, cash, "v6", 0.0, 3, 0, 2, None)
    u_gross, _ = _sleeve(panels["US"], "SPX", prior, TAGS["us"], votes, bond, cash, "v6", 0.0, 3, 0, 2, None)
    return {
        "等权": _mix(a_ew, u_ew, 0.0, 0.4),
        "前3": _mix(a_top, u_top, 0.0, 0.4),
        "毛": _mix(a_gross, u_gross, 0.0, 0.4),
        "A前3": a_top, "A等权": a_ew, "A毛": a_gross,
        "美前3": u_top, "美等权": u_ew, "美毛": u_gross,
    }


def _price_benchmark(panels, weights) -> pd.Series:
    """附表 B 的价格指数基准：沪深300、纳指、标普，月末再平衡。"""
    return benchmark(panels["A"], panels["US"], weights)


def _criteria_book(net, plain, bm_main, bm_same, k2a) -> SpanBook:
    """判据账。不设防守与 v6 净同口径（D51-1），不是拆账用的零成本前 3。"""
    return SpanBook(
        v6=net, gross=net, undefended=plain, equal_weight=plain,
        bm_main_total=bm_main, bm_main_price=bm_main,
        bm_same_total=bm_same, bm_same_price=bm_same, k2a=k2a,
    )


def _attribution_book(net, gross, equal_weight, top, bm_main, bm_same, price_main, price_same, k2a) -> SpanBook:
    """D49 拆账。第⑤块用两条不计成本的序列，不进判据。"""
    return SpanBook(
        v6=net, gross=gross, undefended=top, equal_weight=equal_weight,
        bm_main_total=bm_main, bm_main_price=price_main,
        bm_same_total=bm_same, bm_same_price=price_same, k2a=k2a,
    )


def _same_benchmark(weights: dict[str, float]) -> pd.Series:
    parts = reference_frame(end=DESIGN_END_TEXT).dropna()
    assert_not_after(parts.index, "BM")
    series, _weights = monthly_rebalance(parts, weights)
    _cap(series, "BM-同仓位", DESIGN_END_TEXT)
    return series


def _criteria_row(label: str, role: str, item) -> dict:
    flags = item_result_flags(item)
    return {
        "窗口": label,
        "角色": role,
        "最大回撤": item.max_drawdown,
        "保费": item.premium_pp,
        "年化除以回撤": item.ratio,
        "增强基准年化除以回撤": item.benchmark_ratio,
        "对同仓位基准": item.excess_vs_same_pp,
        **{f"过_{name}": value for name, value in flags.items()},
        "结论": "通过" if all(flags.values()) else "不通过",
        "进入判定": role == "连续运行截出" and label == "检验段",
    }


def item_result_flags(item):
    from src.v6.oneshot_prep import passes
    return passes(item)


def _pick_rows(log, levels, ew: pd.Series, sleeve: str, start: str, end: str) -> list[dict]:
    calendar = levels.index
    mask = np.r_[calendar.month[1:] != calendar.month[:-1], True]
    forward = levels.loc[calendar[mask]].pct_change().shift(-1)
    ew_month = monthly_returns(ew)
    rows = []
    for day, rec in log.items():
        if day < pd.Timestamp(start) or day > pd.Timestamp(end):
            continue
        period = day.to_period("M")
        if period not in ew_month.index:
            continue
        for name in rec.get("持有") or []:
            value = forward.at[day, name] if name in forward.columns else np.nan
            if value != value:
                continue
            rows.append({
                "月份": day.strftime("%Y-%m"),
                "名额": sleeve,
                "候选": name,
                "下月收益": float(value),
                "等权收益": float(ew_month.loc[period]),
            })
    return rows


def _stress_rows(log, sleeve_daily: pd.Series, plain_daily: pd.Series, sleeve: str) -> list[dict]:
    v6_m = monthly_returns(sleeve_daily)
    plain_m = monthly_returns(plain_daily)
    rows = []
    for day, rec in log.items():
        period = day.to_period("M")
        if period not in v6_m.index or period not in plain_m.index:
            continue
        rows.append({
            "月份": day.strftime("%Y-%m"),
            "名额": sleeve,
            "紧张": bool(rec.get("紧张")),
            "股票仓位": float(rec.get("股票仓位", 1.0)),
            "v6": float(v6_m.loc[period]),
            "不设防守": float(plain_m.loc[period]),
        })
    return rows


def _restart_levels(levels: pd.DataFrame, start: str) -> pd.DataFrame:
    clipped = levels.loc[start:]
    if clipped.empty:
        raise IsolationError(f"重新起步从 {start} 没有行情")
    assert_not_after(clipped.index, "重新起步")
    return clipped


def _french_note() -> dict:
    found = None
    for path in FRENCH_CANDIDATES:
        if path.exists() and path.is_file() and not path.is_dir():
            found = path
            break
    panel_files = sorted(PANEL.glob("*.csv")) if PANEL.exists() else []
    note = {
        "登记sha256": FRENCH_SHA,
        "面板": str(PANEL.relative_to(ROOT)) if PANEL.exists() else None,
        "面板sha256": {path.name: _sha_file(path) for path in panel_files},
    }
    if found is None:
        note["文件"] = None
        note["说明"] = "仓库里没有 49_Industry_Portfolios.csv。起点经验用已入库的 1926-07 至 1998-12 面板，不打开官网全表。"
        return note
    digest = _sha_file(found)
    note["文件"] = str(found)
    note["sha256"] = digest
    if digest != FRENCH_SHA:
        raise IsolationError(f"French 文件哈希不符：{digest}")
    return note


def _random_rows(panels, prior, votes, bond, cash) -> list[dict]:
    a_plans = _plans(panels["A"], "csi300", None, TAGS["a"], votes, bond, cash)
    u_plans = _plans(panels["US"], "SPX", prior, TAGS["us"], votes, bond, cash)
    a_check = _simulate(panels["A"], bond, cash, a_plans, _v6_picks(a_plans), COST)[0]
    u_check = _simulate(panels["US"], bond, cash, u_plans, _v6_picks(u_plans), COST)[0]
    a_slot, _, _ = slot(panels["A"], "csi300", 3, None, TAGS["a"], "v6", COST, votes, bond, cash)
    u_slot, _, _ = slot(panels["US"], "SPX", 3, prior, TAGS["us"], "v6", COST, votes, bond, cash)
    gap_a = float(np.max(np.abs(a_check - a_slot.to_numpy())))
    gap_u = float(np.max(np.abs(u_check - u_slot.to_numpy())))
    if gap_a > 1e-8 or gap_u > 1e-8:
        raise IsolationError(f"随机引擎和 v6 引擎不一致：A {gap_a}，美股 {gap_u}")
    rng = np.random.default_rng(SEED)
    a_paths = _simulate(panels["A"], bond, cash, a_plans, _draw(a_plans, rng, TRIALS), COST)
    u_paths = _simulate(panels["US"], bond, cash, u_plans, _draw(u_plans, rng, TRIALS), COST)
    mixed = np.empty_like(a_paths)
    for i in range(TRIALS):
        mixed[i] = mix_monthly(
            pd.Series(a_paths[i], index=panels["A"].index),
            pd.Series(u_paths[i], index=panels["US"].index),
            COST,
        ).to_numpy()
    rule = mix_monthly(a_slot, u_slot, COST)
    _cap(rule, "随机规则", DESIGN_END_TEXT)
    rows = (
        _window_rows("组合", rule, mixed)
        + _window_rows("A股", a_slot, a_paths)
        + _window_rows("美股", u_slot, u_paths)
    )
    return rows


def _line_table(series: dict[str, pd.Series], start: str, end: str) -> list[dict]:
    rows = []
    for name in EIGHT_LINES:
        book = series.get(name)
        if book is None:
            rows.append({"线": name, "状态": "未完成"})
            continue
        window = book.loc[start:end].dropna()
        if window.empty:
            rows.append({"线": name, "状态": "该窗口没有数据"})
            continue
        depth = max_drawdown(window)
        rows.append({
            "线": name,
            "状态": "ok",
            "年化": cagr(window),
            "年化百分点": cagr(window) * 100.0,
            "最大回撤": depth["max_drawdown"],
            "高点": pd.Timestamp(depth["peak"]).date().isoformat(),
            "低点": pd.Timestamp(depth["trough"]).date().isoformat(),
        })
    return rows


def _forecast(parts: dict[str, float]) -> list[dict]:
    """与体检预测对账的五项。仓位差和保费已经是组合数。"""
    rows = []
    for item, sleeve, weight in (
        ("美股挑选", parts["美股挑选"], 0.6),
        ("A股挑选", parts["A股挑选"], 0.4),
        ("A股等权倾斜", parts["A股等权倾斜"], 0.4),
        ("防守保费", parts["防守保费"], None),
        ("美股60%仓位差", parts["美股60%仓位差"], None),
    ):
        rows.append({
            "项": item,
            "名额内": sleeve,
            "权重": weight,
            "组合贡献": sleeve if weight is None else sleeve * weight,
        })
    return rows


def _compare(out_dir: Path) -> dict:
    """对照已签收的体检数字。只读 results/v6/health-*.csv，不改它们。"""
    gates = pd.read_csv(ROOT / "results/v6/health-gates.csv")
    scatter = pd.read_csv(ROOT / "results/v6/health-scatter.csv")
    random_frame = pd.read_csv(ROOT / "results/v6/health-random.csv")
    forecast = pd.read_csv(ROOT / "results/v6/health-forecast.csv")
    produced_lines = pd.read_csv(out_dir / "lines.csv")
    produced_criteria = pd.read_csv(out_dir / "criteria.csv")
    produced_random = pd.read_csv(out_dir / "random.csv")
    produced_forecast = pd.read_csv(out_dir / "forecast.csv")
    diffs = []

    def add(kind, segment, item, signed, got):
        if signed is None or got is None or (isinstance(got, float) and got != got):
            diffs.append({"类": kind, "段": segment, "项": item, "签收": signed, "预演": got, "差": None, "实质差异": True})
            return
        delta = float(got) - float(signed)
        limit = PREMIUM_TOLERANCE if kind == "判据" and item == "防守平时保费" else 1e-4
        material = abs(delta) > limit
        diffs.append({"类": kind, "段": segment, "项": item, "签收": float(signed), "预演": float(got), "差": delta, "实质差异": material})

    segment_map = {"2011-2015": "检验段", "2006-2015": "全段"}
    gate_map = {
        "v6净最大回撤": "最大回撤",
        "防守平时保费": "保费",
        "v6年化/最大回撤绝对值": "年化除以回撤",
        "K2A年化/最大回撤绝对值": "增强基准年化除以回撤",
        "v6净减BM-同仓位年化": "对同仓位基准",
    }
    for signed_segment, label in segment_map.items():
        block = gates[gates["segment"] == signed_segment]
        got = produced_criteria[(produced_criteria["窗口"] == label) & (produced_criteria["角色"] == "连续运行截出")]
        if got.empty:
            continue
        row = got.iloc[0]
        for item, column in gate_map.items():
            signed = block.loc[block["item"] == item, "value"]
            add("判据", label, item, None if signed.empty else signed.iloc[0], row[column])
        lines = scatter[scatter["segment"] == signed_segment]
        mine = produced_lines[produced_lines["窗口"] == label]
        for _, signed_row in lines.iterrows():
            hit = mine[mine["线"] == signed_row["series"]]
            if hit.empty:
                add("八条线年化", label, signed_row["series"], signed_row["cagr_pct"], None)
                continue
            add("八条线年化", label, signed_row["series"], signed_row["cagr_pct"], hit.iloc[0]["年化百分点"])
            add("八条线回撤", label, signed_row["series"], signed_row["max_drawdown"], hit.iloc[0]["最大回撤"])
    random_signed = random_frame[(random_frame["book"] == "组合") & (random_frame["segment"] == "2011-2015")]
    random_got = produced_random[(produced_random["book"] == "组合") & (produced_random["segment"] == "2011-2015")]
    if len(random_signed) and len(random_got):
        add("随机", "检验段", "百分位", random_signed.iloc[0]["percentile"], random_got.iloc[0]["percentile"])
        add("随机", "检验段", "每月跑赢", random_signed.iloc[0]["beat_random_median_share"], random_got.iloc[0]["beat_random_median_share"])
    forecast_signed = forecast[(forecast["segment"] == "2011-2015") & (forecast["role"] == "主值")]
    for _, signed_row in forecast_signed.iterrows():
        hit = produced_forecast[produced_forecast["项"] == signed_row["item"]]
        add("预测对账", "检验段", signed_row["item"], signed_row["contribution_pp"], None if hit.empty else hit.iloc[0]["组合贡献"])
    material = [row for row in diffs if row["实质差异"]]
    return {"条数": len(diffs), "实质差异": len(material), "明细": diffs, "可以签收": len(material) == 0}


def execute(windows: Windows, out: Path) -> dict:
    if windows.exam_end > DESIGN_END_TEXT or windows.full_end > DESIGN_END_TEXT:
        raise IsolationError("这个窗口晚于 2015-12-31。正式考试未授权，不装载。")
    refuse_market_after_design(windows.full_end)
    panels = load_panels()
    french = _french_note()
    if not PANEL.exists():
        raise IsolationError("美股起点经验面板不在")
    prior = us_prior(PANEL)
    bond, cash = panels["bond"], panels["cash"]
    votes = panels["votes"]
    saved = {key: panels["trin"][key].copy() for key in ("csi300", "SPX")}
    panels["trin"]["csi300"] = month_end_mean(clip_expanding(_a_daily(panels)))
    panels["trin"]["SPX"] = month_end_mean(clip_expanding(_us_daily(panels)))
    try:
        base = _variant(panels, prior, votes, bond, cash, n=3, cost=COST, lag=0, stress=2, exclude=None, weight_a=0.4)
        blocks = _zero_cost_blocks(panels, prior, votes, bond, cash)
        a_id, _ = _sleeve(panels["A"], "csi300", None, TAGS["a"], votes, bond, cash, "id", COST, 3, 0, 2, None)
        continuity = _mix(a_id, base["美"], COST, 0.4)
        bm_main, bm_same = _benchmarks()
        bm_same_s6 = _same_benchmark(S6_SAME_WEIGHTS)
        k2a = _k2a(panels, True)
        price_main = _price_benchmark(panels, (0.70, 0.15, 0.15))
        price_same = _price_benchmark(panels, (0.40, 0.30, 0.30))
        a1, a1_note = _read_peer("A1", A1_SHA)
        a2, a2_note = _read_peer("A2", A2_SHA)
        try:
            current, current_evidence = design_book()
        except (IsolationError, OSError, ValueError) as exc:
            current, current_evidence = None, {"status": "未完成", "reason": str(exc)}
        for series, name in (
            (base["净"], "v6"), (bm_main, "BM-主"), (bm_same, "BM-同仓位"), (k2a, "K2A"),
        ):
            _cap(series, name, windows.full_end)

        attr = _attribution_book(
            base["净"], blocks["毛"], blocks["等权"], blocks["前3"],
            bm_main, bm_same, price_main, price_same, k2a,
        )
        judged = _criteria_book(base["净"], base["不设防守"], bm_main, bm_same, k2a)
        exam = evaluate(judged, windows.exam_start, windows.exam_end)
        full = evaluate(judged, windows.full_start, windows.full_end)
        restart = _variant(
            {
                "A": _restart_levels(panels["A"], windows.exam_start),
                "US": _restart_levels(panels["US"], windows.exam_start),
            },
            prior, votes, bond, cash, n=3, cost=COST, lag=0, stress=2, exclude=None, weight_a=0.4,
        )
        restart_exam = evaluate(
            _criteria_book(restart["净"], restart["不设防守"], bm_main, bm_same, k2a),
            windows.exam_start, windows.exam_end,
        )

        pick_rows = _pick_rows(base["A记录"], panels["A"], blocks["A等权"], "A股", windows.exam_start, windows.exam_end)
        pick_rows += _pick_rows(base["美记录"], panels["US"], blocks["美等权"], "美股", windows.exam_start, windows.exam_end)
        table = pick_detail(pick_rows, {"A股": [], "美股": []}, windows.exam_start, windows.exam_end)
        pooled = []
        for body in table.values():
            pooled.extend(body["前10"])
        pooled.sort(key=lambda row: (-row["对挑选的贡献"], row["候选"]))
        seen = []
        for row in pooled:
            if row["候选"] not in seen:
                seen.append(row["候选"])
        dropped = {"S3": seen[:1], "S4": seen[:2], "S5": seen[:3]}

        scenarios = {
            "S1": dict(n=3, cost=COST * 2, lag=0, stress=2, exclude=None, weight_a=0.4),
            "S2": dict(n=3, cost=COST, lag=1, stress=2, exclude=None, weight_a=0.4),
            "S3": dict(n=3, cost=COST, lag=0, stress=2, exclude=dropped["S3"], weight_a=0.4),
            "S4": dict(n=3, cost=COST, lag=0, stress=2, exclude=dropped["S4"], weight_a=0.4),
            "S5": dict(n=3, cost=COST, lag=0, stress=2, exclude=dropped["S5"], weight_a=0.4),
            "S6": dict(n=3, cost=COST, lag=0, stress=2, exclude=None, weight_a=0.5),
            "S7": dict(n=2, cost=COST, lag=0, stress=2, exclude=None, weight_a=0.4),
            "S8": dict(n=3, cost=COST, lag=0, stress=3, exclude=None, weight_a=0.4),
        }
        variant_criteria = {}
        robustness_rows = []
        for code, spec in scenarios.items():
            plain = control_spec(code, spec)
            ran = _variant(panels, prior, votes, bond, cash, plain=plain, **spec)
            same = bm_same_s6 if code == "S6" else bm_same
            variant_book = _criteria_book(ran["净"], ran["不设防守"], bm_main, same, k2a)
            _cap(ran["净"], code, windows.full_end)
            item = evaluate(variant_book, windows.exam_start, windows.exam_end)
            variant_criteria[code] = item
            row = _criteria_row("检验段", code, item)
            row["去掉"] = "" if spec["exclude"] is None else ",".join(spec["exclude"])
            robustness_rows.append(row)
        verdict = official_verdict({("检验段", "指数池"): (exam, variant_criteria)})
        verdict["判定路径"] = "连续运行截出"
        verdict["重新起步"] = select_judgment(exam, restart_exam)
        if verdict["重新起步"]["主判"] != ("通过" if all(item_result_flags(exam).values()) else "不通过"):
            raise IsolationError("重新起步写进了官方主判")

        lines = {
            "v6": base["净"],
            "连续性版": continuity,
            "K2A": k2a,
            "A1": a1,
            "A2": a2,
            "现行配置": current,
            "BM-主": bm_main,
            "BM-同仓位": bm_same,
        }
        present = {name: series for name, series in lines.items() if series is not None}
        character = eight_line_table(present, windows.full_start, windows.full_end) if len(present) == len(EIGHT_LINES) else _line_table(lines, windows.full_start, windows.full_end)
        level = panels["ns"]["P"]["csi300"] if "P" in panels["ns"] else panels["A"]["csi300"]
        labels = month_regime(level.loc[:windows.full_end])
        regimes = regime_table(base["净"], {"BM-主": bm_main, "BM-同仓位": bm_same, "K2A": k2a}, labels)
        starts = {}
        for years, length in HOLD_DAYS.items():
            starts[str(years)] = any_start(
                {"v6": base["净"], "BM-主": bm_main, "BM-同仓位": bm_same, "K2A": k2a},
                "v6",
                years,
            )
            starts[str(years)]["交易日"] = length
        csi = panels["A"]["csi300"].pct_change().fillna(0.0)
        spx = panels["US"]["SPX"].pct_change().fillna(0.0)
        sleeve_rows = sleeve_split({
            "A股前3": blocks["A前3"], "A股等权": blocks["A等权"], "A股母指数": csi,
            "A股毛": blocks["A毛"], "A股净": base["A"],
            "美股前3": blocks["美前3"], "美股等权": blocks["美等权"], "美股母指数": spx,
            "美股毛": blocks["美毛"], "美股净": base["美"], "SPX": spx,
        }, windows.exam_start, windows.exam_end)
        universe = {"A股": list(panels["A"].columns), "美股": list(panels["US"].columns)}
        picks = pick_detail(pick_rows, universe, windows.exam_start, windows.exam_end)
        stress = stress_detail(
            _stress_rows(base["A记录"], base["A"], blocks["A前3"], "A股")
            + _stress_rows(base["美记录"], base["美"], blocks["美前3"], "美股")
        )
        forecast_rows = _forecast(_forecast_values(
            base, blocks, csi, spx, bm_main, bm_same, windows.exam_start, windows.exam_end,
        ))
        block_rows = _available_blocks(attr, windows)
        random_rows = _random_rows(panels, prior, votes, bond, cash)
        line_rows = []
        for label, start, end in (("检验段", windows.exam_start, windows.exam_end), ("全段", windows.full_start, windows.full_end)):
            for row in _line_table(lines, start, end):
                row["窗口"] = label
                line_rows.append(row)
        criteria_rows = [
            _criteria_row("检验段", "连续运行截出", exam),
            _criteria_row("检验段", "重新起步", restart_exam),
            _criteria_row("全段", "只报告", full),
        ]
        criteria_rows[-1]["进入判定"] = False
    finally:
        panels["trin"]["csi300"] = saved["csi300"]
        panels["trin"]["SPX"] = saved["SPX"]

    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(criteria_rows).to_csv(out / "criteria.csv", index=False)
    pd.DataFrame(robustness_rows).to_csv(out / "robustness.csv", index=False)
    pd.DataFrame(line_rows).to_csv(out / "lines.csv", index=False)
    pd.DataFrame(random_rows).to_csv(out / "random.csv", index=False)
    pd.DataFrame(forecast_rows).to_csv(out / "forecast.csv", index=False)
    pd.DataFrame(block_rows).to_csv(out / "blocks.csv", index=False)
    pd.DataFrame(_yearly_blocks(attr, windows)).to_csv(out / "blocks-yearly.csv", index=False)
    pd.DataFrame(sleeve_rows).to_csv(out / "sleeves.csv", index=False)
    pd.DataFrame(verdict["重新起步"]["差异"]).to_csv(out / "restart-diff.csv", index=False)
    (out / "verdict.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out / "picks.json").write_text(json.dumps(picks, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "stress.json").write_text(json.dumps(stress, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out / "character.json").write_text(json.dumps(character, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out / "regimes.json").write_text(json.dumps(regimes, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "anystart.json").write_text(json.dumps(starts, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "peers.json").write_text(json.dumps({"A1": a1_note, "A2": a2_note}, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "panel.json").write_text(json.dumps(current_evidence, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out / "extend-2026-09.json").write_text(json.dumps(extend_plan("2026-09-30"), ensure_ascii=False, indent=1), encoding="utf-8")
    comparison = _compare(out)
    acceptance = d51_accept(comparison)
    comparison["D51验收"] = acceptance
    (out / "comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "acceptance.json").write_text(json.dumps(acceptance, ensure_ascii=False, indent=1), encoding="utf-8")
    _write_mismatch_note(out, acceptance)
    manifest = {
        "窗口": asdict(windows),
        "命令": ".venv/bin/python -I -c \"import sys; sys.path.insert(0,'.'); from src.v6.oneshot_exam import main; main()\"",
        "正式考试": "未跑。ACTIVE 是预演。run_exam 与本模块的 official() 都拒绝。",
        "封顶": DESIGN_END_TEXT,
        "french": french,
        "行情库sha256": _sha_file(ROOT / "data/market.sqlite"),
        "代码sha256": _tree_sha((ROOT / "src/v6/oneshot_exam.py", ROOT / "src/v6/oneshot_prep.py", ROOT / "src/v6/engine.py")),
        "D51": "判据②用单边 0.2% 的前 3；S1–S7 对照跟着改；S8 对照不变；S6 的 BM-同仓位是 50/25/25。",
        "对照": {
            "实质差异": comparison["实质差异"],
            "可以签收": comparison["可以签收"],
            "D51验收": acceptance["通过"],
            "保费": acceptance["保费"],
        },
        "投票": "expanding99，与体检同一段替换",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    _write_comparison_md(out, comparison)
    if not acceptance["通过"]:
        raise IsolationError(acceptance["说明"] + f" 保费差 {acceptance['保费差']}。")
    return {
        "窗口": windows.name,
        "实质差异": comparison["实质差异"],
        "D51验收": True,
        "目录": str(out.relative_to(ROOT)),
    }


def _available_blocks(book: SpanBook, windows: Windows) -> list[dict]:
    """预演只算封顶以内的段。2016 年以后不贴 D49-8 的标签，也不编数。"""
    spans = (
        ("2006–10", "2006-01-01", "2010-12-31"),
        ("2011–15", windows.exam_start, windows.exam_end),
        ("全段", windows.full_start, windows.full_end),
    )
    rows = []
    for label, start, end in spans:
        parts = six_blocks(book, start, end)
        rows.append({"段": label, **{name: parts[name] for name in BLOCKS}, "和": parts["和"], "读法": "预演没有2016年以后，不贴标签"})
    return rows


def _yearly_blocks(book: SpanBook, windows: Windows) -> list[dict]:
    rows = []
    for year in range(2006, 2016):
        start, end = f"{year}-01-01", f"{year}-12-31"
        if end > windows.full_end:
            continue
        try:
            parts = six_blocks(book, start, end)
        except IsolationError:
            continue
        rows.append({"年": str(year), **{name: parts[name] for name in BLOCKS}})
    return rows


def _forecast_values(base, blocks, csi, spx, bm_main, bm_same, start, end) -> dict:
    def pp(series):
        return cagr(series.loc[start:end].dropna()) * 100.0

    from src.v6.oneshot_prep import premium_pp
    premium = premium_pp(base["净"], base["不设防守"], bm_main, start, end)
    return {
        "美股挑选": pp(blocks["美前3"]) - pp(spx),
        "A股挑选": pp(blocks["A前3"]) - pp(blocks["A等权"]),
        "A股等权倾斜": pp(blocks["A等权"]) - pp(csi),
        "防守保费": -premium,
        "美股60%仓位差": pp(bm_same) - pp(bm_main),
    }


def _tree_sha(paths: tuple[Path, ...]) -> dict[str, str]:
    return {str(path.relative_to(ROOT)): _sha_file(path) for path in paths}


def d51_accept(comparison: dict) -> dict:
    """D51-4。保费对签收值容差 0.01 点，其余已对上的项不容许再偏。"""
    premium = None
    others = []
    for row in comparison["明细"]:
        if row["差"] is None:
            others.append(row)
            continue
        if row["类"] == "判据" and row["段"] == "检验段" and row["项"] == "防守平时保费":
            premium = row
            continue
        if abs(row["差"]) > 1e-4:
            others.append(row)
    premium_ok = premium is not None and abs(premium["预演"] - SIGNED_PREMIUM) <= PREMIUM_TOLERANCE
    passed = premium_ok and not others
    return {
        "通过": passed,
        "保费": None if premium is None else premium["预演"],
        "签收保费": SIGNED_PREMIUM,
        "容差": PREMIUM_TOLERANCE,
        "保费差": None if premium is None else premium["预演"] - SIGNED_PREMIUM,
        "其余越界": others,
        "说明": (
            "判据②已按 D51 用单边 0.2% 的前 3、不设防守。上一轮 2.83 点是把不计成本的前 3 送进了判据。"
            if passed else
            "D51 验收没过。不改参数，不重跑。"
        ),
    }


def _write_mismatch_note(out: Path, acceptance: dict) -> None:
    if acceptance["通过"]:
        text = (
            "# 预演对照\n\n"
            "差异已按 D51 消除。判据②的不设防守是前 3、单边 0.2%、每月末 60/40，"
            f"检验段保费 {acceptance['保费']}，签收 {acceptance['签收保费']}，"
            f"差 {acceptance['保费差']}，容差 {acceptance['容差']} 点。\n\n"
            "上一轮 2.829 点是把 D49 拆账用的零成本前 3 送进了判据。"
            "第⑤块仍只用两条不计成本的序列，不进判据。\n"
            "S1–S7 的不设防守跟着同一改动；S8 只改紧张门槛，对照仍是主规则。"
            "BM-主和 K2A 在各 S 项下不变；S6 的 BM-同仓位改为沪深300 50%、纳指100 25%、标普500 25%。\n"
        )
    else:
        lines = ["# 预演对照", "", acceptance["说明"], ""]
        for row in acceptance["其余越界"]:
            lines.append(f"- {row['类']} {row['段']} {row['项']}：签收 {row['签收']}，预演 {row['预演']}，差 {row['差']}")
        if acceptance["保费差"] is not None and abs(acceptance["保费差"]) > PREMIUM_TOLERANCE:
            lines.append(f"- 保费差 {acceptance['保费差']} 超出 {PREMIUM_TOLERANCE}")
        text = "\n".join(lines) + "\n"
    (out / "mismatch-note.md").write_text(text, encoding="utf-8")


def _write_comparison_md(out: Path, comparison: dict) -> None:
    lines = [
        "# 预演对照",
        "",
        f"实质差异 {comparison['实质差异']} 条。可以签收：{comparison['可以签收']}。",
        "",
        "| 类 | 段 | 项 | 签收 | 预演 | 差 | 实质差异 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in comparison["明细"]:
        if row["实质差异"] or row["类"] in ("判据", "随机", "预测对账"):
            lines.append(
                f"| {row['类']} | {row['段']} | {row['项']} | {row['签收']} | {row['预演']} | {row['差']} | {row['实质差异']} |"
            )
    (out / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def official() -> None:
    """正式考试入口。未授权。"""
    run_exam()


def main() -> None:
    past_design = ACTIVE.exam_end > DESIGN_END_TEXT or ACTIVE.full_end > DESIGN_END_TEXT
    if ACTIVE is OFFICIAL or (past_design and not OFFICIAL_AUTHORIZED):
        official()
    if ACTIVE is not REHEARSAL:
        raise IsolationError("ACTIVE 不是预演窗口。正式考试未授权。")
    print(json.dumps(execute(ACTIVE, REHEARSAL_OUT), ensure_ascii=False))


if __name__ == "__main__":
    main()
