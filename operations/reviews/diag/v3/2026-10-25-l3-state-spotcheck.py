#!/usr/bin/env python3
"""Independent §5.2 state spot-check at Dev-listed dates (Reviewer L3).

Uses src.v3.engine.prices.lag_asof only (not src.v3.premium). State rules duplicated from prereg §5.2.
"""
from __future__ import annotations

import json
import math
import sqlite3
import statistics
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.v3.engine.prices import lag_asof

SQLITE = ROOT / "data" / "market.sqlite"
OUT = Path(__file__).resolve().parent / "2026-10-25-l3-state-spotcheck.json"

NAV_LAG = 2
NAV_DAYS = 20
BASELINE_CUT = 0.05
DISCOUNT = 0.05
PULSE = "脉冲"
STRUCTURAL_HIGH = "结构型冲高"
STRUCTURAL_DISCOUNT = "结构型折价"
NORMAL = "常态"

CHECKS = [
    ("2025-04-07", "513100", 250, 0.10, NORMAL),
    ("2025-04-07", "159941", 250, 0.10, NORMAL),
    ("2025-04-07", "159509", 250, 0.10, STRUCTURAL_DISCOUNT),
    ("2025-04-30", "513100", 250, 0.10, NORMAL),
    ("2025-04-30", "159941", 250, 0.10, NORMAL),
    ("2025-04-30", "159509", 250, 0.10, NORMAL),
    ("2026-03-11", "161129", 250, 0.10, NORMAL),
    ("2026-03-11", "160723", 250, 0.10, NORMAL),
    ("2026-03-11", "501018", 250, 0.10, NORMAL),
    ("2026-03-31", "161129", 250, 0.10, PULSE),
    ("2026-03-31", "160723", 250, 0.10, PULSE),
    ("2026-03-31", "501018", 250, 0.10, PULSE),
    ("2026-03-31", "513100", 250, 0.10, NORMAL),
    ("2026-03-31", "159529", 120, 0.10, NORMAL),
    ("2026-03-31", "159529", 250, 0.15, STRUCTURAL_DISCOUNT),
]


def _ge(a: float, b: float) -> bool:
    return a > b or math.isclose(a, b, abs_tol=1e-12, rel_tol=0.0)


def _le(a: float, b: float) -> bool:
    return a < b or math.isclose(a, b, abs_tol=1e-12, rel_tol=0.0)


def classify(p: float, b: float, d: float, nav_ret: float, theta: float) -> str:
    if _le(b, BASELINE_CUT) and _ge(d, theta):
        return PULSE
    if not _le(b, BASELINE_CUT) and _ge(d, theta):
        return STRUCTURAL_HIGH
    if not _le(b, BASELINE_CUT) and _le(d, -DISCOUNT) and nav_ret < 0.0:
        return STRUCTURAL_DISCOUNT
    return NORMAL


def load_calendar(con: sqlite3.Connection) -> pd.DatetimeIndex:
    rows = con.execute("SELECT date FROM calendar ORDER BY date").fetchall()
    return pd.DatetimeIndex(pd.to_datetime([r[0] for r in rows]))


def load_close(con: sqlite3.Connection, code: str) -> pd.Series:
    frame = pd.read_sql(
        "SELECT date, close FROM bars WHERE adj='raw' AND code=? ORDER BY date",
        con,
        params=(code,),
        index_col="date",
    )
    s = pd.Series(frame["close"], dtype=float)
    s.index = pd.to_datetime(s.index)
    return s


def load_nav(con: sqlite3.Connection, code: str) -> pd.Series:
    frame = pd.read_sql(
        "SELECT date, unit_nav FROM fund_nav WHERE code=? ORDER BY date",
        con,
        params=(code,),
        index_col="date",
    )
    s = pd.Series(frame["unit_nav"], dtype=float)
    s.index = pd.to_datetime(s.index)
    return s


def metrics(
    close: pd.Series,
    nav: pd.Series,
    calendar: pd.DatetimeIndex,
    day: str,
    window: int,
    theta: float,
) -> dict:
    days = pd.DatetimeIndex(calendar).sort_values().unique()
    prices = close.sort_index()
    prices = prices[prices > 0]
    values = nav.sort_index()
    values = values[values > 0]
    aligned = prices.reindex(days)
    lagged = lag_asof(values, days, NAV_LAG)
    premium = aligned / lagged - 1.0
    premium = premium.where(aligned.notna() & lagged.gt(0))
    finite = premium.dropna()
    median = finite.rolling(window, min_periods=window).median().reindex(days)
    deviation = premium - median
    nav_return = lagged / lagged.shift(NAV_DAYS) - 1.0
    stamp = pd.Timestamp(day)
    p = float(premium.loc[stamp])
    b = float(median.loc[stamp])
    d = float(deviation.loc[stamp])
    nr = float(nav_return.loc[stamp])
    hist = premium.loc[:stamp].dropna()
    manual_b = statistics.median([float(x) for x in hist.iloc[-window:]])
    state = classify(p, b, d, nr, theta)
    return {
        "premium": round(p, 6),
        "baseline": round(b, 6),
        "baseline_manual": round(manual_b, 6),
        "deviation": round(d, 6),
        "nav_return": round(nr, 6),
        "state": state,
    }


def main() -> int:
    con = sqlite3.connect(f"file:{SQLITE}?mode=ro", uri=True)
    calendar = load_calendar(con)
    codes = sorted({c[1] for c in CHECKS})
    prices = {c: load_close(con, c) for c in codes}
    navs = {c: load_nav(con, c) for c in codes}
    con.close()

    rows = []
    ok = True
    for day, code, window, theta, expected in CHECKS:
        m = metrics(prices[code], navs[code], calendar, day, window, theta)
        passed = m["state"] == expected
        ok = ok and passed
        rows.append(
            {
                "date": day,
                "code": code,
                "W": window,
                "theta": theta,
                "expected": expected,
                "got": m["state"],
                "pass": passed,
                **m,
            }
        )
    payload = {"all_pass": ok, "checks": rows}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
