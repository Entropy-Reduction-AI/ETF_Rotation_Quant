"""§7.1 稳健性 S1–S17。只报告，不改规则，不改过关。

中国组合只到 2015-12-31。S1–S16 在 U-指数，S17 在 U-可交易且关掉相近替身。
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from src.v3.engine.book import simulate, to_execution
from src.v3.eval.robustness import delay_targets
from src.report.metrics import yearly_returns

from .design import (
    DESIGN_END,
    LEDGER,
    OUT as DESIGN_OUT,
    WINDOWS,
    _signal,
    design_params,
    eligible_frame,
    metric_block,
)
from .ledger import upsert
from .params import DESIGN_END_TEXT, Params, V51Error

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "v5.1" / "robustness"
RUNNER = "dev"
SEGMENT = "design"
CASES = (
    {"id": "S1", "pool": "index", "change": "成本加倍", "cost_multiplier": 2.0},
    {"id": "S2", "pool": "index", "change": "决策日延后 1 天", "decision_delay": 1},
    {"id": "S3", "pool": "index", "change": "去掉最好的 1 个容器", "drop_best": 1},
    {"id": "S4", "pool": "index", "change": "去掉最好的 2 个容器", "drop_best": 2},
    {"id": "S5", "pool": "index", "change": "去掉最好的 3 个容器", "drop_best": 3},
    {"id": "S6", "pool": "index", "change": "前沿门槛 0.4", "frontier": 0.4},
    {"id": "S7", "pool": "index", "change": "前沿门槛 0.6", "frontier": 0.6},
    {"id": "S8", "pool": "index", "change": "长尺子放缓比 10 个交易日之前", "slow_gap": 10},
    {"id": "S9", "pool": "index", "change": "长尺子放缓比 40 个交易日之前", "slow_gap": 40},
    {"id": "S10", "pool": "index", "change": "噪音带 0.5", "noise_band": 0.5},
    {"id": "S11", "pool": "index", "change": "噪音带 2", "noise_band": 2.0},
    {"id": "S12", "pool": "index", "change": "第一层改为 B", "selection": "all"},
    {"id": "S13", "pool": "index", "change": "只在周度决策日减仓", "daily_look": False},
    {"id": "S14", "pool": "index", "change": "硬闸门 8%", "hard_stop": 0.08},
    {"id": "S15", "pool": "index", "change": "硬闸门 12%", "hard_stop": 0.12},
    {"id": "S16", "pool": "index", "change": "硬闸门不设", "hard_stop": None},
    {"id": "S17", "pool": "tradable", "change": "不含相近替身", "allow_substitute": False},
)


def knobs(**overrides):
    """冻结参数的一份副本。只在这一次稳健性里改被点名的那一项。"""
    base = Params()
    names = (
        "rulers", "long_min_days", "sigma_window", "quantile_min", "slow_gap",
        "frontier", "noise_band", "breadth_min", "top_n", "hard_stop",
        "bond", "gold", "cash",
    )
    data = {name: getattr(base, name) for name in names}
    data.update(overrides)
    return SimpleNamespace(**data)


def rank_best(pnl: pd.DataFrame, names: list[str], start: str, end: str) -> list[str]:
    """设计期里有限日收益的累计。高的在前，累计相同则名字较小的在前。"""
    window = pnl.loc[start:end]
    if len(window.index) and pd.Timestamp(window.index.max()) > pd.Timestamp(DESIGN_END):
        raise V51Error("排名用的收益晚于 2015-12-31")
    scored = []
    for name in names:
        values = window[name].to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        if len(finite) == 0 or np.any(finite <= -1.0):
            total = -np.inf
        else:
            total = float(np.expm1(np.log1p(finite).sum()))
        scored.append((total, name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [name for _, name in scored]


def universe_without(universe, dropped: set[str]):
    """去掉容器。代表被去掉的市场退出第一层。国债被去掉就退回现金。"""
    from .universe import Market, Universe

    markets = []
    for market in universe.markets:
        if market.representative in dropped:
            continue
        members = tuple(name for name in market.members if name not in dropped)
        if market.representative not in members:
            continue
        markets.append(Market(market.name, market.representative, members))
    if not markets:
        raise V51Error("去掉容器后没有剩下的市场")
    bond = universe.cash if universe.bond in dropped else universe.bond
    return Universe(tuple(markets), bond=bond, gold=universe.gold, cash=universe.cash)


def _slim(book) -> pd.DataFrame:
    net = book.net.astype(float).sort_index()
    net.index = pd.DatetimeIndex(pd.to_datetime(net.index)).normalize()
    if len(net.index) and pd.Timestamp(net.index.max()) > pd.Timestamp(DESIGN_END):
        raise V51Error("稳健性净值晚于 2015-12-31")
    frame = pd.DataFrame({
        "net": net,
        "gross": book.gross.reindex(net.index).astype(float),
        "nav": (1.0 + net).cumprod(),
        "cost": book.cost.reindex(net.index).astype(float),
        "buy": book.buy.reindex(net.index).astype(float),
        "sell": book.sell.reindex(net.index).astype(float),
    })
    frame.index.name = "date"
    return frame


def _execute(market, decisions: pd.DataFrame, spec, *, cost_multiplier: float, delay: int):
    targets = to_execution(decisions, market.pnl.index)
    if delay:
        targets = delay_targets(targets, market.pnl.index)
    return simulate(
        market.pnl, targets, market.fees, market.cash_id,
        trade_eps=float(spec.trade_eps), cost_multiplier=float(cost_multiplier),
    )


def _case_params(pool: str, spec, case: dict, dropped: list[str]) -> dict:
    payload = design_params(pool, spec)
    payload["case"] = case["id"]
    payload["kind"] = "robustness"
    payload["change"] = case["change"]
    payload["pass_fail"] = "只报告"
    for key in ("cost_multiplier", "decision_delay", "frontier", "slow_gap", "noise_band", "hard_stop"):
        if key in case:
            payload[key] = case[key]
    if case.get("selection"):
        payload["selection"] = case["selection"]
    if "daily_look" in case:
        payload["daily_look"] = bool(case["daily_look"])
    if "allow_substitute" in case:
        payload["allow_substitute"] = bool(case["allow_substitute"])
    if case.get("drop_best"):
        payload["drop_best"] = int(case["drop_best"])
        payload["dropped"] = list(dropped)
    payload["end"] = DESIGN_END_TEXT
    return payload


def run_robustness(*, ledger: Path = LEDGER, out: Path = OUT) -> dict:
    """十七行都跑完并写账。不改 gate，不写 LOCK。"""
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import require_frozen_db

    from .allocate import allocate
    from .execute import open_market, universe_for
    from .readings import level_index, read_panel

    digest = require_frozen_db()
    spec = load_spec()
    benchmark = pd.read_csv(DESIGN_OUT / "benchmark.csv", parse_dates=["date"], index_col="date")["benchmark"]
    benchmark.index = pd.DatetimeIndex(benchmark.index).normalize()
    blocks = []
    payloads = []
    cache: dict[str, dict] = {}

    def prepare(pool: str, allow_substitute: bool = True) -> dict:
        key = (pool, bool(allow_substitute))
        if key in cache:
            return cache[key]
        print(f"稳健性装 {pool} substitute={allow_substitute}", flush=True)
        market = open_market(pool, spec, allow_substitute=allow_substitute)
        signal = _signal(market)
        if len(signal.index) and pd.Timestamp(signal.index.max()) > pd.Timestamp(DESIGN_END):
            raise V51Error("稳健性的中国行情晚于 2015-12-31")
        universe = universe_for(market)
        eligible = eligible_frame(pool, market.liquidity, signal.index)
        panel = read_panel(signal, universe.cash)
        packed = {
            "market": market,
            "signal": signal,
            "universe": universe,
            "eligible": eligible,
            "panel": panel,
            "prices": level_index(signal),
        }
        cache[key] = packed
        return packed

    index = prepare("index")
    print("对照冻结规则的成交", flush=True)
    base_alloc = allocate(
        index["panel"].H.index, index["panel"].H, index["panel"].F, index["panel"].E, index["universe"],
        prices=index["prices"], returns=index["signal"], eligible=index["eligible"],
    )
    base_book = _execute(index["market"], base_alloc.decisions, spec, cost_multiplier=1.0, delay=0)
    saved = pd.read_csv(DESIGN_OUT / "index" / "daily.csv", parse_dates=["date"], index_col="date")["net"]
    gap = float((base_book.net.reindex(saved.index) - saved).abs().max())
    if gap > 1e-8:
        raise V51Error(f"稳健性起跑和设计期净值不一致（最大差 {gap:.3g}）")

    for case in CASES:
        rules = knobs(**{key: case[key] for key in ("frontier", "noise_band", "slow_gap", "hard_stop") if key in case})
        packed = prepare(case["pool"], allow_substitute=case.get("allow_substitute", True))
        universe = packed["universe"]
        panel = packed["panel"] if "slow_gap" not in case else read_panel(
            packed["signal"], packed["universe"].cash, params=rules,
        )
        signal = packed["signal"]
        prices = packed["prices"]
        eligible = packed["eligible"]
        market = packed["market"]
        dropped: list[str] = []
        if case.get("drop_best"):
            ranked = rank_best(market.pnl, list(market.names), "2006-01-01", DESIGN_END_TEXT)
            dropped = ranked[:int(case["drop_best"])]
            universe = universe_without(universe, set(dropped))
            banned = set(dropped)
            keep = [name for name in panel.H.columns if name not in banned]
            from .readings import PanelReadings

            panel = PanelReadings(
                H=panel.H.loc[:, keep], F=panel.F.loc[:, keep], E=panel.E.loc[:, keep],
                warmup=panel.warmup.loc[:, keep],
                weight={name: frame for name, frame in panel.weight.items() if name not in banned},
            )
            signal = signal.drop(columns=[name for name in banned if name in signal.columns])
            prices = prices.drop(columns=[name for name in banned if name in prices.columns])
            print(f"{case['id']} 去掉 {dropped}", flush=True)
        allocation = allocate(
            panel.H.index, panel.H, panel.F, panel.E, universe,
            prices=prices, returns=signal, eligible=eligible, params=rules,
            selection=case.get("selection", "market"),
            daily_look=case.get("daily_look", True),
        )
        book = _execute(
            market, allocation.decisions, spec,
            cost_multiplier=float(case.get("cost_multiplier", 1.0)),
            delay=int(case.get("decision_delay", 0)),
        )
        daily = _slim(book)
        folder = out / case["id"]
        folder.mkdir(parents=True, exist_ok=True)
        daily.to_csv(folder / "daily.csv", float_format="%.12g")
        window = daily.loc["2006-01-01":, "net"]
        years = [{"year": year, "return": value} for year, value in yearly_returns(window).items()]
        pd.DataFrame(years).to_csv(folder / "yearly.csv", index=False)
        decisions = allocation.decisions.copy()
        decisions.index.name = "date"
        decisions.to_csv(folder / "decisions.csv", float_format="%.12g")
        allocation.exits.to_csv(folder / "exits.csv", index=False)
        if dropped:
            pd.DataFrame({"id": dropped}).to_csv(folder / "dropped.csv", index=False)
        for segment, start, end in WINDOWS:
            row = metric_block(case["pool"], segment, start, end, daily["net"], benchmark)
            row["case"] = case["id"]
            row["change"] = case["change"]
            row["status"] = "只报告"
            blocks.append(row)
        payloads.append(_case_params(case["pool"], spec, case, dropped))
        full = next(row for row in blocks if row["case"] == case["id"] and row["segment"] == "full")
        print(f"{case['id']} {case['change']} 年化 {full['cagr']:.4f} Calmar {full['calmar']:.4f}", flush=True)

    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(blocks).to_csv(out / "summary.csv", index=False, float_format="%.12g")
    manifest = {
        "rules": "v5.1",
        "section": "7.1",
        "window": ["2006-01-01", DESIGN_END_TEXT],
        "report_only": True,
        "changes_pass_fail": False,
        "cases": [{key: value for key, value in case.items()} for case in CASES],
        "s12": "不先锁定一个市场。够格市场里 H>0 且 F<前沿的 ETF 按 H 一起取前 3，风险仓位是这些市场 r 的平均，平分。每天只减不加。一只都不够格时，持有资格市场里 H 最高的那个市场的代表。",
        "s13": "减仓、前沿、硬闸门和换防守只在周度决策日做。",
        "s3_s5": "最好 = 2006-01-01→2015-12-31 有限日收益的累计，平局按名字升序。现金不参加。代表被去掉的市场退出第一层。",
        "db_sha256": digest,
        "lock": False,
        "gate": "不改",
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    (out / "params.json").write_text(
        json.dumps(payloads, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    for payload in payloads:
        arm = payload["case"]
        upsert(
            ledger, payload, arm=arm, segment=SEGMENT, runner=RUNNER,
            same=lambda row, old, arm=arm: (
                row.get("arm") == arm and row.get("segment") == SEGMENT and old.get("kind") == "robustness"
            ),
        )
    return {"cases": [case["id"] for case in CASES], "db_sha256": digest}
