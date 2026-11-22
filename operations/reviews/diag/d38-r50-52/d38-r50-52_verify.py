#!/usr/bin/env python3
"""D38 r50–53 @ PR #330：登记序、四脚本重跑、清单 2.1、第 53 行主张。"""
from __future__ import annotations

import hashlib
import json
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
OUT = HERE / "d38-r50-52-recalc.json"
PY = ROOT / ".venv/bin/python"

SUBJECT = "30185bb03c7d915b19804f00386bf7b11f8df35f"
MAIN_TIP = "982243d9d4445ac0289ff7a665ac74e8b6a6b401"
UNIQUE_START = "ca08b30cb68d6a43e2c61f9aaedd9136f87ded73"

COMMITS = {
    "row50_reg": "ca08b30cb68d6a43e2c61f9aaedd9136f87ded73",
    "row50_res": "9f5b1b8e26bc238934efbf77e99a9705d6b90d1b",
    "row51_52_reg": "26690a5d392570b3e7be5fd0b621e0be420060a0",
    "row51_note1": "131a6db3a3def1ca6859aacedce47f4f4ea92416",
    "row51_note2": "dc09a680572c560c403aba93ea8d1e035a590821",
    "row51_52_res": "4859cb29a3feea878b0601585623aaffbcfd11c2",
    "row53_reg": "09b1d039e40bb35d672c9d3c6074a990c2b0f251",
    "row53_res": SUBJECT,
}

SCRIPTS = [
    ("a_structure", "results/v6-preflight/a-structure.json"),
    ("voi_value", "results/v6-preflight/voi-value.json"),
    ("a_n5", "results/v6-preflight/a-n5.json"),
    ("a_theme_split", "results/v6-preflight/a-theme-split.json"),
]

REG_ARTIFACTS = [
    "results/v6-preflight/a-structure.json",
    "results/v6-preflight/voi-value.json",
    "results/v6-preflight/a-n5.json",
    "results/v6-preflight/a-theme-split.json",
    "scripts/preflight/a_structure.py",
    "scripts/preflight/voi_value.py",
    "scripts/preflight/a_n5.py",
    "scripts/preflight/a_theme_split.py",
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
    planning_only = "operations/planning" in stat and "results/" not in stat and "scripts/" not in stat
    return {
        "full": h,
        "parent": parent,
        "author_date": author,
        "committer_date": committer,
        "author_date_taipei": author.replace("+0000", " UTC → Taipei +8h"),
        "subject": subj,
        "planning_only": planning_only,
        "artifacts_present": {p: git_cat(sha, p) for p in REG_ARTIFACTS},
    }


def json_body_hash(raw: bytes) -> str:
    s = raw.decode("utf-8")
    if s.endswith("\n"):
        s = s[:-1]
    return hashlib.sha256(s.encode()).hexdigest()


def run_preflight(module: str) -> None:
    cmd = [str(PY), "-I", str(ROOT / f"scripts/preflight/{module}.py"), str(FFP), str(DTB3)]
    subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)


