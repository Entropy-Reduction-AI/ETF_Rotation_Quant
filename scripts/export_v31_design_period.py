"""把正式设计期 Book 写成 csv。

只调用已经存在的运行与评估函数，不写 trial-ledger，不改规则，不读 2016-01-01 及以后的组合收益。
命令行本身丢掉 Book。本脚本用与 `python -m src.v3.engine` 相同的 `load_market` + `execute` 再取回对象。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src.data import db as DB
from src.report.metrics import cagr, excess_cagr, max_drawdown, yearly_returns
from src.v3.data.universe import containers as load_containers
from src.v3.engine.arms import execute
from src.v3.engine.benchmark import bm_main
from src.v3.engine.book import DESIGN_END
from src.v3.engine.market import load_market
from src.v3.engine.spec import LEDGER, load_spec
from src.v3.engine.universe import pool_members
from src.v3.eval.controls import eligibility
from src.v3.eval.drawdown import criterion_4, drawdown_stats, equity_weight, position_matched
from src.v3.eval.eras import criterion_3
from src.v3.eval.windows import criterion_1

RUNS = (
    ("P1", "A", "index", "official"),
    ("P2", "A", "index", "publish_date"),
    ("P3", "S1", "index", "official"),
    ("P4", "S2", "index", "official"),
    ("P5", "B", "index", "official"),
    ("P6", "A", "tradable", "official"),
    ("P7", "A", "tradable", "publish_date"),
    ("P8", "S1", "tradable", "official"),
    ("P9", "S2", "tradable", "official"),
    ("P10", "B", "tradable", "official"),
)


def _sha() -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stamp(value) -> str:
    return str(pd.Timestamp(value).date())


def _year_crash(rets: pd.Series, year: int) -> dict | None:
    """年内回撤最深的一天。峰值用该日之前净值的最高点，与 `max_drawdown` 同一条净值路径。"""
    series = pd.Series(rets, dtype=float).sort_index()
    nav = (1.0 + series).cumprod()
    drawdown = nav / nav.cummax() - 1.0
    block = drawdown[drawdown.index.year == year]
    if block.empty:
        return None
    trough = pd.Timestamp(block.idxmin())
    peak = pd.Timestamp(nav.loc[:trough].idxmax())
    return {
        "year": year,
        "peak": _stamp(peak),
        "trough": _stamp(trough),
        "drawdown": float(drawdown.loc[trough]),
    }


def _holdings(held: pd.DataFrame, day, cash_id: str, eps: float, meta: dict) -> list[dict]:
    stamp = pd.Timestamp(day)
    row = held.loc[stamp]
    cash = float(row[cash_id])
    names = []
    for name, weight in row.items():
        if name == cash_id or float(weight) <= eps:
            continue
        info = meta.get(str(name), {})
        names.append({
            "id": str(name),
            "name": info.get("name") or str(name),
            "asset_class": info.get("asset_class") or "",
            "weight": float(weight),
        })
    names.sort(key=lambda item: (-item["weight"], item["id"]))
    return {"date": _stamp(stamp), "cash": cash, "n_nonzero": len(names), "positions": names}


def _deferred(book) -> pd.DataFrame:
    """A/S 的平均账本没有把各路 deferred_exits 抄上来。字段是 None 时改记各路账本。"""
    own = book.deferred_exits
    if own is not None:
        frame = own.copy()
        if frame.empty and len(frame.columns) == 0:
            frame = pd.DataFrame(columns=["date", "name", "reason"])
        frame.insert(0, "path", "executed")
        frame.insert(0, "source", "book.deferred_exits")
        return frame
    parts = []
    for key, path_book in (book.paths or {}).items():
        part = path_book.deferred_exits
        if not isinstance(part, pd.DataFrame):
            continue
        frame = part.copy()
        if frame.empty and len(frame.columns) == 0:
            continue
        label = f"{key[0]}-{key[1]}" if isinstance(key, tuple) else str(key)
        frame.insert(0, "path", label)
        frame.insert(0, "source", "path.deferred_exits")
        parts.append(frame)
    if not parts:
        return pd.DataFrame(columns=["source", "path", "date", "name", "reason"])
    return pd.concat(parts, ignore_index=True)


def _paths_frame(book) -> pd.DataFrame:
    columns = {"executed": book.net.astype(float)}
    for key, path_book in (book.paths or {}).items():
        label = f"{key[0]}-{key[1]}" if isinstance(key, tuple) else str(key)
        columns[label] = path_book.net.astype(float).reindex(book.net.index)
    return pd.DataFrame(columns)


def _eligible_summary(ok: pd.DataFrame, member_ids: list[str]) -> dict:
    counts = ok.sum(axis=1).astype(int)
    never = sorted(name for name in ok.columns if not bool(ok[name].any()))
    absent = sorted(name for name in member_ids if name not in set(ok.columns))
    yearly = []
    for year, block in counts.groupby(counts.index.year):
        values = block.to_numpy(dtype=float)
        yearly.append({
            "year": int(year),
            "n_days": int(len(block)),
            "min": int(values.min()),
            "median": float(np.median(values)),
            "max": int(values.max()),
        })
    return {
        "n_days": int(len(counts)),
        "min": int(counts.min()) if len(counts) else None,
        "median": float(np.median(counts.to_numpy(dtype=float))) if len(counts) else None,
        "max": int(counts.max()) if len(counts) else None,
        "never_eligible": never,
        "pool_ids_absent_from_eligibility": absent,
        "yearly": yearly,
        "counts": counts,
    }


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return _stamp(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if not np.isfinite(number):
            return None
        return number
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _write(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def export_one(run_id: str, arm: str, pool: str, mode: str, spec, meta: dict, bm: pd.Series,
               out_dir: Path, *, criteria: bool) -> dict:
    end = pd.Timestamp("2015-12-31")
    market = load_market(
        DB.MARKET_DB, load_containers(), arm, pool, end, spec,
        cost_multiplier=1.0, allow_after=False, history_mode=mode,
    )
    book = execute(market, spec, arm, allow_after=False, exit_drawdown=0.10, premium_spec=None)
    if book.net.empty:
        raise RuntimeError(f"{run_id} 没有收益")
    last = pd.Timestamp(book.net.index.max())
    first = pd.Timestamp(book.net.index.min())
    if last > DESIGN_END or first > DESIGN_END:
        raise RuntimeError(f"{run_id} 日期越过设计期：{first.date()}→{last.date()}")
    depth = max_drawdown(book.net)
    ann = cagr(book.net)
    overlap = book.net.index.intersection(bm.dropna().index)
    bm_on = bm.reindex(overlap)
    strategy_on = book.net.reindex(overlap)
    yearly_strategy = yearly_returns(book.net)
    yearly_bm = yearly_returns(bm_on)
    cash = book.held[market.cash_id].astype(float)
    ok = eligibility(market, spec)
    members = [
        str(row["id"]) for row in pool_members(load_containers(), arm, pool)
        if row.get("asset_class") != "现金"
    ]
    eligible = _eligible_summary(ok, members)
    counts = eligible.pop("counts")
    nonzero = (book.held.drop(columns=[market.cash_id]) > spec.weight_eps).sum(axis=1).astype(int)
    years = sorted(set(book.net.index.year))
    yearly_rows = []
    for year in years:
        year_index = book.net.index[book.net.index.year == year]
        end_day = year_index[-1]
        yearly_rows.append({
            "year": int(year),
            "arm": yearly_strategy.get(int(year)),
            "bm_main": yearly_bm.get(int(year)),
            "excess": None if int(year) not in yearly_bm else yearly_strategy[int(year)] - yearly_bm[int(year)],
            "year_end": _stamp(end_day),
            "year_end_cash": float(cash.loc[end_day]),
            "n_arm": int(len(year_index)),
            "n_bm": int(np.sum(np.asarray(bm_on.index.year) == year)),
        })
    crashes = {}
    snapshots = {}
    for year in (2008, 2015):
        crash = _year_crash(book.net, year)
        crashes[str(year)] = crash
        if crash is not None:
            snapshots[str(year)] = {
                "trough": _holdings(book.held, crash["trough"], market.cash_id, spec.weight_eps, meta),
                "peak": _holdings(book.held, crash["peak"], market.cash_id, spec.weight_eps, meta),
            }
    sample_days = []
    seen = set()
    candidates = [book.net.index[0], book.net.index[-1]]
    for year in years:
        candidates.append(book.net.index[book.net.index.year == year][-1])
    for year in (2008, 2015):
        crash = crashes.get(str(year))
        if crash is not None:
            candidates.append(pd.Timestamp(crash["trough"]))
    for day in candidates:
        stamp = pd.Timestamp(day)
        key = _stamp(stamp)
        if key in seen or stamp not in book.held.index:
            continue
        seen.add(key)
        info = _holdings(book.held, stamp, market.cash_id, spec.weight_eps, meta)
        sample_days.append({
            "date": key,
            "n_eligible": int(counts.loc[stamp]) if stamp in counts.index else None,
            "n_held": int(nonzero.loc[stamp]),
            "cash": info["cash"],
        })
    matched = None
    if criteria:
        classes = {key: value.get("asset_class") or "" for key, value in meta.items()}
        equity = equity_weight(book.held, classes)
        matched_book = position_matched(
            bm.reindex(book.net.index),
            market.pnl[market.cash_id].reindex(book.net.index),
            equity.reindex(book.net.index),
        )
        matched = {
            "average_equity_weight": matched_book["average_equity_weight"],
            "cagr": cagr(matched_book["returns"]),
            "max_drawdown": max_drawdown(matched_book["returns"])["max_drawdown"],
        }
        stats = drawdown_stats(book.net)
        bench_stats = drawdown_stats(bm_on)
        crit4 = criterion_4(strategy_on, bm_on)
        crit1 = criterion_1(strategy_on, bm_on, market.dates)
        crit3 = criterion_3(strategy_on, bm_on, market.dates)
        criteria_payload = {
            "drawdown_stats": {
                "max_drawdown": stats["max_drawdown"],
                "peak": stats["peak"],
                "trough": stats["trough"],
                "underwater_days": stats["underwater_days"],
                "underwater_fraction": stats["underwater_fraction"],
                "longest_underwater_days": stats["longest_underwater_days"],
            },
            "bm_drawdown_stats": {
                "max_drawdown": bench_stats["max_drawdown"],
                "peak": bench_stats["peak"],
                "trough": bench_stats["trough"],
                "underwater_days": bench_stats["underwater_days"],
                "underwater_fraction": bench_stats["underwater_fraction"],
                "longest_underwater_days": bench_stats["longest_underwater_days"],
            },
            "criterion_4_deeper_by": crit4["deeper_by"],
            "criterion_1": {
                "n_36": crit1["n_36"],
                "n_60": crit1["n_60"],
                "median_36": crit1["median_36"],
                "median_60": crit1["median_60"],
                "fraction_positive_60": crit1["fraction_positive_60"],
            },
            "criterion_3": [
                {
                    "era": row["era"],
                    "status": row["status"],
                    "n": row["n"],
                    "ann_strategy": row["ann_strategy"],
                    "ann_benchmark": row["ann_benchmark"],
                    "excess": row["excess"],
                }
                for row in crit3["eras"]
            ],
        }
    else:
        criteria_payload = None
    choices = {}
    for year, key in (book.choices or {}).items():
        choices[str(year)] = None if key is None else [int(key[0]), str(key[1])]
    run_dir = out_dir / run_id
    held = book.held.copy()
    held.insert(0, "date", [_stamp(day) for day in held.index])
    _write(held, run_dir / "held.csv")
    paths = _paths_frame(book)
    paths.insert(0, "date", [_stamp(day) for day in paths.index])
    _write(paths, run_dir / "paths.csv")
    exits = book.exits if isinstance(book.exits, pd.DataFrame) else pd.DataFrame()
    if exits.empty and len(exits.columns) == 0:
        exits = pd.DataFrame(columns=["date", "name", "price", "kind"])
    _write(exits, run_dir / "exits.csv")
    _write(_deferred(book), run_dir / "deferred-exits.csv")
    turnover = pd.DataFrame({
        "date": [_stamp(day) for day in book.net.index],
        "cash": cash.to_numpy(dtype=float),
        "buy": book.buy.to_numpy(dtype=float),
        "sell": book.sell.to_numpy(dtype=float),
        "cost": book.cost.to_numpy(dtype=float),
    })
    _write(turnover, run_dir / "turnover.csv")
    eligible_frame = ok.astype(int).copy()
    eligible_frame.insert(0, "n_eligible", counts.to_numpy(dtype=int))
    eligible_frame.insert(0, "date", [_stamp(day) for day in eligible_frame.index])
    _write(eligible_frame, run_dir / "eligible.csv")
    _write(pd.DataFrame(yearly_rows), run_dir / "yearly.csv")
    n_days = int(len(book.net))
    summary = {
        "id": run_id,
        "arm": arm,
        "pool": pool,
        "history_mode": mode,
        "exit_drawdown": 0.10,
        "start": _stamp(first),
        "end": _stamp(last),
        "n": n_days,
        "cagr": ann,
        "max_drawdown": depth["max_drawdown"],
        "max_drawdown_peak": _stamp(depth["peak"]),
        "max_drawdown_trough": _stamp(depth["trough"]),
        "bm_main_cagr_on_overlap": cagr(bm_on),
        "bm_main_max_drawdown_on_overlap": max_drawdown(bm_on)["max_drawdown"],
        "excess_cagr_vs_bm_main": excess_cagr(book.net, bm),
        "overlap_n": int(len(overlap)),
        "average_cash": float(cash.mean()),
        "buy_sum": float(book.buy.sum()),
        "sell_sum": float(book.sell.sum()),
        "turnover_one_way_annual": float(book.buy.sum() / (n_days / 252.0)),
        "yearly": yearly_rows,
        "eligibility": eligible,
        "samples": sample_days,
        "crashes": crashes,
        "snapshots": snapshots,
        "choices": choices,
        "position_matched": matched,
        "criteria": criteria_payload,
        "deferred_rows": int(len(_deferred(book))),
        "exit_rows": int(len(exits)),
    }
    return _jsonable(summary)


def main() -> None:
    sha = _sha()
    if not sha.startswith("9b421c0"):
        raise SystemExit(f"导出时期望复跑提交 9b421c0，当前 HEAD 是 {sha}")
    ledger_before = _file_sha(LEDGER) if LEDGER.exists() else None
    spec = load_spec()
    meta = {
        str(row["id"]): {"name": row.get("name") or row["id"], "asset_class": row.get("asset_class") or ""}
        for row in load_containers()
    }
    bm = bm_main(DB.MARKET_DB, "2015-12-31")
    if pd.Timestamp(bm.index.max()) > DESIGN_END:
        raise SystemExit("BM-主 越过设计期")
    out_dir = ROOT / "results" / "v3" / "design-period" / sha
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    for run_id, arm, pool, mode in RUNS:
        print(f"export {run_id}", flush=True)
        summaries.append(export_one(
            run_id, arm, pool, mode, spec, meta, bm, out_dir, criteria=(run_id == "P1"),
        ))
        row = summaries[-1]
        if row["end"] > "2015-12-31":
            raise SystemExit(f"{run_id} end {row['end']}")
        print(
            f"  {row['start']}→{row['end']} n={row['n']} cagr={row['cagr']:.6f} "
            f"max_drawdown={row['max_drawdown']:.6f}",
            flush=True,
        )
    payload = {"git_sha": sha, "end_limit": "2015-12-31", "runs": summaries}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    (out_dir / "summary.json").write_text(text + "\n", encoding="utf-8")
    ledger_after = _file_sha(LEDGER) if LEDGER.exists() else None
    if ledger_before != ledger_after:
        raise SystemExit("导出改写了 trial-ledger.csv")
    print(f"wrote {out_dir}", flush=True)


if __name__ == "__main__":
    main()
