#!/usr/bin/env python3
"""Independent v4-R5c D25 review (PR #132). Design period only (≤2015-12-31)."""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.report.metrics import cagr, max_drawdown
from src.v3.engine.arms import execute
from src.v3.engine.spec import load_spec
from src.v3.data.universe import containers as load_containers
from src.v4.engine.carriers import build_candidates, choose_on, sse_calendar
from src.v4.r5 import design as D
from src.v4.r5.design import Job, Markets, file_sha256, read_net, require_frozen_db, series_sha256
from src.v4.engine.pool import US_SECTORS
from src.v4.peers import load_peer, run_peer
from src.v4.r5 import peers as r5_peers
from src.v4.scorecard.gate import GATE_COLUMNS, candidate_gate

DESIGN_END = "2015-12-31"
YEARS = list(range(2005, 2016))
EXPECTED_GATE_SHA = "52fc1c9d653c27236df258cd0789ada7e4c4b27a842b2e82b004380bde445d74"
EXPECTED_DB_SHA = "550c1aee17a099dfc206876503ef436456bc5e87441db6947692abd3d6868c6c"
DEV_GIT_SHA = "c700ca095057baa524be01f6566d342c43976bea"
RUN_ORDER = ("B0", "T1", "T2", "T3", "T4")
ORCH_CAGR_FROM_2006 = 0.246
ORCH_MDD = -0.353
WEIGHT_COLS = ("cgb-5y", "cgb-10y", "gold", "chinext")
PATH_CHECKS = (
    ("csi300", "2006-06-30"),
    ("hsi", "2012-12-31"),
    ("ndx100", "2013-12-31"),
    ("gold", "2013-12-31"),
    ("theme-标普全球石油指数", "2012-12-31"),
    ("chinext", "2012-03-13"),
)
GROUP = {
    "A股宽基": "A 股",
    "A股行业": "A 股",
    "A股红利": "A 股",
    "港股": "港股",
    "美股宽基": "美股",
    "美股和全球主题": "海外主题（QDII、LOF）",
    "商品": "商品、债券、现金",
    "债券": "商品、债券、现金",
    "现金": "商品、债券、现金",
    "美股行业": "美股",
    "港股分类": "港股",
}
TRADABLE_RUNS = (
    ("B0", dict(case="B0", t1=False, t2=False, t3=False, t4=False)),
    ("T1", dict(case="T1", t1=True, t2=False, t3=False, t4=False)),
    ("T2", dict(case="T2", t1=False, t2=True, t3=False, t4=False)),
    ("T3", dict(case="T3", t1=False, t2=False, t3=True, t4=False)),
    ("T4", dict(case="T4", t1=False, t2=False, t3=False, t4=True)),
    ("final", dict(case="final", t1=False, t2=False, t3=False, t4=False, kind="final")),
    ("A1", dict(peer="A1")),
    ("A2", dict(peer="A2")),
)
SEGMENTS = (
    ("s1", "2006-01-01", "2010-12-31"),
    ("s2", "2011-01-01", "2015-12-31"),
)
TRADING_DAYS = 252


def container_groups() -> dict[str, str]:
    out = {}
    for row in load_containers():
        cid = str(row.get("id") or "")
        out[cid] = GROUP.get(str(row.get("asset_class") or ""), str(row.get("asset_class") or ""))
    board = ROOT / "results/v4/diag/data-board/out/containers.csv"
    if board.is_file():
        for row in csv.DictReader(open(board)):
            out[row["id"]] = row["group"]
    return out


def board_buy_total(year: int, *, include_us_sectors: bool) -> int:
    summary = json.loads((ROOT / "results/v4/diag/data-board/out/summary.json").read_text())
    total = sum(summary["buy_by_year"][g].get(str(year), 0) for g in summary["buy_by_year"])
    if include_us_sectors:
        return total
    end = f"{year}-12-31"
    us_sector = sum(
        1
        for row in csv.DictReader(open(ROOT / "results/v4/diag/data-board/out/containers.csv"))
        if row["id"].startswith("us-") and row.get("buy_first") and row["buy_first"] <= end
    )
    return total - us_sector


def _annualized(values: np.ndarray) -> float:
    growth = float(np.expm1(np.log1p(values).sum()))
    if growth <= -1.0:
        return float("nan")
    return float(np.exp(np.log1p(growth) * TRADING_DAYS / len(values)) - 1.0)


