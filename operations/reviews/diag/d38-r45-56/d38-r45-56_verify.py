#!/usr/bin/env python3
"""D38 r45–56 @ PR #346：登记序、Reviewer 独立回测（非 exec 作者 prep/pick/run/report）、Dev 重跑对照。"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
FFP = HERE / "cache" / "49_Industry_Portfolios.csv"
DTB3 = ROOT / "results/v5/other-market/raw/DTB3.csv"
SQLITE = ROOT / "data/market.sqlite"
LOCK = ROOT / "results/v5/LOCK"
OUT = HERE / "d38-r45-56-recalc.json"
PY = ROOT / ".venv/bin/python"
SUBJECT_HEAD = "0bff3eda70c64d62944940a4cd94ea702cd95adb"
ROW45_56_REG = "4de51bc40268380e11be08ec1c71b11026d107a4"
ROW45_56_RES = SUBJECT_HEAD
ROW55_RES_ON_MAIN = "ff5112c389bbc88759ab470b1bfde11813e21bdf"
ARTIFACTS = [
    "scripts/preflight/a_memory_csi300.py",
    "scripts/preflight/a_decompose_sw.py",
    "results/v6-preflight/a-memory-csi300.json",
    "results/v6-preflight/a-decompose-sw-step1.json",
    "results/v6-preflight/a-decompose-sw.json",
]
TOL_PTS = 0.15
TOL_T = 0.05
ROW55_DECOMPOSE_SHA = "e3839caadfbe8483e6e21c735678302633eaf6c13dbf179a2a0ff049b0031514"


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


def run_cmd(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)


def tt(x) -> float | None:
    x = pd.Series(x).dropna()
    if len(x) <= 2:
        return None
    return round(float(x.mean() / x.std(ddof=1) * math.sqrt(len(x))), 2)


# ---------- 独立复算：第 45 行（不 exec Dev 脚本） ----------
def independent_row45() -> dict:
    COST = 0.002
    import sqlite3

    con = sqlite3.connect(SQLITE)
    csi = pd.read_sql_query(
        "select date, close from bars where code='H00300' and adj='raw' and close>0 and date<='2015-12-31' order by date",
        con,
    )
    csi.index = pd.to_datetime(csi["date"])
    csi["close"] = csi["close"] / csi["close"].iloc[0]
    PKG = ROOT / "incoming/grok-csi300-sectors-20261123/dailies/from-publish-date"
    L = {"csi300": csi["close"]}
    for i in range(8, 18):
        code = f"H00{900 + i}"
        f = next(PKG.glob(f"{code}*.csv"))
        d = pd.read_csv(f, dtype={"tradeDate": str})
        d.index = pd.to_datetime(d["tradeDate"])
        d = d[d["close"] > 0]
        L[code] = d["close"].loc[: "2015-12-31"]
    lvl = pd.DataFrame(L).loc["2005-01-01": "2015-12-31"]
    lvl = lvl.reindex(csi.index).ffill()
    for c in lvl.columns:
        if c != "csi300":
            lvl[c] = lvl[c].where(lvl.index >= L[c].index[0])
    cal = lvl.index
    me = lvl[np.r_[cal.month[1:] != cal.month[:-1], True]]

    def run_seg(a, b):
        nxt = me.pct_change().shift(-1)
        s12 = me.shift(1) / me.shift(12) - 1
        s1 = (me / me.shift(1) - 1).where(s12.notna())
        out = {}
        for nm, sc in (("12−1", s12), ("上月涨幅", s1)):
            rows = []
            prev = pd.Series(0.0, index=me.columns)
            for d in me.loc[a:b].index:
                s = sc.loc[d].dropna()
                if len(s) < 5 or not np.isfinite(nxt.loc[d, "csi300"]):
                    prev = pd.Series(0.0, index=me.columns)
                    continue
                top = s.nlargest(3).index
                v = nxt.loc[d, top]
                if v.isna().any():
                    continue
                w = pd.Series(0.0, index=me.columns)
                w[top] = 1 / 3
                tr = float((w - prev).abs().sum())
                prev = w
                g = float(v.mean() - nxt.loc[d, "csi300"])
                rows.append((d, g, g - COST * tr))
            out[nm] = pd.DataFrame(rows, columns=["d", "gross", "net"]).set_index("d")
        return out

    new = run_seg("2008-07", "2011-07")
    full = run_seg("2008-07", "2015-11")
    s1n = new["上月涨幅"]["net"].mean() * 1200
    r0n = new["12−1"]["net"].mean() * 1200
    net_full = full["上月涨幅"]["net"]
    full_t_raw = float(net_full.mean() / net_full.std(ddof=1) * math.sqrt(len(net_full)))
    full_t = tt(net_full)
    return {
        "新段_S1_净_每年点": round(s1n, 1),
        "新段_R0_净_每年点": round(r0n, 1),
        "全段_S1_t": full_t,
        "全段_S1_t_未四舍五入": full_t_raw,
        "判据_新段S1净>0": bool(s1n > 0),
        "判据_新段S1>R0": bool(s1n > r0n),
        "判据_全段S1_t>=2": bool((full_t or -99) >= 2),
    }


import importlib.util

_DIAG = Path(__file__).resolve().parent


def _import_local(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _DIAG / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_plumb = _import_local("reviewer_data_plumbing", "reviewer_data_plumbing.py")
_bt = _import_local("reviewer_backtest_independent", "reviewer_backtest_independent.py")

L1_COLS = [
    "allshare-energy",
    "allshare-materials",
    "allshare-industrials",
    "allshare-discretionary",
    "allshare-staples",
    "allshare-healthcare",
    "allshare-financials-re",
    "allshare-it",
    "allshare-communication",
    "allshare-utilities",
]


def _tag_lookup(cols: list[str]) -> dict[str, str]:
    base = _plumb.load_sector_tags_a()
    return {c: (base.get(c, "") or f"_{c}") for c in cols}


def independent_decompose_p3() -> dict:
    a_old, cal, csi = _plumb.load_a_lvl_calendar()
    bond, _ = _plumb.load_market_bond_cash(cal)
    L = _plumb.load_p3_sw(cal, csi)
    ms = _bt.build_month_state(L, None)
    sim = _bt.simulate_rules(L, bond, ms, ["B0", "C1"], False, _tag_lookup(list(L.columns)), _plumb.END)
    rep = _bt.summarize_vs_ew(sim, ["B0", "C1"], "2006-01", "2015-11")
    return rep


def independent_c2_formal() -> dict:
    a_old, cal, csi = _plumb.load_a_lvl_calendar()
    bond, _ = _plumb.load_market_bond_cash(cal)
    on_l1 = _plumb.load_allshare_overnight_from_incoming()
    L1 = a_old[L1_COLS]
    ms1 = _bt.build_month_state(L1, on_l1)
    sim1 = _bt.simulate_rules(L1, bond, ms1, ["B0", "C2"], True, _tag_lookup(list(L1.columns)), _plumb.END)
    rep1 = _bt.summarize_vs_ew(sim1, ["B0", "C2"], "2006-01", "2015-11")
    ph1 = _bt.phase_b0_minus(sim1, "C2", _bt.P1_PHASES)
    wins1 = _bt.count_phases_beat(ph1)

    a_pool = _plumb.load_official_a_pool(a_old, cal)
    on_a = _plumb.load_official_overnight(list(a_pool.columns), cal)
    sub = [c for c in a_pool.columns if c in on_a]
    L2 = a_pool[sub]
    ms2 = _bt.build_month_state(L2, {c: on_a[c] for c in sub})
    sim2 = _bt.simulate_rules(L2, bond, ms2, ["B0", "C2"], True, _tag_lookup(list(L2.columns)), _plumb.END)
    rep2 = _bt.summarize_vs_ew(sim2, ["B0", "C2"], "2011-08", "2015-11")
    ph2 = _bt.phase_b0_minus(sim2, "C2", _bt.P2_PHASES)

    c2_p1_t = rep1["C2"]["对等权_t"]
    c2_p2_b0 = rep2["C2"]["对B0_每年点"]
    formal = {
        "P1_五段C2好于B0_段数": wins1,
        "P1_五段至少四段": wins1 >= 4,
        "P1_C2对等权_t": c2_p1_t,
        "P1_C2对等权_t>=1": (c2_p1_t or -99) >= 1,
        "P1_C2对B0_每年点": rep1["C2"]["对B0_每年点"],
        "P2_C2对B0_每年点": c2_p2_b0,
        "P1与P2子池对B0同为正": (rep1["C2"]["对B0_每年点"] or 0) > 0 and (c2_p2_b0 or 0) > 0,
        "换规则": wins1 >= 4 and (c2_p1_t or -99) >= 1 and (rep1["C2"]["对B0_每年点"] or 0) > 0 and (c2_p2_b0 or 0) > 0,
        "结论_C2关闭": True,
    }
    formal["结论_C2关闭"] = not formal["换规则"]
    return {
        "P1_summary": rep1,
        "P2_summary": rep2,
        "P1_C2分阶段对B0每年点": ph1,
        "P2_C2分阶段对B0每年点": ph2,
        "正式三项独立判定": formal,
        "plumbing_note": "债券=cgb-10y via Markets(signal)；A 池=sqlite+universe.toml",
    }


def audit_definitions(sw_py: str, decomp_py: str) -> dict:
    chunk = sw_py.split("# ---------- 池子 ----------")[0] if "# ---------- 池子 ----------" in decomp_py else ""
    exec_head = sw_py.split("exec(src.split('# ---------- 池子 ----------')[0], G)")[0]
    row55 = subprocess.check_output(
        ["git", "show", f"{ROW55_RES_ON_MAIN}:scripts/preflight/a_decompose.py"], cwd=ROOT, text=True
    )
    same_as_row55 = decomp_py == row55
    markers = {
        "C1_ID_formula": "np.sign(mom) * (neg - pos)" in decomp_py,
        "C1_pick_lowest_ID": "sort_values(['id', 'm'], ascending=[True, False])" in decomp_py,
        "C2_overnight_sum": "rule == 'C2'" in decomp_py and "nlargest(N)" in decomp_py,
        "MINDAYS_200": "MINDAYS = 200" in decomp_py,
        "cost_0.002": "COST = 0.002" in decomp_py,
        "sw_reuses_decompose_core": "exec(src.split('# ---------- 池子 ----------')[0], G)" in sw_py,
        "a_decompose_unchanged_vs_row55_main": same_as_row55,
    }
    return markers


def close(a, b, tol=TOL_PTS):
    return abs(a - b) <= tol


def main() -> int:
    subprocess.run(["git", "fetch", "origin", "claude/d38-r45-r56"], cwd=ROOT, capture_output=True)
    subject_remote = subprocess.check_output(
        ["git", "rev-parse", "origin/claude/d38-r45-r56"], cwd=ROOT, text=True
    ).strip()
    worktree_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    report: dict = {
        "subject_pr": 346,
        "subject_head_expected": SUBJECT_HEAD,
        "subject_head_remote": subject_remote,
        "worktree_HEAD": worktree_head,
        "head_drift": subject_remote != SUBJECT_HEAD,
        "inputs": {},
        "commit_order": {},
        "registration_order_proof": {},
        "independent_recalc": {},
        "rerun_dev_scripts": {},
        "criteria_audit": {},
        "definition_continuity_row55": {},
        "method": "independent_reviewer_backtest_v2",
        "computation_recommendation": None,
        "formal_reviewer_decision_record": "operations/reviews/diag/d38-r45-56/d38-r45-56-reviewer-formal-decision.json",
        "decision_inputs": {},
        "verify_exit_code": None,
    }
    if report["head_drift"]:
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 2

    for label, path, expected in [
        ("french_49_csv", FFP, "633958bf36d25da6d95876bfc468536029db600c32c65b7a3e0f7fba59a04609"),
        ("dtb3_csv", DTB3, "29fe11e20522b4d293cdbbbfd37f2862264692519a251e712747a8532ee95a00"),
        ("market_sqlite", SQLITE, "79ba7780f7f5304d189bc49bd7dda9ff1e6325c88888165d71a0c9fae7c26a52"),
    ]:
        p = Path(path)
        got = sha256(p) if p.is_file() else None
        report["inputs"][label] = {"path": str(p), "sha256": got, "matches_signed": got == expected if got else False}

    for key, sha in (("row45_56_reg", ROW45_56_REG), ("row45_56_res", ROW45_56_RES)):
        report["commit_order"][key] = commit_meta(sha)
    co = report["commit_order"]
    is_anc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ROW45_56_REG, ROW45_56_RES], cwd=ROOT
    ).returncode == 0
    report["registration_order_proof"] = {
        "reg_is_ancestor_of_res": is_anc,
        "reg_planning_only": co["row45_56_reg"]["planning_only"],
        "res_parent_is_reg": co["row45_56_res"]["parent"].startswith(ROW45_56_REG[:8]),
        "reg_before_res_author_time": co["row45_56_reg"]["author_date"] < co["row45_56_res"]["author_date"],
        "artifacts_missing_at_reg": {p: not git_cat(ROW45_56_REG, p) for p in ARTIFACTS},
        "reg_commit_touches_only_planning": len(
            subprocess.check_output(
                ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", ROW45_56_REG], cwd=ROOT, text=True
            ).strip().splitlines()
        )
        == 1,
    }

    committed = {
        "memory": json.loads(
            subprocess.check_output(["git", "show", f"{SUBJECT_HEAD}:results/v6-preflight/a-memory-csi300.json"], text=True)
        ),
        "sw": json.loads(
            subprocess.check_output(["git", "show", f"{SUBJECT_HEAD}:results/v6-preflight/a-decompose-sw.json"], text=True)
        ),
        "sw_s1": json.loads(
            subprocess.check_output(
                ["git", "show", f"{SUBJECT_HEAD}:results/v6-preflight/a-decompose-sw-step1.json"], text=True
            )
        ),
    }

    backups = {
        "memory": (ROOT / "results/v6-preflight/a-memory-csi300.json").read_bytes(),
        "sw_s1": (ROOT / "results/v6-preflight/a-decompose-sw-step1.json").read_bytes(),
        "sw": (ROOT / "results/v6-preflight/a-decompose-sw.json").read_bytes(),
    }
    run_cmd([str(PY), "-I", str(ROOT / "scripts/preflight/a_memory_csi300.py"), str(FFP), str(DTB3)])
    run_cmd([str(PY), "-I", str(ROOT / "scripts/preflight/a_decompose_sw.py"), str(FFP), str(DTB3), "step1"])
    run_cmd([str(PY), "-I", str(ROOT / "scripts/preflight/a_decompose_sw.py"), str(FFP), str(DTB3), "step2"])
    for key, rel in (
        ("memory", "results/v6-preflight/a-memory-csi300.json"),
        ("sw_s1", "results/v6-preflight/a-decompose-sw-step1.json"),
        ("sw", "results/v6-preflight/a-decompose-sw.json"),
    ):
        after = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        report["rerun_dev_scripts"][key] = {"semantic_equal_to_head_commit": after == committed[key]}

    ind45 = independent_row45()
    ind_p3 = independent_decompose_p3()
    ind_c2 = independent_c2_formal()
    mem = committed["memory"]
    sw = committed["sw"]
    p3 = sw["P3 申万一级 + 沪深300 2006-01 → 2015-11"]
    p1c2 = sw["P1 子池（10 个一级行业，有开盘价）2006-01 → 2015-11"]
    crit_c2_json = sw["(一) C2 正式判据"]

    report["independent_recalc"] = {
        "row45": ind45,
        "row45_vs_committed": {
            "新段_S1_净": close(ind45["新段_S1_净_每年点"], -3.6),
            "全段_S1_t": abs((ind45["全段_S1_t"] or 0) - 0.08) <= TOL_T,
        },
        "p3_independent": ind_p3,
        "p3_vs_committed_after_calc": {
            "B0_对等权": close(ind_p3["B0"]["对等权_每年点"], p3["B0"]["对等权全部 每年点"]),
            "B0_t": abs((ind_p3["B0"]["对等权_t"] or 0) - (p3["B0"]["对等权 t"] or 0)) <= TOL_T,
            "C1_对等权": close(ind_p3["C1"]["对等权_每年点"], p3["C1"]["对等权全部 每年点"]),
            "C1_t": abs((ind_p3["C1"]["对等权_t"] or 0) - (p3["C1"]["对等权 t"] or 0)) <= TOL_T,
            "C1_对B0": close(ind_p3["C1"]["对B0_每年点"], p3["C1"]["对 B0 每年点"]),
            "C1_对B0_t": abs((ind_p3["C1"]["对B0_t"] or 0) - (p3["C1"]["对 B0 t"] or 0)) <= TOL_T,
            "committed_for_diff_only": {
                "B0": p3["B0"],
                "C1": p3["C1"],
            },
        },
        "c2_independent": ind_c2,
        "c2_vs_committed_after_calc": {
            "P1_C2_对等权_t": abs((ind_c2["P1_summary"]["C2"]["对等权_t"] or 0) - (p1c2["C2"]["对等权 t"] or 0)) <= TOL_T,
            "P1_C2_对B0": close(ind_c2["P1_summary"]["C2"]["对B0_每年点"], p1c2["C2"]["对 B0 每年点"]),
            "P1_阶段赢数": ind_c2["正式三项独立判定"]["P1_五段C2好于B0_段数"] == 4,
            "P2_C2_对B0": close(
                ind_c2["P2_summary"]["C2"]["对B0_每年点"],
                sw["P2 子池（官方池中有开盘价的候选）2011-08 → 2015-11"]["C2"]["对 B0 每年点"],
            ),
        },
    }

    fin = ind_c2["正式三项独立判定"]
    report["criteria_audit"] = {
        "row45_preregistered_three_independent": {
            "def_source": "operations/planning row45 + 运行口径",
            "checks": {
                "新段 S1 净超额 > 0": ind45["判据_新段S1净>0"],
                "新段 S1 > R0": ind45["判据_新段S1>R0"],
                "全段 S1 净超额 t ≥ 2": ind45["判据_全段S1_t>=2"],
            },
            "conclusion_independent": "维持 12−1，上月涨幅不进 v6",
        },
        "row56_C2_three_formal_independent": {
            "def_source": "planning row56 / row55 C2 正式判据",
            "three_core": {
                "P1五段至少四段C2好于B0": fin["P1_五段至少四段"],
                "P1对等权_t_ge_1": fin["P1_C2对等权_t>=1"],
                "P1与P2对B0同为正": fin["P1与P2子池对B0同为正"],
            },
            "numbers": fin,
            "committed_json_for_diff": crit_c2_json,
        },
        "row56_P3_reference_independent": {
            "B0_vs_EW": ind_p3["B0"],
            "C1_vs_EW_and_B0": ind_p3["C1"],
        },
    }

    decomp_py = (ROOT / "scripts/preflight/a_decompose.py").read_text(encoding="utf-8")
    sw_py = (ROOT / "scripts/preflight/a_decompose_sw.py").read_text(encoding="utf-8")
    report["definition_continuity_row55"] = audit_definitions(sw_py, decomp_py)

    reg_ok = (
        report["registration_order_proof"]["reg_is_ancestor_of_res"]
        and report["registration_order_proof"]["reg_planning_only"]
        and report["registration_order_proof"]["reg_before_res_author_time"]
        and all(report["registration_order_proof"]["artifacts_missing_at_reg"].values())
    )
    rerun_ok = all(v["semantic_equal_to_head_commit"] for v in report["rerun_dev_scripts"].values())
    p3_cmp = {
        k: v
        for k, v in report["independent_recalc"]["p3_vs_committed_after_calc"].items()
        if k != "committed_for_diff_only"
    }
    indep_ok = (
        all(report["independent_recalc"]["row45_vs_committed"].values())
        and all(p3_cmp.values())
        and all(report["independent_recalc"]["c2_vs_committed_after_calc"].values())
    )
    inputs_ok = all(v["matches_signed"] for v in report["inputs"].values())
    defs_ok = report["definition_continuity_row55"]["a_decompose_unchanged_vs_row55_main"]

    report["decision_inputs"] = {
        "subject_head_match": not report["head_drift"],
        "registration_order_ok": reg_ok,
        "inputs_ok": inputs_ok,
        "rerun_ok": rerun_ok,
        "independent_spot_ok": indep_ok,
        "row55_definitions_unchanged": defs_ok,
        "row45_three_criteria_fail_independent": not any(
            bool(v) for v in report["criteria_audit"]["row45_preregistered_three_independent"]["checks"].values()
        ),
        "c2_closed_independent": fin["结论_C2关闭"] and not fin["换规则"],
    }
    report["decision_inputs"] = {k: bool(v) for k, v in report["decision_inputs"].items()}
    report["computation_recommendation"] = (
        "approve" if all(report["decision_inputs"].values()) else "investigate_discrepancy"
    )

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report["decision_inputs"], ensure_ascii=False, indent=2))
    ec = 0 if all(report["decision_inputs"].values()) else 1
    report["verify_exit_code"] = ec
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return ec


if __name__ == "__main__":
    raise SystemExit(main())