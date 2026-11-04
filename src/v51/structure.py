"""R1：同结构随机。仓位档位和调仓日照抄 v5.1，只重抽市场和最多 3 只。

两个池各 2000 次。随机数和 R0 同一条约定：种子 20261101，每个池各自起一条流，
一次模拟先走完所有调仓日再开始下一次。空的资格集合不抽数。

周度调仓日才重抽。周度之间的调仓只把已经抽中的名字缩放到当天的档位，防守也照抄。
卖出名单是信号路径自己的，随机账上不沿用。资格仍是：市场 r>0 且当天买得到；
名字 H>0 且 F 低于前沿，买得到。一只都不够格时持该市场代表，和 §3.2 的退路一样。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.v3.engine.book import simulate, to_execution
from src.v3.engine.sessions import decision_dates, next_session

from .allocate import _cell, _flag_on, _rank, breadth, leg_score
from .controls import _distribution, _quantile
from .design import (
    DESIGN_END,
    LEDGER,
    OUT as DESIGN_OUT,
    WINDOW_START,
    _signal,
    design_params,
    eligible_frame,
)
from .hold import N_SIMS, SEED
from .ledger import upsert
from .params import V51Error

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "v5.1" / "controls" / "r1"
RUNNER = "dev"
SEGMENT = "design"
TOP_N = 3
K_NAMES = 6


@dataclass(frozen=True)
class Slot:
    date: pd.Timestamp
    weekly: bool
    risk: float
    defense: str
    market: str
    picks: tuple[str, ...]
    markets: tuple[str, ...]
    pools: tuple[tuple[str, ...], ...]
    fallback: tuple[str | None, ...]


def _buyable(eligible: pd.DataFrame | None, day, name: str) -> bool:
    if eligible is None:
        return True
    return _flag_on(eligible, day, name)


def _qualified(market, day, level, frontier_share, eligible, frontier: float) -> list[str]:
    found = []
    for name in market.members:
        if not _buyable(eligible, day, name):
            continue
        height = _cell(level, day, name)
        share = _cell(frontier_share, day, name)
        if pd.isna(height) or pd.isna(share):
            continue
        if height > 0.0 and share < frontier:
            found.append(name)
    return _rank(found, day, level)


def _fallback(market, day, level, frontier_share, eligible) -> str | None:
    """不够格时持代表。代表买不到，就持该市场 H 最高且买得到的成员。"""
    rep = market.representative
    if _buyable(eligible, day, rep):
        return rep
    pool = [name for name in market.members if _buyable(eligible, day, name)]
    ranked = _rank(pool, day, level)
    return ranked[0] if ranked else None


def _text(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    text = str(value).strip()
    return "" if text == "nan" else text


def _names(value) -> tuple[str, ...]:
    text = _text(value)
    if not text:
        return ()
    return tuple(part for part in text.split("|") if part)


def build_slots(allocation, panel, universe, eligible, *, frontier: float,
                weekly: pd.DatetimeIndex) -> list[Slot]:
    """每个 v5.1 调仓日一行。周度日附上当天的资格集合。"""
    week_set = {pd.Timestamp(day).normalize() for day in weekly}
    bands = {
        market.representative: breadth(
            panel.F, market.members, eligible=eligible, minimum=3, frontier=frontier,
        )
        for market in universe.markets
    }
    state = allocation.state
    slots: list[Slot] = []
    for day in allocation.decisions.index:
        stamp = pd.Timestamp(day).normalize()
        risk = float(state.at[stamp, "risk"])
        defense = _text(state.at[stamp, "defense"]) or universe.cash
        market_id = _text(state.at[stamp, "market"])
        picks = _names(state.at[stamp, "picks"])
        weekly_day = stamp in week_set
        markets: list[str] = []
        pools: list[tuple[str, ...]] = []
        fallback: list[str | None] = []
        if weekly_day and risk > 0.0:
            for market in universe.markets:
                band = bands[market.representative]
                width = float(band.at[stamp]) if stamp in band.index else float("nan")
                score = leg_score(
                    market.representative, stamp, panel.H, panel.F, panel.E, width, frontier,
                )
                if not score or not any(_buyable(eligible, stamp, name) for name in market.members):
                    continue
                markets.append(market.representative)
                pool = tuple(sorted(_qualified(market, stamp, panel.H, panel.F, eligible, frontier)))
                pools.append(pool)
                fallback.append(_fallback(market, stamp, panel.H, panel.F, eligible))
            if market_id and market_id not in markets:
                raise V51Error(f"{stamp.date()} 的持有市场 {market_id} 不在 R1 资格里")
            if not markets:
                raise V51Error(f"{stamp.date()} 有风险仓位，但没有合格市场")
            allowed = set(pools[markets.index(market_id)]) if market_id in markets else set()
            spare = fallback[markets.index(market_id)] if market_id in markets else None
            for name in picks:
                if name in allowed or name == spare:
                    continue
                raise V51Error(f"{stamp.date()} 的 {name} 不在 {market_id} 的 R1 资格里")
        slots.append(Slot(
            date=stamp, weekly=weekly_day, risk=risk, defense=defense, market=market_id,
            picks=picks, markets=tuple(sorted(markets)),
            pools=tuple(pools[markets.index(name)] for name in sorted(markets)) if markets else (),
            fallback=tuple(fallback[markets.index(name)] for name in sorted(markets)) if markets else (),
        ))
    return slots


def _weights(names: list[str], risk: float, defense: str) -> dict[str, float]:
    out: dict[str, float] = {}
    if names and risk > 0.0:
        share = float(risk) / len(names)
        for name in names:
            out[name] = out.get(name, 0.0) + share
    rest = 1.0 - sum(out.values())
    if abs(rest) <= 1e-12:
        rest = 0.0
    if abs(rest) > 0.0:
        out[defense] = out.get(defense, 0.0) + rest
    elif defense not in out:
        out[defense] = 0.0
    return out


def draw_paths(slots: list[Slot], *, n: int = N_SIMS, seed: int = SEED,
               top_n: int = TOP_N) -> list[list[dict]]:
    """返回 n 条路径。每步是调仓日上的目标权重。"""
    rng = np.random.default_rng(seed)
    paths: list[list[dict]] = []
    for _ in range(n):
        last: list[str] = []
        last_market = ""
        path = []
        for slot in slots:
            if slot.risk <= 0.0:
                last = []
                last_market = ""
                names: list[str] = []
                market = ""
            else:
                redraw = slot.weekly or not last
                if redraw:
                    if not slot.markets:
                        if slot.risk > 0.0:
                            raise V51Error(f"{slot.date.date()} 要持有风险仓位，但没有可抽的市场")
                        last = []
                        last_market = ""
                    else:
                        market_id = str(rng.choice(np.asarray(slot.markets, dtype=object), size=1, replace=False)[0])
                        place = slot.markets.index(market_id)
                        pool = slot.pools[place]
                        if pool:
                            count = min(int(top_n), len(pool))
                            picked = rng.choice(np.asarray(pool, dtype=object), size=count, replace=False)
                            last = sorted(str(item) for item in np.atleast_1d(picked))
                        else:
                            spare = slot.fallback[place]
                            last = [spare] if spare else []
                        last_market = market_id
                names = list(last)
                market = last_market
            weights = _weights(names, slot.risk if names else 0.0, slot.defense)
            if abs(sum(weights.values()) - 1.0) > 1e-8:
                raise V51Error("R1 目标权重加总不是 1")
            path.append({
                "date": slot.date,
                "weekly": slot.weekly,
                "risk": slot.risk,
                "defense": slot.defense,
                "market": market,
                "names": list(names),
                "weights": weights,
            })
        paths.append(path)
    return paths


def portfolio_nets(returns: pd.DataFrame, cash_id: str, paths: list[list[dict]],
                   fees: dict[str, float], *, trade_eps: float = 1e-12,
                   cost_multiplier: float = 1.0) -> np.ndarray:
    """和 `simulate` 同一套漂移与扣费。调仓日相同，所以成交日也相同。"""
    frame = returns.copy()
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index)).normalize()
    columns = list(frame.columns)
    if cash_id not in columns:
        raise V51Error("收益里没有现金列")
    codes = {name: i for i, name in enumerate(columns)}
    values = frame.to_numpy(dtype=float)
    values = np.where(np.isfinite(values), values, 0.0)
    missing = [name for name in fees if name not in codes]
    if missing:
        raise V51Error(f"费用表有收益里没有的列：{missing[:5]}")
    fee = np.array([float(fees[name]) for name in columns], dtype=float)
    n_sims = len(paths)
    if n_sims == 0:
        raise V51Error("没有 R1 路径")
    order: list[pd.Timestamp] = []
    seen: set[pd.Timestamp] = set()
    latest: list[dict[pd.Timestamp, dict]] = []
    for path in paths:
        chosen: dict[pd.Timestamp, dict] = {}
        for slot in path:
            nxt = next_session(frame.index, pd.Timestamp(slot["date"]))
            if nxt is None:
                continue
            stamp = pd.Timestamp(nxt).normalize()
            chosen[stamp] = slot
            if stamp not in seen:
                seen.add(stamp)
                order.append(stamp)
        latest.append(chosen)
    cols = np.full((len(order), n_sims, K_NAMES), -1, dtype=np.int16)
    wts = np.zeros((len(order), n_sims, K_NAMES), dtype=float)
    place = {day: i for i, day in enumerate(order)}
    for sim, chosen in enumerate(latest):
        for day, slot in chosen.items():
            e = place[day]
            used = 0
            for name, weight in slot["weights"].items():
                if name not in codes:
                    raise V51Error(f"R1 抽到了收益里没有的容器：{name}")
                if used >= K_NAMES:
                    raise V51Error("R1 一天的持仓只数超出了预留")
                cols[e, sim, used] = np.int16(codes[name])
                wts[e, sim, used] = float(weight)
                used += 1
    hold = np.zeros((n_sims, len(columns)), dtype=float)
    hold[:, codes[cash_id]] = 1.0
    net = np.zeros((n_sims, len(frame)), dtype=float)
    exec_at = {int(frame.index.get_loc(day)): e for e, day in enumerate(order)}
    multiplier = float(cost_multiplier)
    eps = float(trade_eps)
    for t in range(len(frame)):
        rets = values[t]
        gross = hold @ rets
        scale = 1.0 + gross
        grown = hold * (1.0 + rets)
        drifted = np.divide(grown, scale[:, None], out=hold.copy(), where=(scale[:, None] != 0.0))
        cost = np.zeros(n_sims, dtype=float)
        if t in exec_at:
            e = exec_at[t]
            target = np.zeros((n_sims, len(columns)), dtype=float)
            for k in range(K_NAMES):
                col = cols[e, :, k]
                valid = col >= 0
                if not valid.any():
                    continue
                sims = np.flatnonzero(valid)
                np.add.at(target, (sims, col[valid]), wts[e, valid, k])
            delta = target - drifted
            traded = np.where(np.abs(delta) <= eps, 0.0, delta)
            cost = (np.abs(traded) * fee).sum(axis=1) * multiplier
            hold = target
        else:
            hold = drifted
        net[:, t] = gross - cost
    return net


def _decision_frame(path: list[dict], columns: list[str]) -> pd.DataFrame:
    rows = []
    index = []
    for slot in path:
        row = {name: 0.0 for name in columns}
        for name, weight in slot["weights"].items():
            row[name] = float(weight)
        rows.append([row[name] for name in columns])
        index.append(slot["date"])
    return pd.DataFrame(rows, index=pd.DatetimeIndex(index), columns=columns)


def _check_against_book(returns, cash_id, path, fees, nets: np.ndarray, row: int,
                        trade_eps: float) -> None:
    frame = _decision_frame(path, list(returns.columns))
    book = simulate(
        returns, to_execution(frame, returns.index), fees, cash_id,
        trade_eps=trade_eps, cost_multiplier=1.0,
    )
    gap = float(np.max(np.abs(book.net.to_numpy(dtype=float) - nets[row])))
    if gap > 1e-8:
        raise V51Error(f"R1 快速成交和 simulate 不一致（模拟 {row}，最大差 {gap:.3g}）")


def _percentile(value: float, sample: pd.Series) -> float:
    return float((sample.to_numpy(dtype=float) <= float(value)).mean())


def _control_params(pool: str, spec) -> dict:
    payload = design_params(pool, spec)
    payload["case"] = "R1"
    payload["kind"] = "control"
    payload["n"] = N_SIMS
    payload["seed"] = SEED
    payload["top_n"] = TOP_N
    payload["draw"] = "weekly: random eligible market, then up to 3 eligible names"
    payload["copied"] = "risk tier, rebalance dates, defense"
    return payload


def run_r1(*, ledger: Path = LEDGER, out: Path = OUT, n: int = N_SIMS) -> dict:
    """两个池各跑 n 次。会写设计期的随机账，不改过关表，不写 LOCK。"""
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import require_frozen_db

    from .allocate import allocate
    from .execute import open_market, universe_for
    from .params import Params
    from .readings import level_index, read_panel

    if int(n) != N_SIMS:
        raise V51Error("正式 R1 只跑预注册写死的 2000 次")
    digest = require_frozen_db()
    spec = load_spec()
    frozen = Params()
    design = pd.read_csv(DESIGN_OUT / "summary.csv")
    report = []
    payloads = []
    for pool in ("index", "tradable"):
        print(f"R1 {pool} 读数", flush=True)
        market = open_market(pool, spec)
        signal = _signal(market)
        if len(signal.index) and pd.Timestamp(signal.index.max()) > pd.Timestamp(DESIGN_END):
            raise V51Error("R1 的中国行情晚于 2015-12-31")
        universe = universe_for(market)
        eligible = eligible_frame(pool, market.liquidity, signal.index)
        panel = read_panel(signal, universe.cash)
        allocation = allocate(
            panel.H.index, panel.H, panel.F, panel.E, universe,
            prices=level_index(signal), returns=signal, eligible=eligible,
        )
        weekly = decision_dates(pd.DatetimeIndex(signal.index), "week")
        slots = build_slots(allocation, panel, universe, eligible, frontier=frozen.frontier, weekly=weekly)
        print(f"R1 {pool} 抽 {n} 次，调仓日 {len(slots)} 个", flush=True)
        paths = draw_paths(slots, n=n, seed=SEED, top_n=frozen.top_n)
        nets = portfolio_nets(
            market.pnl, market.cash_id, paths, market.fees, trade_eps=float(spec.trade_eps),
        )
        _check_against_book(market.pnl, market.cash_id, paths[0], market.fees, nets, 0, float(spec.trade_eps))
        _check_against_book(
            market.pnl, market.cash_id, paths[min(1, n - 1)], market.fees, nets, min(1, n - 1),
            float(spec.trade_eps),
        )
        sims = _distribution(nets, market.pnl.index)
        base = design[(design["pool"] == pool) & (design["segment"] == "full")].iloc[0]
        stats = {
            "pool": pool,
            "n": int(n),
            "seed": SEED,
            "decisions": int(len(slots)),
            "cagr_median": float(sims["cagr"].median()),
            "cagr_p95": _quantile(sims["cagr"], 0.95),
            "calmar_median": float(sims["calmar"].median()),
            "calmar_p95": _quantile(sims["calmar"], 0.95),
            "max_drawdown_median": float(sims["max_drawdown"].median()),
            "v51_cagr": float(base["cagr"]),
            "v51_calmar": float(base["calmar"]),
            "v51_cagr_percentile": _percentile(float(base["cagr"]), sims["cagr"]),
            "v51_calmar_percentile": _percentile(float(base["calmar"]), sims["calmar"]),
        }
        stats["cagr_ge_median"] = bool(stats["v51_cagr"] >= stats["cagr_median"])
        stats["calmar_gt_p95"] = bool(stats["v51_calmar"] > stats["calmar_p95"])
        folder = out / pool
        folder.mkdir(parents=True, exist_ok=True)
        sims.to_csv(folder / "sims.csv", index=False, float_format="%.16g")
        pd.DataFrame([stats]).to_csv(folder / "summary.csv", index=False, float_format="%.16g")
        pd.DataFrame([{
            "date": slot.date.date().isoformat(),
            "weekly": int(slot.weekly),
            "risk": slot.risk,
            "defense": slot.defense,
            "n_markets": len(slot.markets),
            "markets": "|".join(slot.markets),
        } for slot in slots]).to_csv(folder / "eligibility.csv", index=False, float_format="%.16g")
        pd.DataFrame([{
            "date": step["date"].date().isoformat(),
            "weekly": int(step["weekly"]),
            "risk": step["risk"],
            "defense": step["defense"],
            "market": step["market"],
            "names": "|".join(step["names"]),
        } for step in paths[0]]).to_csv(folder / "draws-0.csv", index=False, float_format="%.16g")
        report.append(stats)
        payloads.append(_control_params(pool, spec))
        print(
            f"R1 {pool} 年化中位 {stats['cagr_median']:.4f} Calmar95 {stats['calmar_p95']:.4f}"
            f" v5.1 年化分位 {stats['v51_cagr_percentile']:.3f}",
            flush=True,
        )
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(report).to_csv(out / "summary.csv", index=False, float_format="%.16g")
    manifest = {
        "rules": "v5.1",
        "case": "R1",
        "window": [WINDOW_START, "2015-12-31"],
        "n": N_SIMS,
        "seed": SEED,
        "generator": "numpy.random.Generator",
        "stream": "每次模拟先走完所有调仓日，再开始下一次；两个池各起一条种子相同的流",
        "copied": "v5.1 的风险仓位档位、调仓日、防守容器",
        "redraw": "只在周度调仓日重抽第一层市场和第二层最多 3 只；周中调仓沿用上次抽中的名字，缩放到当天档位",
        "eligibility": "市场 r>0 且当天至少一只可买；名字 H>0、F<前沿、可买。不够格则持代表。不沿用信号路径的卖出名单",
        "execution": "下一交易日收盘；漂移和扣费与 book.simulate 相同，前两条模拟逐日对照",
        "gate": "不改 §6.3。和 R0 同一口径的比较只写在 summary，供对照",
        "db_sha256": digest,
        "lock": False,
        "pools": report,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    for payload in payloads:
        pool = payload["pool"]
        upsert(
            ledger, payload, arm="R1", segment=SEGMENT, runner=RUNNER,
            same=lambda row, old, pool=pool: (
                row.get("arm") == "R1" and row.get("segment") == SEGMENT
                and old.get("pool") == pool and old.get("kind") == "control"
            ),
        )
    return {"pools": report, "db_sha256": digest}
