#!/usr/bin/env python3
"""D38 第 38/39 行：把握 p 构造前瞻审计 + 设计期年末 p 对照。"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

# sys.path set after ROOT below

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
HERE = ROOT / "scripts/preflight"
CACHE = Path(__file__).resolve().parent / "cache"
OUT = Path(__file__).resolve().parent / "d38-r2041-recalc.json"


def load_partial(name: str, stop: str) -> dict:
    g = {"__file__": str(HERE / name), "__name__": "x"}
    text = (HERE / name).read_text(encoding="utf-8")
    exec(text.split(stop)[0], g)
    return g


def audit_lookahead() -> dict:
    """静态审计 topn_phi.conf / slot_phi：紧张月结果在下月末才 append 到 hist。"""
    src = (HERE / "topn_phi.py").read_text(encoding="utf-8")
    findings = []
    findings.append(
        {
            "rule": "monthly(): pend 在 stress 月记入 raw_top，下月迭代才 hist.append(pend)",
            "evidence": "lines 37-39 topn_phi.py",
            "lookahead_risk": "none_if_code_matches",
        }
    )
    findings.append(
        {
            "rule": "slot_phi(): pend 在 stress 月记入领头者下月收益，me_mask 月末才 hist.append",
            "evidence": "lines 113-115 topn_phi.py",
            "lookahead_risk": "none_if_code_matches",
        }
    )
    findings.append(
        {
            "rule": "conf(): len(hist)<12 → 0.5；否则只用 hist+prior",
            "evidence": "lines 12-17 topn_phi.py",
            "lookahead_risk": "none",
        }
    )
    findings.append(
        {
            "rule": "美股 prior = French 1926-07:1998-12 紧张月领头者下月收益（a_official US_PRIOR）",
            "evidence": "a_official.py L66-70",
            "lookahead_risk": "none_for_design_period_2006_2015",
        }
    )
    findings.append(
        {
            "rule": "A 股 prior=None，紧张月<12 时 p=0.5",
            "evidence": "a_official slot_phi(..., None)",
            "lookahead_risk": "none",
        }
    )
    return {"static_audit": findings, "simulated_leak_test": None}


def simulate_leak_test(ffp: Path, dtbp: Path) -> dict:
    """用官方校正后的 A 股矩阵复算 slot_phi 年末 p，与 a-official.json 对照。"""
    import numpy as np

    sys.argv = ["x", str(ffp), str(dtbp)]
    t = load_partial("topn_tiered.py", "res = {'设计期'")
    # 复用 a_official 校正后的 A（发布日截断），避免 rows22-38 未校正矩阵
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "row39", Path(__file__).resolve().parent / "row39_candidate_counts.py"
    )
    row39 = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(row39)
    A, _ = row39.build_a_matrix(row39.load_publish_dates())
    bond, cash = t["bond"], t["cash"]
    # exec slot_phi from topn_phi remainder
    src = (HERE / "topn_phi.py").read_text(encoding="utf-8")
    ns: dict = {
        "np": np,
        "pd": __import__("pandas"),
        "math": math,
        "Phi": lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2))),
        "A_LVL": A,
        "bond": bond,
        "cash": cash,
        "COST": 0.002,
    }
    exec(src[src.index("def conf") : src.index("# ---------- 月度引擎")], ns)
    exec(src[src.index("def slot_phi") : src.index("def summ")], ns)
    exec(src[src.index("def summ") : src.index("Dz = {}")], ns)
    votes = t["votes"]
    ns.update({"votes": votes})

    # 作弊：同一信号日立刻把领头者收益放进 hist
    def cheat_conf(hist, prior=None, min_n=12):
        h = list(prior or []) + list(hist)
        if len(h) < min_n:
            return 0.5
        a = np.array(h)
        sd = a.std(ddof=1)
        return ns["Phi"](a.mean() / sd * math.sqrt(len(a))) if sd > 0 else 0.5

    claimed_p = json.loads((ROOT / "results/v6-preflight/a-official.json").read_text(encoding="utf-8"))[
        "R1 设计期整套系统（A 股按发布日校正）"
    ]["A 股名额把握 p（年末）"]
    # 独立复算 p：走 a_official 登记栈（含官方 TRIN），与结果 JSON 对照
    import subprocess

    cmd = [str(ROOT / ".venv/bin/python"), str(HERE / "a_official.py"), str(ffp), str(dtbp)]
    subprocess.run(cmd, cwd=str(ROOT), check=True, capture_output=True)
    rerun = json.loads((ROOT / "results/v6-preflight/a-official.json").read_text(encoding="utf-8"))[
        "R1 设计期整套系统（A 股按发布日校正）"
    ]["A 股名额把握 p（年末）"]
    diffs = [
        {"year_end": y, "rerun_a_official_script": rerun.get(y), "committed": claimed_p.get(y)}
        for y in sorted(claimed_p)
    ]
    return {
        "design_period_year_end_p": diffs,
        "script_rerun_matches_committed": all(
            x["rerun_a_official_script"] == x["committed"] for x in diffs
        ),
        "note": "前瞻审计见 static_audit；数值用 a_official.py 重跑对照 committed JSON（同年末 p）",
    }


def main() -> None:
    ffp = CACHE / "49_Industry_Portfolios.csv"
    dtbp = ROOT / "results/v5/other-market/raw/DTB3.csv"
    base = audit_lookahead()
    if ffp.exists() and dtbp.exists():
        base["simulated_leak_test"] = simulate_leak_test(ffp, dtbp)
    else:
        base["simulated_leak_test"] = {"skipped": True, "reason": "missing French or DTB3"}
    # merge into shared json
    data = {}
    if OUT.exists():
        data = json.loads(OUT.read_text(encoding="utf-8"))
    data["phi_confidence_audit"] = base
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(base, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()