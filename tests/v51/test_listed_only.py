"""D35 场内口径。默认关闭。不写 oneshot，也不跑组合收益。"""
from __future__ import annotations

import inspect
import sqlite3
import unittest
from pathlib import Path

import pandas as pd

from src.v3.engine.switches import EngineSwitches
from src.v4.engine.apply import _grouped
from src.v4.engine.carriers import (
    MIN_AMOUNT,
    SUBSTITUTES,
    _Candidate,
    build_candidates,
    choose_on,
    listed_carriers,
)
from src.v4.r5.design import Markets, prepare_market
from src.v4.r5.peers import research_panel
from src.v51.execute import open_market
from src.v51.listed import listed_only_enabled, refuse_listed_output, run_listed
from src.v51.oneshot import OUT, OneshotError

ROOT = Path(__file__).resolve().parents[2]


def _candidate(code: str, tier: int, vehicle: str) -> _Candidate:
    day = pd.Timestamp("2010-06-01")
    index = pd.DatetimeIndex([day])
    return _Candidate(
        container="box", code=code, vehicle=vehicle, tier=tier,
        inception="", nav_start="", order=0,
        available=pd.Series([True], index=index),
        median=pd.Series([80_000_000.0], index=index),
        board="main" if vehicle == "etf" else "none",
    )


class ListedDefaults(unittest.TestCase):
    def test_config_and_switches_default_off(self):
        self.assertFalse(listed_only_enabled())
        self.assertFalse(EngineSwitches().listed_only)
        self.assertEqual(MIN_AMOUNT, 30_000_000.0)
        self.assertFalse(inspect.signature(prepare_market).parameters["listed_only"].default)
        self.assertFalse(inspect.signature(Markets.get).parameters["listed_only"].default)
        self.assertFalse(inspect.signature(research_panel).parameters["listed_only"].default)
        self.assertFalse(inspect.signature(open_market).parameters["listed_only"].default)
        self.assertEqual(OUT, ROOT / "results" / "v5" / "oneshot")

    def test_index_pool_rejects_the_switch(self):
        with self.assertRaises(OneshotError):
            refuse_listed_output(ROOT / "results" / "v5" / "oneshot")
        with self.assertRaises(OneshotError):
            refuse_listed_output(ROOT / "results" / "v5" / "oneshot" / "tradable")
        with self.assertRaises(OneshotError):
            run_listed(out=ROOT / "results" / "v5" / "oneshot")
        with self.assertRaisesRegex(Exception, "场内口径只作用于 U-可交易"):
            prepare_market(
                "index", t4=False, allow_substitute=True, spec=object(), listed_only=True)

    def test_listed_filter_drops_otc_and_keeps_510880(self):
        etf = _candidate("510300", 1, "etf")
        otc = _candidate("090010", 2, "otc")
        feeder = _candidate("161211", 3, "near")
        dividend = _candidate("510880", 3, "etf")
        kept = listed_carriers({"box": [etf, otc, feeder, dividend]})["box"]
        self.assertEqual([row.code for row in kept], ["510300", "510880"])
        self.assertIs(kept[1], dividend)
        self.assertEqual(
            frozenset(row["code"] for row in SUBSTITUTES if row["vehicle"] != "etf"),
            frozenset({"161211"}),
        )
        day = pd.Timestamp("2010-06-01")
        self.assertEqual(choose_on([otc], day).label, "otc:090010")
        self.assertIsNone(choose_on(listed_carriers({"box": [otc]})["box"], day))
        self.assertEqual(choose_on(kept, day).label, "etf:510300")


class ListedGrouped(unittest.TestCase):
    def test_off_keeps_tier_2_and_on_drops_it(self):
        con = sqlite3.connect(":memory:")
        dates = pd.bdate_range("2006-01-02", periods=150)
        con.execute("CREATE TABLE bars (code TEXT, adj TEXT, date TEXT, close REAL, amount REAL)")
        con.execute("CREATE TABLE v4_series (code TEXT, kind TEXT, date TEXT, close REAL)")
        con.execute(
            "CREATE TABLE v4_listing (code TEXT, name TEXT, maps_to TEXT, tracked_index TEXT, "
            "inception TEXT, enhanced INTEGER)")
        rows = []
        for i, day in enumerate(dates):
            text = str(day.date())
            rows.append(("H00300", "raw", text, 1000.0, None))
            high = 90_000_000.0 if i < 80 else 1_000_000.0
            rows.append(("510300", "raw", text, 3.0, high))
        con.executemany("INSERT INTO bars VALUES (?, ?, ?, ?, ?)", rows)
        backward = [("510300", "backward", str(day.date()), 3.0) for day in dates]
        nav = [("000311", "otc_nav", str(day.date()), 1.2) for day in dates]
        con.executemany("INSERT INTO v4_series VALUES (?, ?, ?, ?)", backward + nav)
        con.execute(
            "INSERT INTO v4_listing VALUES (?, ?, ?, ?, ?, ?)",
            ("000311", "某某沪深300联接", "csi300", "沪深300指数", "2005-03-01", 0),
        )
        containers = [{
            "id": "csi300", "arm": "main", "asset_class": "A股宽基",
            "execution": [{"code": "510300", "track": "沪深300指数", "name": "沪深300ETF"}],
            "research": {"index_name": "沪深300指数", "index_code": "000300"},
        }]
        end = str(dates[-1].date())
        built = build_candidates(con, containers, dates, end)
        off = _grouped(con, containers, end, EngineSwitches(listed_only=False))
        on = _grouped(con, containers, end, EngineSwitches(listed_only=True))
        self.assertEqual([row.code for row in off["csi300"]], [row.code for row in built["csi300"]])
        self.assertIn("000311", [row.code for row in off["csi300"]])
        self.assertNotIn("000311", [row.code for row in on["csi300"]])
        self.assertTrue(all(row.tier != 2 for row in on["csi300"]))
        cold = dates[140]
        self.assertEqual(choose_on(off["csi300"], cold).label, "otc:000311")
        self.assertIsNone(choose_on(on["csi300"], cold))


if __name__ == "__main__":
    unittest.main()
