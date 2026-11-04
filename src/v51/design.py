"""v5.1 设计期两池。只跑冻结规则的 U-指数和 U-可交易，窗口到 2015-12-31。

用法（仓库根；`data/market.sqlite` 必须是 LFS 实文件，SHA256 与 v4 R5 登记一致）：

    git lfs pull --include=data/market.sqlite
    .venv/bin/python -m src.v51 design

写出 `results/v5.1/design/`，并在 `results/v5.1/trial-ledger.csv` 留下两行
（臂 `v5.1`、段 `design`、两池各一行）。不写 LOCK，不打标签，不跑 R5 对照、
G 池或稳健性。单元测试不连行情库，也不跑这段。

读数和目标权重走 `target_weights`（研究序列，与 R3 相同）。U-可交易另把
v4 的载体掩码交给 `eligible`。成交走 `run_book`。BM-主和月份状态沿用
`src.v4.r5.design` 的 `benchmark_returns` / `month_states`，这里不另写。
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from src.data.db import git_head
from src.report.metrics import cagr, calmar, max_drawdown, monthly_returns, yearly_returns
from src.v3.engine.book import DESIGN_END
from src.v3.engine.ledger import COLUMNS, canonical_params
from src.v3.engine.spec import LEDGER as V3_LEDGER
from src.v4.scorecard.core import STATE_ORDER
from src.v4.scorecard.gate import SEGMENTS, V4_LEDGER, state_points
from src.v5.campaign import LEDGER as V5_LEDGER
from src.v5.engine.execute import b0_switches

from .params import V51Error, load_params

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "results" / "v5.1" / "trial-ledger.csv"
OUT = ROOT / "results" / "v5.1" / "design"
A1_NET = ROOT / "results" / "v4" / "r5" / "design" / "A1"
SEGMENT = "design"
ARM = "v5.1"
RUNNER = "dev"
WINDOW_START = "2006-01-01"
TAIPEI = ZoneInfo("Asia/Taipei")
WINDOWS = (("full", WINDOW_START, "2015-12-31"),) + tuple(SEGMENTS)
HURDLE_T = -2.0
_BANNED = {V3_LEDGER.resolve(), V4_LEDGER.resolve(), V5_LEDGER.resolve()}


def _end_text() -> str:
    return str(pd.Timestamp(DESIGN_END).date())


def windowed(series: pd.Series, start: str, end: str) -> pd.Series:
    """设计期里的一段日收益。晚于 2015-12-31 的日期直接拒绝。"""
    out = pd.Series(series, dtype=float).dropna().sort_index()
    out.index = pd.DatetimeIndex(pd.to_datetime(out.index)).normalize()
    if out.index.has_duplicates:
        raise V51Error("日收益索引重复")
    if len(out) and pd.Timestamp(out.index.max()) > pd.Timestamp(DESIGN_END):
        raise V51Error(f"日收益晚于 {_end_text()}")
    block = out.loc[start:end]
    if block.empty:
        raise V51Error(f"{start} → {end} 没有日收益")
    return block


def t_of(excess: pd.Series) -> float:
    """月度超额 t：均值 ÷（样本标准差 ÷ √月数）。不做 Newey-West。"""
    values = pd.Series(excess, dtype=float).dropna()
    n = int(len(values))
    if n < 2:
        return float("nan")
    scale = float(values.std(ddof=1))
    if scale == 0.0 or not math.isfinite(scale):
        return float("nan")
    return float(values.mean() / (scale / math.sqrt(n)))


def monthly_excess_t(strategy: pd.Series, benchmark: pd.Series) -> tuple[float, int]:
    left = monthly_returns(strategy)
    right = monthly_returns(benchmark)
    both = pd.concat([left.rename("strategy"), right.rename("benchmark")], axis=1).dropna()
    excess = both["strategy"] - both["benchmark"]
    return t_of(excess), int(len(excess))


def eligible_frame(pool: str, liquidity: pd.DataFrame | None, index: pd.DatetimeIndex) -> pd.DataFrame | None:
    """U-指数不套载体掩码（与 R3、画像一致）。U-可交易用 v4 §3.2 的可买掩码。"""
    if pool == "index":
        return None
    if pool != "tradable":
        raise V51Error(f"v5.1 设计期没有这个池：{pool}")
    if liquidity is None:
        raise V51Error("U-可交易没有可买掩码")
    frame = liquidity.reindex(index)
    return frame.fillna(False).astype(bool)


def design_params(pool: str, spec) -> dict:
    """写进账本的参数。数字全部来自冻结表和 v4 B0 成交开关，不在这里另选。"""
    if pool not in {"index", "tradable"}:
        raise V51Error(f"v5.1 设计期没有这个池：{pool}")
    frozen = load_params().params
    switches = b0_switches()
    return {
        "rules": "v5.1",
        "case": ARM,
        "kind": "design",
        "pool": pool,
        "start": WINDOW_START,
        "end": frozen.design_end,
        "schema": "v5.1",
        "engine_arm": "A",
        "paths": ["week"],
        "fill_limits": switches.fill_limits,
        "fx_v4": switches.fx_v4,
        "carriers": switches.carriers,
        "allow_substitute": switches.allow_substitute,
        "t1_turn": switches.t1_turn,
        "t2_state_weights": switches.t2_state_weights,
        "t3_refill": switches.t3_refill,
        "t4_pool": switches.t4_pool,
        "cross_border": switches.cross_border is not None,
        "cost_multiplier": 1.0,
        "decision_delay": 0,
        "hard_stop": frozen.hard_stop,
        "frontier": frozen.frontier,
        "noise_band": frozen.noise_band,
        "breadth_min": frozen.breadth_min,
        "top_n": frozen.top_n,
        "slow_gap": frozen.slow_gap,
        "long_min_days": frozen.long_min_days,
        "sigma_window": frozen.sigma_window,
        "quantile_min": frozen.quantile_min,
        "rulers": list(frozen.rulers),
        "classes": frozen.classes,
        "bond": frozen.bond,
        "gold": frozen.gold,
        "cash": frozen.cash,
        "layer1": list(frozen.layer1),
        "lookbacks": [int(item) for item in spec.lookbacks],
        "trade_eps": float(spec.trade_eps),
        "weight_eps": float(spec.weight_eps),
    }


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _same_pool(row: dict, pool: str) -> bool:
    if row.get("arm") != ARM or row.get("segment") != SEGMENT:
        return False
    try:
        payload = json.loads(row.get("params") or "{}")
    except json.JSONDecodeError:
        return False
    return payload.get("pool") == pool and payload.get("case") == ARM and payload.get("kind") == "design"


def _refuse_ledger(path: Path) -> None:
    resolved = Path(path).resolve()
    if resolved.name == "LOCK":
        raise V51Error("不写 LOCK")
    if resolved in _BANNED:
        raise V51Error(f"v5.1 不写 {path}")


def record_design(params: dict, path: Path, *, runner: str = RUNNER) -> str:
    """同一池的设计期只留一行。重跑替换这一行，不另起。"""
    _refuse_ledger(path)
    if params.get("case") != ARM or params.get("kind") != "design":
        raise V51Error("设计期账本只收 v5.1 这一条")
    pool = str(params["pool"])
    encoded = canonical_params(params)
    fresh = {
        "run_at": datetime.now(TAIPEI).isoformat(timespec="seconds"),
        "git_sha": git_head() or "",
        "arm": ARM,
        "params": encoded,
        "segment": SEGMENT,
        "runner": runner,
    }
    kept = [row for row in _rows(path) if not _same_pool(row, pool)]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(kept)
        writer.writerow(fresh)
    return encoded


def metric_block(pool: str, segment: str, start: str, end: str,
                 strategy: pd.Series, benchmark: pd.Series) -> dict:
    """A 臂扣费后的日净收益。年化、回撤、Calmar 各自用自己的日历；月度超额按月对齐。"""
    left = windowed(strategy, start, end)
    right = windowed(benchmark, start, end)
    depth_s = max_drawdown(left)
    depth_b = max_drawdown(right)
    excess_t, n_months = monthly_excess_t(left, right)
    return {
        "pool": pool,
        "segment": segment,
        "start": str(pd.Timestamp(left.index[0]).date()),
        "end": str(pd.Timestamp(left.index[-1]).date()),
        "n": int(len(left)),
        "n_benchmark": int(len(right)),
        "n_months": n_months,
        "cagr": cagr(left),
        "max_drawdown": depth_s["max_drawdown"],
        "max_drawdown_peak": str(depth_s["peak"].date()),
        "max_drawdown_trough": str(depth_s["trough"].date()),
        "calmar": calmar(left),
        "bm_cagr": cagr(right),
        "bm_max_drawdown": depth_b["max_drawdown"],
        "bm_calmar": calmar(right),
        "monthly_excess_t": excess_t,
    }


def _cell(metrics: list[dict], pool: str, segment: str) -> dict:
    found = [row for row in metrics if row["pool"] == pool and row["segment"] == segment]
    if len(found) != 1:
        raise V51Error(f"缺少 {pool} {segment} 的指标")
    return found[0]


def _finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _check(ok: bool) -> str:
    return "通过" if ok else "未通过"


def _line(item: str, criterion: str, pool: str, segment: str, metric: str,
          strategy, benchmark, hurdle, status: str, note: str) -> dict:
    return {
        "item": item,
        "criterion": criterion,
        "pool": pool,
        "segment": segment,
        "metric": metric,
        "strategy": strategy,
        "benchmark": benchmark,
        "hurdle": hurdle,
        "status": status,
        "note": note,
    }


def gate_draft(metrics: list[dict], states: dict, a1: dict | None) -> pd.DataFrame:
    """§6.3 草稿。能算的写数；R0/R1/C-等权/C-波动比标待 R5；G 池标待 R6。"""
    rows: list[dict] = []
    for pool in ("index", "tradable"):
        for segment, _start, _end in WINDOWS:
            block = _cell(metrics, pool, segment)
            for metric, bm_metric in (
                ("cagr", "bm_cagr"),
                ("max_drawdown", "bm_max_drawdown"),
                ("calmar", "bm_calmar"),
            ):
                rows.append(_line(
                    "报告", "分段", pool, segment, metric,
                    block[metric], block[bm_metric], "", "报告", "A 臂扣费后；对照列是 BM-主",
                ))
            rows.append(_line(
                "报告", "分段", pool, segment, "monthly_excess_t",
                block["monthly_excess_t"], "", str(HURDLE_T), "报告",
                "策略月收益减 BM-主月收益；门槛只在第 1 条的四格上使用",
            ))
    for pool in ("index", "tradable"):
        full = _cell(metrics, pool, "full")
        rows.append(_line(
            "0", "先赢随机", pool, "full", "calmar",
            full["calmar"], "", "R0 的 95 分位", "待 R5", "需要 R0，本轮不跑",
        ))
        rows.append(_line(
            "0", "先赢随机", pool, "full", "cagr",
            full["cagr"], "", "R0 的中位数", "待 R5", "需要 R0，本轮不跑",
        ))
    for pool in ("index", "tradable"):
        full = _cell(metrics, pool, "full")
        rows.append(_line(
            "1", "跑赢基准", pool, "full", "cagr",
            full["cagr"], full["bm_cagr"], "高于 BM-主",
            _check(_finite(full["cagr"]) and _finite(full["bm_cagr"]) and full["cagr"] > full["bm_cagr"]),
            "十年年化，各自日历",
        ))
    for pool in ("index", "tradable"):
        for segment in ("s1", "s2"):
            block = _cell(metrics, pool, segment)
            rows.append(_line(
                "1", "跑赢基准", pool, segment, "monthly_excess_t",
                block["monthly_excess_t"], "", str(HURDLE_T),
                _check(_finite(block["monthly_excess_t"]) and block["monthly_excess_t"] >= HURDLE_T),
                "四格只用该格内的月份",
            ))
    for pool in ("index", "tradable"):
        if not a1 or pool not in a1 or not _finite(a1[pool].get("monthly_excess_t")):
            rows.append(_line(
                "2", "复杂要有回报", pool, "full", "monthly_excess_t",
                "", "", str(HURDLE_T), "待引用", "A1 净收益不在 results/v4/r5/design/A1，本轮不重跑",
            ))
            continue
        value = a1[pool]["monthly_excess_t"]
        rows.append(_line(
            "2", "复杂要有回报", pool, "full", "monthly_excess_t",
            value, "", str(HURDLE_T),
            _check(value >= HURDLE_T),
            "引用 results/v4/r5/design/A1，不重跑；策略月收益减 A1 月收益",
        ))
    index_full = _cell(metrics, "index", "full")
    rows.append(_line(
        "3", "复杂度本身要有回报", "index", "full", "cagr",
        index_full["cagr"], "", "高于 C-等权与 C-波动比", "待 R5",
        "需要 C-等权和 C-波动比，本轮不跑",
    ))
    for pool in ("index", "tradable"):
        full = _cell(metrics, pool, "full")
        rows.append(_line(
            "4", "回撤不比基准深", pool, "full", "max_drawdown",
            full["max_drawdown"], full["bm_max_drawdown"], "不深于 BM-主",
            _check(
                _finite(full["max_drawdown"]) and _finite(full["bm_max_drawdown"])
                and full["max_drawdown"] >= full["bm_max_drawdown"]
            ),
            "回撤为负；策略值不低于基准即不更深",
        ))
    rows.append(_line(
        "5", "别的市场也成立", "G", "full", "calmar",
        "", "", "高于 G 的 R0 的 95 分位", "待 R6", "§7.2，本轮不跑",
    ))
    rows.append(_line(
        "5", "别的市场也成立", "G", "full", "cagr",
        "", "", "高于基准 G", "待 R6", "§7.2，本轮不跑",
    ))
    p_bull = states.get("牛市")
    rows.append(_line(
        "6", "顺应市场", "index", "full", "p_bull",
        p_bull, 0.0, "≥ 0",
        _check(_finite(p_bull) and float(p_bull) >= 0.0),
        "state_points 的牛市：100×日超额之和，不四舍五入",
    ))
    rebound_t = states.get("rebound_t")
    rows.append(_line(
        "6", "顺应市场", "index", "full", "rebound_t",
        rebound_t, "", str(HURDLE_T),
        _check(_finite(rebound_t) and float(rebound_t) >= HURDLE_T),
        f"反弹月份 {states.get('rebound_n', 0)} 个；月度超额 t",
    ))
    for name, metric in (("回调", "p_correction"), ("熊市", "p_bear"), ("反弹", "p_rebound")):
        rows.append(_line(
            "6", "顺应市场", "index", "full", metric,
            states.get(name), "", "", "只报告", "不参与第 6 条的过关",
        ))
    pending = [row["status"] for row in rows if row["item"] in {"0", "2", "3", "5"}]
    done = all(row["status"] == "通过" for row in rows if row["status"] in {"通过", "未通过"})
    if any(status.startswith("待") for status in pending) or not done:
        admission = "未完成"
        note = "对照未齐或已算条目未全过。这张表不是入围结论"
    else:
        admission = "通过"
        note = "§6.3 已列条目全部通过"
    rows.append(_line("入围", "全部满足才入围", "both", "full", "", "", "", "0–6", admission, note))
    return pd.DataFrame(rows)


def _read_net(path: Path) -> pd.Series:
    frame = pd.read_csv(path, parse_dates=["date"], index_col="date")
    series = frame["net"].astype(float).sort_index()
    series.index = pd.DatetimeIndex(series.index).normalize()
    if len(series) and pd.Timestamp(series.index.max()) > pd.Timestamp(DESIGN_END):
        raise V51Error(f"{path} 晚于 {_end_text()}")
    return series


def cited_a1(nets: dict[str, pd.Series]) -> dict[str, dict]:
    """v4 已经落盘的 A1。缺文件就不编数。"""
    out = {}
    for pool, strategy in nets.items():
        path = A1_NET / pool / "net.csv"
        if not path.is_file():
            continue
        peer = windowed(_read_net(path), WINDOW_START, _end_text())
        left = windowed(strategy, WINDOW_START, _end_text())
        value, n_months = monthly_excess_t(left, peer)
        out[pool] = {"monthly_excess_t": value, "n_months": n_months, "path": str(path.relative_to(ROOT))}
    return out


def market_states(strategy: pd.Series, benchmark: pd.Series, states: pd.Series) -> dict:
    """U-指数相对 BM-主。P 用 v4 的 state_points，反弹 t 用月收益。"""
    left = windowed(strategy, WINDOW_START, _end_text())
    right = windowed(benchmark, WINDOW_START, _end_text())
    both = pd.concat([left.rename("strategy"), right.rename("benchmark")], axis=1).dropna()
    excess = both["strategy"] - both["benchmark"]
    points = state_points(excess, states)
    labels = states.dropna().copy()
    labels.index = pd.DatetimeIndex(pd.to_datetime(labels.index)).to_period("M")
    labels = labels[~labels.index.duplicated(keep="last")]
    months_s = monthly_returns(both["strategy"])
    months_b = monthly_returns(both["benchmark"])
    paired = pd.concat([months_s.rename("strategy"), months_b.rename("benchmark")], axis=1).dropna()
    month_excess = paired["strategy"] - paired["benchmark"]
    rebound = month_excess[labels.reindex(month_excess.index) == "反弹"]
    report = {name: float(points[name]) for name in STATE_ORDER}
    report["rebound_t"] = t_of(rebound)
    report["rebound_n"] = int(len(rebound))
    return report


def _signal(market) -> pd.DataFrame:
    signal = market.signal.copy()
    signal.index = pd.DatetimeIndex(pd.to_datetime(signal.index)).normalize()
    dates = pd.DatetimeIndex(pd.to_datetime(market.dates)).normalize()
    if not signal.index.equals(dates):
        raise V51Error("信号日历和成交日历不一致")
    if market.cash_id not in signal.columns:
        raise V51Error("信号里没有现金列")
    if len(signal.index) and pd.Timestamp(signal.index.max()) > pd.Timestamp(DESIGN_END):
        raise V51Error(f"信号晚于 {_end_text()}")
    return signal


def _aligned(series: pd.Series, index: pd.DatetimeIndex, what: str) -> pd.Series:
    out = series.astype(float).copy()
    out.index = pd.DatetimeIndex(pd.to_datetime(out.index)).normalize()
    if not out.index.equals(index):
        raise V51Error(f"{what} 的日期和净值对不齐")
    return out


def _write_pool(pool: str, book, allocation, folder: Path) -> pd.Series:
    from src.v4.r5.design import require_design_index, series_sha256

    net = book.net.astype(float).sort_index()
    net.index = pd.DatetimeIndex(pd.to_datetime(net.index)).normalize()
    require_design_index(net.index, what=f"v5.1 {pool}")
    if not pd.Series(net.to_numpy(dtype=float)).map(math.isfinite).all():
        raise V51Error(f"{pool} 的日收益有空值")
    folder.mkdir(parents=True, exist_ok=True)
    daily = pd.DataFrame({
        "net": net,
        "gross": _aligned(book.gross, net.index, f"{pool} 毛收益"),
        "nav": (1.0 + net).cumprod(),
        "cost": _aligned(book.cost, net.index, f"{pool} 成本"),
        "buy": _aligned(book.buy, net.index, f"{pool} 买入"),
        "sell": _aligned(book.sell, net.index, f"{pool} 卖出"),
    })
    state = allocation.state.copy()
    state.index = pd.DatetimeIndex(pd.to_datetime(state.index)).normalize()
    if not state.index.equals(net.index):
        raise V51Error(f"{pool} 的目标状态日期和净值对不齐")
    daily = daily.join(state)
    daily.index.name = "date"
    daily.to_csv(folder / "daily.csv", float_format="%.12g")
    decisions = allocation.decisions.copy()
    decisions.index.name = "date"
    decisions.to_csv(folder / "decisions.csv", float_format="%.12g")
    exits = allocation.exits.copy()
    exits.to_csv(folder / "exits.csv", index=False)
    held = book.held.copy()
    held.index = pd.DatetimeIndex(pd.to_datetime(held.index)).normalize()
    if not held.index.equals(net.index):
        raise V51Error(f"{pool} 的持仓日期和净值对不齐")
    held.index.name = "date"
    held.to_csv(folder / "held.csv", float_format="%.12g")
    window = windowed(net, WINDOW_START, _end_text())
    years = [{"year": year, "return": value} for year, value in yearly_returns(window).items()]
    pd.DataFrame(years).to_csv(folder / "yearly.csv", index=False)
    (folder / "net-sha256.txt").write_text(series_sha256(net) + "\n", encoding="utf-8")
    return net


def run_design(*, ledger: Path = LEDGER, out: Path = OUT) -> dict:
    """两个池各跑一次。会算设计期组合收益。不写 LOCK。"""
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import benchmark_returns, month_states, require_frozen_db

    from .allocate import target_weights
    from .execute import open_market, run_book, universe_for

    _refuse_ledger(ledger)
    digest = require_frozen_db()
    spec = load_spec()
    nets: dict[str, pd.Series] = {}
    payloads: dict[str, dict] = {}
    for pool in ("index", "tradable"):
        print(f"v5.1 {pool} 读数与成交", flush=True)
        market = open_market(pool, spec)
        signal = _signal(market)
        universe = universe_for(market)
        allocation = target_weights(
            signal, universe, eligible=eligible_frame(pool, market.liquidity, signal.index),
        )
        missing = [name for name in allocation.decisions.columns if name not in market.pnl.columns]
        if missing:
            raise V51Error(f"{pool} 的决策有行情没有的列：{missing}")
        book = run_book(market, spec, allocation.decisions)
        nets[pool] = _write_pool(pool, book, allocation, out / pool)
        payloads[pool] = design_params(pool, spec)
        print(
            f"v5.1 {pool} {nets[pool].index[0].date()}→{nets[pool].index[-1].date()} n={len(nets[pool])}",
            flush=True,
        )
    benchmark = benchmark_returns()
    states = month_states()
    metrics = [
        metric_block(pool, segment, start, end, nets[pool], benchmark)
        for pool in ("index", "tradable")
        for segment, start, end in WINDOWS
    ]
    fit = market_states(nets["index"], benchmark, states)
    peers = cited_a1(nets)
    draft = gate_draft(metrics, fit, peers)
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(metrics).to_csv(out / "summary.csv", index=False, float_format="%.12g")
    draft.to_csv(out / "gate-draft.csv", index=False, float_format="%.12g")
    bench = benchmark.rename("benchmark").to_frame()
    bench.index.name = "date"
    bench.to_csv(out / "benchmark.csv", float_format="%.12g")
    labeled = states.dropna().rename("state").to_frame()
    labeled.index.name = "month_end"
    labeled.to_csv(out / "month-states.csv")
    encoded = {pool: canonical_params(payloads[pool]) for pool in payloads}
    (out / "params.json").write_text(
        json.dumps(payloads, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "rules": "v5.1",
        "window": [WINDOW_START, _end_text()],
        "git_sha": git_head() or "",
        "db_sha256": digest,
        "pools": ["index", "tradable"],
        "benchmark": "src.v4.r5.design.benchmark_returns",
        "month_states": "src.v4.r5.design.month_states",
        "a1": {pool: peers[pool]["path"] for pool in peers},
        "ledger_params": encoded,
        "excluded": ["R0", "R1", "C-等权", "C-波动比", "G", "robustness"],
        "lock": False,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for pool in ("index", "tradable"):
        record_design(payloads[pool], ledger)
    return {"metrics": metrics, "states": fit, "a1": peers, "db_sha256": digest}
