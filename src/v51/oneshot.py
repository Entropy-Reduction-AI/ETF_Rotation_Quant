"""D34-4 一次性检验。窗口 2016-01-01 → 2026-09-30，只跑一次。

入口：`python -m src.v51 oneshot`。

两个池用配置里的 id：`index`（U-指数）、`tradable`（U-可交易）。
入围臂是 E2/B0。A1、A2、BM-主、沪深300、标普500、纳指100，以及 v5.1，都只作对照。
v5.1 的目录名带「对照」，不入围，不计入判据 ⑤。

成交、成本、池子和溢价沿用 v4 B0 与 v5.1 已经在用的入口。
信号可以用 2016 年以前的价格；写进 `results/v5/oneshot/` 的收益只含锁定窗口。
不写 LOCK，不改账本，不打标签。
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from src.report.metrics import cagr, max_drawdown, monthly_returns, yearly_returns
from src.v3.eval.common import (
    EXPLORATION_TRIALS,
    ORCHESTRATOR_DIAGNOSTIC_TRIALS,
    C1_SHADOW_ARM,
    annualized_return,
)
from src.v3.eval.windows import engineering_check_1, rolling_windows
from src.v4.scorecard.core import STATE_ORDER, any_start, any_start_summary, growth_nav
from src.v4.scorecard.gate import _deduped, state_points
from src.v51.design import t_of

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "v5" / "oneshot"
LOCK = ROOT / "results" / "v5" / "LOCK"
FREEZE_SHA = "8970bcbc7986c9a67d9ca535ca58a8855c910495"
WINDOW_START = "2016-01-01"
WINDOW_END = "2026-09-30"
HURDLE_T = -2.0
POOLS = ("index", "tradable")
POOL_LABEL = {"index": "U-指数", "tradable": "U-可交易"}
PRIMARY = "E2-B0"
# 目录名把 v5.1 标成对照，避免和入围臂放在一起时看混。
ARM_ROLE = {
    "E2-B0": "入围",
    "A1": "对照",
    "A2": "对照",
    "v5.1-对照": "对照",
}
BENCHMARKS = ("BM-main", "HS300", "SPX", "NDX")
REFERENCE_COLUMN = {"HS300": "H00300", "SPX": "SP500TR", "NDX": "XNDX"}
# 这些文件的策略数字必须仍是代码冻结那一版。日期门的改动不在这份名单里。
FROZEN_BLOBS = (
    "src/v51/allocate.py",
    "src/v51/readings.py",
    "src/v51/params.py",
    "src/v51/universe.py",
    "src/v51/hold.py",
    "src/v5/engine/allocate.py",
    "src/v5/engine/execute.py",
    "src/v5/engine/paths.py",
    "src/v3/engine/book.py",
    "src/v3/engine/exit.py",
    "src/v3/premium/rules.py",
    "src/v4/peers/signals.py",
    "src/v4/peers/config.py",
    "config/v5.1/params.toml",
    "config/v4/peers.toml",
    "config/v3/arms.toml",
    "config/v5/classes.csv",
)


class OneshotError(RuntimeError):
    pass


def arm_dir(out: Path, pool: str, arm: str) -> Path:
    if pool not in POOLS:
        raise OneshotError(f"没有这个池：{pool}")
    if arm not in ARM_ROLE:
        raise OneshotError(f"没有这条臂：{arm}")
    return Path(out) / pool / arm


def is_formal(arm: str, pool: str) -> bool:
    """判据①⑥只对 U-指数上的 E2/B0 给出通过与否。"""
    return arm == PRIMARY and pool == "index"


def _refuse_target(out: Path, lock: Path) -> None:
    resolved = Path(out).resolve()
    if resolved == Path(lock).resolve() or resolved.name == "LOCK":
        raise OneshotError("不写 LOCK")
    if "trial-ledger" in resolved.name:
        raise OneshotError("一次性检验不写账本")


def authorize(lock: Path, out: Path) -> None:
    """LOCK 已在树上，窗口写明，而且这次还没跑完。"""
    _refuse_target(out, lock)
    path = Path(lock)
    if not path.is_file():
        raise OneshotError("results/v5/LOCK 不存在，拒绝计算 2016 年以后的组合收益")
    text = path.read_text(encoding="utf-8")
    if FREEZE_SHA not in text:
        raise OneshotError("LOCK 没有绑定 milestone/v5-code-freeze 的提交")
    if WINDOW_START not in text or WINDOW_END not in text:
        raise OneshotError("LOCK 的窗口不是 2016-01-01 → 2026-09-30")
    if (Path(out) / "ran.json").exists():
        raise OneshotError("一次性检验已经跑过，拒绝再跑")


def assert_lineage() -> str:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    probe = subprocess.run(
        ["git", "merge-base", "--is-ancestor", FREEZE_SHA, "HEAD"],
        check=False,
    )
    if probe.returncode != 0:
        raise OneshotError("当前提交不是 milestone/v5-code-freeze 的后继")
    return head


def assert_frozen_blobs() -> None:
    for rel in FROZEN_BLOBS:
        work = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        data = subprocess.check_output(["git", "show", f"{FREEZE_SHA}:{rel}"])
        frozen = hashlib.sha256(data).hexdigest()
        if work != frozen:
            raise OneshotError(f"{rel} 与代码冻结不一致")


def _file_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scored(series: pd.Series, last: pd.Timestamp) -> pd.Series:
    """锁定窗口里的日收益。最后一天必须是窗口内的最后一个交易日。"""
    out = pd.Series(series, dtype=float).dropna().sort_index()
    out.index = pd.DatetimeIndex(pd.to_datetime(out.index)).normalize()
    out = out[~out.index.duplicated(keep="last")]
    if len(out) and pd.Timestamp(out.index.max()) > pd.Timestamp(WINDOW_END):
        raise OneshotError("收益晚于 2026-09-30")
    block = out.loc[WINDOW_START:WINDOW_END]
    if block.empty:
        raise OneshotError("锁定窗口里没有收益")
    if pd.Timestamp(block.index.max()) != pd.Timestamp(last):
        raise OneshotError(
            f"收益停在 {pd.Timestamp(block.index.max()).date()}，窗口最后交易日是 {pd.Timestamp(last).date()}"
        )
    return block


def attempt_report(v3_path: Path, v4_path: Path, v5_path: Path) -> dict:
    """v5 §6.4 的尝试次数。v5.1 与 A1 按 D34-3 不计入。"""
    v3 = _deduped(Path(v3_path))
    v4 = _deduped(Path(v4_path))
    present = Path(v5_path).is_file()
    v5 = _deduped(Path(v5_path)) if present else []
    shadow = sum(1 for row in v3 + v4 if (row.get("arm") or "") == C1_SHADOW_ARM)
    l3, l4, l5 = len(v3), len(v4), len(v5)
    count = l3 + l4 + l5 - shadow + EXPLORATION_TRIALS + ORCHESTRATOR_DIAGNOSTIC_TRIALS + 1
    return {
        "L3": l3,
        "L4": l4,
        "L5": l5,
        "C": shadow,
        "exploration": EXPLORATION_TRIALS,
        "diagnostic": ORCHESTRATOR_DIAGNOSTIC_TRIALS,
        "evidence": 1,
        "attempts": count,
        "v5_ledger_present": present,
        "excluded_from_L5": ["v5.1", "A1"],
        "note": "D34-3：v5.1 不计入判据⑤。入围名单只有 E2/B0，所以 A1 也不加 1 行。",
    }


def criterion_1_on_window(strategy: pd.Series, benchmark: pd.Series) -> dict:
    """§6.4 ①。36 与 60 个月窗口都落在锁定窗口里。"""
    both = pd.concat([
        pd.Series(strategy, dtype=float).rename("strategy"),
        pd.Series(benchmark, dtype=float).rename("benchmark"),
    ], axis=1).dropna().sort_index()
    both = both.loc[WINDOW_START:WINDOW_END]
    if both.empty:
        raise OneshotError("判据①没有重叠的日收益")
    calendar = pd.DatetimeIndex(both.index)

    def records(months: int) -> list[dict]:
        rows = []
        for start, end in rolling_windows(calendar, months, end_limit=WINDOW_END):
            if pd.Timestamp(start) < pd.Timestamp(WINDOW_START):
                continue
            days = calendar[(calendar >= start) & (calendar <= end)]
            left = both["strategy"].reindex(days)
            right = both["benchmark"].reindex(days)
            if left.isna().any() or right.isna().any():
                continue
            ann_strategy = annualized_return(left.to_numpy())
            ann_benchmark = annualized_return(right.to_numpy())
            rows.append({
                "start": pd.Timestamp(start).date().isoformat(),
                "end": pd.Timestamp(end).date().isoformat(),
                "months": months,
                "n": int(len(days)),
                "ann_strategy": ann_strategy,
                "ann_benchmark": ann_benchmark,
                "excess": ann_strategy - ann_benchmark,
            })
        return rows

    windows_36 = records(36)
    windows_60 = records(60)
    excess_36 = [row["excess"] for row in windows_36]
    excess_60 = [row["excess"] for row in windows_60]
    median_36 = None if not excess_36 else float(np.median(np.asarray(excess_36, dtype=float)))
    median_60 = None if not excess_60 else float(np.median(np.asarray(excess_60, dtype=float)))
    fraction = None if not excess_60 else float(np.mean(np.asarray(excess_60) > 0.0))
    return {
        "n_36": len(windows_36),
        "n_60": len(windows_60),
        "median_36": median_36,
        "median_60": median_60,
        "fraction_positive_60": fraction,
        "pass": bool(engineering_check_1(median_36, median_60, fraction)),
        "windows_36": windows_36,
        "windows_60": windows_60,
    }


def criterion_6(strategy: pd.Series, benchmark: pd.Series, states: pd.Series) -> dict:
    """⑥：P(牛市) ≥ 0，反弹月份的月度超额 t ≥ −2（D33-3）。"""
    both = pd.concat([
        pd.Series(strategy, dtype=float).rename("strategy"),
        pd.Series(benchmark, dtype=float).rename("benchmark"),
    ], axis=1).dropna().sort_index()
    both = both.loc[WINDOW_START:WINDOW_END]
    if both.empty:
        raise OneshotError("判据⑥没有重叠的日收益")
    excess = both["strategy"] - both["benchmark"]
    points = state_points(excess, states)
    labels = states.dropna().copy()
    labels.index = pd.DatetimeIndex(pd.to_datetime(labels.index)).to_period("M")
    labels = labels[~labels.index.duplicated(keep="last")]
    paired = pd.concat([
        monthly_returns(both["strategy"]).rename("strategy"),
        monthly_returns(both["benchmark"]).rename("benchmark"),
    ], axis=1).dropna()
    month_excess = paired["strategy"] - paired["benchmark"]
    rebound = month_excess[labels.reindex(month_excess.index) == "反弹"]
    rebound_t = t_of(rebound)
    bull = float(points["牛市"])
    pass_bull = bool(bull >= 0.0)
    pass_rebound = bool(math.isfinite(rebound_t) and rebound_t >= HURDLE_T)
    report = {name: float(points[name]) for name in STATE_ORDER}
    report.update({
        "rebound_t": rebound_t,
        "rebound_n": int(len(rebound)),
        "pass_bull": pass_bull,
        "pass_rebound": pass_rebound,
        "pass": bool(pass_bull and pass_rebound),
    })
    return report


def _yearly(series: pd.Series) -> pd.DataFrame:
    rows = [{"year": year, "return": value} for year, value in yearly_returns(series).items()]
    return pd.DataFrame(rows)


def _summary_numbers(series: pd.Series) -> dict:
    depth = max_drawdown(series)
    return {
        "cagr": cagr(series),
        "max_drawdown": depth["max_drawdown"],
        "n": int(len(series)),
        "start": pd.Timestamp(series.index.min()).date().isoformat(),
        "end": pd.Timestamp(series.index.max()).date().isoformat(),
    }


def _write_frame(folder: Path, frame: pd.DataFrame, name: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    out.index.name = "date"
    out.to_csv(folder / name, float_format="%.12g")


def _write_series(folder: Path, series: pd.Series, *, role: str, arm: str, pool: str | None) -> dict:
    from src.v4.r5.design import series_sha256

    folder.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame({"net": series, "nav": (1.0 + series).cumprod()})
    _write_frame(folder, frame, "net.csv")
    _yearly(series).to_csv(folder / "yearly.csv", index=False, float_format="%.12g")
    (folder / "role.txt").write_text(role + "\n", encoding="utf-8")
    numbers = _summary_numbers(series)
    numbers.update({
        "arm": arm,
        "role": role,
        "pool": pool,
        "pool_label": None if pool is None else POOL_LABEL[pool],
        "net_sha256": series_sha256(series),
        "contender": arm == PRIMARY,
    })
    (folder / "summary.json").write_text(
        json.dumps(numbers, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return numbers


def _align(series: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    out = pd.Series(series, dtype=float)
    out.index = pd.DatetimeIndex(pd.to_datetime(out.index)).normalize()
    return out.reindex(index)


def _write_book(folder: Path, book, window: pd.Series) -> None:
    extra = {}
    for name in ("gross", "cost", "buy", "sell"):
        series = getattr(book, name, None)
        if isinstance(series, pd.Series):
            extra[name] = _align(series, window.index)
    frame = pd.DataFrame({"net": window, "nav": (1.0 + window).cumprod(), **extra})
    _write_frame(folder, frame, "net.csv")
    held = book.held.copy()
    held.index = pd.DatetimeIndex(pd.to_datetime(held.index)).normalize()
    held = held.reindex(window.index)
    _write_frame(folder, held, "held.csv")


def _anystart(strategy: str, series: dict[str, pd.Series]) -> pd.DataFrame:
    frame = pd.DataFrame({
        name: pd.Series(values, dtype=float) for name, values in series.items()
    }).dropna(how="any").sort_index()
    if frame.empty:
        raise OneshotError("任意起点没有共同的交易日")
    index = pd.DatetimeIndex(frame.index)
    navs = {name: growth_nav(frame[name], index) for name in frame.columns}
    tables = any_start(navs, strategy=strategy, horizons=(1, 3, 5), allow_after=True)
    return any_start_summary(tables, strategy=strategy)


def _blank(value):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return None
    return value


def _criteria_row(pool: str | None, arm: str, role: str, numbers: dict, rule1: dict | None,
                  rule6: dict | None, *, formal: bool) -> dict:
    row = {
        "pool": pool or "",
        "pool_label": "" if pool is None else POOL_LABEL[pool],
        "arm": arm,
        "role": role,
        "contender": arm == PRIMARY,
        "formal": formal,
        "cagr": numbers["cagr"],
        "max_drawdown": numbers["max_drawdown"],
        "n": numbers["n"],
        "median_36": None if rule1 is None else _blank(rule1["median_36"]),
        "median_60": None if rule1 is None else _blank(rule1["median_60"]),
        "fraction_positive_60": None if rule1 is None else _blank(rule1["fraction_positive_60"]),
        "n_36": None if rule1 is None else rule1["n_36"],
        "n_60": None if rule1 is None else rule1["n_60"],
        "pass_1": None if rule1 is None or not formal else rule1["pass"],
        "pp_bull": None if rule6 is None else rule6["牛市"],
        "pp_correction": None if rule6 is None else rule6["回调"],
        "pp_bear": None if rule6 is None else rule6["熊市"],
        "pp_rebound": None if rule6 is None else rule6["反弹"],
        "rebound_t": None if rule6 is None else _blank(rule6["rebound_t"]),
        "rebound_n": None if rule6 is None else rule6["rebound_n"],
        "pass_bull": None if rule6 is None or not formal else rule6["pass_bull"],
        "pass_rebound": None if rule6 is None or not formal else rule6["pass_rebound"],
        "pass_6": None if rule6 is None or not formal else rule6["pass"],
    }
    if formal and rule1 is not None and rule6 is not None:
        row["pass"] = bool(rule1["pass"] and rule6["pass"])
    else:
        row["pass"] = None
    return row


def _run_b0(market, spec):
    from src.v3.engine.arms import execute
    from src.v3.engine.exit import EXIT_DRAWDOWN
    from src.v5.engine.execute import b0_switches

    return execute(
        market, spec, "A", allow_after=True,
        exit_drawdown=EXIT_DRAWDOWN, switches=b0_switches(),
    )


def _run_v51(market, spec, pool: str):
    from src.v51.allocate import target_weights
    from src.v51.design import eligible_frame
    from src.v51.execute import run_book, universe_for

    signal = market.signal.copy()
    signal.index = pd.DatetimeIndex(pd.to_datetime(signal.index)).normalize()
    dates = pd.DatetimeIndex(pd.to_datetime(market.dates)).normalize()
    if not signal.index.equals(dates):
        raise OneshotError(f"{pool} 的信号日历和成交日历不一致")
    allocation = target_weights(
        signal, universe_for(market),
        eligible=eligible_frame(pool, market.liquidity, signal.index),
        allow_after=True,
    )
    book = run_book(market, spec, allocation.decisions, allow_after=True)
    return book, allocation


def _run_peers(spec) -> dict:
    from src.v4.peers import load_peer, run_peer
    from src.v4.r5.peers import research_panel

    panel = research_panel(spec, end=WINDOW_END, allow_after=True)
    found = {}
    for peer_id in ("A1", "A2"):
        for pool in POOLS:
            print(f"对照 {peer_id} {pool}", flush=True)
            peer = load_peer(peer_id, pool)
            carriers = panel["carriers"] if pool == "tradable" else None
            quotes = panel["tradable_quotes"] if pool == "tradable" else panel["index_quotes"]
            levels = panel["tradable_levels"] if pool == "tradable" else panel["levels"]
            signal_levels = panel["levels"] if pool == "tradable" else None
            found[(peer_id, pool)] = run_peer(
                peer, panel["calendar"], levels, signal_levels=signal_levels,
                cash=panel["cash"], carriers=carriers, quotes=quotes,
                calendar_closed=True, allow_after=True,
            )
    return found


def _last_session() -> pd.Timestamp:
    from src.v3.engine.benchmark import _calendar
    from src.v4.r5.design import _connect

    con = _connect()
    try:
        days = _calendar(con, WINDOW_END)
    finally:
        con.close()
    if len(days) == 0:
        raise OneshotError("锁定窗口没有交易日")
    last = pd.Timestamp(days.max())
    if last > pd.Timestamp(WINDOW_END) or last < pd.Timestamp("2026-09-01"):
        raise OneshotError(f"窗口最后交易日不对：{last.date()}")
    return last


def _store_arm(out: Path, pool: str, arm: str, window: pd.Series, book, benchmark: pd.Series,
               states: pd.Series, refs: dict[str, pd.Series], rows: list[dict], *,
               allocation=None) -> dict:
    from src.v4.r5.design import series_sha256

    folder = arm_dir(out, pool, arm)
    folder.mkdir(parents=True, exist_ok=True)
    _write_book(folder, book, window)
    _yearly(window).to_csv(folder / "yearly.csv", index=False, float_format="%.12g")
    role = ARM_ROLE[arm]
    (folder / "role.txt").write_text(role + "\n", encoding="utf-8")
    numbers = _summary_numbers(window)
    numbers.update({
        "arm": arm,
        "role": role,
        "pool": pool,
        "pool_label": POOL_LABEL[pool],
        "net_sha256": series_sha256(window),
        "contender": arm == PRIMARY,
    })
    rule1 = criterion_1_on_window(window, benchmark.reindex(window.index))
    rule6 = criterion_6(window, benchmark, states)
    formal = is_formal(arm, pool)
    numbers["pass_1"] = rule1["pass"] if formal else None
    numbers["pass_6"] = rule6["pass"] if formal else None
    (folder / "summary.json").write_text(
        json.dumps(numbers, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    windows = pd.DataFrame(rule1["windows_36"] + rule1["windows_60"])
    windows.to_csv(folder / "criterion-1-windows.csv", index=False, float_format="%.12g")
    _anystart(arm, {arm: window, **{name: refs[name].reindex(window.index) for name in BENCHMARKS}}).to_csv(
        folder / "anystart.csv", index=False, float_format="%.12g",
    )
    if allocation is not None:
        state = allocation.state.copy()
        state.index = pd.DatetimeIndex(pd.to_datetime(state.index)).normalize()
        _write_frame(folder, state.reindex(window.index), "state.csv")
        decisions = allocation.decisions.copy()
        decisions.index = pd.DatetimeIndex(pd.to_datetime(decisions.index)).normalize()
        kept = decisions.loc[(decisions.index >= WINDOW_START) & (decisions.index <= WINDOW_END)]
        _write_frame(folder, kept, "decisions.csv")
        exits = allocation.exits.copy()
        if "t" in exits.columns and len(exits):
            stamp = pd.to_datetime(exits["t"])
            exits = exits.loc[(stamp >= WINDOW_START) & (stamp <= WINDOW_END)]
        exits.to_csv(folder / "exits.csv", index=False)
    rows.append(_criteria_row(pool, arm, role, numbers, rule1, rule6, formal=formal))
    return {"rule1": rule1, "rule6": rule6, "numbers": numbers}


def run_oneshot(*, out: Path | None = None, lock: Path | None = None) -> dict:
    """两个池各跑一次。会计算锁定窗口里的组合收益。不写 LOCK。"""
    from src.data.db import git_head
    from src.v3.engine.spec import LEDGER as V3_LEDGER
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import (
        benchmark_returns,
        prepare_market,
        reference_frame,
        require_frozen_db,
    )
    from src.v4.scorecard.gate import V4_LEDGER
    from src.v5.campaign import LEDGER as V5_LEDGER

    destination = OUT if out is None else Path(out)
    lock_path = LOCK if lock is None else Path(lock)
    authorize(lock_path, destination)
    head = assert_lineage()
    assert_frozen_blobs()
    lock_before = _file_sha(lock_path)
    digest = require_frozen_db()
    spec = load_spec()
    last = _last_session()
    print(f"参照指数与 BM-主，窗口最后交易日 {last.date()}", flush=True)
    parts = reference_frame(end=WINDOW_END, allow_after=True)
    benchmark = scored(benchmark_returns(end=WINDOW_END, allow_after=True), last)
    from src.v4.r5.design import month_states

    states = month_states(end=WINDOW_END, allow_after=True)
    refs = {"BM-main": benchmark}
    for name, column in REFERENCE_COLUMN.items():
        refs[name] = scored(parts[column], last)
    bench_dir = destination / "benchmarks"
    for name in BENCHMARKS:
        _write_series(bench_dir / name, refs[name], role="对照", arm=name, pool=None)
    labeled = states.dropna().rename("state").to_frame()
    labeled.index.name = "month_end"
    destination.mkdir(parents=True, exist_ok=True)
    labeled.to_csv(destination / "month-states.csv")
    peers = _run_peers(spec)
    rows: list[dict] = []
    for name in BENCHMARKS:
        rows.append(_criteria_row(None, name, "对照", _summary_numbers(refs[name]), None, None, formal=False))
    formal = None
    tradable_median_60 = None
    for pool in POOLS:
        print(f"装 {POOL_LABEL[pool]}", flush=True)
        market = prepare_market(
            pool, t4=False, allow_substitute=True, spec=spec,
            end=WINDOW_END, allow_after=True,
        )
        print(f"E2/B0 {pool}", flush=True)
        b0 = _run_b0(market, spec)
        stored = _store_arm(
            destination, pool, PRIMARY, scored(b0.net, last), b0, benchmark, states, refs, rows,
        )
        if pool == "index":
            formal = stored
        else:
            tradable_median_60 = stored["rule1"]["median_60"]
        print(f"v5.1 对照 {pool}", flush=True)
        book, allocation = _run_v51(market, spec, pool)
        _store_arm(
            destination, pool, "v5.1-对照", scored(book.net, last), book, benchmark, states, refs, rows,
            allocation=allocation,
        )
        for peer_id in ("A1", "A2"):
            result = peers[(peer_id, pool)]
            _store_arm(
                destination, pool, peer_id, scored(result.net, last), result, benchmark, states, refs, rows,
            )
        del market
    if formal is None or tradable_median_60 is None:
        raise OneshotError("两个池没有都跑完")
    downgrade = bool(tradable_median_60 is not None and tradable_median_60 <= 0.0)
    table = pd.DataFrame(rows)
    table.to_csv(destination / "criteria.csv", index=False, float_format="%.12g")
    attempts = attempt_report(V3_LEDGER, V4_LEDGER, V5_LEDGER)
    (destination / "attempts.json").write_text(
        json.dumps(attempts, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if _file_sha(lock_path) != lock_before:
        raise OneshotError("运行过程中 LOCK 被改动")
    manifest = {
        "window": [WINDOW_START, WINDOW_END],
        "last_session": last.date().isoformat(),
        "freeze_sha": FREEZE_SHA,
        "head_sha": head,
        "git_head": git_head() or head,
        "lock": "results/v5/LOCK",
        "lock_sha256": lock_before,
        "db_sha256": digest,
        "pools": {pool: POOL_LABEL[pool] for pool in POOLS},
        "primary": PRIMARY,
        "comparison": ["A1", "A2", "v5.1-对照", *BENCHMARKS],
        "v51_role": "对照",
        "scored_slice": "报告里的日收益只含锁定窗口。2016 年以前的价格只用于信号和持仓延续。",
        "criterion_6_rebound": "月度超额 t ≥ -2（D33-3），不是 P(反弹) ≥ 0",
        "formal_pool": "index",
        "pass_1": formal["rule1"]["pass"],
        "pass_6": formal["rule6"]["pass"],
        "pass": bool(formal["rule1"]["pass"] and formal["rule6"]["pass"]),
        "tradable_median_60": tradable_median_60,
        "tradable_downgrade_rule_1": downgrade,
        "attempts": attempts["attempts"],
        "single_pass": True,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (destination / "ran.json").write_text(
        json.dumps({"single_pass": True, "window": manifest["window"], "freeze_sha": FREEZE_SHA, "head_sha": head},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "window": [WINDOW_START, WINDOW_END],
        "primary": PRIMARY,
        "pass_1": formal["rule1"]["pass"],
        "pass_6": formal["rule6"]["pass"],
        "head": head,
        "freeze": FREEZE_SHA,
        "out": str(destination),
    }
