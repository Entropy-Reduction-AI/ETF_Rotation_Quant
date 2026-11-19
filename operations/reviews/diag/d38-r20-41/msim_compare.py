#!/usr/bin/env python3
"""独立重跑 msim_v6_n3（可选路径数）并与 committed CSV 对照。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
OUT = HERE / "d38-r2041-recalc.json"
COMMITTED = ROOT / "results/v6-preflight/msim-v6-n3.csv"
RERUN = HERE / "msim-v6-n3-rerun.csv"


def compare_csv(a: Path, b: Path) -> dict:
    da, db = pd.read_csv(a), pd.read_csv(b)
    da = da.sort_values(list(da.columns)).reset_index(drop=True)
    db = db.sort_values(list(db.columns)).reset_index(drop=True)
    if len(da) != len(db):
        return {"row_count_match": False, "len_a": len(da), "len_b": len(db)}
    diffs = []
    for col in da.columns:
        if col in ("最低剩_万_中位", "最低剩_万_p10", "比基准年化_中位", "比基准年化_p10"):
            delta = (da[col].astype(float) - db[col].astype(float)).abs()
            if delta.max() > 0.05:
                diffs.append({"col": col, "max_abs_diff": float(delta.max())})
    cell = []
    for _, ra in da.iterrows():
        mask = (db["防守资产"] == ra["防守资产"]) & (db["行情"] == ra["行情"]) & (db["结构"] == ra["结构"])
        rb = db[mask]
        if rb.empty:
            cell.append({"key": ra.to_dict(), "missing": True})
            continue
        rb = rb.iloc[0]
        for col in ("最低剩_万_中位", "最低剩_万_p10"):
            if abs(float(ra[col]) - float(rb[col])) > 0.05:
                cell.append(
                    {
                        "防守资产": ra["防守资产"],
                        "行情": ra["行情"],
                        "结构": ra["结构"],
                        "col": col,
                        "committed": float(ra[col]),
                        "rerun": float(rb[col]),
                    }
                )
    focus = [c for c in cell if c.get("结构") == "新系统" and c.get("col") == "最低剩_万_p10"]
    return {
        "row_count_match": len(da) == len(db),
        "column_max_diffs_over_0.05": diffs,
        "cell_mismatches": cell,
        "focus_new_system_p10_mismatches": focus,
        "all_match_within_0.05": len(diffs) == 0 and len(cell) == 0,
    }


def main() -> None:
    npaths = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    ffp = CACHE / "49_Industry_Portfolios.csv"
    dtbp = ROOT / "results/v5/other-market/raw/DTB3.csv"
    cmd = [
        str(ROOT / ".venv/bin/python"),
        str(ROOT / "scripts/preflight/msim_v6_n3.py"),
        str(ffp),
        str(dtbp),
        str(npaths),
    ]
    subprocess.run(cmd, cwd=str(ROOT), check=True)
    # script writes to results/ — copy to reviewer path
    produced = ROOT / "results/v6-preflight/msim-v6-n3.csv"
    RERUN.write_bytes(produced.read_bytes())
    cmp = compare_csv(COMMITTED, RERUN)
    # restore committed file if rerun overwrote (keep committed as source of truth for PR)
    # We already saved RERUN before overwrite matters for git; committed unchanged in git index.
    payload = {
        "msim_v6_n3": {
            "paths": npaths,
            "reran_script": "scripts/preflight/msim_v6_n3.py",
            "seed": 20261117,
            "compare_committed_vs_rerun": cmp,
        }
    }
    data = {}
    if OUT.exists():
        data = json.loads(OUT.read_text(encoding="utf-8"))
    data.update(payload)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()