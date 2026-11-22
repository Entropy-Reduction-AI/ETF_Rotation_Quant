#!/usr/bin/env python3
"""D38 r54–55 @ PR #332 / #333：登记序、脚本重跑、登记规则抽查、判据核对。"""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
FFP = CACHE / "49_Industry_Portfolios.csv"
DTB3 = ROOT / "results/v5/other-market/raw/DTB3.csv"
SQLITE = ROOT / "data/market.sqlite"
LOCK = ROOT / "results/v5/LOCK"
OUT = HERE / "d38-r54-55-recalc.json"
PY = ROOT / ".venv/bin/python"

MAIN_TIP = "4b3b533c7e0d8788d5814092c884c6bd1f85a1af"
ROW54_REG = "533ebe979063177cee6b29bdace963f68d6f9aec"
ROW54_RES = "1206a458a4198f131e9b65a2107119ef93072082"
ROW55_REG = "bd96c8a4f2ae382b6a5205bfa0097ee01dea733e"
ROW55_RES = "e43cfa33e332328b77c35b9c19b4ec463ed6e328"

ROW54_ARTIFACTS = [
    "scripts/preflight/a_reactive.py",
    "results/v6-preflight/a-reactive.json",
]
ROW55_ARTIFACTS = [
    "scripts/preflight/a_decompose.py",
    "results/v6-preflight/a-decompose-step1.json",
    "results/v6-preflight/a-decompose.json",
]
ROW55_UNIQUE_VS_1206 = [
    "operations/planning/2026-11-16-d38-project-diagnosis-and-preflight.md",
    "scripts/preflight/a_decompose.py",
    "results/v6-preflight/a-decompose-step1.json",
    "results/v6-preflight/a-decompose.json",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_cat(sha: str, path: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{sha}:{path}"], cwd=ROOT, capture_output=True).returncode == 0


def commit_meta(sha: str) -> dict:
    auth = subprocess.check_output(
        ["git", "log", "-1", "--format=%H|%P|%ai|%ci|%s", sha], cwd=ROOT, text=True
    ).strip()
    h, parent, author, committer, subj = auth.split("|", 4)
    stat = subprocess.check_output(["git", "show", "--stat", "--oneline", sha], cwd=ROOT, text=True)
    planning_only = (
        "operations/planning" in stat
        and "results/" not in stat
        and "scripts/" not in stat
        and "docs/artifact" not in stat
    )
    return {
        "full": h,
        "parent": parent,
        "author_date": author,
        "committer_date": committer,
        "subject": subj,
        "planning_only": planning_only,
    }


def json_body_hash(raw: bytes) -> str:
    s = raw.decode("utf-8")
    if s.endswith("\n"):
        s = s[:-1]
    return hashlib.sha256(s.encode()).hexdigest()


def run_cmd(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)


def audit_row54(reactive: dict) -> dict:
    l1 = reactive["A 股 10 个一级行业 2006-01 → 2015-11"]
    theme = reactive["主题池（按发布日截断）2011-08 → 2015-11"]
    phases = l1["分阶段：对 B0 的差（每年点）"]
    b2_wins = sum(1 for v in phases.values() if v.get("B2 − B0", 0) > 0)
    sell_fly = l1.get("反对意见 ③ 卖飞：卖掉后当月剩余时间仍跑赢池中位数的比例")
    return {
        "B1_L1_vs_EW_pts": l1["B1"]["对等权全部 每年点"],
        "B1_L1_cost_per_year": l1["B1"]["每年成本点"],
        "B2_minus_B0_L1_ew": round(l1["B2"]["对等权全部 每年点"] - l1["B0"]["对等权全部 每年点"], 1),
        "B2_minus_B0_theme_ew": round(theme["B2"]["对等权全部 每年点"] - theme["B0"]["对等权全部 每年点"], 1),
        "B2_phase_wins_out_of_5": b2_wins,
        "sell_fly_beat_median_ratio": sell_fly,
        "pr332_half_rebound_wording_note": sell_fly is not None and sell_fly < 0.5,
        "keep_B0_implied": b2_wins < 3,
    }


def audit_row55(decomp: dict, script: str) -> dict:
    p1 = decomp["P1 沪深300 + 10 个一级行业 2006-01 → 2015-11"]
    p2 = decomp["P2 官方池 2011-08 → 2015-11"]
    crit = decomp["C1 判据"]
    phases_win = int(p1["C1 好于 B0 的阶段数"].split(" / ")[0])
    c1_t = p1["C1"]["对等权 t"] or 0
    c1_b0_p1 = p1["C1"]["对 B0 每年点"]
    c1_b0_p2 = p2["C1"]["对 B0 每年点"]
    return {
        "implementation_C1_top_half_ceil": "math.ceil(len(m) / 2)" in script,
        "implementation_C1_lowest_ID": "sort_values(['id', 'm'], ascending=[True, False])" in script,
        "implementation_C2_overnight_nlargest": "rule == 'C2'" in script and "nlargest(N)" in script,
        "implementation_MINDAYS_200": "MINDAYS = 200" in script,
        "implementation_bars_cutoff_2015": "date<='2015-12-31'" in script,
        "P1_C1_beats_B0_phases": phases_win,
        "P1_C1_vs_EW_t": c1_t,
        "P1_C1_vs_B0_pts": c1_b0_p1,
        "P2_C1_vs_B0_pts": c1_b0_p2,
        "criteria_from_json": crit,
        "stop_rule_triggered": crit.get("换规则") is False and crit.get("P1、P2 对 B0 同为正") is False,
        "C2_section_marked_preliminary": "初步" in decomp.get("说明", ""),
    }


def main() -> int:
    report: dict = {
        "subject_head_row55": ROW55_RES,
        "subject_head_row54": ROW54_RES,
        "main_tip": MAIN_TIP,
        "inputs": {},
        "commit_order": {},
        "registration_order_proof": {},
        "row55_unique_files_vs_1206a458": {},
        "rerun": {},
        "implementation_audit": {},
        "claims_row54": {},
        "claims_row55": {},
        "invariants": {},
        "decision_inputs": {},
    }

    for label, path, expected in [
        ("french_49_csv", FFP, "633958bf36d25da6d95876bfc468536029db600c32c65b7a3e0f7fba59a04609"),
        ("dtb3_csv", DTB3, "29fe11e20522b4d293cdbbbfd37f2862264692519a251e712747a8532ee95a00"),
        ("market_sqlite", SQLITE, "79ba7780f7f5304d189bc49bd7dda9ff1e6325c88888165d71a0c9fae7c26a52"),
    ]:
        p = Path(path)
        got = sha256(p) if p.is_file() else None
        report["inputs"][label] = {
            "path": str(p),
            "sha256": got,
            "matches_prior_signed": got == expected if got else False,
        }

    if not FFP.is_file():
        print(f"Missing French CSV at {FFP} (Ken French 49_Industry_Portfolios_CSV.zip)", file=sys.stderr)
        return 2

    for key, sha in (
        ("row54_reg", ROW54_REG),
        ("row54_res", ROW54_RES),
        ("row55_reg", ROW55_REG),
        ("row55_res", ROW55_RES),
    ):
        report["commit_order"][key] = commit_meta(sha)

    co = report["commit_order"]
    report["registration_order_proof"] = {
        "row54_reg_parent_is_main": co["row54_reg"]["parent"].startswith(MAIN_TIP[:8]),
        "row54_reg_planning_only": co["row54_reg"]["planning_only"],
        "row54_artifacts_404_at_reg": {p: not git_cat(ROW54_REG, p) for p in ROW54_ARTIFACTS},
        "row54_res_parent_is_reg": co["row54_res"]["parent"].startswith(ROW54_REG[:8]),
        "row54_reg_before_res_author_time": co["row54_reg"]["author_date"] < co["row54_res"]["author_date"],
        "row55_reg_parent_is_row54_res": co["row55_reg"]["parent"].startswith(ROW54_RES[:8]),
        "row55_reg_planning_only": co["row55_reg"]["planning_only"],
        "row55_artifacts_404_at_reg": {p: not git_cat(ROW55_REG, p) for p in ROW55_ARTIFACTS},
        "row55_res_parent_is_reg": co["row55_res"]["parent"].startswith(ROW55_REG[:8]),
        "row55_reg_before_res_author_time": co["row55_reg"]["author_date"] < co["row55_res"]["author_date"],
    }

    diff_names = subprocess.check_output(
        ["git", "diff", "--name-only", ROW54_RES, ROW55_RES], cwd=ROOT, text=True
    ).strip().splitlines()
    report["row55_unique_files_vs_1206a458"] = {
        "expected": ROW55_UNIQUE_VS_1206,
        "actual": diff_names,
        "exact_set_match": sorted(diff_names) == sorted(ROW55_UNIQUE_VS_1206),
    }

    backups = {
        "a-reactive.json": (ROOT / "results/v6-preflight/a-reactive.json").read_bytes(),
        "a-decompose-step1.json": (ROOT / "results/v6-preflight/a-decompose-step1.json").read_bytes(),
        "a-decompose.json": (ROOT / "results/v6-preflight/a-decompose.json").read_bytes(),
    }
    report["rerun"]["scripts"] = {}

    run_cmd([str(PY), "-I", str(ROOT / "scripts/preflight/a_reactive.py"), str(FFP), str(DTB3)])
    after = (ROOT / "results/v6-preflight/a-reactive.json").read_bytes()
    committed = backups["a-reactive.json"]
    report["rerun"]["scripts"]["a_reactive"] = {
        "semantic_equal": json.loads(committed) == json.loads(after),
        "bytes_unchanged_after_rerun": committed == after,
        "committed_body_sha256": json_body_hash(committed),
    }

    for step, rel, key in (
        ("step1", "results/v6-preflight/a-decompose-step1.json", "a_decompose_step1"),
        ("step2", "results/v6-preflight/a-decompose.json", "a_decompose_step2"),
    ):
        committed = backups[rel.split("/")[-1]]
        run_cmd(
            [str(PY), "-I", str(ROOT / "scripts/preflight/a_decompose.py"), str(FFP), str(DTB3), step]
        )
        after = (ROOT / rel).read_bytes()
        report["rerun"]["scripts"][key] = {
            "step": step,
            "semantic_equal": json.loads(committed) == json.loads(after),
            "bytes_unchanged_after_rerun": committed == after,
            "committed_body_sha256": json_body_hash(committed),
        }

    for rel, b in backups.items():
        (ROOT / "results/v6-preflight" / rel).write_bytes(b)

    reactive = json.loads(backups["a-reactive.json"].decode())
    decomp = json.loads(backups["a-decompose.json"].decode())
    script_text = (ROOT / "scripts/preflight/a_decompose.py").read_text(encoding="utf-8")
    report["claims_row54"] = audit_row54(reactive)
    report["claims_row55"] = audit_row55(decomp, script_text)
    report["implementation_audit"]["v2_ema_same_basket"] = "v2 近似" in (ROOT / "scripts/preflight/a_reactive.py").read_text(
        encoding="utf-8"
    )

    for anchor in (ROW54_REG, ROW55_REG):
        report["invariants"][f"lock_diff_bytes_vs_{anchor[:7]}"] = len(
            subprocess.check_output(["git", "diff", anchor, ROW55_RES, "--", str(LOCK)], cwd=ROOT)
        )
        report["invariants"][f"sqlite_diff_bytes_vs_{anchor[:7]}"] = len(
            subprocess.check_output(["git", "diff", anchor, ROW55_RES, "--", "data/market.sqlite"], cwd=ROOT)
        )

    rerun_ok = all(
        v["semantic_equal"] and v["bytes_unchanged_after_rerun"] for v in report["rerun"]["scripts"].values()
    )
    reg_ok = all(
        v
        for k, v in report["registration_order_proof"].items()
        if not k.endswith("_404_at_reg") and k != "row54_artifacts_404_at_reg" and k != "row55_artifacts_404_at_reg"
    ) and all(report["registration_order_proof"]["row54_artifacts_404_at_reg"].values()) and all(
        report["registration_order_proof"]["row55_artifacts_404_at_reg"].values()
    )
    inputs_ok = all(v["matches_prior_signed"] for v in report["inputs"].values())
    lock_ok = all(v == 0 for v in report["invariants"].values())

    report["decision_inputs"] = {
        "registration_order_ok": reg_ok,
        "rerun_ok": rerun_ok,
        "inputs_ok": inputs_ok,
        "lock_sqlite_unchanged": lock_ok,
        "row54_claims_ok": report["claims_row54"]["keep_B0_implied"]
        and report["claims_row54"]["B1_L1_vs_EW_pts"] == -4.8,
        "row55_stop_rule_ok": report["claims_row55"]["stop_rule_triggered"],
        "row55_unique_files_ok": report["row55_unique_files_vs_1206a458"]["exact_set_match"],
    }

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["decision_inputs"], ensure_ascii=False, indent=2))
    return 0 if all(report["decision_inputs"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())