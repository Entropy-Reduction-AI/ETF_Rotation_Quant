#!/usr/bin/env python3
"""D38 r45–56 @ PR #346 head 0bff3eda：登记序、独立复算、Dev 脚本重跑、判据核对。"""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

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
    full_t = tt(full["上月涨幅"]["net"])
    return {
        "新段_S1_净_每年点": round(s1n, 1),
        "新段_R0_净_每年点": round(r0n, 1),
        "全段_S1_t": full_t,
        "判据_新段S1净>0": bool(s1n > 0),
        "判据_新段S1>R0": bool(s1n > r0n),
        "判据_全段S1_t>=2": bool((full_t or -99) >= 2),
    }


# ---------- 独立复算：第 56 行 P3 B0/C1（移植 run/report 语义，不 import Dev 模块） ----------
def _load_a_old_csi_and_cal() -> tuple[pd.Series, pd.DatetimeIndex, pd.Series]:
    """仅取 A_OLD 日历与 csi300 全收益列（与 Dev 行情口径一致，不读结果 JSON）。"""
    import warnings

    warnings.filterwarnings("ignore")
    HERE_PF = ROOT / "scripts/preflight"
    G = {"__file__": str(HERE_PF / "a_official.py"), "__name__": "x"}
    import sys as _sys

    _argv = _sys.argv
    _sys.argv = ["x", str(FFP), str(DTB3)]
    try:
        _sys.path.insert(0, str(HERE_PF))
        exec(open(HERE_PF / "a_official.py").read().split("res = {'每年末")[0], G)
    finally:
        _sys.argv = _argv
    a = G["A_OLD"]["csi300"].loc[: "2015-12-31"]
    bond = G["bond"].reindex(a.index).fillna(0.0)
    return a, a.index, bond


def _reviewer_engine_ns(bond: pd.Series, tags: dict) -> dict:
    """第 55 行 a_decompose.py 核心（prep/pick/run/report）哈希锁定克隆；与 row56 登记「定义不变」对账。"""
    path = ROOT / "scripts/preflight/a_decompose.py"
    raw = path.read_bytes()
    if sha256(path) != ROW55_DECOMPOSE_SHA:
        raise RuntimeError(f"a_decompose.py SHA 漂移：期望 {ROW55_DECOMPOSE_SHA}")
    src = raw.decode("utf-8")
    chunk = src[src.index("def prep(") : src.index("# ---------- 池子 ----------")]
    chunk += src[src.index("def run(L, a, b, rules, need_on, c300):") : src.index("P1PH = {")]
    ns: dict = {
        "np": np,
        "pd": pd,
        "math": math,
        "sqlite3": __import__("sqlite3"),
        "warnings": __import__("warnings"),
        "bond": bond,
        "TAGS": tags,
        "COST": 0.002,
        "N": 3,
        "MINDAYS": 200,
        "ON": {},
        "AMT": {},
    }
    exec(chunk, ns)
    return ns


def _independent_decompose_metrics(
    L: pd.DataFrame, a: str, b: str, rules: list[str], need_on: bool, bond: pd.Series, tags: dict, c300: pd.Series
) -> dict:
    eng = _reviewer_engine_ns(bond, tags)
    O, r = eng["run"](L, a, "2015-12-31", rules, need_on, c300)
    rep = eng["report"](O, r, L, a, b, rules, {"_": ("2006-01", "2015-11")}, need_on)
    return {k: rep[k] for k in rules if k in rep}


def _build_p3_levels() -> tuple[pd.DataFrame, pd.Series, pd.Series, dict]:
    import tomllib

    csi, cal, bond = _load_a_old_csi_and_cal()
    tags = tomllib.load(open(ROOT / "config/v6-preflight/sector-tags.toml", "rb"))["a"]
    SWD = ROOT / "incoming/grok-sw-l1-20261123/dailies"
    cols = {"csi300": csi}
    for f in sorted(SWD.glob("*.trend.csv")):
        d = pd.read_csv(f, dtype={"bargaindate": str})
        d.index = pd.to_datetime(d["bargaindate"])
        if d.index[0] > pd.Timestamp("2015-12-31"):
            continue
        d = d.loc[: "2015-12-31"]
        cid = "sw-" + f.name.split(".")[0]
        cols[cid] = d["closeindex"].reindex(cal).ffill().where(lambda s, d=d: s.index >= d.index[0])
    L = pd.DataFrame(cols).loc[: "2015-12-31"]
    return L, bond.reindex(L.index).fillna(0.0), csi, tags


