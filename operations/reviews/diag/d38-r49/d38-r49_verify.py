#!/usr/bin/env python3
"""D38 r49：独立重跑 a_signals、commit 序、登记规则抽查。"""
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
OUT = HERE / "d38-r49-recalc.json"
PY = ROOT / ".venv/bin/python"
REG = "9db6b0ee816981193d5fecad6d0ddd26885a8dcb"
RES = "f378a7bc6af25714bd03ad555a9feaa953e867cf"
BASE = "092bdc053533c03630fa9c1f3144eb37b534d464"

EXPECTED = {
    "A0_full_net": 5.3,
    "A0_full_t": 1.03,
    "A1_full_net": -2.9,
    "A2_full_net": 5.1,
    "A2_corr_vs_A0": 0.96,
    "A4_net": 1.3,
    "A4_A0_same_months": 7.6,
    "wf_net": 5.5,
    "always_A0": 5.8,
    "PBO": 0.83,
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_cat_ok(rev: str, rel: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{rev}:{rel}"], cwd=ROOT, capture_output=True).returncode == 0


def main() -> int:
    report: dict = {
        "subject_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "dev_pr328_head": RES,
        "inputs": {},
        "implementation_audit": {},
        "commit_order": {},
        "rerun": {},
        "key_figures": {},
    }
    for label, path in [
        ("french_49_csv", FFP),
        ("dtb3_csv", DTB3),
        ("market_sqlite", ROOT / "data/market.sqlite"),
    ]:
        p = Path(path)
        report["inputs"][label] = {
            "path": str(p),
            "sha256": sha256(p) if p.is_file() else None,
            "exists": p.is_file(),
        }

    script = (ROOT / "scripts/preflight/a_signals.py").read_text(encoding="utf-8")
    report["implementation_audit"]["A4_hot_threshold_0_9"] = "> 0.9" in script
    report["implementation_audit"]["CSCV_S_equals_8"] = bool(re.search(r"\bS = 8\b", script))
    report["implementation_audit"]["A3_absent_from_SC_dict"] = "A3" not in script.split("SC = ", 1)[-1].split("\n", 1)[0]
    report["implementation_audit"]["amount_cutoff_2015"] = "2015-12-31" in script

    for sha, tag in ((REG, "registration"), (RES, "results")):
        meta = subprocess.check_output(
            ["git", "log", "-1", "--format=%H|%P|%ai|%ci|%s", sha], cwd=ROOT, text=True
        ).strip().split("|", 4)
        report["commit_order"][tag] = {
            "sha": meta[0],
            "parent": meta[1],
            "author_date": meta[2],
            "committer_date": meta[3],
            "subject": meta[4],
            "has_a_signals_json": git_cat_ok(sha, "results/v6-preflight/a-signals.json"),
            "has_a_signals_py": git_cat_ok(sha, "scripts/preflight/a_signals.py"),
        }
    reg_t = report["commit_order"]["registration"]["committer_date"]
    res_t = report["commit_order"]["results"]["committer_date"]
    report["commit_order"]["registration_strictly_before_results"] = reg_t < res_t
    report["commit_order"]["results_parent_is_registration"] = report["commit_order"]["results"]["parent"].startswith(
        REG[:8]
    )

    if not FFP.is_file():
        print(f"Missing French CSV: {FFP}", file=sys.stderr)
        return 2

    committed_path = ROOT / "results/v6-preflight/a-signals.json"
    committed_bytes = committed_path.read_bytes()
    committed = json.loads(committed_bytes.decode("utf-8"))
    report["rerun"]["committed_bytes_sha256"] = hashlib.sha256(committed_bytes).hexdigest()

    subprocess.run(
        [str(PY), "-I", str(ROOT / "scripts/preflight/a_signals.py"), str(FFP), str(DTB3)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    rerun = json.loads(committed_path.read_text(encoding="utf-8"))
    report["rerun"]["semantic_equal"] = committed == rerun
    report["rerun"]["bytes_unchanged_after_rerun"] = committed_path.read_bytes() == committed_bytes

    j = committed
    report["key_figures"]["A0_full"] = j["各选法"]["A0 12−1"]["全段 2006-01 → 2015-11"]
    report["key_figures"]["A1_full"] = j["各选法"]["A1 6−1"]["全段 2006-01 → 2015-11"]
    report["key_figures"]["A2_full"] = j["各选法"]["A2 风险调整 12−1"]["全段 2006-01 → 2015-11"]
    report["key_figures"]["A4"] = j["各选法"]["A4 12−1 + 拥挤度刹车"]
    report["key_figures"]["walk_forward"] = j["滚动前推（2008–2015）"]
    report["key_figures"]["cscv"] = j["过拟合概率（CSCV，A0–A2，8 段）"]
    report["key_figures"]["A0_A2_corr"] = j["A0–A2 月度净超额相关"]["A0 12−1"]["A2 风险调整 12−1"]

    checks = {
        "A0_full_net": report["key_figures"]["A0_full"]["净超额_点每年"],
        "A0_full_t": report["key_figures"]["A0_full"]["t_净"],
        "A1_full_net": report["key_figures"]["A1_full"]["净超额_点每年"],
        "A2_full_net": report["key_figures"]["A2_full"]["净超额_点每年"],
        "A2_corr_vs_A0": report["key_figures"]["A0_A2_corr"],
        "A4_net": report["key_figures"]["A4"]["发布后可算月份（2012-08 起）"]["净超额_点每年"],
        "A4_A0_same_months": report["key_figures"]["A4"]["对照 A0 同月份"]["净超额_点每年"],
        "wf_net": report["key_figures"]["walk_forward"]["滚动前推净超额_点每年"],
        "always_A0": report["key_figures"]["walk_forward"]["一直用 A0 同期_点每年"],
        "PBO": report["key_figures"]["cscv"]["PBO"],
    }
    report["key_figures"]["match_expected_dev_claims"] = {k: checks[k] == v for k, v in EXPECTED.items()}
    report["key_figures"]["all_claims_match"] = all(report["key_figures"]["match_expected_dev_claims"].values())

    for rel in ("results/v5/LOCK", "data/market.sqlite"):
        diff_len = len(subprocess.check_output(["git", "diff", f"{BASE}..{RES}", "--", rel], cwd=ROOT))
        report.setdefault("pr_scope", {})[rel] = {"diff_bytes": diff_len, "unchanged": diff_len == 0}

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    ok = (
        report["rerun"]["semantic_equal"]
        and report["commit_order"]["registration_strictly_before_results"]
        and not report["commit_order"]["registration"]["has_a_signals_json"]
        and report["commit_order"]["results"]["has_a_signals_json"]
        and report["key_figures"]["all_claims_match"]
        and report["implementation_audit"]["A4_hot_threshold_0_9"]
        and report["implementation_audit"]["CSCV_S_equals_8"]
        and report["pr_scope"]["results/v5/LOCK"]["unchanged"]
        and report["pr_scope"]["data/market.sqlite"]["unchanged"]
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())