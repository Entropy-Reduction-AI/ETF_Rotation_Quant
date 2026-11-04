"""v5.1 R5：设计期的 R0、C-等权、C-波动比。

不写 LOCK，不打标签，不跑 R1、G 池和稳健性。中国组合只到 2015-12-31。

    git lfs pull --include=data/market.sqlite
    .venv/bin/python -m src.v51 controls
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.db import git_head
from src.report.metrics import cagr, calmar, max_drawdown
from src.v3.engine.ledger import COLUMNS, canonical_params
from src.v3.engine.limits import quotes_from_market

from .allocate import allocate
from .design import (
    LEDGER,
    OUT as DESIGN_OUT,
    WINDOWS,
    _refuse_ledger,
    _rows,
    _signal,
    _write_pool,
    design_params,
    eligible_frame,
    metric_block,
    windowed,
)
from .hold import N_SIMS, SEED, decision_frame, draw_names, single_name_nets, trade_masks
from .params import V51Error
from .readings import level_index, read_panel
from .volratio import vol_ratio

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "v5.1" / "controls"
GATE = DESIGN_OUT / "gate-draft.csv"
DESIGN_MANIFEST = DESIGN_OUT / "manifest.json"
RUNNER = "dev"
SEGMENT = "design"


def rankable_names(panel, universe, day, eligible: pd.DataFrame | None) -> list[str]:
    """三个市场里，当天 H、F、E 都有定义的成员。可交易池还要当天买得到。"""
    found = []
    for market in universe.markets:
        for name in market.members:
            if eligible is not None and not _on(eligible, day, name):
                continue
            if _defined(panel.H, day, name) and _defined(panel.F, day, name) and _defined(panel.E, day, name):
                found.append(name)
    return sorted(set(found))


def _on(frame: pd.DataFrame, day, name: str) -> bool:
    if name not in frame.columns or day not in frame.index:
        return False
    value = frame.at[day, name]
    if pd.isna(value):
        return False
    return bool(value)


def _defined(frame: pd.DataFrame, day, name: str) -> bool:
    if name not in frame.columns or day not in frame.index:
        return False
    value = frame.at[day, name]
    if pd.isna(value):
        return False
    return bool(np.isfinite(float(value)))


def _num(value: float) -> str:
    return format(float(value), ".16g")


def apply_control_results(rows: list[dict], r0: dict, equal_cagr: float, vol_cagr: float) -> list[dict]:
    """只改 §6.3 第 0、3 条和入围注记。其余行原样返回。"""
    out = [dict(row) for row in rows]
    for row in out:
        if row.get("item") == "0" and row.get("metric") == "calmar":
            hurdle = float(r0[row["pool"]]["calmar_p95"])
            value = float(row["strategy"])
            row["benchmark"] = _num(hurdle)
            row["status"] = "通过" if value > hurdle else "未通过"
            row["note"] = f"R0 {r0[row['pool']]['n']} 次；种子 {r0[row['pool']]['seed']}；高于 95 分位"
        elif row.get("item") == "0" and row.get("metric") == "cagr":
            hurdle = float(r0[row["pool"]]["cagr_median"])
            value = float(row["strategy"])
            row["benchmark"] = _num(hurdle)
            row["status"] = "通过" if value >= hurdle else "未通过"
            row["note"] = f"R0 {r0[row['pool']]['n']} 次；种子 {r0[row['pool']]['seed']}；不低于中位数"
        elif row.get("item") == "3":
            value = float(row["strategy"])
            binding = max(float(equal_cagr), float(vol_cagr))
            ok = value > float(equal_cagr) and value > float(vol_cagr)
            row["benchmark"] = _num(binding)
            row["status"] = "通过" if ok else "未通过"
            row["note"] = f"C-等权 {_num(equal_cagr)}；C-波动比 {_num(vol_cagr)}"
    scored = [row["status"] for row in out if row["status"] in {"通过", "未通过"}]
    pending = [row["status"] for row in out if row.get("item") in {"0", "2", "3", "5"}]
    for row in out:
        if row.get("item") != "入围":
            continue
        if any(status.startswith("待") for status in pending) or any(status != "通过" for status in scored):
            row["status"] = "未完成"
            row["note"] = "第 0、3 条已写入 R5 对照。第 5 条待 R6。已算条目未全过。这张表不是入围结论"
        else:
            row["status"] = "通过"
            row["note"] = "§6.3 已列条目全部通过"
    return out


def _patch_gate(path: Path, r0: dict, equal_cagr: float, vol_cagr: float) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = apply_control_results(list(reader), r0, equal_cagr, vol_cagr)
    if not fields:
        raise V51Error("过关表没有表头")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _distribution(matrix: np.ndarray, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """和 `cagr` / `max_drawdown` / `calmar` 同一窗口。先对第 0 条对一下再用于全部模拟。"""
    probe = windowed(pd.Series(matrix[0], index=dates), WINDOWS[0][1], WINDOWS[0][2])
    mask = dates.isin(probe.index)
    block = matrix[:, mask]
    growth = np.cumprod(1.0 + block, axis=1)
    years = block.shape[1] / 252.0
    annual = growth[:, -1] ** (1.0 / years) - 1.0
    drawdown = growth / np.maximum.accumulate(growth, axis=1) - 1.0
    depth = drawdown.min(axis=1)
    ratio = annual / np.abs(depth)
    series = pd.Series(block[0], index=probe.index)
    if abs(float(annual[0]) - cagr(series)) > 1e-12:
        raise V51Error("R0 年化和 metrics.cagr 不一致")
    if abs(float(depth[0]) - max_drawdown(series)["max_drawdown"]) > 1e-12:
        raise V51Error("R0 回撤和 metrics.max_drawdown 不一致")
    if abs(float(ratio[0]) - calmar(series)) > 1e-12:
        raise V51Error("R0 Calmar 和 metrics.calmar 不一致")
    return pd.DataFrame({"sim": np.arange(len(annual)), "cagr": annual, "max_drawdown": depth, "calmar": ratio})


def _quantile(series: pd.Series, q: float) -> float:
    return float(series.quantile(q, interpolation="linear"))


def _check_book(market, spec, decisions: pd.DatetimeIndex, picks: list[str], nets: np.ndarray, row: int) -> None:
    from .execute import run_book

    frame = decision_frame(list(market.pnl.columns), market.cash_id, decisions, picks)
    book = run_book(market, spec, frame)
    aligned = book.net.reindex(market.pnl.index)
    if aligned.isna().any():
        raise V51Error("对照成交和行情日历对不齐")
    gap = float(np.max(np.abs(aligned.to_numpy(dtype=float) - nets[row])))
    if gap > 1e-8:
        raise V51Error(f"R0 快速成交和 A 臂不一致（模拟 {row}，最大差 {gap:.3g}）")


def _run_r0(pool: str, market, spec, panel, universe, eligible, folder: Path) -> dict:
    from src.v3.engine.sessions import decision_dates

    dates = pd.DatetimeIndex(pd.to_datetime(market.dates)).normalize()
    months = decision_dates(dates, "month")
    if months.empty or pd.Timestamp(months[0]) not in panel.H.index:
        raise V51Error(f"R0 {pool} 的月末不在读数日历里")
    roster = [rankable_names(panel, universe, day, eligible) for day in months]
    print(f"R0 {pool} 抽 {N_SIMS} 次，月末 {len(months)} 个", flush=True)
    picks = draw_names(roster, n=N_SIMS, seed=SEED, cash_id=market.cash_id)
    quotes = quotes_from_market(market)
    can_buy, can_sell = trade_masks(quotes, dates, list(market.pnl.columns), market.cash_id)
    nets = single_name_nets(
        market.pnl, market.cash_id, months, picks, market.fees, can_buy, can_sell,
        cost_multiplier=1.0,
    )
    _check_book(market, spec, months, picks[0], nets, 0)
    _check_book(market, spec, months, picks[min(1, N_SIMS - 1)], nets, min(1, N_SIMS - 1))
    sims = _distribution(nets, market.pnl.index)
    if int(sims["cagr"].isna().sum()) or int(sims["calmar"].isna().sum()):
        raise V51Error(f"R0 {pool} 有模拟没有年化或 Calmar")
    stats = {
        "pool": pool,
        "n": N_SIMS,
        "seed": SEED,
        "cagr_median": float(sims["cagr"].median()),
        "cagr_p95": _quantile(sims["cagr"], 0.95),
        "calmar_median": float(sims["calmar"].median()),
        "calmar_p95": _quantile(sims["calmar"], 0.95),
        "max_drawdown_median": float(sims["max_drawdown"].median()),
        "months": int(len(months)),
        "eligible_mean": float(np.mean([len(names) for names in roster])),
    }
    if stats["eligible_mean"] <= 0.0:
        raise V51Error(f"R0 {pool} 没有任何月份有可排名的容器")
    folder.mkdir(parents=True, exist_ok=True)
    sims.to_csv(folder / "sims.csv", index=False, float_format="%.16g")
    pd.DataFrame([{
        "date": pd.Timestamp(day).date().isoformat(),
        "n": len(names),
        "names": "|".join(names),
    } for day, names in zip(months, roster)]).to_csv(folder / "eligibility.csv", index=False)
    pd.DataFrame({
        "date": [pd.Timestamp(day).date().isoformat() for day in months],
        "name": picks[0],
    }).to_csv(folder / "draws-0.csv", index=False)
    pd.DataFrame([stats]).to_csv(folder / "summary.csv", index=False, float_format="%.16g")
    print(
        f"R0 {pool} 年化中位 {stats['cagr_median']:.4f} Calmar95 {stats['calmar_p95']:.4f}",
        flush=True,
    )
    return stats


def _control_params(pool: str, spec, case: str, **extra) -> dict:
    payload = design_params(pool, spec)
    payload["case"] = case
    payload["kind"] = "control"
    payload.update(extra)
    return payload


def record_control(params: dict, path: Path = LEDGER, *, runner: str = RUNNER) -> None:
    """同一对照、同一池只留一行。不碰设计期那两行，不写 LOCK。"""
    _refuse_ledger(path)
    if params.get("kind") != "control":
        raise V51Error("对照账本只收 kind=control")
    arm = str(params["case"])
    pool = str(params["pool"])
    from zoneinfo import ZoneInfo

    fresh = {
        "run_at": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "git_sha": git_head() or "",
        "arm": arm,
        "params": canonical_params(params),
        "segment": SEGMENT,
        "runner": runner,
    }
    kept = []
    for row in _rows(path):
        try:
            old = json.loads(row.get("params") or "{}")
        except json.JSONDecodeError:
            kept.append(row)
            continue
        if row.get("arm") == arm and row.get("segment") == SEGMENT and old.get("pool") == pool and old.get("kind") == "control":
            continue
        kept.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(kept)
        writer.writerow(fresh)


def _book(pool: str, market, spec, allocation, folder: Path) -> pd.Series:
    from .execute import run_book

    missing = [name for name in allocation.decisions.columns if name not in market.pnl.columns]
    if missing:
        raise V51Error(f"{pool} 的决策有行情没有的列：{missing}")
    book = run_book(market, spec, allocation.decisions)
    return _write_pool(pool, book, allocation, folder)


def run_controls(*, ledger: Path = LEDGER, out: Path = OUT, gate: Path = GATE) -> dict:
    """两个池的 R0 和 C-等权，加上 U-指数的 C-波动比。会写设计期收益。"""
    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import require_frozen_db

    from .execute import open_market, universe_for

    _refuse_ledger(ledger)
    if not gate.is_file():
        raise V51Error("还没有设计期过关表，先跑设计期")
    digest = require_frozen_db()
    spec = load_spec()
    bench_path = DESIGN_OUT / "benchmark.csv"
    benchmark = pd.read_csv(bench_path, parse_dates=["date"], index_col="date")["benchmark"].astype(float)
    benchmark.index = pd.DatetimeIndex(benchmark.index).normalize()
    blocks = []
    payloads = []
    r0 = {}
    for pool in ("index", "tradable"):
        print(f"C-等权 {pool}", flush=True)
        market = open_market(pool, spec)
        signal = _signal(market)
        universe = universe_for(market)
        eligible = eligible_frame(pool, market.liquidity, signal.index)
        equal = allocate_equal(signal, universe, eligible)
        equal_net = _book(pool, market, spec, equal, out / "equal" / pool)
        for segment, start, end in WINDOWS:
            row = metric_block(pool, segment, start, end, equal_net, benchmark)
            row["case"] = "C-等权"
            blocks.append(row)
        payloads.append(_control_params(pool, spec, "C-等权", weights="equal"))
        print(f"读数 {pool}", flush=True)
        panel = read_panel(signal, universe.cash)
        if pool == "index":
            print("C-波动比 index", flush=True)
            names = [item.representative for item in universe.markets] + [universe.bond, universe.gold]
            ratio = vol_ratio(signal, universe.cash, names)
            vol_book = allocate(
                panel.H.index, panel.H, panel.F, panel.E, universe,
                prices=level_index(signal), returns=signal, eligible=eligible,
                mode="vol_ratio", strength=ratio.strength, noise=ratio.noise,
            )
            vol_net = _book(pool, market, spec, vol_book, out / "vol" / pool)
            for segment, start, end in WINDOWS:
                row = metric_block(pool, segment, start, end, vol_net, benchmark)
                row["case"] = "C-波动比"
                blocks.append(row)
            payloads.append(_control_params(
                pool, spec, "C-波动比", layer1_rule="vol-ratio",
                strength="L-day log excess over cash",
                quantile_short_history=0.5,
            ))
        r0[pool] = _run_r0(pool, market, spec, panel, universe, eligible, out / "r0" / pool)
        payloads.append(_control_params(
            pool, spec, "R0", n=N_SIMS, seed=SEED, decision="month",
            eligibility="layer1 members with H F E", hold="one full",
        ))
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(blocks).to_csv(out / "summary.csv", index=False, float_format="%.16g")
    equal_full = next(row for row in blocks if row["case"] == "C-等权" and row["pool"] == "index" and row["segment"] == "full")
    vol_full = next(row for row in blocks if row["case"] == "C-波动比" and row["pool"] == "index" and row["segment"] == "full")
    _patch_gate(gate, r0, equal_full["cagr"], vol_full["cagr"])
    _mark_design_manifest()
    protocol = {
        "rules": "v5.1",
        "window": ["2006-01-01", "2015-12-31"],
        "git_sha": git_head() or "",
        "db_sha256": digest,
        "r0": {
            "n": N_SIMS,
            "seed": SEED,
            "generator": "numpy.random.Generator",
            "draw": "choice(sorted ids, size=1, replace=False)；空月为现金且不抽",
            "stream": "每次模拟先走完所有月末，再开始下一次；两个池各起一条种子相同的流",
            "decision": "每月最后一个交易日",
            "execution": "下一交易日收盘；涨跌停与 A 臂相同",
            "eligibility": "第一层三个市场的成员，当天 H、F、E 都有定义；可交易池还要当天可买",
            "metrics": "src.report.metrics cagr / max_drawdown / calmar；pandas quantile(0.95, interpolation=linear)",
        },
        "equal_weight": "§2 第 3 条改为 28 把永远等权，其余同 v5.1",
        "vol_ratio": "强度为 L 日对数超额；历史不足 250 时 q=0.5；第一层按强度持最强，z 差大于 1 才换；离场看强度正负；第二层和单只离场同 v5.1；只跑 U-指数",
        "excluded": ["R1", "G", "robustness"],
        "lock": False,
    }
    (out / "manifest.json").write_text(
        json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    (out / "params.json").write_text(
        json.dumps(payloads, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    for payload in payloads:
        record_control(payload, ledger)
    print(
        f"C-等权指数年化 {equal_full['cagr']:.4f}  C-波动比 {vol_full['cagr']:.4f}",
        flush=True,
    )
    return {"r0": r0, "equal_cagr": equal_full["cagr"], "vol_cagr": vol_full["cagr"], "db_sha256": digest}


def allocate_equal(signal, universe, eligible):
    from .allocate import target_weights

    return target_weights(signal, universe, eligible=eligible, equal_weight=True)


def _mark_design_manifest() -> None:
    if not DESIGN_MANIFEST.is_file():
        return
    payload = json.loads(DESIGN_MANIFEST.read_text(encoding="utf-8"))
    payload["excluded"] = ["R1", "G", "robustness"]
    payload["r5"] = "results/v5.1/controls"
    DESIGN_MANIFEST.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
