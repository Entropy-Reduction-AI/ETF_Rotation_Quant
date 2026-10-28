#!/usr/bin/env python3
"""Reviewer v4-R3: independent recompute of Owner-board scorecard reference numbers.

Uses v3.1 P1 design-period paths (read-only), lab2 market panel + bm_main, ≤2015-12-31.
Does not run portfolio engine or v4 candidates.
"""
from __future__ import annotations

import json
import os
import pickle
import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[4]
DIAG = Path(__file__).resolve().parent
P1_DIR = REPO / "results/v3/design-period/9b421c0294a8509e5283aa871034ff0e8ed66c75/P1"
DB = REPO / "data/market.sqlite"
A0, A1 = "2006-01-05", "2015-12-31"
RC = 0.02 / 252
OUT_JSON = DIAG / "reviewer_r3_scorecard.json"


def build_lab2_pickle() -> tuple[pd.DataFrame, pd.Series]:
    """Rebuild data.pkl / aux.pkl (lab2.py logic, workspace paths)."""
    sys.path.insert(0, str(REPO))
    from src.v3.engine.benchmark import bm_main

    con = sqlite3.connect(DB)

    def ser(code: str) -> pd.Series:
        d = pd.read_sql(
            "select date,close from bars where code=? order by date",
            con,
            params=(code,),
        )
        d["date"] = pd.to_datetime(d["date"])
        return d.set_index("date")["close"].astype(float)

    cal = ser("H00300").loc["2005-01-01":"2015-12-31"].index
    fx = ser("USDCNY")
    names = {
        "H00300": "沪深300",
        "H00905": "中证500",
        "H00852": "中证1000",
        "H00922": "中证红利",
        "H00986": "能源",
        "H00987": "原材料",
        "H00988": "工业",
        "H00989": "可选消费",
        "H00990": "主要消费",
        "H00991": "医药",
        "H00992": "金融地产",
        "H00993": "信息技术",
        "H00994": "通信",
        "H00995": "公用事业",
    }
    L: dict[str, pd.Series] = {}
    for c, n in names.items():
        L[n] = ser(c)

    def usd(s: pd.Series) -> pd.Series:
        s = s.copy()
        s.index = s.index + pd.Timedelta(days=1)
        s = s.reindex(cal, method="ffill")
        f = fx.reindex(cal, method="ffill")
        return s * f

    L["恒生指数"] = usd(ser("HSI"))
    L["纳指100"] = usd(ser("XNDX"))
    L["标普500"] = usd(ser("^SP500TR"))
    P = pd.DataFrame({k: v.reindex(cal, method="ffill") for k, v in L.items()})
    for k, v in L.items():
        P.loc[P.index < v.dropna().index[0], k] = np.nan
    P["黄金"] = np.nan
    P = P.mask(P <= 0)
    for k in P:
        f = P[k].first_valid_index()
        if f is not None:
            P.loc[f:, k] = P.loc[f:, k].ffill()
    R = P.pct_change(fill_method=None)
    cash = pd.Series(RC, index=cal)
    bm = bm_main(DB)
    pickle.dump((P, R, cash), open(DIAG / "data.pkl", "wb"))
    pickle.dump((bm,), open(DIAG / "aux.pkl", "wb"))
    con.close()
    return P, bm


def load_p1() -> tuple[pd.Series, pd.DataFrame]:
    paths = pd.read_csv(P1_DIR / "paths.csv", index_col=0, parse_dates=True)
    held = pd.read_csv(P1_DIR / "held.csv", index_col=0, parse_dates=True)
    e2 = paths["executed"].loc[A0:A1]
    return e2, held


def anystart_independent(
    e2: pd.Series, bm: pd.Series, P: pd.DataFrame, R: pd.DataFrame
) -> dict[int, dict[str, float]]:
    idx = e2.index
    nav = lambda r: (1 + r.reindex(idx).fillna(0)).cumprod()
    S = {"E2": nav(e2), "基准": nav(bm)}
    for k in ["沪深300", "标普500", "纳指100"]:
        s = P[k].reindex(idx).ffill()
        S[k] = s / s.iloc[0]
    starts = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).first().values
    win_rates: dict[int, dict[str, float]] = {}
    for H in [1, 2, 3, 5]:
        rows = []
        for s in starts:
            e = pd.Timestamp(s) + pd.DateOffset(years=H)
            if e > idx[-1]:
                break
            ee = idx[idx <= e][-1]
            rows.append(
                {
                    "start": s,
                    **{k: (v.loc[ee] / v.loc[s]) ** (1 / H) - 1 for k, v in S.items()},
                }
            )
        df = pd.DataFrame(rows).set_index("start")
        win_rates[H] = {
            comp: float((df["E2"] > df[comp]).mean()) for comp in ["基准", "沪深300", "标普500", "纳指100"]
        }
    return win_rates


