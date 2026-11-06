#!/usr/bin/env python3
"""D37 round 4 Reviewer 独立复算（只读 Dev PR #280 产物 + 重跑 S0 V0）。

用法：
  git fetch origin cursor/d37-r4 main
  git worktree add /tmp/d37-r4-dev-review origin/cursor/d37-r4
  git lfs pull -I data/market.sqlite   # 在 worktree 内

  DEV_WORKTREE=/tmp/d37-r4-dev-review \\
    python operations/reviews/diag/v51/d37-r4-verify.py

写入 operations/reviews/diag/v51/d37-r4-recalc.json。
不修改 Dev 分支、不 push Dev、不覆盖 data/market.sqlite。
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
DEV = Path(os.environ.get("DEV_WORKTREE", "/tmp/d37-r4-dev-review"))
OUT_JSON = ROOT / "operations/reviews/diag/v51/d37-r4-recalc.json"
R3_DAILY = Path(os.environ.get("R3_S0_V0_DAILY", "/tmp/r3-s0-v0-daily.csv"))
RERUN_OUT = Path(os.environ.get("RERUN_OUT", "/tmp/d37-r4-reviewer-rerun"))

sys.path.insert(0, str(DEV))

import src.data.db as DB  # noqa: E402
from src.report.metrics import cagr, max_drawdown  # noqa: E402
from src.v51.diag_stats import performance, trade_cost  # noqa: E402
from src.v4.r5.design import benchmark_returns  # noqa: E402

ART = DEV / "results/v51-diag/d37"
DESIGN_START = "2006-01-04"
DESIGN_END = "2015-12-31"
R3_SHA = "e3af3b5e3cb098ee516cf75bc6e87f9e470dace4df2708489f6cc526fae65eda"
R4_SHA = "d0b947d90b444eb1d874a04df6bcb1974cbea4422b489f214a56c0a658abf0d9"
DEV_HEAD = "665f41a94d2d88f8f786a399f6ae38cc2b954b12"
NEW_SPLICES = ("HSSCNE", "HSIII", "HSHCI", "HSCGSI", "HSHYLV", "HSSI", "DJIA", "FCHI")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_r3_daily() -> None:
    if R3_DAILY.is_file():
        return
    raw = subprocess.check_output(
        ["git", "show", "fac651f:results/v51-diag/d37/S0/检验段/V0/daily.csv"],
        cwd=ROOT,
    )
    R3_DAILY.write_bytes(raw)


def s0_v0_vs_r3() -> dict:
    ensure_r3_daily()
    r3 = pd.read_csv(R3_DAILY, parse_dates=["date"], index_col="date")
    r4 = pd.read_csv(ART / "S0/检验段/V0/daily.csv", parse_dates=["date"], index_col="date")
    shared = r3.index.intersection(r4.index)
    net = (r3.loc[shared, "net"].astype(float) - r4.loc[shared, "net"].astype(float)).abs()
    picks = int(
        (r3.loc[shared, "picks"].fillna("").astype(str) != r4.loc[shared, "picks"].fillna("").astype(str)).sum()
    )
    market = int(
        (r3.loc[shared, "market"].fillna("").astype(str) != r4.loc[shared, "market"].fillna("").astype(str)).sum()
    )
    return {
        "method": "fac651f S0/V0/daily.csv vs #280 artifacts",
        "days": int(len(shared)),
        "net_max_abs_diff": float(net.max()) if len(net) else None,
        "picks_differ": picks,
        "market_differ": market,
        "pass": bool(len(shared) == 2611 and float(net.max()) == 0.0 and picks == 0 and market == 0),
    }


def rerun_s0_v0() -> dict:
    from src.v51 import diag_d37 as d37  # noqa: E402

    import shutil

    DB.MARKET_DB = DEV / "data/market.sqlite"
    if RERUN_OUT.exists():
        shutil.rmtree(RERUN_OUT)
    RERUN_OUT.mkdir(parents=True)
    d37.OUT = RERUN_OUT
    problems = d37.run_cn("检验段", ["V0"], ["S0"], bitmatch=False)
    new = pd.read_csv(RERUN_OUT / "S0/检验段/V0/daily.csv", parse_dates=["date"], index_col="date")
    ensure_r3_daily()
    r3 = pd.read_csv(R3_DAILY, parse_dates=["date"], index_col="date")
    shared = new.index.intersection(r3.index)
    net = (new.loc[shared, "net"].astype(float) - r3.loc[shared, "net"].astype(float)).abs()
    return {
        "method": "run_cn on #280 DB vs fac651f daily",
        "days": int(len(shared)),
        "net_max_abs_diff": float(net.max()) if len(net) else None,
        "diag_bitmatch_problems": problems,
        "pass": float(net.max()) == 0.0 if len(net) else False,
    }


def recalc_s1_cells(bm: pd.Series) -> tuple[dict, bool]:
    cells: dict = {}
    all_match = True
    for version in ("V0", "V1", "V2", "V3", "V4"):
        folder = ART / "S1/检验段" / version
        daily = pd.read_csv(folder / "daily.csv", parse_dates=["date"], index_col="date")
        dev_stats = json.loads((folder / "stats.json").read_text(encoding="utf-8"))
        net = daily["net"].astype(float)
        perf = performance(net, bm)
        cost = trade_cost(daily, "检验段")
        reviewer = {
            "ann": perf["ann"],
            "max_drawdown": perf["max_drawdown"],
            "trades_per_year": cost["trades_per_year"],
            "cost_per_year": cost["cost_per_year"],
        }
        dev_p = dev_stats["performance"]
        match = {
            "ann": abs(reviewer["ann"] - dev_p["ann"]) < 1e-9,
            "max_drawdown": abs(reviewer["max_drawdown"] - dev_p["max_drawdown"]) < 1e-9,
            "trades_per_year": abs(reviewer["trades_per_year"] - dev_p["trades_per_year"]) < 0.05,
            "cost_per_year": abs(reviewer["cost_per_year"] - dev_p["cost_per_year"]) < 0.0005,
        }
        if not all(match.values()):
            all_match = False
        cells[f"S1/检验段/{version}"] = {"reviewer": reviewer, "dev": {k: dev_p[k] for k in reviewer}, "match": match}
    return cells, all_match


def splice_db_checks() -> list[dict]:
    roster = pd.read_csv(ART / "s1-splice-roster.csv")
    effect = pd.read_csv(ART / "s1-container-effect-检验段.csv")
    con = sqlite3.connect(f"file:{DEV / 'data/market.sqlite'}?mode=ro", uri=True)
    rows = []
    for code in NEW_SPLICES:
        meta = roster[roster["bars_code"] == code].iloc[0]
        pub = str(meta["publish_date"])
        fl = str(meta["first_list"])
        before = int(
            con.execute(
                "SELECT COUNT(*) FROM bars WHERE code=? AND adj='raw' AND date<?", (code, pub)
            ).fetchone()[0]
        )
        after_list = int(
            con.execute(
                "SELECT COUNT(*) FROM bars WHERE code=? AND adj='raw' AND date>=?", (code, fl)
            ).fetchone()[0]
        )
        eff = effect[effect["bars_code"] == code].iloc[0]
        pub_ts = pd.Timestamp(pub)
        score = eff.get("first_scoreable_post")
        score_ok = bool(pd.Timestamp(score) >= pub_ts) if score and str(score) != "nan" else None
        rows.append(
            {
                "code": code,
                "publish_date": pub,
                "first_list": fl,
                "bars_before_publish": before,
                "bars_on_or_after_first_list": after_list,
                "first_scoreable_post": score,
                "first_score_on_or_after_publish": score_ok,
                "hold_days_post": int(eff.get("hold_days_post") or 0),
                "contribution_post": float(eff.get("contribution_post") or 0),
            }
        )
    con.close()
    return rows


def plan_b_check() -> dict:
    b_dir = ART / "S0/设计期/B"
    s12 = DEV / "results/v5.1/robustness/S12"
    present = b_dir.is_dir() and (b_dir / "daily.csv").is_file()
    out: dict = {"present": present, "other_cells_present": []}
    for scope, seg in [("S0", "别的市场"), ("S0", "检验段"), ("S1", "检验段")]:
        p = ART / scope / seg / "B"
        if p.is_dir() and (p / "daily.csv").is_file():
            out["other_cells_present"].append(f"{scope}/{seg}/B")
    if not present:
        return out
    d_b = pd.read_csv(b_dir / "daily.csv", parse_dates=["date"], index_col="date").loc[DESIGN_START:DESIGN_END]
    d_s = pd.read_csv(s12 / "daily.csv", parse_dates=["date"], index_col="date").loc[DESIGN_START:DESIGN_END]
    dec_b = pd.read_csv(b_dir / "decisions.csv")
    dec_s = pd.read_csv(s12 / "decisions.csv")
    out["decisions_cells_diff"] = int(((dec_b != dec_s) & ~(dec_b.isna() & dec_s.isna())).sum().sum())
    shared = d_b.index.intersection(d_s.index)
    diffs = {}
    for col in ("net", "buy", "sell", "cost"):
        ad = (d_b.loc[shared, col].astype(float) - d_s.loc[shared, col].astype(float)).abs()
        diffs[col] = {"days": int((ad > 1e-9).sum()), "max": float(ad.max())}
    out["daily_diff_vs_s12"] = diffs
    out["reviewer_ann"] = cagr(d_b["net"].astype(float))
    out["reviewer_mdd"] = max_drawdown(d_b["net"].astype(float))["max_drawdown"]
    out["s12_ann"] = cagr(d_s["net"].astype(float))
    out["s12_mdd"] = max_drawdown(d_s["net"].astype(float))["max_drawdown"]
    dev_stats = json.loads((b_dir / "stats.json").read_text(encoding="utf-8"))
    out["dev_ann"] = dev_stats["performance"]["ann"]
    out["dev_mdd"] = dev_stats["performance"]["max_drawdown"]
    out["ann_match_dev"] = abs(out["reviewer_ann"] - out["dev_ann"]) < 1e-9
    return out


def main() -> int:
    db_path = DEV / "data/market.sqlite"
    db_sha = sha256_file(db_path) if db_path.is_file() else None
    bm = benchmark_returns(end="2026-09-30", allow_after=True)
    s1_cells, s1_ok = recalc_s1_cells(bm)
    payload = {
        "diagnostic": "D37-r4",
        "counts_toward_gate": False,
        "dev_pr_head": DEV_HEAD,
        "dev_pr": 280,
        "db_sha256": {
            "dev_worktree": db_sha,
            "expected_r4_after": R4_SHA,
            "main_r3_after": R3_SHA,
            "sha_match_dev_claim": db_sha == R4_SHA,
        },
        "s0_v0_vs_r3": s0_v0_vs_r3(),
        "s0_v0_rerun": rerun_s0_v0(),
        "s1_inspection_recalc": s1_cells,
        "s1_all_match_dev": s1_ok,
        "round4_splice_db_checks": splice_db_checks(),
        "plan_b": plan_b_check(),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