def independent_p3_headline() -> dict:
    L, bond, csi, tags = _build_p3_levels()
    rep = _independent_decompose_metrics(L, "2006-01", "2015-11", ["B0", "C1"], False, bond, tags, csi)
    return {
        "B0_对等权_每年点": rep["B0"]["对等权全部 每年点"],
        "B0_对等权_t": rep["B0"]["对等权 t"],
        "C1_对等权_每年点": rep["C1"]["对等权全部 每年点"],
        "C1_对等权_t": rep["C1"]["对等权 t"],
        "C1_对B0_每年点": rep["C1"]["对 B0 每年点"],
        "C1_对B0_t": rep["C1"]["对 B0 t"],
        "engine_note": "P3 收益由 incoming+sqlite 组层 + SHA 锁定 a_decompose 核心引擎复算",
    }


def independent_c2_p1_headline() -> dict:
    """P1 子池 C2 正式判据 headline：开盘价 incoming 000986–000995。"""
    import tomllib

    _, cal, bond = _load_a_old_csi_and_cal()
    tags = tomllib.load(open(ROOT / "config/v6-preflight/sector-tags.toml", "rb"))["a"]
    G = {"__file__": str(ROOT / "scripts/preflight/a_official.py"), "__name__": "x"}
    import sys as _sys

    _argv = _sys.argv
    _sys.argv = ["x", str(FFP), str(DTB3)]
    try:
        exec(open(ROOT / "scripts/preflight/a_official.py").read().split("res = {'每年末")[0], G)
    finally:
        _sys.argv = _argv
    csi = G["A_OLD"]["csi300"]
    L1IDS = [
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
    on = {}
    for i, cid in enumerate(L1IDS):
        d = pd.read_csv(
            ROOT / f"incoming/grok-csi-allshare-l1-20261123/dailies/{986 + i:06d}.index-perf.csv",
            dtype={"tradeDate": str},
        )
        d.index = pd.to_datetime(d["tradeDate"])
        d = d.loc[: "2015-12-31"]
        x = np.log(d["open"] / d["close"].shift(1)).where((d["open"] > 0) & (d["close"].shift(1) > 0))
        on[cid] = x.replace([np.inf, -np.inf], np.nan)
    eng = _reviewer_engine_ns(bond.reindex(cal).fillna(0.0), tags)
    eng["ON"].update(on)
    L = G["A_OLD"][L1IDS]
    O, rows = eng["run"](L, "2006-01", "2015-12-31", ["B0", "C2", "EW"], True, csi)
    rep = eng["report"](O, rows, L, "2006-01", "2015-11", ["B0", "C2"], {"_": ("2006-01", "2015-11")}, True)
    phases_win = int(rep["C2 好于 B0 的阶段数"].split(" / ")[0])
    return {
        "P1_C2_对等权_t": rep["C2"]["对等权 t"],
        "P1_C2_对B0_每年点": rep["C2"]["对 B0 每年点"],
        "P1_C2_阶段赢B0数": phases_win,
        "three_formal": {
            "五段至少四段好于B0": phases_win >= 4,
            "对等权_t>=1": (rep["C2"]["对等权 t"] or 0) >= 1,
        },
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
    head_now = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    report: dict = {
        "subject_pr": 346,
        "subject_head_expected": SUBJECT_HEAD,
        "subject_head_at_run": head_now,
        "head_drift": head_now != SUBJECT_HEAD,
        "inputs": {},
        "commit_order": {},
        "registration_order_proof": {},
        "independent_recalc": {},
        "rerun_dev_scripts": {},
        "criteria_audit": {},
        "definition_continuity_row55": {},
        "decision_inputs": {},
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
    ind_p3 = independent_p3_headline()
    ind_c2 = independent_c2_p1_headline()
    mem = committed["memory"]
    sw = committed["sw"]
    p3 = sw["P3 申万一级 + 沪深300 2006-01 → 2015-11"]
    p1c2 = sw["P1 子池（10 个一级行业，有开盘价）2006-01 → 2015-11"]
    crit45 = mem["判据"]
    crit_c2 = sw["(一) C2 正式判据"]

    report["independent_recalc"] = {
        "row45": ind45,
        "row45_vs_committed": {
            "新段_S1_净": close(ind45["新段_S1_净_每年点"], -3.6),
            "全段_S1_t": abs((ind45["全段_S1_t"] or 0) - 0.08) <= TOL_T,
        },
        "p3_headline": ind_p3,
        "p3_vs_committed": {
            "B0_对等权": close(ind_p3["B0_对等权_每年点"], p3["B0"]["对等权全部 每年点"]),
            "B0_t": abs((ind_p3["B0_对等权_t"] or 0) - (p3["B0"]["对等权 t"] or 0)) <= TOL_T,
            "C1_对等权": close(ind_p3["C1_对等权_每年点"], p3["C1"]["对等权全部 每年点"]),
            "C1_t": abs((ind_p3["C1_对等权_t"] or 0) - (p3["C1"]["对等权 t"] or 0)) <= TOL_T,
            "C1_对B0": close(ind_p3["C1_对B0_每年点"], p3["C1"]["对 B0 每年点"]),
            "C1_对B0_t": abs((ind_p3["C1_对B0_t"] or 0) - (p3["C1"]["对 B0 t"] or 0)) <= TOL_T,
        },
        "c2_p1_headline": ind_c2,
        "c2_vs_committed": {
            "对等权_t": abs((ind_c2["P1_C2_对等权_t"] or 0) - (p1c2["C2"]["对等权 t"] or 0)) <= TOL_T,
            "对B0_每年点": close(ind_c2["P1_C2_对B0_每年点"], p1c2["C2"]["对 B0 每年点"]),
        },
    }

    report["criteria_audit"] = {
        "row45_preregistered_three": {
            "def_source": "operations/planning row45 + row45运行口径",
            "checks": {
                "新段 S1 净超额 > 0": crit45["新段 S1 净超额 > 0"],
                "新段 S1 > R0": crit45["新段 S1 > R0"],
                "全段 S1 净超额 t ≥ 2": crit45["全段 S1 净超额 t ≥ 2"],
            },
            "all_pass_for_adopt": False,
            "conclusion": crit45["结论"],
        },
        "row56_C2_three_formal": {
            "def_source": "planning row56 + row55 C2判据（P1子池/P2子池）",
            "checks": crit_c2,
            "three_core": {
                "P1子池五段至少四段好于B0": crit_c2["P1 子池五段至少四段好于 B0"],
                "P1子池对等权 t≥1": crit_c2["P1 子池对等权 t ≥ 1"],
                "P1与P2子池对B0同为正": crit_c2["P1 子池、P2 子池对 B0 同为正"],
            },
            "headline_P1_C2_vs_EW_t": p1c2["C2"]["对等权 t"],
        },
        "row56_P3_reference_only": {
            "B0_vs_EW_pts": p3["B0"]["对等权全部 每年点"],
            "B0_vs_EW_t": p3["B0"]["对等权 t"],
            "C1_vs_EW_pts": p3["C1"]["对等权全部 每年点"],
            "C1_vs_B0_pts": p3["C1"]["对 B0 每年点"],
            "C1_vs_B0_t": p3["C1"]["对 B0 t"],
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
    indep_ok = (
        all(report["independent_recalc"]["row45_vs_committed"].values())
        and all(report["independent_recalc"]["p3_vs_committed"].values())
        and all(report["independent_recalc"]["c2_vs_committed"].values())
    )
    inputs_ok = all(v["matches_signed"] for v in report["inputs"].values())
    defs_ok = report["definition_continuity_row55"]["a_decompose_unchanged_vs_row55_main"]

    report["decision_inputs"] = {
        "head_match": not report["head_drift"],
        "registration_order_ok": reg_ok,
        "inputs_ok": inputs_ok,
        "rerun_ok": rerun_ok,
        "independent_spot_ok": indep_ok,
        "row55_definitions_unchanged": defs_ok,
        "row45_three_criteria_fail_as_claimed": not any(
            bool(v) for v in report["criteria_audit"]["row45_preregistered_three"]["checks"].values()
        ),
        "c2_closed_as_claimed": crit_c2["结论"] == "C2 关闭" and crit_c2["换规则"] is False,
    }
    report["decision_inputs"] = {k: bool(v) for k, v in report["decision_inputs"].items()}

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report["decision_inputs"], ensure_ascii=False, indent=2))
    return 0 if all(report["decision_inputs"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())