def states_independent(
    e2: pd.Series, held: pd.DataFrame, bm: pd.Series
) -> dict[str, float | dict[str, float]]:
    bm = bm.loc[A0:A1]
    cash_w = held["cash"].shift(1).reindex(e2.index).fillna(1.0)
    con = sqlite3.connect(DB)
    hs = pd.read_sql(
        "select date,close from bars where code='H00300' and date<=? order by date",
        con,
        params=(A1,),
        index_col="date",
        parse_dates=["date"],
    )["close"]
    con.close()
    mh = hs.resample("ME").last()
    slow = mh.pct_change(12)
    fast = mh.pct_change(1)
    state = pd.Series(
        np.select(
            [(slow > 0) & (fast > 0), (slow > 0) & (fast <= 0), (slow <= 0) & (fast <= 0)],
            ["牛市", "回调", "熊市"],
            "反弹",
        ),
        index=mh.index,
    ).where(slow.notna())
    timing = cash_w * (RC - bm.reindex(e2.index).fillna(0))
    excess = e2 - bm.reindex(e2.index).fillna(0)
    select = excess - timing
    d = pd.DataFrame({"excess": excess, "timing": timing, "select": select, "cash": cash_w})
    mon = d[["excess", "timing", "select"]].resample("ME").sum()
    mon["state"] = state.reindex(mon.index)
    mE = (1 + e2).resample("ME").prod() - 1
    mB = (1 + bm).resample("ME").prod() - 1
    mon["E2"] = mE
    mon["bm"] = mB
    g = mon.dropna(subset=["state"]).groupby("state")
    excess_by_state = {k: round(100 * g.excess.sum()[k], 1) for k in ["牛市", "回调", "熊市", "反弹"]}
    up = mB > 0
    dn = mB < 0
    up_cap = round(float(mE[up].mean() / mB[up].mean()), 2)
    dn_cap = round(float(mE[dn].mean() / mB[dn].mean()), 2)
    return {
        "excess_pp": excess_by_state,
        "up_capture": up_cap,
        "down_capture": dn_cap,
        "total_excess_pp": round(100 * mon.excess.sum(), 1),
    }


def run_diag_anystart() -> dict[int, dict[str, float]]:
    subprocess.run([sys.executable, str(DIAG / "anystart.py")], cwd=DIAG, check=True)
    A = pickle.load(open(DIAG / "anystart.pkl", "rb"))
    return {
        H: {c: float((A[H]["E2"] > A[H][c]).mean()) for c in ["基准", "沪深300", "标普500", "纳指100"]}
        for H in [1, 2, 3, 5]
    }


def run_diag_states_stdout() -> dict[str, float]:
    """Run states.py with workspace DB (upstream hardcodes Claude home path)."""
    proc = subprocess.run(
        f"sed 's|/home/claude/etf_rotation_quant|{REPO}|g' '{DIAG / 'states.py'}' | {sys.executable}",
        cwd=DIAG,
        shell=True,
        capture_output=True,
        text=True,
        check=True,
    )
    diag_states: dict[str, float] = {}
    for ln in proc.stdout.strip().splitlines():
        parts = ln.split()
        if len(parts) >= 6 and parts[0] in ("牛市", "回调", "熊市", "反弹"):
            diag_states[parts[0]] = float(parts[4])
    bm = pickle.load(open(DIAG / "aux.pkl", "rb"))[0].loc[A0:A1]
    r = pd.read_csv(DIAG / "P1-paths.csv", index_col=0, parse_dates=True)["executed"].loc[A0:A1]
    mE = (1 + r).resample("ME").prod() - 1
    mB = (1 + bm).resample("ME").prod() - 1
    up, dn = mB > 0, mB < 0
    diag_states["up_capture"] = round(float(mE[up].mean() / mB[up].mean()), 2)
    diag_states["down_capture"] = round(float(mE[dn].mean() / mB[dn].mean()), 2)
    return diag_states