def _segment_excess(strategy: pd.Series, benchmark: pd.Series, start: str, end: str) -> float:
    both = pd.concat([
        strategy.rename("strategy"),
        benchmark.rename("benchmark"),
    ], axis=1).dropna().sort_index()
    both = both.loc[start:end]
    if len(both) == 0:
        return float("nan")
    left = both["strategy"].to_numpy(dtype=float)
    right = both["benchmark"].to_numpy(dtype=float)
    return _annualized(left) - _annualized(right)


def _state_labels(index: pd.DatetimeIndex, states: pd.Series) -> np.ndarray:
    by_month = states.copy()
    by_month.index = pd.DatetimeIndex(pd.to_datetime(by_month.index)).to_period("M")
    by_month = by_month[~by_month.index.duplicated(keep="last")]
    periods = pd.DatetimeIndex(index).to_period("M")
    return by_month.reindex(periods).to_numpy()


def _excess(strategy: pd.Series, benchmark: pd.Series) -> pd.Series:
    both = pd.concat([
        strategy.rename("strategy"),
        benchmark.rename("benchmark"),
    ], axis=1).dropna().sort_index()
    return both["strategy"] - both["benchmark"]


def _state_points(excess: pd.Series, states: pd.Series) -> dict[str, float]:
    from src.v4.scorecard.gate import TARGET_STATE  # noqa: F401

    labels = _state_labels(pd.DatetimeIndex(excess.index), states)
    values = excess.to_numpy(dtype=float)
    out = {}
    for name in ("牛市", "回调", "熊市", "反弹"):
        mask = labels == name
        total = float(values[mask].sum()) if mask.any() else 0.0
        out[name] = 100.0 * total
    return out


def independent_gate(returns: pd.DataFrame, benchmark: pd.Series, states: pd.Series, *, pool: str) -> pd.DataFrame:
    frame = returns.sort_index()
    bench = benchmark.sort_index()
    b0 = frame["B0"].astype(float)
    b0_ann = {key: _segment_excess(b0, bench, start, end) for key, start, end in SEGMENTS}
    b0_points = _state_points(_excess(b0, bench), states)
    from src.v4.scorecard.gate import TARGET_STATE

    rows = []
    for name in RUN_ORDER:
        if name not in frame.columns:
            continue
        series = frame[name].astype(float)
        points = b0_points if name == "B0" else _state_points(_excess(series, bench), states)
        ann = {key: _segment_excess(series, bench, start, end) for key, start, end in SEGMENTS}
        row = {
            "arm": name,
            "pool": pool,
            "ann_excess_s1": ann["s1"] if name != "B0" else b0_ann["s1"],
            "ann_excess_s2": ann["s2"] if name != "B0" else b0_ann["s2"],
            "pp_bull": points["牛市"],
            "pp_correction": points["回调"],
            "pp_bear": points["熊市"],
            "pp_rebound": points["反弹"],
        }
        if name == "B0":
            row["pass_segments"] = None
            row["pass_target"] = None
            row["pass_bear"] = None
            row["pass"] = None
        else:
            segments_ok = bool(ann["s1"] > b0_ann["s1"] and ann["s2"] > b0_ann["s2"])
            target = TARGET_STATE[name]
            target_ok = bool(points[target] > b0_points[target])
            bear_ok = bool(points["熊市"] >= b0_points["熊市"] - 10.0)
            row["pass_segments"] = segments_ok
            row["pass_target"] = target_ok
            row["pass_bear"] = bear_ok
            row["pass"] = bool(segments_ok and target_ok and bear_ok)
        rows.append(row)
    out = pd.DataFrame(rows, columns=list(GATE_COLUMNS))
    for column in ("pass_segments", "pass_target", "pass_bear", "pass"):
        out[column] = out[column].astype(object)
    return out


def _gate_diff(dev: pd.DataFrame, ind: pd.DataFrame) -> dict:
    float_cols = [
        "ann_excess_s1", "ann_excess_s2",
        "pp_bull", "pp_correction", "pp_bear", "pp_rebound",
    ]
    ok = True
    mismatches = []
    for col in GATE_COLUMNS:
        if dev[col].equals(ind[col]):
            continue
        if col in float_cols:
            diff = (dev[col].astype(float) - ind[col].astype(float)).abs()
            mx = float(diff.max())
            if mx > 1e-9:
                ok = False
                mismatches.append({"column": col, "max_abs_diff": mx})
        else:
            ok = False
            mismatches.append({"column": col, "dev": dev[col].tolist(), "ind": ind[col].tolist()})
    return {"match": ok, "mismatches": mismatches}


