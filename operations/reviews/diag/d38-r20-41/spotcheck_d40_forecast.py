#!/usr/bin/env python3
"""对照 D40、预测表 3.0 与 committed JSON/CSV 的关键数字。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent / "d38-r2041-recalc.json"


def main() -> None:
    official = json.loads((ROOT / "results/v6-preflight/a-official.json").read_text(encoding="utf-8"))
    n3 = pd.read_csv(ROOT / "results/v6-preflight/msim-v6-n3.csv")
    n3bh = n3[(n3["防守资产"] == "不帮忙") & (n3["结构"] == "新系统")]
    design_claim = {
        "前3_美60_年化": official["R1 设计期整套系统（A 股按发布日校正）"]["前3 按把握调节，美股 60%"]["年化"],
        "前3_美60_最低剩": official["R1 设计期整套系统（A 股按发布日校正）"]["前3 按把握调节，美股 60%"]["最低剩"],
    }
    d40_md = (ROOT / "operations/planning/2026-11-19-d40-v6-structure.md").read_text(encoding="utf-8")
    d40_table = re.search(r"前 3.*?12\.6%.*?71\.1", d40_md, re.S) is not None
    synth = {}
    for scen in ("急跌", "慢熊", "震荡"):
        row = n3bh[n3bh["行情"] == scen].iloc[0]
        synth[scen] = {"最低剩_p10": float(row["最低剩_万_p10"]), "最低剩_中位": float(row["最低剩_万_中位"])}
    forecast = (ROOT / "docs/owner/v6-preflight-forecast.md").read_text(encoding="utf-8")
    payload = {
        "spotcheck": {
            "d40_design_period_claimed_in_md": d40_table,
            "a_official_design": design_claim,
            "msim_n3_synthetic_new_system_不帮忙": synth,
            "forecast_v3_mentions_0.6_excess": "每年比基准多约 **0.6**" in forecast,
            "leader_stress_a_share_t": official["R1 A 股紧张期领头者存活度（校正后，前 2）"]["紧张月"]["t_领头绝对"],
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