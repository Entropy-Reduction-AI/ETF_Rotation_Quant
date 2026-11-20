#!/usr/bin/env python3
"""独立重跑 scripts/preflight/topn_speed.py 并与 committed topn-speed.json 逐项对照。"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
OUT_JSON = HERE / "topn-speed-rerun.json"
SUMMARY = HERE / "d38-r4244-recalc.json"
COMMITTED = ROOT / "results/v6-preflight/topn-speed.json"
SCRIPT = ROOT / "scripts/preflight/topn_speed.py"
DTB3 = ROOT / "results/v5/other-market/raw/DTB3.csv"
FFP = CACHE / "49_Industry_Portfolios.csv"
TOL = 0.02  # 百分点 / 数值字面量容差


def parse_excess(s: str) -> float | None:
    m = re.search(r"比全市场 ([+-]?[\d.]+)", s)
    return float(m.group(1)) if m else None


def deep_compare(a, b, path: str = "") -> list[dict]:
    diffs: list[dict] = []
    if type(a) != type(b):
        diffs.append({"path": path, "committed": b, "rerun": a, "kind": "type"})
        return diffs
    if isinstance(a, dict):
        keys = set(a) | set(b)
        for k in sorted(keys):
            p = f"{path}.{k}" if path else k
            if k not in a:
                diffs.append({"path": p, "committed": b[k], "rerun": None, "kind": "missing_rerun"})
            elif k not in b:
                diffs.append({"path": p, "committed": None, "rerun": a[k], "kind": "missing_committed"})
            else:
                diffs.extend(deep_compare(a[k], b[k], p))
        return diffs
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if abs(float(a) - float(b)) > TOL:
            diffs.append({"path": path, "committed": b, "rerun": a, "kind": "numeric", "delta": float(a) - float(b)})
        return diffs
    if isinstance(a, str) and isinstance(b, str):
        if a != b:
            pa, pb = parse_excess(a), parse_excess(b)
            if pa is not None and pb is not None and abs(pa - pb) <= TOL:
                return diffs
            diffs.append({"path": path, "committed": b, "rerun": a, "kind": "string"})
        return diffs
    if a != b:
        diffs.append({"path": path, "committed": b, "rerun": a, "kind": "value"})
    return diffs


def main() -> None:
    if not FFP.exists():
        sys.exit(f"Missing French input: {FFP}")
    if not DTB3.exists():
        sys.exit(f"Missing DTB3: {DTB3}")
    cmd = [str(ROOT / ".venv/bin/python"), "-I", str(SCRIPT), str(FFP), str(DTB3)]
    subprocess.run(cmd, cwd=str(ROOT), check=True)
    OUT_JSON.write_bytes(COMMITTED.read_bytes())
    subprocess.run(["git", "checkout", "--", str(COMMITTED.relative_to(ROOT))], cwd=str(ROOT), check=True)
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    rerun = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    diffs = deep_compare(rerun, committed)
    focus = {
        "R0_excess_全程": rerun["① ② 美国 49 行业 1955–2026，前 3"]["R0 不设防守"]["全程"],
        "R1_excess_全程": rerun["① ② 美国 49 行业 1955–2026，前 3"]["R1 不设防守"]["全程"],
        "R2_excess_全程": rerun["① ② 美国 49 行业 1955–2026，前 3"]["R2 不设防守"]["全程"],
        "A1_A_上月涨幅": rerun["A1 前 3 比母指数（年化点数，t 值，月数）"]["A 股 2011-08 → 2015-12（≥5 个候选的月份）"]["上月涨幅"]["全部"],
        "A1_A_12-1": rerun["A1 前 3 比母指数（年化点数，t 值，月数）"]["A 股 2011-08 → 2015-12（≥5 个候选的月份）"]["12−1"]["全部"],
        "R0+q_最低剩_2008": rerun["③ 设计期整套（A 股按发布日校正，美股 60%，前 3）"]["R0 + 挑选把握 q（美股 60%）"]["最低剩_2008"],
        "R0_最低剩_2008": rerun["③ 设计期整套（A 股按发布日校正，美股 60%，前 3）"]["R0（美股 60%）"]["最低剩_2008"],
    }
    payload = {
        "topn_speed": {
            "script": "scripts/preflight/topn_speed.py",
            "rerun_output": str(OUT_JSON.relative_to(ROOT)),
            "inputs": {
                "french_49_csv": str(FFP),
                "french_sha256": subprocess.check_output(["sha256sum", str(FFP)], text=True).split()[0],
                "dtb3": str(DTB3),
            },
            "tolerance": TOL,
            "diff_count": len(diffs),
            "diffs_sample": diffs[:40],
            "all_match_within_tolerance": len(diffs) == 0,
            "focus_derived": focus,
        }
    }
    data = {}
    if SUMMARY.exists():
        data = json.loads(SUMMARY.read_text(encoding="utf-8"))
    data.update(payload)
    SUMMARY.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()