def audit_claims(structure: dict, voi: dict, an5: dict, theme: dict) -> dict:
    a10 = structure["① 挑选的空间（2006–2015 月度）"]["A 股 10 个一级行业"]
    us = structure["① 挑选的空间（2006–2015 月度）"]["美国 49 行业"]
    vol_ratio = round(a10["市场月波动%"] / us["市场月波动%"], 2)
    t2 = structure["④ A 股名额前 3 要到 t ≥ 2 需要什么"]
    voi_a = voi["A 股：沪深300 + 10 个一级行业，2009–2015"]
    voi_note = voi["第 51 行补注：A 股名额 +5.3 拆开"]
    voi_us = voi["第 51 行补注 2：美股 前 3 比全市场 拆开（1955–2026）"]
    conv = voi_a["换算（跟踪误差按 16.2% 不变）"]
    now_pts = conv["现在：只用 12−1"]["组合每年点（打折后）"]
    opt = conv["最优权重合起来（按本行比例放大）"]
    inc = round(opt["组合每年点（打折后）"] - now_pts, 2)
    row51_worth_fetch = inc >= 0.3 or opt["119 个月的 t"] >= 1.5
    n3, n5 = an5["A 股选 3 个"], an5["A 股选 5 个"]
    row52_pass = (
        n5["最低剩"] >= n3["最低剩"]
        and (n3["年化"] - n5["年化"]) <= 0.3
        and n5["A 股名额对沪深300：年跟踪误差%"] < n3["A 股名额对沪深300：年跟踪误差%"]
    )
    t_early = theme["2011-08 → 2013-12"]
    t_late = theme["2014-01 → 2015-11"]
    t_full = theme["全段 2011-08 → 2015-11"]
    return {
        "row50_vol_ratio_us_market": vol_ratio,
        "row50_years_for_t2": t2["折合年数"],
        "row51_portfolio_increment": inc,
        "row51_do_not_fetch_valuation": not row51_worth_fetch,
        "row51_ew_full_industry_only": voi_note["等权 10 个一级行业对沪深300（不挑选）"]["全段"]["每年点"],
        "row51_sel_full_industry_only": voi_note["12−1 前 3 对等权基线（真正的挑选，扣成本）"]["全段"]["每年点"],
        "row51_us_sel": voi_us["12−1 前 3 对等权基线（真正的挑选，扣成本）"]["每年点"],
        "row52_recommend_n5": row52_pass,
        "row52_annual_gap": round(n3["年化"] - n5["年化"], 2),
        "row53_full_sel_vs_ew": t_full["② 12−1 前 3 对等权 每年点（扣成本）"],
        "row53_phase_early_sel": t_early["② 12−1 前 3 对等权 每年点（扣成本）"],
        "row53_phase_late_sel": t_late["② 12−1 前 3 对等权 每年点（扣成本）"],
        "row53_claims_match_commit_msg": (
            abs(t_early["② 12−1 前 3 对等权 每年点（扣成本）"] - 16.9) < 0.05
            and abs(t_late["② 12−1 前 3 对等权 每年点（扣成本）"] - (-21.1)) < 0.05
            and abs(t_full["② 12−1 前 3 对等权 每年点（扣成本）"] - 0.1) < 0.05
        ),
    }


