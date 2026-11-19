#!/usr/bin/env python3
"""stress.json 字节对照；sim.run bond 省略 vs 1-D 固定 3% 逐位一致。"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).resolve().parent / "d38-r2041-recalc.json"
COMMITTED = ROOT / "results/v6-preflight/stress.json"
TMP = Path(__file__).resolve().parent / "stress.json"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rerun_stress() -> dict:
    spec = importlib.util.spec_from_file_location("stress", ROOT / "scripts/preflight/stress.py")
    mod = importlib.util.module_from_spec(spec)
    sys_argv = sys.argv
    sys.argv = ["stress", str(TMP.parent)]
    assert spec.loader
    spec.loader.exec_module(mod)
    sys.argv = sys_argv
    committed_bytes = COMMITTED.read_bytes()
    rerun_bytes = TMP.read_bytes()
    return {
        "committed_sha256": sha256_file(COMMITTED),
        "rerun_sha256": sha256_file(TMP),
        "byte_identical": committed_bytes == rerun_bytes,
        "json_equal": json.loads(committed_bytes) == json.loads(rerun_bytes),
    }


def bond_dimension_audit() -> dict:
    spec = importlib.util.spec_from_file_location("sim", ROOT / "scripts/preflight/sim.py")
    sim = importlib.util.module_from_spec(spec)
    sys_argv = sys.argv
    sys.argv = ["sim", str(OUT.parent), "1"]
    assert spec.loader
    spec.loader.exec_module(sim)
    sys.argv = sys_argv

    from src.v3.engine.spec import load_spec
    from src.v4.r5.design import Markets

    m = Markets(load_spec()).get("index", t4=False, allow_substitute=True)
    R = m.signal.loc[: "2015-12-31", ["csi300", "ndx100", "spx"]].dropna()
    us = (R["ndx100"] + R["spx"]) / 2
    lr = np.log1p(np.column_stack([R["csi300"].values, us.values]))[None, :, :]
    T = lr.shape[1]
    bd0 = (1 + sim.BOND) ** (1 / sim.D) - 1
    bond_1d = np.full(T, bd0)
    rows = {}
    for kind in ("K0", "K2", "K2A"):
        n0, _, _, _ = sim.run(lr, s_us=0.30, kind=kind, bond=None)
        n1, _, _, _ = sim.run(lr, s_us=0.30, kind=kind, bond=bond_1d)
        rows[kind] = {
            "max_abs_nav_diff": float(np.max(np.abs(n0[0] - n1[0]))),
            "identical_allclose": bool(np.allclose(n0, n1, rtol=0, atol=0)),
        }
    return {"sim_bond_none_vs_1d_fixed_3pct": rows}


def main() -> None:
    payload = {"stress_json_checksum": rerun_stress(), "sim_bond_audit": bond_dimension_audit()}
    data = {}
    if OUT.exists():
        data = json.loads(OUT.read_text(encoding="utf-8"))
    data.update(payload)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()