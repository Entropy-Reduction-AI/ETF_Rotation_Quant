#!/usr/bin/env python3
"""Reviewer 独立手造序列复算（附表 A A1/A2）。不读行情库。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from src.v3.engine.book import leg_cost
from src.v3.engine.limits import FillQuote
from src.v3.engine.sessions import decision_dates
from src.v4.peers import MONTH_END_RULE, SF6_STATUS, load_peer, month_end_sessions, run_peer


def _months(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    year, month = start
    out = []
    while (year, month) <= end:
        out.append((year, month))
        month += 1
        if month == 13:
            year += 1
            month = 1
    return out


def _calendar(extra: dict[tuple[int, int], list[int]] | None = None) -> pd.DatetimeIndex:
    extra = extra or {}
    days = []
    for year, month in _months((2005, 1), (2006, 4)):
        days.append(pd.Timestamp(year, month, 10))
        if (year, month) != (2006, 4):
            days.append(pd.Timestamp(year, month, 20))
        for dom in extra.get((year, month), []):
            days.append(pd.Timestamp(year, month, dom))
    return pd.DatetimeIndex(sorted(set(days)))


def _levels(index, columns, start=100.0, jumps=()):
    frame = pd.DataFrame(float(start), index=index, columns=list(columns), dtype=float)
    for day, column, value in jumps:
        frame.loc[frame.index >= pd.Timestamp(day), column] = float(value)
    return frame


def _zero_cash(index) -> pd.Series:
    return pd.Series(0.0, index=index, dtype=float)


def _slice_holdings(result, keys: list[str]) -> dict[str, list[dict]]:
    out = {}
    for key in keys:
        row = result.close_held.loc[pd.Timestamp(key)]
        out[key] = {c: round(float(row[c]), 4) for c in result.close_held.columns}
    return out


def main() -> int:
    evidence: dict = {
        "dev_tip_note": "run against checkout HEAD",
        "month_end_rule": MONTH_END_RULE,
        "sf6_status": SF6_STATUS,
        "scenarios": {},
    }

    # SF-6 vs decision_dates
    dates = pd.to_datetime([
        "2006-01-30", "2006-01-31", "2006-02-01",
        "2006-04-27", "2006-04-28", "2006-05-08",
    ])
    open_ends = month_end_sessions(dates, calendar_closed=False)
    closed_ends = month_end_sessions(dates, calendar_closed=True)
    dec = decision_dates(dates, "month")
    evidence["sf6_alignment"] = {
        "open": [str(d.date()) for d in open_ends],
        "closed": [str(d.date()) for d in closed_ends],
        "decision_dates_month": [str(d.date()) for d in dec],
        "closed_equals_decision_dates": list(closed_ends) == list(dec),
    }

    # A1: twelve-month wait, bond, fee on fill
    dates = _calendar({(2006, 2): [15]})
    peer = load_peer("A1", "index")
    levels = _levels(dates, [leg.leg_id for leg in peer.legs])
    r1 = run_peer(peer, dates, levels, cash=_zero_cash(dates))
    decision = pd.Timestamp("2006-01-20")
    execute = pd.Timestamp("2006-02-10")
    fees = peer.fees()
    expected_cost, _, _ = leg_cost(
        {"spx": 0.0, "csi300": 0.0, "cgb-10y": 0.0, "cash": 1.0},
        {"spx": 0.0, "csi300": 0.0, "cgb-10y": 1.0, "cash": 0.0},
        fees,
        peer.trade_eps,
    )
    evidence["scenarios"]["a1_twelve_month_bond"] = {
        "decision_target_cgb": float(r1.decisions.loc[decision, "cgb-10y"]),
        "close_held_at_execute": _slice_holdings(r1, [str(execute.date())]),
        "cost_decision": float(r1.cost.loc[decision]),
        "cost_execute": float(r1.cost.loc[execute]),
        "leg_cost_expected_execute": expected_cost,
        "cost_matches_leg_cost": abs(float(r1.cost.loc[execute]) - expected_cost) < 1e-12,
    }

    # A1: crash mid-month — no exit
    dates = _calendar({(2006, 2): [15, 16]})
    levels = _levels(
        dates,
        [leg.leg_id for leg in peer.legs],
        jumps=(
            ("2006-01-20", "spx", 130.0),
            ("2006-02-15", "spx", 70.0),
            ("2006-02-16", "spx", 130.0),
        ),
    )
    r_crash = run_peer(peer, dates, levels, cash=_zero_cash(dates))
    crash = pd.Timestamp("2006-02-15")
    evidence["scenarios"]["a1_crash_no_exit"] = {
        "close_held_spx_crash": float(r_crash.close_held.loc[crash, "spx"]),
        "signal_spx_crash": float(r_crash.signal.loc[crash, "spx"]),
        "cost_crash": float(r_crash.cost.loc[crash]),
        "net_crash": float(r_crash.net.loc[crash]),
        "expected_net": 70.0 / 130.0 - 1.0,
    }

    # A1: limit-up defer
    dates = _calendar({(2006, 2): [15]})
    levels = _levels(
        dates,
        [leg.leg_id for leg in peer.legs],
        jumps=(("2006-01-20", "csi300", 150.0), ("2006-01-20", "spx", 110.0)),
    )
    blocked = pd.Timestamp("2006-02-10")
    retry = pd.Timestamp("2006-02-15")
    quotes = {
        "csi300": FillQuote(
            close=pd.Series({blocked: 10.95, retry: 10.50}),
            board="main",
            prev_close=pd.Series({blocked: 10.0, retry: 10.0}),
        ),
    }
    r_lim = run_peer(peer, dates, levels, cash=_zero_cash(dates), quotes=quotes)
    evidence["scenarios"]["a1_limit_up_defer"] = {
        "close_held_blocked": _slice_holdings(r_lim, [str(blocked.date())]),
        "close_held_retry": _slice_holdings(r_lim, [str(retry.date())]),
        "cost_blocked": float(r_lim.cost.loc[blocked]),
        "cost_retry": float(r_lim.cost.loc[retry]),
    }

    # A2: ten-month sleeves
    dates = _calendar()
    a2 = load_peer("A2", "index")
    columns = [leg.leg_id for leg in a2.legs]
    levels = _levels(
        dates,
        columns,
        start=1.0,
        jumps=(
            ("2005-10-20", "spx", 2.0),
            ("2005-10-20", "hsi", 2.0),
            ("2005-10-20", "gold", 2.0),
            ("2006-01-20", "spx", 0.5),
        ),
    )
    r2 = run_peer(a2, dates, levels, cash=_zero_cash(dates))
    decision_a2 = pd.Timestamp("2005-10-20")
    fill = pd.Timestamp("2005-11-10")
    drop = pd.Timestamp("2006-01-20")
    drop_fill = pd.Timestamp("2006-02-10")
    fees_a2 = a2.fees()
    expected_fill, _, _ = leg_cost(
        {name: 0.0 for name in columns} | {"cash": 1.0},
        {"spx": 0.2, "hsi": 0.2, "csi300": 0.0, "cgb-10y": 0.0, "gold": 0.2, "cash": 0.4},
        fees_a2,
        a2.trade_eps,
    )
    evidence["scenarios"]["a2_ten_month_sleeves"] = {
        "decision_spx": float(r2.decisions.loc[decision_a2, "spx"]),
        "close_held_fill": _slice_holdings(r2, [str(fill.date())]),
        "signal_drop_spx": float(r2.signal.loc[drop, "spx"]),
        "close_held_drop_spx": float(r2.close_held.loc[drop, "spx"]),
        "close_held_drop_fill_spx": float(r2.close_held.loc[drop_fill, "spx"]),
        "cost_fill": float(r2.cost.loc[fill]),
        "leg_cost_expected_fill": expected_fill,
        "cost_matches": abs(float(r2.cost.loc[fill]) - expected_fill) < 1e-12,
    }

    # Config: four runs, switches off
    from src.v4.peers import load_runs

    runs = load_runs()
    evidence["four_runs"] = [
        {
            "peer_id": item.peer_id,
            "pool": item.pool,
            "exit_module": item.exit_module,
            "premium_module": item.premium_module,
            "t1_turn": item.t1_turn,
        }
        for item in runs
    ]

    out_path = Path(__file__).with_suffix(".json")
    out_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    checks = [
        evidence["sf6_alignment"]["closed_equals_decision_dates"],
        evidence["scenarios"]["a1_twelve_month_bond"]["cost_matches_leg_cost"],
        evidence["scenarios"]["a1_crash_no_exit"]["close_held_spx_crash"] == 1.0,
        evidence["scenarios"]["a1_crash_no_exit"]["cost_crash"] == 0.0,
        evidence["scenarios"]["a1_limit_up_defer"]["close_held_blocked"][str(blocked.date())]["cash"] == 1.0,
        evidence["scenarios"]["a1_limit_up_defer"]["close_held_retry"][str(retry.date())]["csi300"] == 1.0,
        evidence["scenarios"]["a2_ten_month_sleeves"]["cost_matches"],
        evidence["scenarios"]["a2_ten_month_sleeves"]["close_held_drop_spx"] > 0.0,
        evidence["scenarios"]["a2_ten_month_sleeves"]["close_held_drop_fill_spx"] == 0.0,
    ]
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