def yearly_census_from_held(
    held: pd.DataFrame,
    cash: str,
    liq: pd.DataFrame | None,
    groups: dict[str, str],
    *,
    t4: bool,
) -> dict:
    held = held.fillna(0.0)
    names = [n for n in held.columns if n != cash and (t4 or not n.startswith("us-"))]
    out = {}
    for year in YEARS:
        mask = held.index.year == year
        if not mask.any():
            continue
        sub = held.loc[mask]
        cash_w = float(sub[cash].mean()) if cash in sub.columns else float("nan")
        tradable_ever = set()
        for name in names:
            if liq is not None and name in liq.columns:
                flags = liq[name].reindex(sub.index).fillna(False).astype(bool)
            else:
                flags = sub[name] > 1e-9
            if flags.any():
                tradable_ever.add(name)
        weights = sub[names].mean().sort_values(ascending=False)
        top5 = [(n, float(weights[n])) for n in weights.head(5).index if weights[n] > 1e-9]
        by_group = defaultdict(int)
        for name in tradable_ever:
            by_group[groups.get(name, "?")] += 1
        out[str(year)] = {
            "tradable_containers_ever": len(tradable_ever),
            "tradable_by_group": dict(by_group),
            "avg_cash_weight": cash_w,
            "top5_mean_weight": top5,
            "board_buy_total": board_buy_total(year, include_us_sectors=t4),
        }
    return out


def run_b0_index_held() -> tuple[pd.Series, pd.DataFrame]:
    spec = load_spec()
    markets = Markets(spec)
    job = Job(case="B0", pool="index", kind="single")
    market = markets.get("index", t4=False, allow_substitute=True)
    book = execute(
        market, spec, "A", allow_after=False,
        exit_drawdown=job.exit_drawdown, switches=job.switches(),
    )
    return book.net.astype(float), book.held.fillna(0.0)


def index_yearly_weights(held: pd.DataFrame, cash_id: str) -> dict:
    yearly = {}
    zero_weight_years = defaultdict(list)
    for year in YEARS:
        sub = held.loc[held.index.year == year]
        if sub.empty:
            continue
        row = {}
        for col in WEIGHT_COLS:
            w = float(sub[col].mean()) if col in sub.columns else 0.0
            row[col] = 100.0 * w
            if w < 1e-9:
                zero_weight_years[col].append(year)
        row["cash"] = 100.0 * float(sub[cash_id].mean()) if cash_id in sub.columns else float("nan")
        yearly[str(year)] = row
    return {"yearly_avg_pct": yearly, "zero_weight_years_by_container": dict(zero_weight_years)}


def first_hold_dates(held: pd.DataFrame, containers: tuple[str, ...]) -> dict:
    out = {}
    for name in containers:
        if name not in held.columns:
            out[name] = None
            continue
        positive = held.index[held[name] > 1e-9]
        out[name] = str(positive[0].date()) if len(positive) else None
    return out


def a1_tradable_2006_07(peer_panel: dict) -> dict:
    peer_cfg = load_peer("A1", "tradable")
    result = run_peer(
        peer_cfg,
        peer_panel["calendar"],
        peer_panel["tradable_levels"],
        cash=peer_panel["cash"],
        carriers=peer_panel["carriers"],
        quotes=peer_panel["tradable_quotes"],
        calendar_closed=True,
        signal_levels=peer_panel["levels"],
    )
    decisions = result.decisions
    rows = []
    for stamp in decisions.index:
        ts = pd.Timestamp(stamp)
        if ts.year not in (2006, 2007):
            continue
        weights = {c: float(decisions.at[stamp, c]) for c in decisions.columns}
        winner = max(weights, key=lambda k: weights[k])
        if weights[winner] < 0.5:
            winner = "mixed"
        rows.append({"month_end": str(ts.date()), "winner": winner, "weights": weights})
    counts = defaultdict(int)
    for row in rows:
        counts[row["winner"]] += 1
    return {
        "n_month_ends": len(rows),
        "counts": dict(counts),
        "detail": rows,
    }


def personality(net: pd.Series) -> dict:
    depth = max_drawdown(net)
    sub = net.loc["2006-01-01":]
    return {
        "cagr_full": cagr(net),
        "cagr_from_2006": cagr(sub) if len(sub) else None,
        "max_drawdown": depth["max_drawdown"],
        "mdd_trough": str(depth["trough"].date()),
    }


