"""§6.1 设计期顺序。S0，然后 P1，再按 C1 是否过关跑 P2。

P2 的上一版写进 ledger 的 `params`：C1 过关则 `base_arm` 为 P1，否则为 S0。
本模块的 `main` 会跑设计期。复核签收之前不要调用它。不写 LOCK，不打标签。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from src.data.db import git_head
from src.v3.engine.book import DESIGN_END
from src.v3.engine.ledger import COLUMNS, canonical_params
from src.v3.engine.spec import LEDGER as V3_LEDGER
from src.v4.scorecard.gate import V4_LEDGER
from src.v5.engine.allocate import STRUCTURE_S0, EngineError
from src.v5.engine.classes import CASH_CLASS, class_map
from src.v5.engine.execute import b0_switches, run_arm
from src.v5.engine.paths import C2_DRAWDOWN
from src.v5.scorecard.gate import COMPONENT_TARGET, ComponentStep, component_gate

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "results" / "v5" / "trial-ledger.csv"
OUT = ROOT / "results" / "v5" / "design"
SEGMENT = "design"
RUNNER = "dev"
DESIGN_ARMS = ("S0", "P1", "P2")
POOLS = ("index", "tradable")
LEDGER_CAP = 45


def _end_text() -> str:
    return str(pd.Timestamp(DESIGN_END).date())


def _banned(path: Path) -> None:
    resolved = Path(path).resolve()
    if resolved.name == "LOCK":
        raise EngineError("不写 LOCK")
    banned = {V3_LEDGER.resolve(), V4_LEDGER.resolve()}
    if resolved in banned:
        raise EngineError(f"v5 不写 {path}")


def version_flags(arm: str, *, c1_passed: bool | None) -> dict:
    """§6.1。P2 = 上一版 + C2。上一版是 P1 时，P2 带上 C1；否则 P2 只有 C2。"""
    if arm == "S0":
        return {"base_arm": "", "enable_c1": False, "enable_c2": False}
    if arm == "P1":
        return {"base_arm": "S0", "enable_c1": True, "enable_c2": False}
    if arm == "P2":
        if c1_passed is None:
            raise EngineError("P2 要先有 C1 的过关结果")
        base = "P1" if c1_passed else "S0"
        return {"base_arm": base, "enable_c1": base == "P1", "enable_c2": True}
    raise EngineError(f"未知版本 {arm}")


def _passed_flag(value) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise EngineError("P1 的 pass 是空的，不能选上一版")
    if isinstance(value, str):
        text = value.strip().lower()
        if text == "true":
            return True
        if text == "false":
            return False
        raise EngineError(f"P1 的 pass 无法判断：{value}")
    if isinstance(value, bool):
        return value
    raise EngineError(f"P1 的 pass 无法判断：{value}")


def c1_passed(table: pd.DataFrame) -> bool:
    """过关表里 P1 那一行的 `pass`。空值不算没过关。"""
    if "arm" not in table.columns or "pass" not in table.columns:
        raise EngineError("过关表缺 arm 或 pass")
    rows = [row for row in table.to_dict(orient="records") if row.get("arm") == "P1"]
    if len(rows) != 1:
        raise EngineError(f"P1 应有一行，实际 {len(rows)}")
    return _passed_flag(rows[0].get("pass"))


def version_params(arm: str, pool: str, *, c1_passed: bool | None, spec,
                   structure: str = STRUCTURE_S0, cost_multiplier: float = 1.0,
                   decision_delay: int = 0, exit_drawdown: float | None = None,
                   allow_substitute: bool = True, lookbacks: tuple[int, ...] | None = None,
                   kind: str = "design") -> dict:
    """写进 ledger 的 `params`。P2 的 `base_arm` 来自 §6.1，不由调用方另选。"""
    if pool not in POOLS:
        raise EngineError(f"未知的池 {pool}")
    if arm not in DESIGN_ARMS and kind == "design":
        raise EngineError(f"未知版本 {arm}")
    flags = version_flags(arm, c1_passed=c1_passed)
    if flags["enable_c2"]:
        drawdown = C2_DRAWDOWN if exit_drawdown is None else float(exit_drawdown)
    else:
        if exit_drawdown is not None:
            raise EngineError("C2 关着时不能另设离场阈值")
        drawdown = None
    switches = b0_switches(allow_substitute=allow_substitute)
    lengths = [int(item) for item in (spec.lookbacks if lookbacks is None else lookbacks)]
    return {
        "rules": "v5",
        "case": arm,
        "kind": kind,
        "pool": pool,
        "end": _end_text(),
        "base_arm": flags["base_arm"],
        "enable_c1": flags["enable_c1"],
        "enable_c2": flags["enable_c2"],
        "structure": structure,
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
        "cost_multiplier": float(cost_multiplier),
        "decision_delay": int(decision_delay),
        "trade_eps": float(spec.trade_eps),
        "weight_eps": float(spec.weight_eps),
        "paths": ["week", "month"],
        "cross_border": switches.cross_border is not None,
    }


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _same(row: dict, arm: str, pool: str) -> bool:
    if row.get("arm") != arm or row.get("segment") != SEGMENT:
        return False
    try:
        payload = json.loads(row.get("params") or "{}")
    except json.JSONDecodeError:
        return False
    return payload.get("pool") == pool and payload.get("case") == arm


def record_version(params: dict, path: Path, *, runner: str = RUNNER) -> str:
    """同一版本、同一池、设计期只留一行。重跑改这一行。"""
    _banned(path)
    arm = str(params["case"])
    pool = str(params["pool"])
    encoded = canonical_params(params)
    from datetime import datetime
    from zoneinfo import ZoneInfo

    fresh = {
        "run_at": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "git_sha": git_head() or "",
        "arm": arm,
        "params": encoded,
        "segment": SEGMENT,
        "runner": runner,
    }
    kept = [row for row in _rows(path) if not _same(row, arm, pool)]
    if len(kept) + 1 > LEDGER_CAP:
        raise EngineError(f"v5 账本超过 {LEDGER_CAP} 行")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(kept)
        writer.writerow(fresh)
    return encoded


def classes_for(names: list[str], cash_id: str, mapping: dict[str, str] | None = None) -> dict[str, str]:
    """大类表里没有的容器直接拒绝，不临时归类。"""
    source = class_map() if mapping is None else mapping
    out = {}
    for name in names:
        if name == cash_id:
            continue
        if name not in source:
            raise EngineError(f"大类表没有 {name}")
        out[name] = source[name]
    out[cash_id] = CASH_CLASS
    return out


def _write_net(arm: str, pool: str, net: pd.Series) -> None:
    folder = OUT / arm / pool
    folder.mkdir(parents=True, exist_ok=True)
    frame = net.rename("net").to_frame()
    frame.index.name = "date"
    frame.to_csv(folder / "net.csv", float_format="%.12g")


def run_design(*, ledger: Path = LEDGER) -> dict:
    """S0 → P1 → 读 C1 过关 → P2。会算设计期组合收益。复核前不要调用。"""
    _banned(ledger)
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import Markets, benchmark_returns, month_states, require_frozen_db

    require_frozen_db()
    spec = load_spec()
    markets = Markets(spec)
    mapping = class_map()
    stored: dict[tuple[str, str], pd.Series] = {}
    for arm in ("S0", "P1"):
        for pool in POOLS:
            params = version_params(arm, pool, c1_passed=None, spec=spec)
            market = markets.get(pool, t4=False, allow_substitute=True)
            result = run_arm(
                market, spec, classes_for(list(market.names), market.cash_id, mapping),
                enable_c2=params["enable_c2"], enable_c1=params["enable_c1"],
                structure=params["structure"], decision_delay=params["decision_delay"],
                exit_drawdown=params["exit_drawdown"], cost_multiplier=params["cost_multiplier"],
                lookbacks=tuple(params["lookbacks"]),
            )
            _write_net(arm, pool, result.net)
            record_version(params, ledger)
            stored[(arm, pool)] = result.net
    index = pd.DataFrame({arm: stored[(arm, "index")] for arm in ("S0", "P1")})
    tradable = pd.DataFrame({arm: stored[(arm, "tradable")] for arm in ("S0", "P1")})
    gate = component_gate(
        index, benchmark_returns(), month_states(),
        steps=(ComponentStep("P1", "S0", COMPONENT_TARGET["C1"]),),
        tradable_returns=tradable, report_arm="S0",
    )
    passed = c1_passed(gate)
    for pool in POOLS:
        params = version_params("P2", pool, c1_passed=passed, spec=spec)
        market = markets.get(pool, t4=False, allow_substitute=True)
        result = run_arm(
            market, spec, classes_for(list(market.names), market.cash_id, mapping),
            enable_c2=params["enable_c2"], enable_c1=params["enable_c1"],
            structure=params["structure"], decision_delay=params["decision_delay"],
            exit_drawdown=params["exit_drawdown"], cost_multiplier=params["cost_multiplier"],
            lookbacks=tuple(params["lookbacks"]),
        )
        stored[("P2", pool)] = result.net
        _write_net("P2", pool, result.net)
        record_version(params, ledger)
    index = pd.DataFrame({arm: stored[(arm, "index")] for arm in DESIGN_ARMS})
    tradable = pd.DataFrame({arm: stored[(arm, "tradable")] for arm in DESIGN_ARMS})
    p2_base = version_flags("P2", c1_passed=passed)["base_arm"]
    full = component_gate(
        index, benchmark_returns(), month_states(),
        steps=(
            ComponentStep("P1", "S0", COMPONENT_TARGET["C1"]),
            ComponentStep("P2", p2_base, COMPONENT_TARGET["C2"]),
        ),
        tradable_returns=tradable, report_arm="S0",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    full.to_csv(OUT / "component-gate.csv", index=False)
    return {"c1_passed": passed, "base_arm": p2_base, "ledger": str(ledger)}
