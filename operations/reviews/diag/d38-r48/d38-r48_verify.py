#!/usr/bin/env python3
"""D38 r48：独立重跑 a_memory_backfill、D40-10 算术、commit 序证据。"""
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
OUT = HERE / "d38-r48-recalc.json"
PY = ROOT / ".venv/bin/python"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_net_annual(line: str) -> float | None:
    m = re.search(r"净\s*([+−-]?\d+\.?\d*)\s*点", line)
    if not m:
        return None
    return float(m.group(1).replace("−", "-"))


def main() -> int:
    report: dict = {
        "subject_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "inputs": {},
        "rerun": {},
        "d40_10": {},
        "commit_order": {},
    }
    for label, path in [
        ("french_49_csv", FFP),
        ("dtb3_csv", DTB3),
        ("market_sqlite", ROOT / "data/market.sqlite"),
    ]:
        p = Path(path)
        report["inputs"][label] = {"path": str(p), "sha256": sha256(p) if p.is_file() else None, "exists": p.is_file()}

    if not FFP.is_file():
        print(f"Missing French CSV: {FFP}", file=sys.stderr)
        return 2

    committed_path = ROOT / "results/v6-preflight/a-memory-backfill.json"
    committed = json.loads(committed_path.read_text(encoding="utf-8"))
    subprocess.run(
        [str(PY), "-I", str(ROOT / "scripts/preflight/a_memory_backfill.py"), str(FFP), str(DTB3)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    rerun = json.loads(committed_path.read_text(encoding="utf-8"))
    report["rerun"]["semantic_equal"] = committed == rerun
    report["rerun"]["committed_bytes_sha256"] = sha256(committed_path)

    seg = committed["A 股：沪深300 + 10 个全指一级行业（含 2011-08 之前的回填点位）"]["全段 2006-01 → 2015-11"]["12−1"]
    net_pts = parse_net_annual(seg)
    report["d40_10"]["json_12m1_net_annual_pts"] = net_pts
    if net_pts is not None:
        mid = net_pts * 0.5 * 0.6 * 0.4
        report["d40_10"]["formula"] = "net × 0.5 × 0.6 × 40%"
        report["d40_10"]["mid_calc"] = round(mid, 4)
        report["d40_10"]["mid_forecast_table"] = 0.6
        report["d40_10"]["hi_bound_note"] = "表列上限 +1.3 = 全段 S1 净 +6.5 × 0.5 × 0.4（无候选个数六折）"
        report["d40_10"]["hi_check"] = round(6.5 * 0.5 * 0.4, 4)
    rows = [(1.0, 0.3, 1.5), (0.6, 0.0, 1.3), (-0.4, -1.6, -0.4)]
    lo = sum(r[1] for r in rows)
    hi = sum(r[2] for r in rows)
    mid = sum(r[0] for r in rows)
    report["d40_10"]["combined_ex_position"] = {"lo": lo, "mid": mid, "hi": hi}
    report["d40_10"]["charts_v3_rows_match"] = {
        "A_mid": 0.6,
        "A_lo": 0.0,
        "A_hi": 1.3,
        "total_mid": 1.2,
        "total_lo": -1.3,
        "total_hi": 2.4,
    }

    for sha in ("9ab039b1cc70d3774de725b70e395360ac22cc31", "260ae20439b48b059f4d8204effc7969a36b520e"):
        meta = subprocess.check_output(
            ["git", "log", "-1", "--format=%H|%P|%ci|%s", sha], cwd=ROOT, text=True
        ).strip().split("|", 3)
        has_json = (
            subprocess.run(
                ["git", "cat-file", "-e", f"{sha}:results/v6-preflight/a-memory-backfill.json"],
                cwd=ROOT,
                capture_output=True,
            ).returncode
            == 0
        )
        report["commit_order"][sha[:8]] = {
            "full": meta[0],
            "parent": meta[1],
            "committer_date": meta[2],
            "subject": meta[3],
            "has_a_memory_backfill_json": has_json,
        }
    report["commit_order"]["260ae20_parent_is_9ab039b"] = report["commit_order"]["260ae204"]["parent"].startswith(
        "9ab039b"
    )

    script_260 = subprocess.check_output(
        ["git", "show", "260ae20439b48b059f4d8204effc7969a36b520e:scripts/preflight/a_memory_backfill.py"],
        cwd=ROOT,
    )
    script_head = (ROOT / "scripts/preflight/a_memory_backfill.py").read_bytes()
    report["script_byte_identical_to_260ae20"] = script_260 == script_head

    json_260 = subprocess.check_output(
        ["git", "show", "260ae20439b48b059f4d8204effc7969a36b520e:results/v6-preflight/a-memory-backfill.json"],
        cwd=ROOT,
        text=True,
    )
    report["json_semantic_identical_to_260ae20"] = json.loads(json_260) == committed

    for rel in (
        "results/v6-preflight/topn-dedupe.json",
        "results/v6-preflight/a-official.json",
        "results/v6-preflight/exec-example.json",
        "results/v6-preflight/topn-speed.json",
    ):
        diff_len = len(
            subprocess.check_output(
                ["git", "diff", "e3cade414080e51cad471f0a38822d1682af0276..HEAD", "--", rel],
                cwd=ROOT,
            )
        )
        report.setdefault("signed_jsons_unchanged_vs_main", {})[rel] = diff_len == 0

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["rerun"]["semantic_equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())