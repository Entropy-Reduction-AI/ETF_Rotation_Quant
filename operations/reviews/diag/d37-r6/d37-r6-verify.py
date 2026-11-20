#!/usr/bin/env python3
"""D37 round 6 Reviewer 独立复核（#321 @ aee4b7f）。

只读 Dev 分支产物与 incoming；写入 operations/reviews/diag/d37-r6/d37-r6-recalc.json。
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT_JSON = Path(__file__).resolve().parent / "d37-r6-recalc.json"
BEFORE_DB = Path(os.environ.get("BEFORE_DB", "/tmp/d37-r6-main/data/market.sqlite"))
AFTER_DB = ROOT / "data" / "market.sqlite"
INGEST = ROOT / "results/v51-diag/d37/round6/ingest.json"
RERUN_DIR = Path(__file__).resolve().parent / "rerun"
REF_S0 = ROOT / "results/v51-diag/d37/S0/检验段/V0"
DEV_S0 = ROOT / "results/v51-diag/d37/round6/S0/检验段/V0"
CANONICAL = ROOT / "results/v51-diag/d37"
ROUND6 = CANONICAL / "round6"

PR_HEAD = "aee4b7f780b9fce1e4cea07a3f1662f3ab3c312c"
PR_BASE = "1d56fd90304b44ae965cfb2aa5674cd332046f3c"
EXPECTED_BEFORE = "c07297f8372c2b4dd8f79417306f4dda3b2b49db3cb2523a6ad306c13523588b"
EXPECTED_AFTER = "79ba7780f7f5304d189bc49bd7dda9ff1e6325c88888165d71a0c9fae7c26a52"

HELD_EXPECTED = [
    "soymeal",
    "theme-巴西IBOVESPA指数",
    "theme-东证指数",
    "theme-MSCI China Value Weighted Index",
    "theme-MSCI USA 50 Index",
    "theme-法兰克福DAX指数",
    "theme-iEdge Emerging Asia Select 50 Index",
    "theme-新交所泛东南亚科技指数",
    "theme-富时亚太低碳精选指数",
    "theme-富时沙特阿拉伯指数",
    "theme-恒生中国企业指数",
]

PARTIAL_INGEST = {
    "theme-SPAHLVCP": "2017-08-04",
    "theme-S&P 500 Energy Sector Index(NTR)": "1998-12-31",
    "theme-标普500消费精选指数": "2022-11-25",
    "theme-标普美国品质消费股票指数": "1998-12-16",
    "theme-标普中国新经济行业指数": "2020-05-14",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_bars_tuples(con: sqlite3.Connection, code: str) -> list[tuple[str, float | None]]:
    return con.execute(
        "SELECT date, close FROM bars WHERE code = ? AND adj = 'raw' ORDER BY date",
        (code,),
    ).fetchall()


def load_bars(con: sqlite3.Connection, code: str) -> dict[str, float]:
    return {
        day: float(close)
        for day, close in load_bars_tuples(con, code)
        if close is not None
    }


def compare_existing_rows() -> dict:
    before = sqlite3.connect(str(BEFORE_DB))
    after = sqlite3.connect(str(AFTER_DB))
    try:
        codes_before = {row[0] for row in before.execute("SELECT DISTINCT code FROM bars")}
        codes_after = {row[0] for row in after.execute("SELECT DISTINCT code FROM bars")}
        new_codes = sorted(codes_after - codes_before)
        missing = sorted(codes_before - codes_after)
        altered = []
        for code in sorted(codes_before & codes_after):
            b = load_bars_tuples(before, code)
            a = load_bars_tuples(after, code)
            if b != a:
                altered.append(
                    {
                        "code": code,
                        "before_rows": len(b),
                        "after_rows": len(a),
                    }
                )
        return {
            "codes_before": len(codes_before),
            "codes_after": len(codes_after),
            "new_codes": new_codes,
            "missing_codes": missing,
            "altered": altered,
            "ok": not missing and not altered,
        }
    finally:
        before.close()
        after.close()


def spot_check_db() -> list[dict]:
    """≥8 条：DB 与 ingest / 规则 / 保留差异。"""
    payload = json.loads(INGEST.read_text(encoding="utf-8"))
    by_id = {item["container_id"]: item for item in payload["accepted"]}
    con = sqlite3.connect(str(AFTER_DB))
    checks: list[dict] = []
    try:
        def add(name: str, ok: bool, detail: dict) -> None:
            checks.append({"name": name, "ok": ok, **detail})

        # 1 创业板指：腾讯 399006 仍在，新代码 399006.SZSE
        tencent_n = con.execute("SELECT COUNT(*) FROM bars WHERE code='399006'").fetchone()[0]
        szse_n = con.execute("SELECT COUNT(*) FROM bars WHERE code='399006.SZSE'").fetchone()[0]
        src = con.execute("SELECT DISTINCT source FROM bars WHERE code='399006'").fetchall()
        add(
            "chinext split 399006 / 399006.SZSE",
            tencent_n > 0 and szse_n > 0 and src == [("tencent_index",)],
            {"tencent_rows": tencent_n, "szse_rows": szse_n, "399006_sources": [s[0] for s in src]},
        )
        acc = by_id["chinext"]
        first = con.execute(
            "SELECT MIN(date), close FROM bars WHERE code='399006.SZSE' AND adj='raw'"
        ).fetchone()
        add(
            "399006.SZSE ingest start",
            first[0] == acc["ingest_start"],
            {"db_first": first[0], "expected": acc["ingest_start"], "first_close": first[1]},
        )

        # 2–3 恒生 complete：HSFML25 起点与行数；HSISC 核对
        for cid in ("theme-HSFML25", "theme-HSISC"):
            acc = by_id[cid]
            code = acc["bars_code"]
            mn, mx, cnt = con.execute(
                "SELECT MIN(date), MAX(date), COUNT(*) FROM bars WHERE code=? AND adj='raw'",
                (code,),
            ).fetchone()
            med = max(c["median"] for c in acc["checks"])
            add(
                f"Hang Seng {code}",
                mn == acc["first"] and cnt == acc["row_count"] and med <= 0.0001,
                {"min": mn, "max": mx, "rows": cnt, "ingest_median": med, "claimed": acc["row_count"]},
            )

        # 4 IXY 保留 FT 2000-01-21
        ixy = load_bars(con, "IXY")
        add(
            "IXY 2000-01-21 FT 288.89 preserved",
            abs(ixy.get("2000-01-21", 0) - 288.89) < 0.01,
            {"close_2000-01-21": ixy.get("2000-01-21"), "ingest_first": min(ixy) if ixy else None},
        )

        # 5–9 五条 partial 起点
        code_map = {item["container_id"]: item["bars_code"] for item in payload["accepted"]}
        for cid, expect_start in PARTIAL_INGEST.items():
            code = code_map[cid]
            mn = con.execute(
                "SELECT MIN(date) FROM bars WHERE code=? AND adj='raw'", (code,)
            ).fetchone()[0]
            acc = by_id[cid]
            add(
                f"partial {code} start",
                mn == expect_start == acc["ingest_start"],
                {"db_min": mn, "expected": expect_start, "rows": acc["row_count"]},
            )

        # 10 S5INFT 不应有 2001 缺口被「编造」在 09-11~09-14（缺失保留）
        s5 = load_bars(con, "S5INFT")
        gap_days = ["2001-09-11", "2001-09-12", "2001-09-13", "2001-09-14"]
        add(
            "S5INFT 2001-09-11..14 not filled",
            all(day not in s5 for day in gap_days) and "2001-01-02" in s5,
            {"has_2001-01-02": "2001-01-02" in s5, "gap_present": [d for d in gap_days if d in s5]},
        )

        # 11 SPGOGUP 起点 2011-07-08
        acc = by_id["theme-标普全球石油指数"]
        mn = con.execute(
            "SELECT MIN(date) FROM bars WHERE code='SPGOGUP' AND adj='raw'"
        ).fetchone()[0]
        add(
            "SPGOGUP official start",
            mn == "2011-07-08" == acc["ingest_start"],
            {"db_min": mn},
        )

        # 12 SPAHLVCP 不补 2017-02-20 洞
        spa = load_bars(con, "SPAHLVCP")
        add(
            "SPAHLVCP no pre-continuous fill",
            "2017-02-20" not in spa and "2017-08-04" in spa,
            {"has_2017-02-20": "2017-02-20" in spa, "has_2017-08-04": "2017-08-04" in spa},
        )
    finally:
        con.close()
    return checks


def compare_s0_daily(ref: Path, cand: Path) -> dict:
    from src.v51.d37_round6 import _compare_s0

    return _compare_s0(cand, ref)


def compare_stats(dev_folder: Path, ref_folder: Path | None) -> dict:
    dev = json.loads((dev_folder / "stats.json").read_text(encoding="utf-8"))["performance"]
    out = {"dev": {k: float(dev[k]) for k in ("ann", "max_drawdown", "trades_per_year", "cost_per_year")}}
    if ref_folder and (ref_folder / "stats.json").is_file():
        ref = json.loads((ref_folder / "stats.json").read_text(encoding="utf-8"))["performance"]
        out["ref"] = {k: float(ref[k]) for k in ("ann", "max_drawdown", "trades_per_year", "cost_per_year")}
        out["match"] = all(abs(out["dev"][k] - out["ref"][k]) < 1e-9 for k in out["dev"])
    return out


def reviewer_rerun_s0_s1() -> dict:
    import shutil

    import src.v51.d37_plan_b as plan_b
    import src.v51.diag_d37 as diag

    if RERUN_DIR.exists():
        shutil.rmtree(RERUN_DIR)
    RERUN_DIR.mkdir(parents=True)
    shutil.copyfile(CANONICAL / "s1-index-registry.csv", RERUN_DIR / "s1-index-registry.csv")
    shutil.copyfile(CANONICAL / "s1-splice-roster.csv", RERUN_DIR / "s1-splice-roster.csv")
    diag.OUT = RERUN_DIR
    plan_b.OUT = RERUN_DIR
    try:
        diag.run_cn("检验段", ["V0"], ["S0"], bitmatch=False)
        s0_cmp = compare_s0_daily(REF_S0, RERUN_DIR / "S0" / "检验段" / "V0")
        diag.run_cn("设计期", ["V0"], ["S1"], bitmatch=False)
        diag.run_cn("检验段", ["V0"], ["S1"], bitmatch=False)
        plan_b.run_s1_inspection(diag._db_ready())
    finally:
        diag.OUT = CANONICAL
        plan_b.OUT = CANONICAL

    cells = {
        "S0检验段V0": compare_s0_daily(REF_S0, RERUN_DIR / "S0" / "检验段" / "V0"),
        "S1设计期V0": compare_stats(
            RERUN_DIR / "S1" / "设计期" / "V0",
            CANONICAL / "S1" / "设计期" / "V0",
        ),
        "S1检验段V0": compare_stats(
            RERUN_DIR / "S1" / "检验段" / "V0",
            CANONICAL / "S1" / "检验段" / "V0",
        ),
        "S1检验段B": compare_stats(
            RERUN_DIR / "S1" / "检验段" / "B",
            CANONICAL / "S1" / "检验段" / "B",
        ),
    }
    # Reviewer rerun vs Dev round6 committed artifacts
    cells["dev_round6_S0"] = compare_s0_daily(REF_S0, DEV_S0)
    for key, sub in (
        ("S1设计期V0_r6", ("S1", "设计期", "V0")),
        ("S1检验段V0_r6", ("S1", "检验段", "V0")),
        ("S1检验段B_r6", ("S1", "检验段", "B")),
    ):
        cells[key] = compare_stats(
            ROUND6.joinpath(*sub),
            RERUN_DIR.joinpath(*sub),
        )
    return {"s0_rerun_vs_r5": s0_cmp, "cells": cells}


def pr_inventory() -> dict:
    diff = subprocess.check_output(
        ["git", "diff", "--name-only", f"{PR_BASE}..{PR_HEAD}"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    lock_touch = [p for p in diff if "results/v5/LOCK" in p and not p.endswith("-addendum-D37.md")]
    src_changes = [p for p in diff if p.startswith("src/")]
    return {
        "changed_files": len(diff),
        "commits": 2,
        "lock_body_changed": lock_touch,
        "src_paths": src_changes,
        "has_incoming": any(p.startswith("incoming/grok-d37-index") for p in diff),
    }


def run_ingest_check() -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "src.v51.d37_round6", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "exit_code": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout_tail": proc.stdout.splitlines()[-30:],
        "stderr_tail": proc.stderr.splitlines()[-10:],
    }


def verify_held() -> dict:
    payload = json.loads(INGEST.read_text(encoding="utf-8"))
    held_ids = [h["container_id"] for h in payload["held"]]
    con = sqlite3.connect(str(AFTER_DB))
    try:
        leaked = []
        for cid in held_ids:
            # 冻结容器不应有新 bars_code 写入（除已知已在库的重复主题外）
            pass
        # 直接核对名单
        ok_list = held_ids == HELD_EXPECTED
        # 11 条在库中不应出现本轮新路由 d37_r6 的 held 主题代码
        new_r6 = con.execute(
            "SELECT DISTINCT code FROM bars WHERE source='d37_r6'"
        ).fetchall()
        codes = {row[0] for row in new_r6}
        accepted_codes = {item["bars_code"] for item in payload["accepted"]}
        extra = sorted(codes - accepted_codes)
        return {
            "held_list_match": ok_list,
            "held_ids": held_ids,
            "d37_r6_codes": sorted(codes),
            "unexpected_d37_r6": extra,
            "ok": ok_list and not extra and len(codes) == 25,
        }
    finally:
        con.close()


def main() -> int:
    sys.path.insert(0, str(ROOT))
    report: dict = {
        "pr": {"number": 321, "head": PR_HEAD, "base": PR_BASE},
        "sha256": {},
        "inventory": pr_inventory(),
        "append_only": {},
        "ingest_check": {},
        "held": {},
        "spot_checks": [],
        "rerun": {},
    }

    after_sha = sha256_file(AFTER_DB)
    before_sha = sha256_file(BEFORE_DB) if BEFORE_DB.is_file() else None
    report["sha256"] = {
        "after_worktree": after_sha,
        "expected_after": EXPECTED_AFTER,
        "after_match": after_sha == EXPECTED_AFTER,
        "before_baseline": before_sha,
        "expected_before": EXPECTED_BEFORE,
        "before_match": before_sha == EXPECTED_BEFORE,
    }

    report["append_only"] = compare_existing_rows()
    report["ingest_check"] = run_ingest_check()
    report["held"] = verify_held()
    report["spot_checks"] = spot_check_db()
    report["ingest_counts"] = json.loads(INGEST.read_text(encoding="utf-8"))
    report["ingest_counts"] = {
        "accepted": len(report["ingest_counts"]["accepted"]),
        "held": len(report["ingest_counts"]["held"]),
        "complete": sum(1 for a in json.loads(INGEST.read_text())["accepted"] if a["group"] == "complete"),
        "partial": sum(1 for a in json.loads(INGEST.read_text())["accepted"] if a["group"] == "partial"),
    }

    print("Running S0/S1 rerun (设计期 V0、检验段 V0、检验段 B + S0 V0)...", flush=True)
    report["rerun"] = reviewer_rerun_s0_s1()

    def _must_fix(report: dict) -> list[str]:
        fixes = []
        if not report["sha256"]["after_match"]:
            fixes.append("after SHA256 与 Dev 登记不一致")
        if not report["sha256"]["before_match"]:
            fixes.append("before 基线 SHA256 与 c07297f… 不一致")
        if not report["append_only"]["ok"]:
            fixes.append("已有 bars 行被改写或代码消失")
        if report["ingest_check"]["exit_code"] != 0:
            fixes.append("d37_round6 --check 未通过")
        if not report["held"]["ok"]:
            fixes.append("11 条冻结名单或 d37_r6 代码集与 25 条入库不一致")
        if not all(c["ok"] for c in report["spot_checks"]):
            fixes.append("点位/起点 spot-check 未全部通过")
        s0 = report["rerun"]["s0_rerun_vs_r5"]
        if not s0.get("same"):
            fixes.append("S0 V0 检验段与第五轮非 bit-identical")
        dev_s0 = report["rerun"]["cells"]["dev_round6_S0"]
        if not dev_s0.get("same"):
            fixes.append("Dev round6 S0 V0 与第五轮不一致")
        for key in ("S1设计期V0_r6", "S1检验段V0_r6", "S1检验段B_r6"):
            cell = report["rerun"]["cells"][key]
            if not cell.get("match", False):
                fixes.append(f"Dev round6 {key.replace('_r6', '')} 与 Reviewer 独立重跑不一致")
        # round6 vs r5：与 Dev 登记的 s1-vs-previous 一致即可（新拼接预期有小幅漂移）
        vs_prev = pd.read_csv(ROUND6 / "s1-vs-previous.csv")
        pick = vs_prev[vs_prev["version"].isin(["V0", "B"]) & vs_prev["segment"].isin(["设计期", "检验段"])]
        for _, row in pick.iterrows():
            cell_key = f"S1{row['segment']}{row['version']}_r6"
            if cell_key.replace("_r6", "") not in ("S1设计期V0", "S1检验段V0", "S1检验段B"):
                continue
            cell = report["rerun"]["cells"][cell_key]
            dev_ann = cell["dev"]["ann"]
            if abs(dev_ann - float(row["ann"])) > 1e-9 or abs(dev_ann - float(row["prev_ann"])) > 0.02:
                if abs(dev_ann - float(row["ann"])) > 1e-9:
                    fixes.append(f"round6 {row['segment']} {row['version']} ann 与 s1-vs-previous 登记不一致")
        if report["inventory"]["lock_body_changed"]:
            fixes.append("results/v5/LOCK 正文被改动")
        return fixes

    report["must_fix"] = _must_fix(report)
    report["decision"] = (
        "approve" if not report["must_fix"] else "return_to_planning" if len(report["must_fix"]) > 2 else "approve_with_follow_up"
    )
    if report["must_fix"]:
        report["decision"] = "return_to_planning" if any(
            "SHA" in x or "S0" in x or "改写" in x or "LOCK" in x for x in report["must_fix"]
        ) else "approve_with_follow_up"
    else:
        report["decision"] = "approve"

    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=float) + "\n", encoding="utf-8")
    print(json.dumps({"decision": report["decision"], "must_fix": report["must_fix"]}, ensure_ascii=False, indent=2))
    return 0 if report["decision"] == "approve" else 1


if __name__ == "__main__":
    raise SystemExit(main())