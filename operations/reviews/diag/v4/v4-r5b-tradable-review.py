#!/usr/bin/env python3
"""Independent v4-R5b D24 U-tradable review (PR #126). Design period only."""
from __future__ import annotations

import csv
import hashlib
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
from src.v4.engine.carriers import build_candidates, choose_on, choose_path, sse_calendar
from src.v4.r5 import design as D
from src.v4.r5.design import Job, file_sha256, read_net, require_frozen_db, series_sha256
from src.v4.engine.pool import US_SECTORS
from src.v4.peers import load_peer, run_peer
from src.v4.r5 import peers as r5_peers

DESIGN_END = "2015-12-31"
YEARS = list(range(2005, 2016))
EXPECTED_GATE_SHA = "32058828326f5155ce9b9a678746d2f55d7a4a023b3d20a883e01676383c1b42"
EXPECTED_DB_SHA = "79ae5a47e1a6eb0977a18f13efb21211d24b48e393ad567f615130d89c8f00cd"
INDEX_NET_SHA = json.loads(
    (ROOT / "operations/reviews/diag/v4/v4-r5-gate-scorecard-recompute.json").read_text()
)["b0_index_series_sha256"]
OTC_SPOT = ("050002", "040046", "050025", "000071", "160416")
PATH_CHECKS = (
    ("csi300", "2006-06-30"),
    ("hsi", "2012-12-31"),
    ("ndx100", "2013-12-31"),
    ("gold", "2013-12-31"),
    ("theme-标普全球石油指数", "2012-12-31"),
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


def container_groups() -> dict[str, str]:
    out = {}
    for row in load_containers():
        cid = str(row.get("id") or "")
        out[cid] = GROUP.get(str(row.get("asset_class") or ""), str(row.get("asset_class") or ""))
    for row in csv.DictReader(open(ROOT / "results/v4/diag/data-board/out/containers.csv")):
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


def otc_spot_check(con: sqlite3.Connection) -> list[dict]:
    rows = []
    for code in OTC_SPOT:
        listing = con.execute(
            "SELECT code, name, maps_to, tracked_index, inception, enhanced FROM v4_listing WHERE code=?",
            (code,),
        ).fetchone()
        nav = con.execute(
            "SELECT date, close FROM v4_series WHERE code=? AND kind='otc_nav' AND close>0 AND date<=? "
            "ORDER BY date DESC LIMIT 6",
            (code, DESIGN_END),
        ).fetchall()
        nav = sorted(nav, key=lambda r: r[0])
        rets = []
        for i in range(1, len(nav)):
            prev, cur = float(nav[i - 1][1]), float(nav[i][1])
            if prev > 0:
                rets.append((nav[i][0], cur / prev - 1.0))
        rows.append(
            {
                "code": code,
                "listing": None
                if listing is None
                else dict(
                    zip(
                        ("code", "name", "maps_to", "tracked_index", "inception", "enhanced"),
                        listing,
                    )
                ),
                "nav_sample": [{"date": d, "value": v} for d, v in nav[-5:]],
                "daily_returns": [{"date": d, "ret": r} for d, r in rets[-5:]],
            }
        )
    return rows


def explain_choice(grouped, identity: str, day: str) -> dict:
    day_ts = pd.Timestamp(day)
    rows = grouped.get(identity) or []
    calendar = sse_calendar(
        sqlite3.connect(f"file:{D.DB.MARKET_DB}?mode=ro", uri=True), DESIGN_END
    )
    cal = pd.DatetimeIndex(calendar)
    prior = None
    for d in cal[cal < day_ts]:
        prior = choose_on(rows, d, prior=prior)
    sticky = choose_on(rows, day_ts, prior=prior)
    same_day = choose_on(rows, day_ts, prior=None)
    ready = []
    for item in rows:
        if day_ts in item.available.index and bool(item.available.at[day_ts]):
            ready.append(
                dict(code=item.code, tier=item.tier, vehicle=item.vehicle, inception=item.inception)
            )
    def _tier(choice):
        if choice is None:
            return None
        for item in ready:
            if item["code"] == choice.code and item["vehicle"] == choice.vehicle:
                return item["tier"]
        for item in rows:
            if item.code == choice.code and item.vehicle == choice.vehicle:
                return item.tier
        return None

    return {
        "container": identity,
        "day": day,
        "sticky_path": None if sticky is None else sticky.label,
        "choices_on": None if same_day is None else same_day.label,
        "sticky_tier": _tier(sticky),
        "choices_on_tier": _tier(same_day),
        "ready_candidates": ready,
        "sticky_matches_choices_on": sticky == same_day,
    }


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
            elif liq is not None and name in liq:
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


def run_single_tradable(case: str, *, t1=False, t2=False, t3=False, t4=False, kind="single"):
    spec = load_spec()
    job = Job(case=case, pool="tradable", kind=kind, t1=t1, t2=t2, t3=t3, t4=t4)
    market = D.prepare_market("tradable", t4=t4, allow_substitute=True, spec=spec)
    book = execute(
        market,
        spec,
        "A",
        allow_after=False,
        exit_drawdown=job.exit_drawdown,
        switches=job.switches(),
    )
    return market, book


def run_peer_tradable(peer: str, panel: dict):
    peer_cfg = load_peer(peer, "tradable")
    result = run_peer(
        peer_cfg,
        panel["calendar"],
        panel["tradable_levels"],
        cash=panel["cash"],
        carriers=panel["carriers"],
        quotes=panel["tradable_quotes"],
        calendar_closed=True,
    )
    return result


def index_hashes() -> dict:
    expected_path = ROOT / "operations/work_logs/2026-10-29-v4-r5-design-runs.md"
    out = {}
    for path in sorted((ROOT / "results/v4/r5/design").glob("*/index/summary.json")):
        case = path.parts[-3]
        published = json.loads(path.read_text())["net_sha256"]
        net = read_net(case, "index")
        recomputed = series_sha256(net)
        out[case] = {
            "published": published,
            "recomputed": recomputed,
            "published_matches_recomputed": published == recomputed,
            "unchanged_from_pre_d24_b0": published == INDEX_NET_SHA if case in ("B0", "final") else None,
        }
    return out


def ledger_checks() -> dict:
    rows = list(csv.DictReader(open(D.LEDGER)))
    tradable = [r for r in rows if '"pool": "tradable"' in r["params"].replace('""', '"')]
    index_rows = [r for r in rows if '"pool": "index"' in r["params"].replace('""', '"')]
    fix_rows = [r for r in tradable if "D24-1" in r["params"]]
    return {
        "ledger_rows": len(rows),
        "tradable_rows": len(tradable),
        "index_rows": len(index_rows),
        "tradable_with_fix_d24_1": len(fix_rows),
        "ledger_sha256": file_sha256(D.LEDGER),
    }


def main() -> int:
    out: dict = {"design_end": DESIGN_END}
    db_sha = require_frozen_db()
    out["db_sha256"] = db_sha
    out["db_sha_matches"] = db_sha == EXPECTED_DB_SHA

    gate_path = ROOT / "results/v4/r5/candidate-gate.csv"
    out["gate_sha256"] = file_sha256(gate_path)
    out["gate_sha_matches"] = out["gate_sha256"] == EXPECTED_GATE_SHA
    out["gate_file_exists"] = gate_path.is_file()

    con = sqlite3.connect(f"file:{D.DB.MARKET_DB}?mode=ro", uri=True)
    out["otc_spot_check"] = otc_spot_check(con)
    containers = load_containers()
    grouped = build_candidates(con, containers, sse_calendar(con, DESIGN_END), DESIGN_END, us_spdr=())
    out["path_checks"] = [explain_choice(grouped, ident, day) for ident, day in PATH_CHECKS]
    con.close()

    groups = container_groups()
    spec = load_spec()
    peer_panel = r5_peers.research_panel(spec)
    census = {}
    for label, kwargs in TRADABLE_RUNS:
        if "peer" in kwargs:
            result = run_peer_tradable(kwargs["peer"], peer_panel)
            peer_cfg = load_peer(kwargs["peer"], "tradable")
            census[label] = yearly_census_from_held(
                result.held,
                peer_cfg.cash_id,
                peer_panel["carriers"],
                groups,
                t4=False,
            )
            continue
        market, book = run_single_tradable(**kwargs)
        t4 = kwargs.get("t4", False)
        census[label] = yearly_census_from_held(
            book.held, market.cash_id, market.liquidity, groups, t4=t4
        )

    out["yearly_census"] = census

    net = read_net("B0", "tradable")
    net = net.loc[:DESIGN_END]
    pub = json.loads((ROOT / "results/v4/r5/design/B0/tradable/summary.json").read_text())
    out["b0_tradable_recompute"] = {
        "cagr": cagr(net),
        "mdd": max_drawdown(net)["max_drawdown"],
        "published_cagr": pub["cagr"],
        "published_mdd": pub["max_drawdown"],
        "net_sha256_published": pub["net_sha256"],
        "net_sha256_recomputed": series_sha256(net),
    }

    out["index_net_hashes"] = index_hashes()
    out["ledger"] = ledger_checks()

    chinext_otc = ["050021", "110026", "161022"]
    con = sqlite3.connect(f"file:{D.DB.MARKET_DB}?mode=ro", uri=True)
    out["chinext_deferred"] = {
        "codes_checked": chinext_otc,
        "present_in_v4_listing": [
            c
            for c in chinext_otc
            if con.execute("SELECT 1 FROM v4_listing WHERE code=?", (c,)).fetchone()
        ],
    }
    con.close()

    out_path = ROOT / "operations/reviews/diag/v4/v4-r5b-tradable-review.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(
        {
            "db_ok": out["db_sha_matches"],
            "gate_ok": out["gate_sha_matches"],
            "b0_cagr": out["b0_tradable_recompute"]["cagr"],
            "b0_mdd": out["b0_tradable_recompute"]["mdd"],
            "ledger_rows": out["ledger"]["ledger_rows"],
            "index_cases": len(out["index_net_hashes"]),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
