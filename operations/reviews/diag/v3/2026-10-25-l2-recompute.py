#!/usr/bin/env python3
"""Independent A-arm U-指数 design-period recompute (Reviewer).

Does not import src.v3.engine. Uses duplicated §4 logic under operations/reviews/diag/v3/l2/.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from operations.reviews.diag.v3.l2.arms import execute
from operations.reviews.diag.v3.l2.market_loader import ROOT as PKG_ROOT, load_containers_from_toml, load_market_index_a
from operations.reviews.diag.v3.l2.spec_loader import load_spec

UNIVERSE = PKG_ROOT / "config" / "v3" / "universe.toml"
SQLITE = PKG_ROOT / "data" / "market.sqlite"
UNIVERSE_SHA = "693b7d4dff91dff4b9bac4a0c1241eb4692f6b3cbd444965440a265ffa32aaff"
DESIGN_END = "2015-12-31"
TRADING_DAYS = 252


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cagr(rets: pd.Series) -> float:
    series = pd.Series(rets, dtype=float).dropna()
    nav = float((1.0 + series).prod())
    years = len(series) / TRADING_DAYS
    return nav ** (1.0 / years) - 1.0


def max_drawdown(rets: pd.Series) -> float:
    series = pd.Series(rets, dtype=float).dropna()
    nav = (1.0 + series).cumprod()
    drawdown = nav / nav.cummax() - 1.0
    return float(drawdown.min())


def main() -> int:
    uni_sha = sha256_file(UNIVERSE)
    if uni_sha != UNIVERSE_SHA:
        raise SystemExit(f"universe SHA mismatch: {uni_sha}")
    spec = load_spec()
    end = pd.Timestamp(DESIGN_END)
    containers = load_containers_from_toml(UNIVERSE)
    market = load_market_index_a(SQLITE, containers, end, spec)
    book = execute(market, spec, "A", allow_after=False)
    net = book.net
    if net.empty:
        raise SystemExit("empty net series")
    if pd.Timestamp(net.index.max()) > end:
        raise SystemExit("net exceeds design end")
    out = {
        "method": "Reviewer independent path: tomllib universe + sqlite bars/nav/dividends; "
        "pandas/numpy §4.1–4.4 duplicated under operations/reviews/diag/v3/l2/ (no src.v3.engine). "
        "Pool U-指数, arm A, end<=2015-12-31. Costs per config/v3/arms.toml fees.",
        "universe_sha256": uni_sha,
        "design_end": DESIGN_END,
        "start": str(net.index[0].date()),
        "end": str(net.index[-1].date()),
        "n_days": len(net),
        "cagr": cagr(net),
        "max_drawdown": max_drawdown(net),
        "libraries": ["pandas", "numpy", "tomllib", "sqlite3", "src.report.fx", "src.research.prereg_v2.engine (cash only)"],
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