def main() -> int:
    report: dict = {
        "subject_head": SUBJECT,
        "subject_tree": subprocess.check_output(["git", "rev-parse", f"{SUBJECT}^{{tree}}"], cwd=ROOT, text=True).strip(),
        "main_tip": MAIN_TIP,
        "unique_work_start": UNIQUE_START,
        "oldest_unique_parent": subprocess.check_output(
            ["git", "rev-parse", f"{UNIQUE_START}^"], cwd=ROOT, text=True
        ).strip(),
        "merge_base_with_main": subprocess.check_output(
            ["git", "merge-base", "origin/main", SUBJECT], cwd=ROOT, text=True
        ).strip(),
        "inputs": {},
        "commit_order": {},
        "registration_order_proof": {},
        "rerun": {},
        "checklist_2_1": {},
        "row53_design_review_touch": {},
        "claims": {},
        "invariants": {},
        "pr_state": {},
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
        print(f"Missing French CSV: {FFP}", file=sys.stderr)
        return 2

    for key, sha in COMMITS.items():
        report["commit_order"][key] = commit_meta(sha)

    report["registration_order_proof"] = {
        "row50_parent_is_main": report["commit_order"]["row50_reg"]["parent"].startswith(MAIN_TIP[:8]),
        "row50_json_absent_at_reg": not git_cat(COMMITS["row50_reg"], "results/v6-preflight/a-structure.json"),
        "row50_res_parent_is_reg": report["commit_order"]["row50_res"]["parent"].startswith(COMMITS["row50_reg"][:8]),
        "row50_reg_before_res_author_time": report["commit_order"]["row50_reg"]["author_date"]
        < report["commit_order"]["row50_res"]["author_date"],
        "voi_absent_at_note2": not git_cat(COMMITS["row51_note2"], "results/v6-preflight/voi-value.json"),
        "an5_absent_at_note2": not git_cat(COMMITS["row51_note2"], "results/v6-preflight/a-n5.json"),
        "note1_before_results_author_time": report["commit_order"]["row51_note1"]["author_date"]
        < report["commit_order"]["row51_52_res"]["author_date"],
        "note2_before_results_author_time": report["commit_order"]["row51_note2"]["author_date"]
        < report["commit_order"]["row51_52_res"]["author_date"],
        "row51_52_res_parent_is_note2": report["commit_order"]["row51_52_res"]["parent"].startswith(
            COMMITS["row51_note2"][:8]
        ),
        "theme_absent_at_row53_reg": not git_cat(COMMITS["row53_reg"], "results/v6-preflight/a-theme-split.json"),
        "theme_script_absent_at_row53_reg": not git_cat(COMMITS["row53_reg"], "scripts/preflight/a_theme_split.py"),
        "row53_reg_before_res_author_time": report["commit_order"]["row53_reg"]["author_date"]
        < report["commit_order"]["row53_res"]["author_date"],
        "row53_res_parent_is_reg": report["commit_order"]["row53_res"]["parent"].startswith(COMMITS["row53_reg"][:8]),
        "no_328_replay": report["oldest_unique_parent"] == MAIN_TIP,
    }

    backups = {rel: (ROOT / rel).read_bytes() for _, rel in SCRIPTS}
    report["rerun"]["scripts"] = {}
    for mod, rel in SCRIPTS:
        committed_raw = backups[rel]
        committed = json.loads(committed_raw.decode())
        run_preflight(mod)
        after_raw = (ROOT / rel).read_bytes()
        after = json.loads(after_raw.decode())
        report["rerun"]["scripts"][mod] = {
            "output_json": rel,
            "semantic_equal": committed == after,
            "bytes_unchanged_after_rerun": committed_raw == after_raw,
            "committed_body_sha256": json_body_hash(committed_raw),
        }
    for rel, b in backups.items():
        (ROOT / rel).write_bytes(b)

    structure = json.loads(backups["results/v6-preflight/a-structure.json"].decode())
    voi = json.loads(backups["results/v6-preflight/voi-value.json"].decode())
    an5 = json.loads(backups["results/v6-preflight/a-n5.json"].decode())
    theme = json.loads(backups["results/v6-preflight/a-theme-split.json"].decode())
    report["claims"] = audit_claims(structure, voi, an5, theme)

    diff_main = subprocess.check_output(
        ["git", "diff", MAIN_TIP, SUBJECT, "--", "docs/reference/strategy-design-review.md"],
        cwd=ROOT,
        text=True,
    )
    diff_row53 = subprocess.check_output(
        ["git", "diff", COMMITS["row51_52_res"], SUBJECT, "--", "docs/reference/strategy-design-review.md"],
        cwd=ROOT,
    )
    report["checklist_2_1"] = {
        "introduced_in_commit": COMMITS["row51_52_res"],
        "change_1_zero_information_value_step": True,
        "change_2_q5_equal_weight_baseline_example": True,
        "diff_vs_main_hunks": diff_main.count("@@"),
        "matches_voi_industry_split": report["claims"]["row51_ew_full_industry_only"] == 4.6
        and report["claims"]["row51_sel_full_industry_only"] == 0.7,
    }
    report["row53_design_review_touch"] = {
        "strategy_design_review_diff_bytes_vs_4859cb2": len(diff_row53),
        "row53_only_forecast_artifacts_theme_json": len(diff_row53) == 0,
    }

    report["invariants"]["lock_diff_bytes_vs_unique_start"] = len(
        subprocess.check_output(["git", "diff", UNIQUE_START, SUBJECT, "--", str(LOCK)], cwd=ROOT)
    )
    report["invariants"]["sqlite_diff_bytes_vs_unique_start"] = len(
        subprocess.check_output(["git", "diff", UNIQUE_START, SUBJECT, "--", "data/market.sqlite"], cwd=ROOT)
    )

    ahead = subprocess.check_output(["git", "rev-list", "--count", f"origin/main..{SUBJECT}"], cwd=ROOT, text=True).strip()
    behind = subprocess.check_output(["git", "rev-list", "--count", f"{SUBJECT}..origin/main"], cwd=ROOT, text=True).strip()
    report["pr_state"] = {
        "commits_on_branch": int(ahead),
        "behind_main": int(behind),
        "mergeable_clean_per_owner": True,
    }

    report["rerun"]["all_semantic_equal"] = all(v["semantic_equal"] for v in report["rerun"]["scripts"].values())
    report["rerun"]["all_bytes_unchanged"] = all(
        v["bytes_unchanged_after_rerun"] for v in report["rerun"]["scripts"].values()
    )
    reg_ok = all(report["registration_order_proof"].values())
    report["decision_inputs"] = {
        "registration_order_ok": reg_ok,
        "rerun_ok": report["rerun"]["all_semantic_equal"],
        "inputs_ok": all(v["matches_prior_signed"] for v in report["inputs"].values()),
        "lock_sqlite_unchanged": report["invariants"]["lock_diff_bytes_vs_unique_start"] == 0
        and report["invariants"]["sqlite_diff_bytes_vs_unique_start"] == 0,
        "row53_claims_ok": report["claims"]["row53_claims_match_commit_msg"],
    }

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    ok = all(report["decision_inputs"].values())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())