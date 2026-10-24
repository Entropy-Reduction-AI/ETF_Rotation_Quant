#!/usr/bin/env python3
"""Independent prem_episodes replay (Reviewer L3).

Does not import src.v3.premium.*. Logic matches operations/reviews/diag/v3-explore/prem_episodes.py.
Compares to tests/v3/premium/fixtures/prem_episodes.csv (49 segments).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SQLITE = ROOT / "data" / "market.sqlite"
JSON_DIR = ROOT / "incoming" / "2026-10-24-qdii-nav-min"
FIXTURE = ROOT / "tests" / "v3" / "premium" / "fixtures" / "prem_episodes.csv"
OUT = Path(__file__).resolve().parent / "2026-10-25-l3-episodes-compare.json"

DB_CODES = (
    "159509", "159612", "159740", "159866", "159941", "160723", "161129", "501018",
    "513100", "513130", "513180", "513300", "513500", "513520", "513650",
)
JSON_CODES = ("159529", "501225")


def load_series(con: sqlite3.Connection) -> dict[str, tuple[pd.DataFrame, pd.DataFrame]]:
    out: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
    for code in DB_CODES:
        nav = pd.read_sql(
            "select date, unit_nav nav from fund_nav where code=?",
            con,
            params=[code],
            index_col="date",
        )
        px = pd.read_sql(
            "select date, close from bars where adj='raw' and code=?",
            con,
            params=[code],
            index_col="date",
        )
        out[code] = (px, nav)
    for code in JSON_CODES:
        nav_rows = json.loads((JSON_DIR / f"{code}_nav.json").read_text(encoding="utf-8"))
        px_rows = json.loads((JSON_DIR / f"{code}_px.json").read_text(encoding="utf-8"))
        nav = pd.DataFrame(
            [(r["FSRQ"], float(r["DWJZ"])) for r in nav_rows if r["DWJZ"]],
            columns=["date", "nav"],
        ).set_index("date")
        px = pd.DataFrame(
            [(r[0], float(r[2])) for r in px_rows],
            columns=["date", "close"],
        ).drop_duplicates("date").set_index("date")
        out[code] = (px, nav)
    return out


def scan(frames: dict[str, tuple[pd.DataFrame, pd.DataFrame]]) -> pd.DataFrame:
    rows: list[dict] = []
    for code, (price, nav) in frames.items():
        joined = price.join(nav, how="outer").sort_index()
        joined.index = pd.to_datetime(joined.index)
        joined["navl"] = joined["nav"].ffill().shift(1)
        joined = joined.dropna(subset=["close"])
        premium = (joined["close"] / joined["navl"] - 1).dropna()
        premium = premium[premium.index >= "2021-01-01"]
        if len(premium) < 120:
            continue
        baseline = premium.rolling(250, min_periods=120).median().shift(1)
        deviation = premium - baseline
        cursor = 0
        while cursor < len(premium):
            if deviation.iloc[cursor] >= 0.10:
                end = cursor
                while end < len(premium) and deviation.iloc[end] > 0:
                    end += 1
                segment = premium.iloc[cursor:end]
                peak_at = segment.idxmax()
                peak_premium = segment.max()
                base = baseline.loc[peak_at]
                after = premium[peak_at:]
                half = after[after <= base + (peak_premium - base) / 2]
                reverted = half.index[0] if len(half) else None
                record = {
                    "code": str(code).zfill(6),
                    "start": str(segment.index[0].date()),
                    "peak": str(peak_at.date()),
                    "peak_prem": round(float(peak_premium) * 100),
                    "base": round(float(base) * 100),
                    "rise_days": int((peak_at - segment.index[0]).days),
                    "half_revert_days": int((reverted - peak_at).days) if reverted is not None else None,
                    "px_chg": None,
                    "nav_chg": None,
                }
                if reverted is not None:
                    record["px_chg"] = round(
                        (float(joined["close"][reverted]) / float(joined["close"][peak_at]) - 1) * 100,
                        1,
                    )
                    record["nav_chg"] = round(
                        (float(joined["navl"][reverted]) / float(joined["navl"][peak_at]) - 1) * 100,
                        1,
                    )
                rows.append(record)
                cursor = end
            else:
                cursor += 1
    frame = pd.DataFrame(rows)
    return frame.sort_values(["code", "start", "peak"]).reset_index(drop=True)


def canon(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["code"] = out["code"].map(lambda v: str(v).zfill(6))
    for col in ("peak_prem", "base", "rise_days"):
        out[col] = pd.to_numeric(out[col]).astype(int)
    for col in ("half_revert_days", "px_chg", "nav_chg"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.sort_values(["code", "start", "peak"]).reset_index(drop=True)


def main() -> int:
    if not SQLITE.exists():
        print("missing sqlite", file=sys.stderr)
        return 2
    con = sqlite3.connect(f"file:{SQLITE}?mode=ro", uri=True)
    try:
        computed = canon(scan(load_series(con)))
    finally:
        con.close()
    fixture = canon(pd.read_csv(FIXTURE, dtype={"code": str}))
    match = computed.equals(fixture) if len(computed) == len(fixture) else False
    try:
        pd.testing.assert_frame_equal(computed, fixture, check_dtype=False, rtol=0.0, atol=1e-9)
        exact = True
    except AssertionError as exc:
        exact = False
        diff_msg = str(exc)
    else:
        diff_msg = ""

    payload = {
        "reviewer_segments": int(len(computed)),
        "fixture_segments": int(len(fixture)),
        "exact_match": exact and match,
        "crude_161129_2025": computed[
            (computed["code"] == "161129") & (computed["start"] == "2025-04-10")
        ].to_dict(orient="records"),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not payload["exact_match"]:
        print(diff_msg, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
