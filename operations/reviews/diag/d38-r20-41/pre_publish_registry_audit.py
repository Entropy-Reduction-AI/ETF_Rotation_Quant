#!/usr/bin/env python3
"""验证第 22–38 行 A 股仍用回填；第 39 行校正为权威（登记 + 数值翻转证据）。"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent / "d38-r2041-recalc.json"
PLAN = ROOT / "operations/planning/2026-11-16-d38-project-diagnosis-and-preflight.md"


def main() -> None:
    text = PLAN.read_text(encoding="utf-8")
    has_note = "39 补注" in text and "以第 39 行的校正结果为准" in text
    rows_cited = re.findall(r"第 (\d+)、", text.split("39 补注")[1].split("\n")[0] if "39 补注" in text else "")
    official = json.loads((ROOT / "results/v6-preflight/a-official.json").read_text(encoding="utf-8"))
    r1 = official["R1 设计期整套系统（A 股按发布日校正）"]
    flip = {
        "校正后_前2_美60_年化": r1["前2 按把握调节，美股 60%"]["年化"],
        "校正前_前2_美60_年化": r1["校正前 前2 按把握调节，美股常驻 60%"]["年化"],
        "校正后_A股名额单独_2011-15": r1["A 股名额单独（前2）"]["年化_2011–15"],
        "校正前 implication": "rows 22-38 A-share used topn_system A_LVL without publish truncate (topn_system.py L16-17)",
    }
    topn_sys = (ROOT / "scripts/preflight/topn_system.py").read_text(encoding="utf-8")
    no_truncate_in_22_38 = "publish_date" not in topn_sys.split("A_LVL")[1][:400]
    payload = {
        "pre_publish_registry": {
            "planning_row_39_addendum_present": has_note,
            "topn_system_no_publish_truncate": no_truncate_in_22_38,
            "authoritative_row39_fields_in_a_official": list(r1.keys()),
            "correction_flips_performance": flip,
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