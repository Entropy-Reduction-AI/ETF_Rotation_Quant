"""§7.1 稳健性。只报告，不改判。

F 只按 §6.1 从过关表读：P1 过关才保留 C1，P2 过关才保留这一版，否则回到 P2 行上的
`base_arm`。`base_arm` 必须和 P1 的 pass 一致，否则停，不另选。
对照一次只改预注册点名的一项，其余开关与 F 相同，成交仍走 `run_arm`。
不写 LOCK，不打标签，不算 2016 年以后的中国组合收益，不跑 §7.2。
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.report.metrics import max_drawdown
from src.v4.scorecard.gate import SEGMENTS, _excess, _segment_excess, state_points
from src.v5.campaign import (
    DESIGN_ARMS,
    LEDGER,
    LEDGER_CAP,
    OUT,
    POOLS,
    _passed_flag,
    _rows,
    _write_net,
    record_version,
    version_flags,
)
from src.v5.engine.allocate import (
    STRUCTURE_FIXED_BUDGET,
    STRUCTURE_NO_DEFENSE,
    STRUCTURE_S0,
    STRUCTURE_STRONGEST,
    EngineError,
)
from src.v5.engine.execute import b0_switches, run_arm
from src.v5.engine.paths import C2_DRAWDOWN

# v4 §7.2 写死的三组。v5 §7.1 说邻近回看期同那一节。
NEIGHBOR_LOOKBACKS = (
    (10, 40, 90, 180),
    (15, 50, 100, 200),
    (30, 80, 150, 300),
)
# v5 只点了 8% 和 12%。15% 是 v4 的，这里不加。
EXIT_CONTRASTS = (0.08, 0.12)
STRUCTURE_CASES = (
    ("strongest-class", STRUCTURE_STRONGEST),
    ("fixed-budget", STRUCTURE_FIXED_BUDGET),
    ("no-defense", STRUCTURE_NO_DEFENSE),
)
REPORT_COLUMNS = (
    "case", "pool", "kind", "final_arm", "enable_c1", "enable_c2",
    "ann_excess_s1", "ann_excess_s2", "d_s1_pp", "d_s2_pp",
    "pp_bull", "pp_correction", "pp_bear", "pp_rebound",
    "max_drawdown_2006", "series_sha256", "file_sha256", "dropped",
)


@dataclass(frozen=True)
class RobustJob:
    case: str
    pool: str
    final_arm: str
    base_arm: str
    enable_c1: bool
    enable_c2: bool
    structure: str
    cost_multiplier: float
    decision_delay: int
    exit_drawdown: float | None
    allow_substitute: bool
    lookbacks: tuple[int, ...] | None
    drop_best: int


def _blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _text(value) -> str:
    if _blank(value):
        return ""
    return str(value).strip()


def _grouped(table: pd.DataFrame) -> dict[str, list[dict]]:
    if "arm" not in table.columns or "pass" not in table.columns or "base_arm" not in table.columns:
        raise EngineError("过关表缺 arm、base_arm 或 pass")
    grouped: dict[str, list[dict]] = {}
    for row in table.to_dict(orient="records"):
        grouped.setdefault(_text(row.get("arm")), []).append(row)
    return grouped


def _one(grouped: dict[str, list[dict]], arm: str) -> dict:
    rows = grouped.get(arm, [])
    if len(rows) != 1:
        raise EngineError(f"{arm} 应有一行，实际 {len(rows)}，不能确定 F")
    return rows[0]


def final_arm(table: pd.DataFrame) -> str:
    """§6.1 最后一个保留的版本。定不了就抛错，调用方不要再跑稳健性。"""
    grouped = _grouped(table)
    start = _one(grouped, "S0")
    first = _one(grouped, "P1")
    second = _one(grouped, "P2")
    if not _blank(start.get("pass")):
        raise EngineError("S0 的 pass 应留空，不能确定 F")
    kept_c1 = _passed_flag(first.get("pass"))
    kept_c2 = _passed_flag(second.get("pass"))
    expected = "P1" if kept_c1 else "S0"
    actual = _text(second.get("base_arm"))
    if actual != expected:
        raise EngineError(f"P2 的 base_arm 是 {actual or '空'}，按 P1 的 pass 应为 {expected}，不能确定 F")
    if kept_c2:
        return "P2"
    return expected


def _exit_changed(job: RobustJob) -> bool:
    if job.enable_c2:
        if job.exit_drawdown is None:
            return True
        return not math.isclose(float(job.exit_drawdown), C2_DRAWDOWN, rel_tol=0.0, abs_tol=1e-12)
    return job.exit_drawdown is not None


def _changes(job: RobustJob) -> list[str]:
    found = []
    if job.lookbacks is not None:
        found.append("lookbacks")
    if float(job.cost_multiplier) != 1.0:
        found.append("cost")
    if int(job.decision_delay) != 0:
        found.append("delay")
    if int(job.drop_best) != 0:
        found.append("drop")
    if job.structure != STRUCTURE_S0:
        found.append("structure")
    if not job.allow_substitute:
        found.append("substitute")
    if _exit_changed(job):
        found.append("exit")
    return found


def _check_lookbacks(lengths: tuple[int, ...]) -> None:
    if len(lengths) != 4 or len(set(lengths)) != 4:
        raise EngineError(f"回看期要四个不同的长度：{lengths}")
    if tuple(sorted(lengths)) != tuple(lengths):
        raise EngineError(f"回看期按从短到长写：{lengths}")
    if any(int(item) <= 0 for item in lengths):
        raise EngineError(f"回看期要是正整数：{lengths}")


def _job(case: str, pool: str, flags: dict, final: str, **overrides) -> RobustJob:
    if pool not in POOLS:
        raise EngineError(f"未知的池 {pool}")
    payload = {
        "case": case,
        "pool": pool,
        "final_arm": final,
        "base_arm": str(flags["base_arm"]),
        "enable_c1": bool(flags["enable_c1"]),
        "enable_c2": bool(flags["enable_c2"]),
        "structure": STRUCTURE_S0,
        "cost_multiplier": 1.0,
        "decision_delay": 0,
        "exit_drawdown": C2_DRAWDOWN if flags["enable_c2"] else None,
        "allow_substitute": True,
        "lookbacks": None,
        "drop_best": 0,
    }
    payload.update(overrides)
    if payload["lookbacks"] is not None:
        payload["lookbacks"] = tuple(int(item) for item in payload["lookbacks"])
        _check_lookbacks(payload["lookbacks"])
    job = RobustJob(**payload)
    if not job.allow_substitute and job.pool != "tradable":
        raise EngineError("不含相近替身只跑 U-可交易")
    if job.drop_best not in {0, 1, 2, 3}:
        raise EngineError(f"去掉最好的容器只能是 0 到 3 只，收到 {job.drop_best}")
    changed = _changes(job)
    if len(changed) != 1:
        raise EngineError(f"{case}/{pool} 改了 {changed or '没有'}，稳健性一次只改一项")
    return job


def robustness_jobs(flags: dict, *, final: str) -> list[RobustJob]:
    """§7.1 的枚举。F 不含 C2 时没有 8%、12% 两行。"""
    if final not in DESIGN_ARMS:
        raise EngineError(f"F 只能是 S0、P1、P2，收到 {final}")
    if final == "S0" and flags["enable_c1"]:
        raise EngineError("S0 不能带着 C1")
    if final == "P1" and not flags["enable_c1"]:
        raise EngineError("P1 必须带着 C1")
    if bool(flags["enable_c2"]) != (final == "P2"):
        raise EngineError("C2 只在 F 为 P2 时开着")
    jobs: list[RobustJob] = []

    def add(case: str, pools: tuple[str, ...], **overrides) -> None:
        for pool in pools:
            jobs.append(_job(case, pool, flags, final, **overrides))

    for lengths in NEIGHBOR_LOOKBACKS:
        add("lookback-" + "-".join(str(item) for item in lengths), POOLS, lookbacks=lengths)
    add("cost-double", POOLS, cost_multiplier=2.0)
    add("delay-1d", POOLS, decision_delay=1)
    for count in (1, 2, 3):
        add(f"drop-best-{count}", POOLS, drop_best=count)
    for label, structure in STRUCTURE_CASES:
        add(label, POOLS, structure=structure)
    if flags["enable_c2"]:
        for drawdown in EXIT_CONTRASTS:
            add(f"exit-{int(round(drawdown * 100))}", POOLS, exit_drawdown=drawdown)
    add("no-substitute", ("tradable",), allow_substitute=False)
    return jobs


def robustness_params(job: RobustJob, spec, dropped: list[str] | None = None) -> dict:
    """写进 ledger 的 params。`final_arm` 是对照所依附的 F；`base_arm` 是 F 自己的部件上一版。"""
    names = [str(item) for item in (dropped or [])]
    if len(names) != int(job.drop_best):
        raise EngineError(f"{job.case} 要去掉 {job.drop_best} 只，名单有 {len(names)} 只")
    if job.enable_c2:
        drawdown = C2_DRAWDOWN if job.exit_drawdown is None else float(job.exit_drawdown)
    else:
        if job.exit_drawdown is not None:
            raise EngineError("C2 关着时不能另设离场阈值")
        drawdown = None
    switches = b0_switches(allow_substitute=job.allow_substitute)
    lengths = [int(item) for item in (spec.lookbacks if job.lookbacks is None else job.lookbacks)]
    return {
        "rules": "v5",
        "case": job.case,
        "kind": "robustness",
        "pool": job.pool,
        "end": "2015-12-31",
        "final_arm": job.final_arm,
        "base_arm": job.base_arm,
        "enable_c1": job.enable_c1,
        "enable_c2": job.enable_c2,
        "structure": job.structure,
        "fill_limits": switches.fill_limits,
        "fx_v4": switches.fx_v4,
        "carriers": switches.carriers,
        "allow_substitute": switches.allow_substitute,
        "t1_turn": switches.t1_turn,
        "t2_state_weights": switches.t2_state_weights,
        "t3_refill": switches.t3_refill,
        "t4_pool": switches.t4_pool,
        "lookbacks": lengths,
        "exit_drawdown": drawdown,
        "cost_multiplier": float(job.cost_multiplier),
        "decision_delay": int(job.decision_delay),
        "drop_best": int(job.drop_best),
        "dropped": names,
        "trade_eps": float(spec.trade_eps),
        "weight_eps": float(spec.weight_eps),
        "paths": ["week", "month"],
        "cross_border": switches.cross_border is not None,
    }


def _design_rows(rows: list[dict]) -> tuple:
    found = []
    for row in rows:
        try:
            payload = json.loads(row.get("params") or "{}")
        except json.JSONDecodeError:
            continue
        if payload.get("kind") != "design":
            continue
        found.append((row.get("arm"), payload.get("pool"), row.get("git_sha"), row.get("run_at"), row.get("params")))
    return tuple(found)


def _matching_row(rows: list[dict], case: str, pool: str) -> dict | None:
    for row in rows:
        if row.get("arm") != case or row.get("segment") != "design":
            continue
        try:
            payload = json.loads(row.get("params") or "{}")
        except json.JSONDecodeError:
            continue
        if payload.get("pool") == pool and payload.get("case") == case:
            return row
    return None


def _budget(rows: list[dict], jobs: list[RobustJob]) -> None:
    replaced = set()
    for job in jobs:
        if _matching_row(rows, job.case, job.pool) is not None:
            replaced.add((job.case, job.pool))
    if len(rows) - len(replaced) + len(jobs) > LEDGER_CAP:
        raise EngineError(f"v5 账本超过 {LEDGER_CAP} 行")


def _file_sha256(path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _series_sha256(series: pd.Series) -> str:
    from src.v4.r5.design import series_sha256
    return series_sha256(series)


def _read_net(case: str, pool: str) -> pd.Series:
    from src.v4.r5.design import require_design_index
    path = OUT / case / pool / "net.csv"
    frame = pd.read_csv(path, parse_dates=["date"], index_col="date")
    series = frame["net"].astype(float).sort_index()
    require_design_index(series.index, what=f"{case}/{pool}")
    if not np.isfinite(series.to_numpy(dtype=float)).all():
        raise EngineError(f"{case}/{pool} 日收益有空值")
    return series


def _metrics(series: pd.Series, benchmark: pd.Series, states: pd.Series) -> dict:
    window = series.loc["2006-01-01":"2015-12-31"]
    if len(window) == 0:
        raise EngineError("2006-01-01 起没有日收益")
    ann = {key: _segment_excess(series, benchmark, start, end) for key, start, end in SEGMENTS}
    points = state_points(_excess(series, benchmark), states)
    return {
        "ann_excess_s1": ann["s1"],
        "ann_excess_s2": ann["s2"],
        "pp_bull": points["牛市"],
        "pp_correction": points["回调"],
        "pp_bear": points["熊市"],
        "pp_rebound": points["反弹"],
        "max_drawdown_2006": max_drawdown(window)["max_drawdown"],
        "series_sha256": _series_sha256(series),
    }


def _report_row(case: str, pool: str, kind: str, job_flags: dict, metrics: dict,
                reference: dict | None, file_sha: str, dropped: list[str]) -> dict:
    row = {
        "case": case,
        "pool": pool,
        "kind": kind,
        "final_arm": job_flags["final_arm"],
        "enable_c1": job_flags["enable_c1"],
        "enable_c2": job_flags["enable_c2"],
        "file_sha256": file_sha,
        "dropped": "|".join(dropped),
        "d_s1_pp": None,
        "d_s2_pp": None,
    }
    row.update(metrics)
    if reference is not None:
        row["d_s1_pp"] = 100.0 * (metrics["ann_excess_s1"] - reference["ann_excess_s1"])
        row["d_s2_pp"] = 100.0 * (metrics["ann_excess_s2"] - reference["ann_excess_s2"])
    return row


def _ranked(cache: dict, market) -> list[str]:
    from src.v3.eval.robustness import best_containers
    key = id(market)
    if key not in cache:
        cache[key] = list(best_containers(market.pnl, list(market.names), 3))
    return cache[key]


def _execute_job(job: RobustJob, markets, spec, mapping, ranked: dict) -> tuple[pd.Series, list[str]]:
    from src.v4.r5.design import require_design_index, without_names
    from src.v5.campaign import classes_for

    market = markets.get(job.pool, t4=False, allow_substitute=job.allow_substitute)
    dropped: list[str] = []
    used = market
    if job.drop_best:
        order = _ranked(ranked, market)
        if len(order) < job.drop_best:
            raise EngineError(f"{job.pool} 排不出 {job.drop_best} 只")
        dropped = order[:job.drop_best]
        used = without_names(market, dropped)
    result = run_arm(
        used, spec, classes_for(list(used.names), used.cash_id, mapping),
        enable_c2=job.enable_c2, enable_c1=job.enable_c1,
        structure=job.structure, switches=b0_switches(allow_substitute=job.allow_substitute),
        decision_delay=job.decision_delay, exit_drawdown=job.exit_drawdown,
        cost_multiplier=job.cost_multiplier,
        lookbacks=job.lookbacks,
    )
    require_design_index(result.net.index, what=f"{job.case}/{job.pool}")
    if not np.isfinite(result.net.to_numpy(dtype=float)).all():
        raise EngineError(f"{job.case}/{job.pool} 日收益有空值")
    return result.net, dropped


def write_series_manifest(root=OUT) -> None:
    """给目录里每条 net.csv 记文件字节和 v4 同款序列文本的 SHA256。"""
    from src.v4.r5.design import require_design_index
    rows = []
    for path in sorted(root.glob("*/*/net.csv")):
        frame = pd.read_csv(path, parse_dates=["date"], index_col="date")
        series = frame["net"].astype(float).sort_index()
        require_design_index(series.index, what=str(path))
        rows.append({
            "case": path.parent.parent.name,
            "pool": path.parent.name,
            "n": int(len(series)),
            "start": str(pd.Timestamp(series.index.min()).date()),
            "end": str(pd.Timestamp(series.index.max()).date()),
            "file_sha256": _file_sha256(path),
            "series_sha256": _series_sha256(series),
        })
    frame = pd.DataFrame(rows)
    frame.to_csv(root / "series-sha256.csv", index=False)


def run_robustness(*, ledger=LEDGER, gate_path=None) -> dict:
    """F 已由过关表确定时，跑 §7.1 并登记账本。定不了 F 就在跑之前停下。"""
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import Markets, benchmark_returns, month_states, require_frozen_db
    from src.v5.engine.classes import class_map

    path = OUT / "component-gate.csv" if gate_path is None else gate_path
    if not path.exists():
        raise EngineError(f"没有过关表：{path}")
    table = pd.read_csv(path)
    final = final_arm(table)
    kept_c1 = _passed_flag(_one(_grouped(table), "P1").get("pass"))
    flags = version_flags(final, c1_passed=kept_c1 if final == "P2" else None)
    jobs = robustness_jobs(flags, final=final)
    require_frozen_db()
    spec = load_spec()
    rows = _rows(ledger)
    before = _design_rows(rows)
    if len(before) != 6:
        raise EngineError(f"设计期应已有 6 行，实际 {len(before)}")
    _budget(rows, jobs)
    markets = Markets(spec)
    mapping = class_map()
    benchmark = benchmark_returns()
    states = month_states()
    ranked: dict = {}
    reference = {}
    report = []
    for pool in POOLS:
        series = _read_net(final, pool)
        metrics = _metrics(series, benchmark, states)
        reference[pool] = metrics
        report.append(_report_row(
            final, pool, "reference",
            {"final_arm": final, "enable_c1": flags["enable_c1"], "enable_c2": flags["enable_c2"]},
            metrics, None, _file_sha256(OUT / final / pool / "net.csv"), [],
        ))
    from src.v3.engine.ledger import canonical_params

    for index, job in enumerate(jobs, start=1):
        existing = _matching_row(_rows(ledger), job.case, job.pool)
        net_path = OUT / job.case / job.pool / "net.csv"
        dropped: list[str] = []
        reused = False
        if existing is not None and net_path.exists():
            payload = json.loads(existing["params"])
            if int(payload.get("drop_best") or 0) == job.drop_best and payload.get("final_arm") == final:
                series = _read_net(job.case, job.pool)
                dropped = [str(item) for item in payload.get("dropped") or []]
                expected = robustness_params(job, spec, dropped)
                reused = existing["params"] == canonical_params(expected)
        if not reused:
            series, dropped = _execute_job(job, markets, spec, mapping, ranked)
            _write_net(job.case, job.pool, series)
            record_version(robustness_params(job, spec, dropped), ledger)
            print(f"[{index}/{len(jobs)}] {job.case} {job.pool}", flush=True)
        else:
            print(f"[{index}/{len(jobs)}] {job.case} {job.pool} resume", flush=True)
        metrics = _metrics(series, benchmark, states)
        report.append(_report_row(
            job.case, job.pool, "robustness",
            {"final_arm": final, "enable_c1": job.enable_c1, "enable_c2": job.enable_c2},
            metrics, reference[job.pool], _file_sha256(net_path), dropped,
        ))
    after = _design_rows(_rows(ledger))
    if after != before:
        raise EngineError("稳健性改写了设计期账本行")
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(report, columns=list(REPORT_COLUMNS)).to_csv(
        OUT / "robustness.csv", index=False, float_format="%.12g",
    )
    write_series_manifest()
    return {
        "final_arm": final,
        "enable_c1": bool(flags["enable_c1"]),
        "enable_c2": bool(flags["enable_c2"]),
        "base_arm": flags["base_arm"],
        "n_jobs": len(jobs),
        "ledger_rows": len(_rows(ledger)),
        "ledger": str(ledger),
    }