def ledger_checks() -> dict:
    rows = list(csv.DictReader(open(D.LEDGER)))
    parsed = [(r, json.loads(r["params"])) for r in rows]
    index_d25_1 = [r for r, p in parsed if p.get("pool") == "index" and p.get("fix") == "D25-1"]
    trad_d25_3 = [r for r, p in parsed if p.get("pool") == "tradable" and p.get("fix") == "D25-3"]
    trad_d25_2 = [r for r, p in parsed if p.get("pool") == "tradable" and p.get("fix") == "D25-2"]
    trad_d24_1 = [r for r, p in parsed if p.get("pool") == "tradable" and p.get("fix") == "D24-1"]
    git_shas = {r.get("git_sha") for r in rows}
    return {
        "ledger_rows": len(rows),
        "index_fix_d25_1": len(index_d25_1),
        "tradable_fix_d25_3": len(trad_d25_3),
        "peer_tradable_fix_d25_2": len(trad_d25_2),
        "tradable_fix_d24_1": len(trad_d24_1),
        "git_shas": sorted(git_shas),
        "git_sha_single": git_shas == {DEV_GIT_SHA},
    }


def main() -> int:
    out: dict = {"design_end": DESIGN_END, "dev_head_note": "Run at Dev PR #132 head for frozen DB"}
    db_sha = require_frozen_db()
    out["db_sha256"] = db_sha
    out["db_sha_matches"] = db_sha == EXPECTED_DB_SHA

    gate_path = ROOT / "results/v4/r5/candidate-gate.csv"
    out["gate_sha256"] = file_sha256(gate_path)
    out["gate_sha_matches"] = out["gate_sha256"] == EXPECTED_GATE_SHA

    inputs = pd.read_csv(ROOT / "results/v4/r5/gate-inputs.csv", parse_dates=["date"]).set_index("date").sort_index()
    states = pd.read_csv(ROOT / "results/v4/r5/month-states.csv", parse_dates=["month_end"]).set_index("month_end")["state"]
    benchmark = inputs["benchmark"].astype(float)
    returns = inputs[list(RUN_ORDER)].astype(float)
    dev_gate = pd.read_csv(gate_path)
    ind_gate = independent_gate(returns, benchmark, states, pool="index")
    dev_impl = candidate_gate(returns, benchmark, states, pool="index")
    out["gate_independent_vs_dev"] = _gate_diff(dev_gate, ind_gate)
    out["gate_dev_impl_vs_independent"] = _gate_diff(dev_impl, ind_gate)
    out["independent_gate_records"] = ind_gate.to_dict(orient="records")
    out["any_candidate_pass"] = any(bool(x) for x in ind_gate["pass"] if x is not None and x == x)

    b0_index = read_net("B0", "index")
    b0_trad = read_net("B0", "tradable")
    final_index = read_net("final", "index")
    out["b0_final_index_identical"] = bool(np.allclose(b0_index.values, final_index.values, rtol=0, atol=0))

    re_net, held = run_b0_index_held()
    spec = load_spec()
    markets = Markets(spec)
    market = markets.get("index", t4=False, allow_substitute=True)
    cash_id = market.cash_id
    out["b0_index_reexec_max_diff"] = float((re_net.reindex(b0_index.index).fillna(0) - b0_index).abs().max())
    out["b0_index_yearly_weights"] = index_yearly_weights(held, cash_id)
    out["b0_index_first_hold"] = first_hold_dates(held, WEIGHT_COLS)

    pub_idx = json.loads((ROOT / "results/v4/r5/design/B0/index/summary.json").read_text())
    pub_tr = json.loads((ROOT / "results/v4/r5/design/B0/tradable/summary.json").read_text())
    pers_idx = personality(b0_index)
    pers_tr = personality(b0_trad)
    out["b0_index_metrics"] = {
        **pers_idx,
        "published_cagr_full": pub_idx["cagr"],
        "published_cagr_from_2006": pub_idx.get("cagr_from_2006"),
        "published_mdd": pub_idx["max_drawdown"],
        "net_sha256": pub_idx["net_sha256"],
        "net_sha256_recomputed": series_sha256(b0_index),
    }
    out["b0_tradable_metrics"] = {
        **pers_tr,
        "published_cagr_full": pub_tr["cagr"],
        "published_cagr_from_2006": pub_tr.get("cagr_from_2006"),
        "published_mdd": pub_tr["max_drawdown"],
        "net_sha256": pub_tr["net_sha256"],
        "net_sha256_recomputed": series_sha256(b0_trad),
    }
    out["vs_orchestrator_diagnostic"] = {
        "orch_cagr_from_2006": ORCH_CAGR_FROM_2006,
        "orch_mdd": ORCH_MDD,
        "reviewer_cagr_from_2006": pers_idx["cagr_from_2006"],
        "reviewer_mdd": pers_idx["max_drawdown"],
        "cagr_gap_pp": 100.0 * (pers_idx["cagr_from_2006"] - ORCH_CAGR_FROM_2006),
        "mdd_gap_pp": 100.0 * (pers_idx["max_drawdown"] - ORCH_MDD),
    }

    groups = container_groups()
    spec = load_spec()
    peer_panel = r5_peers.research_panel(spec)
    census = {}
    for label, kwargs in TRADABLE_RUNS:
        if "peer" in kwargs:
            peer_cfg = load_peer(kwargs["peer"], "tradable")
            result = run_peer(
                peer_cfg,
                peer_panel["calendar"],
                peer_panel["tradable_levels"],
                cash=peer_panel["cash"],
                carriers=peer_panel["carriers"],
                quotes=peer_panel["tradable_quotes"],
                calendar_closed=True,
                signal_levels=peer_panel["levels"],
            )
            census[label] = yearly_census_from_held(
                result.held, peer_cfg.cash_id, peer_panel["carriers"], groups, t4=False,
            )
            if kwargs["peer"] == "A1":
                out["a1_tradable_2006_07"] = a1_tradable_2006_07(peer_panel)
            continue
        kind = kwargs.get("kind", "single")
        job = Job(
            case=kwargs["case"],
            pool="tradable",
            kind=kind,
            t1=kwargs.get("t1", False),
            t2=kwargs.get("t2", False),
            t3=kwargs.get("t3", False),
            t4=kwargs.get("t4", False),
        )
        market_t = D.prepare_market("tradable", t4=kwargs.get("t4", False), allow_substitute=True, spec=spec)
        book = execute(
            market_t, spec, "A", allow_after=False,
            exit_drawdown=job.exit_drawdown, switches=job.switches(),
        )
        census[label] = yearly_census_from_held(
            book.held, market_t.cash_id, market_t.liquidity, groups, t4=kwargs.get("t4", False),
        )
    out["yearly_census"] = census

    con = sqlite3.connect(f"file:{D.DB.MARKET_DB}?mode=ro", uri=True)
    containers = load_containers()
    grouped = build_candidates(con, containers, sse_calendar(con, DESIGN_END), DESIGN_END, us_spdr=())
    out["path_checks"] = []
    for ident, day in PATH_CHECKS:
        day_ts = pd.Timestamp(day)
        rows = grouped.get(ident) or []
        prior = None
        cal = pd.DatetimeIndex(sse_calendar(con, DESIGN_END))
        for d in cal[cal < day_ts]:
            prior = choose_on(rows, d, prior=prior)
        sticky = choose_on(rows, day_ts, prior=prior)
        out["path_checks"].append({
            "container": ident,
            "day": day,
            "path": None if sticky is None else sticky.label,
        })
    chinext_codes = ["050021", "110026", "161022", "160637", "001592", "001593"]
    out["chinext_otc_present"] = [
        c for c in chinext_codes
        if con.execute("SELECT 1 FROM v4_listing WHERE code=?", (c,)).fetchone()
    ]
    con.close()

    out["ledger"] = ledger_checks()
    out["lock_exists"] = (ROOT / "results/v4/LOCK").exists()
    out["gate_inputs_max_date"] = str(inputs.index.max().date())

    out_path = ROOT / "operations/reviews/diag/v4/v4-r5c-d25-review.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "db_ok": out["db_sha_matches"],
        "gate_ok": out["gate_sha_matches"] and out["gate_independent_vs_dev"]["match"],
        "b0_index_cagr_2006": out["b0_index_metrics"]["cagr_from_2006"],
        "b0_index_mdd": out["b0_index_metrics"]["max_drawdown"],
        "b0_tradable_cagr": out["b0_tradable_metrics"]["cagr_full"],
        "any_pass": out["any_candidate_pass"],
        "a1_2006_07": out.get("a1_tradable_2006_07", {}).get("counts"),
    }
    print(json.dumps(summary, indent=2))
    ok = summary["db_ok"] and summary["gate_ok"] and out["b0_index_reexec_max_diff"] < 1e-10
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
