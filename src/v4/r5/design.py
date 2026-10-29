"""设计期配置、账本和过关表。

E2 新口径是 B0：E2 的规则不动，打开 v4 的成交限制、汇率和载体。
T1–T3 在 B0 上各加一个开关，T4 加上美股行业和港股分类。
过关只看 U-指数。最终版是 B0 加上过关的候选。稳健性沿用最终版，只改预注册点名的那一项。

不读 2016-01-01 及以后的组合收益，不写 LOCK。
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.data import db as DB
from src.data.db import git_head
from src.report.metrics import cagr, max_drawdown, yearly_returns
from src.v3.data.history import OFFICIAL, history_floor
from src.v3.data.universe import containers as load_containers
from src.v3.engine.arms import execute, group_decisions
from src.v3.engine.benchmark import (
    WEIGHTS,
    _closes,
    _cny_returns,
    _level_returns,
    _ohlc,
    cash_returns,
)
from src.v3.engine.book import DESIGN_END as ENGINE_END
from src.v3.engine.book import RunnerError
from src.v3.engine.exit import EXIT_DRAWDOWN, simulate_path
from src.v3.engine.ledger import COLUMNS, append_ledger, canonical_params
from src.v3.engine.limits import quotes_from_market
from src.v3.engine.market import _usd_level, load_market
from src.v3.engine.score import lookback_panel
from src.v3.engine.spec import Spec, load_spec
from src.v3.engine.switches import EngineSwitches
from src.v3.engine.universe import parse_date, research_code
from src.v3.eval.robustness import best_containers, delay_targets
from src.v4.engine.apply import apply_market, apply_tradable_execution
from src.v4.engine.pool import US_SECTORS, _closes_frame, load_mid
from src.v4.scorecard.core import ScorecardError, classify_months, refuse_portfolio_dates
from src.v4.scorecard.gate import GATE_COLUMNS, candidate_gate
from src.report.blend import monthly_rebalance
from src.report.fx import cny_from_usd

ROOT = Path(__file__).resolve().parents[3]
DESIGN_END = "2015-12-31"
# D22 曾登记 1adb6d43384be3336a3f58e993dd31ed3d75e705935aa2ff16c575a30fc00e27。
# D24-1 只插入第 2 档场外复权净值，没有改已有行。对不上就停。
DB_SHA256 = "79ae5a47e1a6eb0977a18f13efb21211d24b48e393ad567f615130d89c8f00cd"
LEDGER = ROOT / "results" / "v4" / "trial-ledger.csv"
OUT = ROOT / "results" / "v4" / "r5"
SEGMENT = "design"
RUNNER = "dev"
# 价格指数相对全收益出现大幅跳动时，当作拆股而不是分红。
SPLIT_GUARD = 0.15
PRICE_FOR_TR = {"^SP500TR": "SPX", "XNDX": "NDX"}
SINGLE = ("B0", "T1", "T2", "T3", "T4")
POOLS = ("index", "tradable")
LOOKBACKS = (
    (10, 40, 90, 180),
    (15, 50, 100, 200),
    (30, 80, 150, 300),
)
EXITS = (0.08, 0.12, 0.15)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_frozen_db() -> str:
    """库必须仍是 D22 登记的那一份。不匹配就停止，避免在另一份数据上出设计期结果。"""
    path = DB.MARKET_DB
    if not path.exists() or path.stat().st_size < 1000:
        raise RunnerError(f"行情库不可读：{path}")
    digest = file_sha256(path)
    if digest != DB_SHA256:
        raise RunnerError(f"行情库 SHA256 与登记不一致：{digest}")
    wal = path.with_name(path.name + "-wal")
    shm = path.with_name(path.name + "-shm")
    if wal.exists() or shm.exists():
        raise RunnerError("行情库旁有 -wal 或 -shm，先确认没有未合并的写入")
    return digest


def require_design_index(index, *, what: str) -> pd.DatetimeIndex:
    stamps = pd.DatetimeIndex(pd.to_datetime(index)).dropna().sort_values()
    if len(stamps) == 0:
        raise RunnerError(f"{what} 没有日期")
    try:
        refuse_portfolio_dates(stamps, what=what)
    except ScorecardError as exc:
        raise RunnerError(str(exc)) from exc
    if pd.Timestamp(stamps.max()) > pd.Timestamp(DESIGN_END):
        raise RunnerError(f"{what} 晚于 {DESIGN_END}")
    if pd.Timestamp(ENGINE_END) != pd.Timestamp(DESIGN_END):
        raise RunnerError("引擎设计期结束日与 v4-R5 不一致")
    return stamps


@dataclass(frozen=True)
class Job:
    """一条要写入 ledger 的设计期配置。`passed` 只在最终版和稳健性里有内容。"""

    case: str
    pool: str
    kind: str
    t1: bool = False
    t2: bool = False
    t3: bool = False
    t4: bool = False
    lookbacks: tuple[int, ...] | None = None
    exit_drawdown: float = EXIT_DRAWDOWN
    cost_multiplier: float = 1.0
    decision_delay: int = 0
    us_dividend_retained: float = 1.0
    allow_substitute: bool = True
    drop_best: int = 0
    passed: tuple[str, ...] = ()

    def switches(self) -> EngineSwitches:
        return EngineSwitches(
            fill_limits=True,
            fx_v4=True,
            carriers=True,
            allow_substitute=self.allow_substitute,
            t1_turn=self.t1,
            t2_state_weights=self.t2,
            t3_refill=self.t3,
            t4_pool=self.t4,
        )

    def params(self, dropped: list[str] | None = None) -> dict:
        lookbacks = list(self.lookbacks) if self.lookbacks is not None else None
        payload = {
            "rules": "v4",
            "case": self.case,
            "kind": self.kind,
            "pool": self.pool,
            "end": DESIGN_END,
            "history_mode": OFFICIAL,
            "engine_arm": "A",
            "fill_limits": True,
            "fx_v4": True,
            "carriers": True,
            "allow_substitute": self.allow_substitute,
            "t1_turn": self.t1,
            "t2_state_weights": self.t2,
            "t3_refill": self.t3,
            "t4_pool": self.t4,
            "lookbacks": lookbacks,
            "exit_drawdown": self.exit_drawdown,
            "cost_multiplier": self.cost_multiplier,
            "decision_delay": self.decision_delay,
            "us_dividend_retained": self.us_dividend_retained,
            "drop_best": self.drop_best,
            "dropped": list(dropped or []),
            "passed": list(self.passed),
        }
        if self.pool == "tradable":
            payload["fix"] = "D24-1"
        return payload


def single_jobs() -> list[Job]:
    """E2 新口径和 T1–T4，两个池各一行。"""
    jobs = []
    for case in SINGLE:
        flags = {"t1": case == "T1", "t2": case == "T2", "t3": case == "T3", "t4": case == "T4"}
        for pool in POOLS:
            jobs.append(Job(case=case, pool=pool, kind="single", **flags))
    return jobs


def final_jobs(passed: list[str]) -> list[Job]:
    names = tuple(name for name in SINGLE if name in set(passed) and name != "B0")
    flags = {"t1": "T1" in names, "t2": "T2" in names, "t3": "T3" in names, "t4": "T4" in names}
    return [
        Job(case="final", pool=pool, kind="final", passed=names, **flags)
        for pool in POOLS
    ]


def robustness_jobs(final: Job) -> list[Job]:
    """§7.2。除了被点名的那一项，其余与最终版相同。不含相近替身只跑 U-可交易。"""
    if final.case != "final" or final.pool != "index":
        raise RunnerError("稳健性要从 U-指数上的最终版抄开关")
    base = {
        "t1": final.t1, "t2": final.t2, "t3": final.t3, "t4": final.t4,
        "passed": final.passed, "kind": "robustness",
    }
    jobs: list[Job] = []
    for lengths in LOOKBACKS:
        label = "lookback-" + "-".join(str(item) for item in lengths)
        for pool in POOLS:
            jobs.append(Job(case=label, pool=pool, lookbacks=lengths, **base))
    for drawdown in EXITS:
        label = f"exit-{int(round(drawdown * 100))}"
        for pool in POOLS:
            jobs.append(Job(case=label, pool=pool, exit_drawdown=drawdown, **base))
    for pool in POOLS:
        jobs.append(Job(case="cost-double", pool=pool, cost_multiplier=2.0, **base))
        jobs.append(Job(case="delay-1d", pool=pool, decision_delay=1, **base))
        jobs.append(Job(case="us-div-90", pool=pool, us_dividend_retained=0.9, **base))
        for count in (1, 2, 3):
            jobs.append(Job(case=f"drop-best-{count}", pool=pool, drop_best=count, **base))
    jobs.append(Job(case="no-substitute", pool="tradable", allow_substitute=False, **base))
    return jobs


def budget_jobs(passed: list[str]) -> list[Job]:
    final = final_jobs(passed)
    return single_jobs() + final + robustness_jobs(final[0])


def peer_params(peer_id: str, pool: str) -> dict:
    payload = {
        "rules": "v4",
        "case": peer_id,
        "kind": "peer",
        "pool": pool,
        "end": DESIGN_END,
        "peer": peer_id,
        "month_end_rule": "sse-last-session-of-calendar-month",
        "calendar_closed": True,
        "exit_module": False,
        "premium_module": False,
        "t1_turn": False,
        "t2_state_weights": False,
        "t3_refill": False,
        "t4_pool": False,
        "cash": "v3-cash-sequence",
    }
    if pool == "tradable":
        payload["fix"] = "D24-1"
    return payload


def ledger_rows(path: Path = LEDGER) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _same_job(row: dict, *, arm: str, pool: str) -> bool:
    if row.get("arm") != arm or row.get("segment") != SEGMENT:
        return False
    try:
        payload = json.loads(row.get("params") or "{}")
    except json.JSONDecodeError:
        return False
    return payload.get("pool") == pool and payload.get("case") == arm


def upsert_ledger(params: dict, *, path: Path = LEDGER, runner: str = RUNNER) -> str:
    """同一 case、同一池、设计期只留一行。重跑改这一行，不另起一行。"""
    arm = str(params["case"])
    pool = str(params["pool"])
    encoded = canonical_params(params)
    rows = ledger_rows(path)
    kept = [row for row in rows if not _same_job(row, arm=arm, pool=pool)]
    replaced = len(kept) != len(rows)
    if not replaced:
        wrote = append_ledger(path, arm=arm, params=params, segment=SEGMENT, runner=runner)
        return "appended" if wrote else "unchanged"
    from datetime import datetime
    from zoneinfo import ZoneInfo
    new = {
        "run_at": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "git_sha": git_head() or "",
        "arm": arm,
        "params": encoded,
        "segment": SEGMENT,
        "runner": runner,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(kept)
        writer.writerow(new)
    return "replaced"


def series_sha256(series: pd.Series) -> str:
    lines = [f"{pd.Timestamp(day).date().isoformat()},{float(value):.12g}" for day, value in series.items()]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def run_dir(case: str, pool: str) -> Path:
    return OUT / "design" / case / pool


def write_run(case: str, pool: str, net: pd.Series, summary: dict) -> Path:
    require_design_index(net.index, what=f"{case}/{pool}")
    if not np.isfinite(net.to_numpy(dtype=float)).all():
        raise RunnerError(f"{case}/{pool} 的日收益有空值")
    folder = run_dir(case, pool)
    folder.mkdir(parents=True, exist_ok=True)
    frame = net.rename("net").to_frame()
    frame.index.name = "date"
    frame.to_csv(folder / "net.csv", float_format="%.12g")
    years = [{"year": year, "return": value} for year, value in yearly_returns(net).items()]
    pd.DataFrame(years).to_csv(folder / "yearly.csv", index=False)
    summary = dict(summary)
    summary["net_sha256"] = series_sha256(net)
    summary["n"] = int(len(net))
    summary["start"] = str(pd.Timestamp(net.index.min()).date())
    summary["end"] = str(pd.Timestamp(net.index.max()).date())
    (folder / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return folder


def read_net(case: str, pool: str) -> pd.Series:
    path = run_dir(case, pool) / "net.csv"
    frame = pd.read_csv(path, parse_dates=["date"], index_col="date")
    series = frame["net"].astype(float).sort_index()
    require_design_index(series.index, what=f"{case}/{pool}")
    return series


def _connect():
    uri = f"{DB.MARKET_DB.resolve().as_uri()}?mode=ro"
    import sqlite3
    return sqlite3.connect(uri, uri=True)


def prior_positive(series: pd.Series) -> pd.Series:
    """每个打印日的上一笔正收盘。与 `previous_and_close` 不传 prev 时一致，但只扫一遍。"""
    ordered = series.sort_index()
    ordered = ordered[~ordered.index.duplicated(keep="last")]
    last = float("nan")
    values = []
    raw = ordered.to_numpy(dtype=float)
    for value in raw:
        values.append(last)
        if np.isfinite(value) and float(value) > 0.0:
            last = float(value)
    return pd.Series(values, index=ordered.index, dtype=float)


def attach_prev_closes(market) -> None:
    """成交限制每天要上一笔收盘。预先算好，避免在每个交易日重扫整条序列。"""
    closes = getattr(market, "fill_close", None) or {}
    prevs = dict(getattr(market, "fill_prev", None) or {})
    for name, series in closes.items():
        current = prevs.get(name)
        if current is not None and len(current):
            continue
        if series is None or len(series) == 0:
            continue
        prevs[name] = prior_positive(series)
    market.fill_prev = prevs


def prepare_market(pool: str, *, t4: bool, allow_substitute: bool, spec: Spec):
    """装好 B0 的数据开关。T2 的净值在这里附上，权重仍由执行时的开关决定。

    两个池的排名信号都从 U-指数的研究序列出发。U-可交易再把计价收益换成载体自己的日收益，
    并且只有当天选得到载体才进排名。不含相近替身只影响载体，不改研究序列。
    """
    if pool not in POOLS:
        raise RunnerError(f"未知的池 {pool}")
    containers = load_containers()
    signal_switches = EngineSwitches(
        fill_limits=True,
        fx_v4=True,
        carriers=True,
        t4_pool=t4,
        allow_substitute=True,
        t2_state_weights=True,
    )
    market = load_market(
        DB.MARKET_DB, containers, "A", "index", DESIGN_END, spec,
        cost_multiplier=1.0, allow_after=False, history_mode=OFFICIAL,
    )
    market = apply_market(
        market, signal_switches, db=DB.MARKET_DB, containers=containers, spec=spec, pool="index")
    if pool == "tradable":
        carrier_switches = EngineSwitches(
            fill_limits=True,
            fx_v4=True,
            carriers=True,
            t4_pool=t4,
            allow_substitute=allow_substitute,
            t2_state_weights=True,
        )
        market = apply_tradable_execution(
            market, carrier_switches, db=DB.MARKET_DB, containers=containers, spec=spec)
    attach_prev_closes(market)
    require_design_index(market.dates, what="行情")
    return market


def dividend_contribution(total: pd.Series, price: pd.Series, rate: float) -> pd.Series:
    """全收益减价格指数。价格指数当天绝对收益超过拆股门槛时，这一天不扣。"""
    left = total.astype(float)
    right = price.astype(float).reindex(left.index)
    out = left.copy()
    ok = left.notna() & right.notna() & (right.abs() <= SPLIT_GUARD)
    gap = (left - right).clip(lower=0.0)
    out.loc[ok] = left.loc[ok] - float(rate) * gap.loc[ok]
    return out


def _releveled(level: pd.Series, new_ret: pd.Series) -> pd.Series:
    values = level.astype(float).to_numpy(dtype=float).copy()
    rets = new_ret.reindex(level.index).to_numpy(dtype=float)
    for pos in range(1, len(values)):
        if np.isfinite(values[pos - 1]) and np.isfinite(rets[pos]):
            values[pos] = values[pos - 1] * (1.0 + float(rets[pos]))
    return pd.Series(values, index=level.index, dtype=float)


def with_us_dividend(market, spec: Spec, rate: float):
    """美股宽基和美股行业的计价收益只保留 (1 − rate) 的分红贡献。信号仍用全额。"""
    if rate < 0.0 or rate > 1.0:
        raise RunnerError(f"分红预扣比例不对：{rate}")
    containers = {str(row.get("id") or ""): row for row in load_containers()}
    sectors = dict(US_SECTORS)
    pnl = market.pnl.copy()
    levels = market.levels.copy()
    con = _connect()
    try:
        usd = load_mid(con, "USDCNY", DESIGN_END, filled=True)
        for name, asset in (market.asset_classes or {}).items():
            if asset == "美股宽基":
                container = containers.get(name)
                if container is None:
                    raise RunnerError(f"没有容器 {name}")
                code = research_code(container) or ""
                price_code = PRICE_FOR_TR.get(code)
                if price_code is None:
                    raise RunnerError(f"{name} 没有价格指数对照：{code}")
                floor = parse_date(history_floor(container, OFFICIAL))
            elif asset == "美股行业":
                price_code = sectors.get(name)
                if price_code is None:
                    raise RunnerError(f"不认识的美股行业 {name}")
                floor = None
            else:
                continue
            block = _closes_frame(con, price_code, DESIGN_END, kind="raw")
            if block.empty:
                raise RunnerError(f"没有 {price_code} 的原始收盘")
            level, _fresh, _gaps = _usd_level(block, usd, market.dates, spec.stale_limit, floor)
            price = _level_returns(level).reindex(market.dates)
            updated = dividend_contribution(pnl[name], price, rate)
            pnl[name] = updated
            if name in levels.columns:
                levels[name] = _releveled(levels[name], updated)
    finally:
        con.close()
    cloned = copy.copy(market)
    cloned.pnl = pnl
    cloned.levels = levels
    return cloned


def without_names(market, drop: list[str]):
    banned = set(drop)
    keep = [name for name in market.names if name not in banned]
    columns = [*keep, market.cash_id]

    def frame(table: pd.DataFrame | None) -> pd.DataFrame | None:
        if table is None:
            return None
        kept = [name for name in columns if name in table.columns]
        return table.loc[:, kept].copy()

    def mapping(source):
        if not source:
            return source
        return {key: value for key, value in source.items() if key in keep or key == market.cash_id}

    cloned = copy.copy(market)
    cloned.signal = frame(market.signal)
    cloned.pnl = frame(market.pnl)
    cloned.levels = frame(market.levels)
    cloned.liquidity = frame(market.liquidity)
    cloned.names = keep
    cloned.fees = {name: market.fees[name] for name in columns if name in market.fees}
    cloned.sort_ids = {name: market.sort_ids[name] for name in keep if name in market.sort_ids}
    cloned.fill_close = mapping(market.fill_close)
    cloned.fill_board = mapping(market.fill_board)
    cloned.fill_prev = mapping(market.fill_prev)
    cloned.fill_board_by_day = mapping(market.fill_board_by_day)
    cloned.asset_classes = mapping(market.asset_classes)
    if market.premium_inputs:
        cloned.premium_inputs = {key: value for key, value in market.premium_inputs.items() if key in keep} or None
    if market.code_levels:
        cloned.code_levels = {key: value for key, value in market.code_levels.items() if key in keep} or None
    if market.code_returns:
        cloned.code_returns = {key: value for key, value in market.code_returns.items() if key in keep} or None
    cloned.premium_ids = tuple(name for name in (market.premium_ids or ()) if name in keep)
    return cloned


def _refill_frames(market, spec: Spec, switches: EngineSwitches) -> dict:
    prepared = {
        length: lookback_panel(market.signal, market.cash_id, length) for length in spec.lookbacks
    }
    level = getattr(market, "bm_nav", None) if switches.t2_state_weights else None
    frames = {}
    for count, freq in spec.candidates():
        frames[(count, freq)] = group_decisions(
            prepared, market.dates, freq, count, list(market.names), market.cash_id, market.sort_ids,
            market.liquidity, spec.lookbacks,
            switches=switches, market_level=level, weight_eps=spec.weight_eps, every_session=True,
        )
    return frames


def _average_net(paths: dict) -> pd.Series:
    series = [book.net.astype(float) for book in paths.values()]
    if not series:
        raise RunnerError("没有路径")
    index = series[0].index
    for item in series[1:]:
        if not item.index.equals(index):
            raise RunnerError("六路没有对齐到同一交易日历")
    out = sum(series) / float(len(series))
    out.name = "net"
    return out


def _execute(market, spec: Spec, switches: EngineSwitches, job: Job) -> pd.Series:
    if job.decision_delay not in {0, 1}:
        raise RunnerError("决策日只延后 0 天或 1 天")
    running = copy.copy(market)
    running.cost_multiplier = float(job.cost_multiplier)
    if job.decision_delay == 0:
        book = execute(
            running, spec, "A", allow_after=False,
            exit_drawdown=job.exit_drawdown, switches=switches)
        return book.net.astype(float)
    base = execute(
        running, spec, "A", allow_after=False,
        exit_drawdown=job.exit_drawdown, switches=switches)
    if not base.paths:
        raise RunnerError("延后成交需要六路账本")
    quotes = quotes_from_market(running) if switches.fill_limits else None
    refill = _refill_frames(running, spec, switches) if switches.t3_refill else {}
    delayed = {}
    for key, path in base.paths.items():
        targets = delay_targets(path.targets, running.dates)
        extra = {}
        if switches.fill_limits:
            extra["fill_limits"] = True
            extra["fill_quotes"] = quotes
        if switches.t3_refill:
            extra["refill_targets"] = refill.get(key)
        delayed[key] = simulate_path(
            running.pnl, running.levels, running.fees, running.cash_id,
            targets=targets,
            exit_drawdown=job.exit_drawdown,
            trade_eps=spec.trade_eps,
            cost_multiplier=running.cost_multiplier,
            allow_after=False,
            weight_eps=spec.weight_eps,
            **extra,
        )
    return _average_net(delayed)


def execute_job(job: Job, market, spec: Spec) -> tuple[pd.Series, list[str]]:
    """在已经装好的行情上跑一条配置。返回日净收益和被去掉的容器。"""
    switches = job.switches()
    used = market
    dropped: list[str] = []
    if job.us_dividend_retained != 1.0:
        rate = 1.0 - float(job.us_dividend_retained)
        used = with_us_dividend(used, spec, rate)
    if job.drop_best:
        ranked = best_containers(used.pnl, list(used.names), job.drop_best)
        dropped = list(ranked)
        used = without_names(used, dropped)
    chosen = spec if job.lookbacks is None else replace_lookbacks(spec, job.lookbacks)
    net = _execute(used, chosen, switches, job)
    require_design_index(net.index, what=job.case)
    return net, dropped


def replace_lookbacks(spec: Spec, lookbacks: tuple[int, ...]) -> Spec:
    from dataclasses import replace
    if len(lookbacks) != 4 or len(set(lookbacks)) != 4:
        raise RunnerError(f"回看期要四个不同的长度：{lookbacks}")
    if tuple(sorted(lookbacks)) != tuple(lookbacks):
        raise RunnerError(f"回看期按从短到长写：{lookbacks}")
    return replace(spec, lookbacks=tuple(int(item) for item in lookbacks))


def summarize(job: Job, net: pd.Series, dropped: list[str]) -> dict:
    window = net.loc["2006-01-01":]
    depth = max_drawdown(net)
    return {
        "case": job.case,
        "pool": job.pool,
        "kind": job.kind,
        "cagr": cagr(net),
        "cagr_from_2006": cagr(window) if len(window) else None,
        "max_drawdown": depth["max_drawdown"],
        "passed": list(job.passed),
        "dropped": dropped,
        "exit_drawdown": job.exit_drawdown,
        "cost_multiplier": job.cost_multiplier,
        "decision_delay": job.decision_delay,
        "us_dividend_retained": job.us_dividend_retained,
        "lookbacks": None if job.lookbacks is None else list(job.lookbacks),
        "t1_turn": job.t1,
        "t2_state_weights": job.t2,
        "t3_refill": job.t3,
        "t4_pool": job.t4,
        "allow_substitute": job.allow_substitute,
    }


class Markets:
    """同一套数据开关只装一次。T1–T3 不改行情，只改执行。"""

    def __init__(self, spec: Spec):
        self.spec = spec
        self._cache: dict[tuple, object] = {}

    def get(self, pool: str, *, t4: bool, allow_substitute: bool = True):
        key = (pool, bool(t4), bool(allow_substitute))
        if key not in self._cache:
            self._cache[key] = prepare_market(
                pool, t4=t4, allow_substitute=allow_substitute, spec=self.spec)
        return self._cache[key]


def complete_params(job: Job, spec: Spec, dropped: list[str] | None = None) -> dict:
    payload = job.params(dropped)
    if payload["lookbacks"] is None:
        payload["lookbacks"] = [int(item) for item in spec.lookbacks]
    return payload


def run_job(job: Job, markets: Markets, *, resume: bool = True) -> pd.Series:
    folder = run_dir(job.case, job.pool)
    if resume and (folder / "summary.json").exists() and (folder / "net.csv").exists():
        net = read_net(job.case, job.pool)
        if not any(_same_job(row, arm=job.case, pool=job.pool) for row in ledger_rows()):
            summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
            upsert_ledger(complete_params(job, markets.spec, summary.get("dropped") or []))
        return net
    market = markets.get(job.pool, t4=job.t4, allow_substitute=job.allow_substitute)
    net, dropped = execute_job(job, market, markets.spec)
    summary = summarize(job, net, dropped)
    if job.lookbacks is None:
        summary["lookbacks"] = [int(item) for item in markets.spec.lookbacks]
    write_run(job.case, job.pool, net, summary)
    upsert_ledger(complete_params(job, markets.spec, dropped))
    return net


def benchmark_returns() -> pd.Series:
    """与 T2 同一条 BM-主：补齐后的美元中间价，美股严格早于 D。返回日收益，不是净值。"""
    con = _connect()
    try:
        from src.v3.engine.benchmark import _calendar
        calendar = _calendar(con, DESIGN_END)
        fx = load_mid(con, "USDCNY", DESIGN_END, filled=True)
        h00300 = _level_returns(_closes(con, "H00300", calendar, DESIGN_END))
        xndx = _cny_returns(cny_from_usd(_ohlc(con, "XNDX", DESIGN_END), fx, calendar))
        spx = _cny_returns(cny_from_usd(_ohlc(con, "^SP500TR", DESIGN_END), fx, calendar))
    finally:
        con.close()
    parts = pd.concat([
        h00300.rename("H00300"), xndx.rename("XNDX"), spx.rename("SP500TR"),
    ], axis=1).dropna()
    series, _weights = monthly_rebalance(parts, WEIGHTS)
    series = series.sort_index().astype(float)
    require_design_index(series.index, what="BM-主")
    return series


def month_states() -> pd.Series:
    con = _connect()
    try:
        from src.v3.engine.benchmark import _calendar
        calendar = _calendar(con, DESIGN_END)
        level = _closes(con, "H00300", calendar, DESIGN_END)
    finally:
        con.close()
    states = classify_months(level)
    require_design_index(states.dropna().index, what="月份状态")
    return states


def write_gate(returns: pd.DataFrame, benchmark: pd.Series, states: pd.Series) -> pd.DataFrame:
    table = candidate_gate(returns, benchmark, states, pool="index")
    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT / "candidate-gate.csv", index=False)
    inputs = returns.copy()
    inputs["benchmark"] = benchmark.reindex(inputs.index)
    inputs.index.name = "date"
    inputs.to_csv(OUT / "gate-inputs.csv", float_format="%.12g")
    state_frame = states.dropna().rename("state").to_frame()
    state_frame.index.name = "month_end"
    state_frame.to_csv(OUT / "month-states.csv")
    return table


def passed_from_table(table: pd.DataFrame) -> list[str]:
    """U-指数过关表里 pass 为真的 T1–T4。B0 不参与。"""
    if list(table.columns) != list(GATE_COLUMNS):
        raise RunnerError(f"过关表列名不对：{list(table.columns)}")
    found = []
    for row in table.to_dict(orient="records"):
        if row["pool"] != "index":
            raise RunnerError("过关表只接受 U-指数")
        if row["arm"] == "B0":
            continue
        if row["arm"] not in {"T1", "T2", "T3", "T4"}:
            raise RunnerError(f"不认识的候选 {row['arm']}")
        if _as_bool(row["pass"]):
            found.append(str(row["arm"]))
    return found


def _as_bool(value) -> bool:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return False
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"", "none", "nan"}:
        return False
    if text == "true":
        return True
    if text == "false":
        return False
    raise RunnerError(f"无法读取过关标记 {value!r}")


def load_gate_table(path: Path | None = None) -> pd.DataFrame:
    frame = pd.read_csv(path or (OUT / "candidate-gate.csv"))
    return frame


def cash_on(calendar, spec: Spec) -> pd.Series:
    series = cash_returns(DB.MARKET_DB, pd.DatetimeIndex(calendar), DESIGN_END, spec.cash_annual)
    require_design_index(series.index, what="现金")
    return series.astype(float)
