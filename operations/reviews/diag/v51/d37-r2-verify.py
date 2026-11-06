#!/usr/bin/env python3
"""D37 round 2 Reviewer 独立复算（只读 Dev 产物 + 可选重跑 1a）。

用法（Reviewer 环境示例）：
  git fetch origin cursor/d37-v51-cadence-diag-68d4 main
  git worktree add /tmp/d37-dev-review origin/cursor/d37-v51-cadence-diag-68d4
  git lfs pull -I data/market.sqlite   # 在 worktree 内
  git lfs fetch origin af8edfd -I data/market.sqlite
  cp .git/lfs/objects/16/7d/167d4e39ffab4302e6f55d2b3436b3400ea28b2282cd7f9b9bda644d87c1acf3 /tmp/market-167d4e39.sqlite

  DEV_WORKTREE=/tmp/d37-dev-review SIGNED_DB=/tmp/market-167d4e39.sqlite \\
    python operations/reviews/diag/v51/d37-r2-verify.py

写入 stdout 与 operations/reviews/diag/v51/d37-r2-recalc.json（相对仓库根）。
不修改 data/market.sqlite，不 push Dev 分支。
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
DEV = Path(os.environ.get("DEV_WORKTREE", "/tmp/d37-dev-review"))
SIGNED_DB = Path(os.environ.get("SIGNED_DB", "/tmp/market-167d4e39.sqlite"))
BASELINE_OUT = Path(os.environ.get("BASELINE_OUT", "/tmp/d37-reviewer-baseline-167d4e39"))
OUT_JSON = ROOT / "operations/reviews/diag/v51/d37-r2-recalc.json"

sys.path.insert(0, str(DEV))

import src.data.db as DB  # noqa: E402
import src.v51.diag_d37 as d37  # noqa: E402
from src.report.metrics import cagr, max_drawdown  # noqa: E402
from src.v51.diag_stats import performance, trade_cost  # noqa: E402
from src.v4.r5.design import benchmark_returns  # noqa: E402

ART = DEV / "results/v51-diag/d37"
ONES = DEV / "results/v5/oneshot/index/v5.1-对照"
SIGNED_SHA = "167d4e39ffab4302e6f55d2b3436b3400ea28b2282cd7f9b9bda644d87c1acf3"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_1a() -> dict:
    if not SIGNED_DB.is_file():
        raise FileNotFoundError(SIGNED_DB)
    if sha256_file(SIGNED_DB) != SIGNED_SHA:
        raise ValueError(f"signed db sha mismatch: {SIGNED_DB}")
    DB.MARKET_DB = SIGNED_DB
    d37.OUT = BASELINE_OUT
    problems = d37.run_cn("检验段", ["V0"], ["S0"], bitmatch=True)
    got = pd.read_csv(BASELINE_OUT / "S0/检验段/V0/daily.csv", parse_dates=["date"], index_col="date")
    ref = pd.read_csv(ONES / "net.csv", parse_dates=["date"], index_col="date")
    shared = got.index.intersection(ref.index)
    diff = (got.loc[shared, "net"].astype(float) - ref.loc[shared, "net"].astype(float)).abs()
    max_diff = float(diff.max()) if len(diff) else float("nan")
    return {
        "signed_db_sha256": SIGNED_SHA,
        "git_object": "af8edfd",
        "temp_db": str(SIGNED_DB),
        "rows": int(len(shared)),
        "max_abs_net_diff": max_diff,
        "mismatch_dates": [str(d.date()) for d in diff[diff > 0].index[:20]],
        "diag_bitmatch_problems": problems,
        "pass": max_diff == 0.0 and not problems,
    }


def recalc_cells(bm: pd.Series) -> tuple[dict, bool]:
    cells: dict = {}
    all_match = True
    for scope in ("S0", "S1"):
        for version in ("V0", "V1", "V2", "V3", "V4"):
            folder = ART / scope / "检验段" / version
            daily = pd.read_csv(folder / "daily.csv", parse_dates=["date"], index_col="date")
            dev_stats = json.loads((folder / "stats.json").read_text(encoding="utf-8"))
            net = daily["net"].astype(float)
            perf = performance(net, bm)
            cost = trade_cost(daily, "检验段")
            reviewer = {
                "ann": perf["ann"],
                "max_drawdown": perf["max_drawdown"],
                "trades_per_year": cost["trades_per_year"],
                "turnover_two_way_per_year": cost["turnover_two_way_per_year"],
                "cost_per_year": cost["cost_per_year"],
                "n": perf["n"],
            }
            dev_p = dev_stats["performance"]
            match = {
                "ann": abs(reviewer["ann"] - dev_p["ann"]) < 1e-9,
                "max_drawdown": abs(reviewer["max_drawdown"] - dev_p["max_drawdown"]) < 1e-9,
                "trades_per_year": abs(reviewer["trades_per_year"] - dev_p["trades_per_year"]) < 0.05,
                "turnover_two_way_per_year": abs(reviewer["turnover_two_way_per_year"] - dev_p["turnover_two_way_per_year"]) < 0.05,
                "cost_per_year": abs(reviewer["cost_per_year"] - dev_p["cost_per_year"]) < 0.0005,
            }
            if not all(match.values()):
                all_match = False
            key = f"{scope}/检验段/{version}"
            cells[key] = {
                "reviewer": reviewer,
                "dev": {k: dev_p[k] for k in reviewer if k != "n"},
                "match": match,
            }
    return cells, all_match


def signed_vs_current(got_signed: pd.DataFrame) -> dict:
    current = pd.read_csv(ART / "S0/检验段/V0/daily.csv", parse_dates=["date"], index_col="date")
    ref_state = pd.read_csv(ONES / "state.csv", parse_dates=["date"], index_col="date")
    shared = current.index.intersection(ref_state.index)
    picks_diff = int(
        (current.loc[shared, "picks"].fillna("").astype(str) != ref_state.loc[shared, "picks"].fillna("").astype(str)).sum()
    )
    market_diff = int(
        (current.loc[shared, "market"].fillna("").astype(str) != ref_state.loc[shared, "market"].fillna("").astype(str)).sum()
    )
    bad = current.loc[shared, "picks"].fillna("").astype(str) != ref_state.loc[shared, "picks"].fillna("").astype(str)
    first_pick = str(bad[bad].index[0].date()) if bad.any() else None
    summary = json.loads((ONES / "summary.json").read_text(encoding="utf-8"))
    return {
        "ann_signed_db_rerun": cagr(got_signed["net"].astype(float)),
        "mdd_signed_db_rerun": max_drawdown(got_signed["net"].astype(float))["max_drawdown"],
        "ann_current_db_artifacts": cagr(current["net"].astype(float)),
        "mdd_current_db_artifacts": max_drawdown(current["net"].astype(float))["max_drawdown"],
        "ann_signed_oneshot_summary": float(summary["cagr"]),
        "mdd_signed_oneshot_summary": float(summary["max_drawdown"]),
        "picks_diff_days_vs_signed_oneshot_state": picks_diff,
        "market_diff_days": market_diff,
        "first_picks_diff_date": first_pick,
    }


def s1_spot_check() -> dict:
    db = DEV / "data/market.sqlite"
    roster = pd.read_csv(ART / "s1-splice-roster.csv")
    effect = pd.read_csv(ART / "s1-container-effect-检验段.csv")
    notes_list = json.loads((ART / "s1-splice-notes.json").read_text(encoding="utf-8"))
    notes = {n.get("container_id"): n for n in notes_list if isinstance(n, dict)}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)

    def first_bar(code: str) -> str | None:
        row = con.execute("SELECT MIN(date) FROM bars WHERE code=? AND adj='raw'", (code,)).fetchone()
        return row[0]

    def bars_before_publish(code: str, pub: str) -> int | None:
        if not code or code in ("取不到", "nan") or not pub or pub == "nan":
            return None
        return int(con.execute(
            "SELECT COUNT(*) FROM bars WHERE code=? AND adj='raw' AND date < ?", (code, pub),
        ).fetchone()[0])

    def pack_row(r: pd.Series) -> dict:
        cid = str(r["container_id"])
        pub = str(r.get("publish_date") or "")
        code = str(r.get("bars_code") or "")
        eff = effect[effect["container_id"] == cid]
        eff_row = eff.iloc[0].to_dict() if len(eff) else {}
        first_score = eff_row.get("first_scoreable_post")
        pub_ts = pd.Timestamp(pub) if pub and pub != "nan" else None
        score_ok = None
        if first_score and pub_ts is not None and str(first_score) not in ("", "nan"):
            score_ok = pd.Timestamp(first_score) >= pub_ts
        hold = eff_row.get("first_hold_post")
        if isinstance(hold, float) and pd.isna(hold):
            hold = None
        return {
            "container_id": cid,
            "status": r.get("status"),
            "publish_date": pub,
            "bars_code": code,
            "first_list": str(r.get("first_list") or ""),
            "series_first_in_db": first_bar(code) if code not in ("", "取不到", "nan") else None,
            "bars_strictly_before_publish_in_db": bars_before_publish(code, pub),
            "first_scoreable_post_splice": first_score,
            "first_score_on_or_after_publish": score_ok,
            "first_hold_post": hold,
            "reason_if_not_spliced": str(r.get("reason") or ""),
            "note_status": (notes.get(cid) or {}).get("status"),
        }

    keys = ["费城半导体", "纳斯达克生物科技", "纳斯达克科技市值", "中韩半导体", "海外中国互联网", "港股通高股息", "恒生科技"]
    targets = roster[roster["container_id"].astype(str).apply(lambda s: any(k in s for k in keys))]
    spot = [pack_row(r) for _, r in targets.iterrows()]
    sample_spliced = [pack_row(r) for _, r in roster[roster["status"] == "spliced"].head(8).iterrows()]
    sample_not = [pack_row(r) for _, r in roster[roster["status"] != "spliced"].head(6).iterrows()]
    viol = [x for x in spot + sample_spliced if x.get("first_score_on_or_after_publish") is False]
    con.close()
    return {
        "spliced_count_roster": int((roster["status"] == "spliced").sum()),
        "spot_checks": spot,
        "sample_spliced": sample_spliced,
        "sample_not_spliced": sample_not,
        "publish_date_violations_in_sample": viol,
        "pass_spot_check": len(viol) == 0,
    }


def main() -> int:
    bitmatch = run_1a()
    got_signed = pd.read_csv(BASELINE_OUT / "S0/检验段/V0/daily.csv", parse_dates=["date"], index_col="date")
    DB.MARKET_DB = DEV / "data/market.sqlite"
    bm = benchmark_returns(end="2026-09-30", allow_after=True)
    cells, all_match = recalc_cells(bm)
    payload = {
        "diagnostic": "D37-r2",
        "counts_toward_gate": False,
        "dev_pr_head": "447b5453c89ebb2f3a79ee87bb1961c59566c8c1",
        "1a_signed_db_bitmatch": bitmatch,
        "db_sha256": {
            "signed_167d4e39": SIGNED_SHA,
            "dev_end_round_worktree": sha256_file(DEV / "data/market.sqlite"),
            "main_worktree": sha256_file(ROOT / "data/market.sqlite") if (ROOT / "data/market.sqlite").is_file() else None,
        },
        "signed_vs_current_s0_v0_inspection": signed_vs_current(got_signed),
        "inspection_cells_recalc": cells,
        "inspection_cells_all_match_dev": all_match,
        "s1_publish_spot_check": s1_spot_check(),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