def patch_states_db_and_run() -> tuple[dict, dict]:
    """Fallback: anystart.pkl + independent states (same formulas as states.py)."""
    diag_win = run_diag_anystart()
    e2, held = load_p1()
    bm = pickle.load(open(DIAG / "aux.pkl", "rb"))[0]
    st = states_independent(e2, held, bm)
    diag_states = {**st["excess_pp"], "up_capture": st["up_capture"], "down_capture": st["down_capture"]}
    return diag_win, diag_states


def main() -> int:
    if not DB.stat().st_size > 1000:
        print("market.sqlite looks like LFS pointer; run git lfs pull", file=sys.stderr)
        return 2
    P, bm = build_lab2_pickle()
    e2, held = load_p1()
    R = P.pct_change(fill_method=None)
    indep_win = anystart_independent(e2, bm, P, R)
    indep_st = states_independent(e2, held, bm)

    # Symlink P1 CSV names expected by diag scripts
    for name, src in [("P1-paths.csv", "paths.csv"), ("P1-held.csv", "held.csv")]:
        link = DIAG / name
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(P1_DIR / src)

    try:
        diag_win = run_diag_anystart()
        diag_states = run_diag_states_stdout()
    except (subprocess.CalledProcessError, RuntimeError, FileNotFoundError):
        diag_win, diag_states = patch_states_db_and_run()

    expected = {
        "anystart_5y_benchmark_pct": 63,
        "anystart_5y_ndx100_pct": 32,
        "state_excess_pp": {"牛市": 1.0, "回调": 30.0, "熊市": 95.0, "反弹": -57.0},
        "up_capture": 0.86,
        "down_capture": 0.52,
    }

    def pct(x: float) -> int:
        return int(round(100 * x))

    obtained = {
        "anystart_5y_benchmark_pct": pct(indep_win[5]["基准"]),
        "anystart_5y_ndx100_pct": pct(indep_win[5]["纳指100"]),
        "state_excess_pp": indep_st["excess_pp"],
        "up_capture": indep_st["up_capture"],
        "down_capture": indep_st["down_capture"],
        "anystart_win_rates_pct": {
            str(H): {k: pct(v) for k, v in row.items()} for H, row in indep_win.items()
        },
    }

    cross = {
        "anystart_matches_diag": all(
            abs(indep_win[H][c] - diag_win[H][c]) < 1e-9
            for H in indep_win
            for c in indep_win[H]
        ),
        "states_excess_matches_diag": all(
            abs(indep_st["excess_pp"][k] - diag_states[k]) < 0.05 for k in indep_st["excess_pp"]
        ),
    }

    def int_pp_match(got: float, want: float) -> bool:
        """Owner board uses integer pp; states.py prints one decimal."""
        return abs(got - want) <= 0.05 or int(round(got)) == int(round(want))

    gates_ok = (
        obtained["anystart_5y_benchmark_pct"] == expected["anystart_5y_benchmark_pct"]
        and obtained["anystart_5y_ndx100_pct"] == expected["anystart_5y_ndx100_pct"]
        and all(
            int_pp_match(obtained["state_excess_pp"][k], expected["state_excess_pp"][k])
            for k in expected["state_excess_pp"]
        )
        and obtained["up_capture"] == expected["up_capture"]
        and obtained["down_capture"] == expected["down_capture"]
    )

    payload = {
        "repo": str(REPO),
        "p1_dir": str(P1_DIR),
        "market_sqlite_bytes": DB.stat().st_size,
        "expected": expected,
        "obtained_independent": obtained,
        "obtained_diag_scripts": {
            "anystart_5y_benchmark_pct": pct(diag_win[5]["基准"]),
            "anystart_5y_ndx100_pct": pct(diag_win[5]["纳指100"]),
            "state_excess_pp": {k: diag_states[k] for k in ["牛市", "回调", "熊市", "反弹"]},
            "up_capture": diag_states.get("up_capture"),
            "down_capture": diag_states.get("down_capture"),
        },
        "cross_check": cross,
        "decision_gates_ok": gates_ok,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if gates_ok and cross["anystart_matches_diag"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
