#!/usr/bin/env python3
"""Independent v4-R2 freeze-equivalence check (Reviewer).

Runs P1 (arm A, index pool, official, design window) with all EngineSwitches off
under PYTHONHASHSEED=0 and compares SHA256 digests to the milestone/v3-code-freeze
reference table. Optionally compares net series to a detached worktree at the
annotated tag commit.

Requires: repo at Dev #67 tip (or post-merge main with R2 engine), LFS market DB.
Does not compute 2016+ portfolio PnL or v4 candidate paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FREEZE_TAG_COMMIT = "b1f84d899f4a37914c1ce4ef0ab16484f0ef7cdb"
EXPECTED = {
    "net": "962178c503df7d1ee900971711271fc4fac4436522053dbc9c297b48c3b8fa57",
    "held": "bdd1521f7d9d66404184351dfe50e3e4681edfd91415e46572394c44d6eea32b",
    "cost": "62b76e5375f73360de7e4b03753808bd00058310c7dc35ce353ca091a4e44e0c",
    "3-week": "75e3f744c2f347781965632729a184cd9c0244efc41a84963f5b3550f0e6e5a6",
    "3-month": "6cbf6fd1e24696d6c855305a63447f0e761f7ca73c6c559a28dfea253243d42f",
    "5-week": "d5bddc5cea82b4aa9bc3b32bda21c8c00e8af66e31f8aac7ed8afafdf10ce760",
    "5-month": "f2470bf01046c3739b4fafd87dc356b80212a52ba2f20db37297c04320478fe3",
    "8-week": "64ed67d0756a69cda899903ea8da7db100828b07f09cd6560a730e5c73d2aa7f",
    "8-month": "83131d7b8d4f010fec33bf799669cfa88bae465d483be7bd03dcee4f3acf1f6e",
}


def _sha(values) -> str:
    array = np.ascontiguousarray(values, dtype=np.float64)
    return hashlib.sha256(array.tobytes()).hexdigest()


def _run_p1(*, use_idle_switches: bool):
    from src.data import db as DB
    from src.v3.data.universe import containers
    from src.v3.engine.arms import execute
    from src.v3.engine.market import load_market
    from src.v3.engine.spec import load_spec
    from src.v3.engine.switches import EngineSwitches

    db = DB.MARKET_DB
    if not db.exists() or db.stat().st_size < 1_000_000:
        raise SystemExit(f"market DB missing or LFS pointer: {db}")

    spec = load_spec()
    market = load_market(
        db, containers(), "A", "index", pd.Timestamp(spec.design_end), spec, history_mode="official"
    )
    kwargs = {}
    if use_idle_switches:
        kwargs["switches"] = EngineSwitches()
    book = execute(market, spec, "A", **kwargs)
    shas = {
        "net": _sha(book.net.to_numpy()),
        "held": _sha(book.held.to_numpy()),
        "cost": _sha(book.cost.to_numpy()),
    }
    for n, freq in ((3, "week"), (3, "month"), (5, "week"), (5, "month"), (8, "week"), (8, "month")):
        shas[f"{n}-{freq}"] = _sha(book.paths[(n, freq)].net.to_numpy())
    meta = {
        "n_days": len(book.net),
        "first_day": str(book.net.index[0].date()),
        "last_day": str(book.net.index[-1].date()),
    }
    return shas, meta, book.net.to_numpy()


def _freeze_net_sha(worktree: Path) -> str | None:
    if not worktree.is_dir():
        return None
    db_link = worktree / "data" / "market.sqlite"
    if not db_link.exists():
        db_link.parent.mkdir(parents=True, exist_ok=True)
        db_link.symlink_to(ROOT / "data" / "market.sqlite")
    code = f"""
import hashlib, numpy as np, pandas as pd
from src.data import db as DB
from src.v3.data.universe import containers
from src.v3.engine.arms import execute
from src.v3.engine.market import load_market
from src.v3.engine.spec import load_spec
spec = load_spec()
market = load_market(DB.MARKET_DB, containers(), "A", "index", pd.Timestamp(spec.design_end), spec, history_mode="official")
book = execute(market, spec, "A")
arr = np.ascontiguousarray(book.net.to_numpy(), dtype=np.float64)
print(hashlib.sha256(arr.tobytes()).hexdigest())
"""
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=worktree,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--freeze-worktree", type=Path, default=None)
    parser.add_argument("--dev-tip", default="")
    args = parser.parse_args()

    if os.environ.get("PYTHONHASHSEED") != "0":
        print("Set PYTHONHASHSEED=0", file=sys.stderr)
        return 2

    plain_shas, meta, plain_net = _run_p1(use_idle_switches=False)
    idle_shas, _, _ = _run_p1(use_idle_switches=True)
    matches = {k: plain_shas[k] == EXPECTED[k] for k in EXPECTED}
    freeze_net = _freeze_net_sha(args.freeze_worktree) if args.freeze_worktree else None

    report = {
        "dev_tip": args.dev_tip or None,
        "pythonhashseed": "0",
        "p1": meta,
        "shas": plain_shas,
        "matches_expected": matches,
        "plain_equals_engine_switches_idle": plain_shas == idle_shas,
        "freeze_tag_commit": FREEZE_TAG_COMMIT,
        "freeze_worktree_net_sha": freeze_net,
        "freeze_net_matches": freeze_net == EXPECTED["net"] if freeze_net else None,
        "decision_inputs_ok": all(matches.values()) and plain_shas == idle_shas,
    }
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    return 0 if report["decision_inputs_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
