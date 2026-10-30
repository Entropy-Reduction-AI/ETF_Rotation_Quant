"""v4-R2b 开关。不跑 v4 候选的组合收益，也不汇总 2016-01-01 及以后的收益。"""
from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.v3.data.universe import containers
from src.v3.engine.arms import group_decisions
from src.v3.engine.costs import US_SECTOR_LEG, leg_fee
from src.v3.engine.exit import _fill_due_refills
from src.v3.engine.limits import blocked, fill_board_for, limit_ratio
from src.v3.engine.regime import (
    Q_MIN_HISTORY,
    efficiency_series,
    percentile_q,
    sleeve_weights_from_q,
    speed_fraction,
)
from src.v3.engine.spec import load_spec
from src.v3.engine.switches import EngineSwitches
from src.v4.engine.carriers import (
    build_candidates,
    choices_on,
    nth_session_after,
    raw_dates,
    sse_calendar,
)

from src.data import db as DB

ROOT = Path(__file__).resolve().parents[3]
SELECTION = ROOT / "results" / "v4" / "inventory" / "explore-selections.csv"
YEARS = {
    2006: "2006-12-29",
    2007: "2007-12-28",
    2008: "2008-12-31",
    2009: "2009-12-31",
    2010: "2010-12-31",
    2011: "2011-12-30",
    2012: "2012-12-31",
    2013: "2013-12-31",
    2014: "2014-12-31",
    2015: "2015-12-31",
}
MAIN = (
    "csi300", "csi500", "csi1000", "allshare-energy", "allshare-materials",
    "allshare-industrials", "allshare-discretionary", "allshare-staples",
    "allshare-healthcare", "allshare-financials-re", "allshare-it",
    "allshare-communication", "allshare-utilities", "csi-dividend",
)
# 载体表主表。空字符串表示没有载体。
TABLE = {
    "csi300": {2006: "otc:050002", 2007: "otc:050002", 2008: "otc:050002", 2009: "otc:050002",
               2010: "otc:050002", 2011: "otc:050002", 2012: "etf:510300", 2013: "etf:510300",
               2014: "etf:510300", 2015: "etf:510300"},
    "csi500": {2006: "", 2007: "", 2008: "", 2009: "otc:160119", 2010: "otc:160119",
               2011: "otc:160119", 2012: "otc:160119", 2013: "otc:160119",
               2014: "etf:510500", 2015: "etf:510500"},
    "csi-dividend": {2006: "", 2007: "near:510880", 2008: "near:510880", 2009: "near:510880",
                     2010: "otc:090010", 2011: "otc:090010", 2012: "otc:090010",
                     2013: "otc:090010", 2014: "otc:090010", 2015: "otc:090010"},
    "allshare-financials-re": {2006: "", 2007: "", 2008: "", 2009: "",
                               2010: "near:161211", 2011: "near:161211", 2012: "near:161211",
                               2013: "near:161211", 2014: "near:161211", 2015: "otc:001469"},
    "allshare-discretionary": {2006: "", 2007: "", 2008: "", 2009: "", 2010: "", 2011: "",
                               2012: "", 2013: "", 2014: "", 2015: "otc:001133"},
    "allshare-healthcare": {2006: "", 2007: "", 2008: "", 2009: "", 2010: "", 2011: "",
                            2012: "", 2013: "", 2014: "", 2015: "otc:001180"},
    "allshare-it": {2006: "", 2007: "", 2008: "", 2009: "", 2010: "", 2011: "",
                    2012: "", 2013: "", 2014: "", 2015: "otc:000942"},
}
NONE_IDS = (
    "csi1000", "allshare-energy", "allshare-materials", "allshare-industrials",
    "allshare-staples", "allshare-communication", "allshare-utilities",
)


def _label(choice) -> str:
    return "" if choice is None else choice.label


class HandCheckedState(unittest.TestCase):
    def test_q_on_a_five_point_series(self):
        # 窗口 2。价格 10, 13, 12, 14, 11。
        # E(12) = |12-10| / (|13-10|+|12-13|) = 2/4 = 0.5
        # E(14) = |14-13| / (|12-13|+|14-12|) = 1/3
        # E(11) = |11-12| / (|14-12|+|11-14|) = 1/5 = 0.2
        # 历史少于 2 个时 q = 0.5。E(11) 之前两个都比 0.2 大，q = 0。
        prices = pd.Series([10.0, 13.0, 12.0, 14.0, 11.0], index=pd.bdate_range("2006-01-02", periods=5))
        efficiency = efficiency_series(prices, 2)
        self.assertTrue(np.isnan(efficiency.iloc[0]))
        self.assertTrue(np.isnan(efficiency.iloc[1]))
        self.assertAlmostEqual(float(efficiency.iloc[2]), 0.5)
        self.assertAlmostEqual(float(efficiency.iloc[3]), 1.0 / 3.0)
        self.assertAlmostEqual(float(efficiency.iloc[4]), 0.2)
        q = percentile_q(efficiency, min_history=2)
        self.assertAlmostEqual(float(q.iloc[2]), 0.5)
        self.assertAlmostEqual(float(q.iloc[3]), 0.5)
        self.assertAlmostEqual(float(q.iloc[4]), 0.0)
        self.assertAlmostEqual(speed_fraction(0.0), 0.25)
        self.assertAlmostEqual(speed_fraction(0.5), 0.5)
        self.assertAlmostEqual(speed_fraction(1.0), 0.75)
        weights = sleeve_weights_from_q(0.0, (20, 60, 120, 250))
        self.assertEqual(weights, [0.125, 0.125, 0.375, 0.375])
        self.assertEqual(Q_MIN_HISTORY, 250)
        self.assertIsNone(sleeve_weights_from_q(None, (20, 60, 120, 250)))

    def test_short_history_stays_at_one_half_and_a_long_trend_slows_down(self):
        level = pd.Series(np.arange(1, 321, dtype=float), index=pd.bdate_range("2006-01-02", periods=320))
        q = percentile_q(efficiency_series(level, 60))
        # 第 311 个价格（下标 310）之前正好有 250 个 E，而且全是 1，所以 q = 0。
        self.assertAlmostEqual(float(q.iloc[309]), 0.5)
        self.assertAlmostEqual(float(q.iloc[310]), 0.0)
        day = level.index[310]
        names = ["f20", "f60", "s120", "s250"]
        flags = {}
        for length, name in ((20, "f20"), (60, "f60"), (120, "s120"), (250, "s250")):
            flags[length] = {day: {item: (item == name, 1.0 if item == name else 0.0, 0.1, True) for item in names}}
        from tests.v3.engine.test_v4_r2 import TurnAndRefill
        prepared = TurnAndRefill()._prepared(pd.DatetimeIndex([day]), names, flags)
        book = group_decisions(
            prepared, pd.DatetimeIndex([day]), "month", 1, names, "cash",
            {name: name for name in names}, None, (20, 60, 120, 250),
            switches=EngineSwitches(t2_state_weights=True), market_level=level)
        self.assertAlmostEqual(float(book.loc[day, "f20"]), 0.125)
        self.assertAlmostEqual(float(book.loc[day, "s120"]), 0.375)


class FillAndFee(unittest.TestCase):
    def test_buffer_is_half_a_point_inside_the_band(self):
        band10 = limit_ratio("main", "2015-08-24")
        band20 = limit_ratio("chinext", "2020-08-24")
        self.assertTrue(blocked(10.0, 10.95, "buy", band10))
        self.assertFalse(blocked(10.0, 10.94, "buy", band10))
        self.assertTrue(blocked(10.0, 9.05, "sell", band10))
        self.assertFalse(blocked(10.0, 9.06, "sell", band10))
        self.assertTrue(blocked(10.0, 11.95, "buy", band20))
        self.assertFalse(blocked(10.0, 11.94, "buy", band20))
        self.assertEqual(fill_board_for("", "", "A股行业"), "main")
        self.assertEqual(fill_board_for("纳斯达克100指数", "QQQ", "美股宽基"), "none")
        self.assertEqual(fill_board_for("", "159915", "A股宽基"), "main")

    def test_us_sector_fee_and_otc_uses_the_listed_schedule(self):
        spec = load_spec()
        self.assertEqual(US_SECTOR_LEG, 0.0015)
        self.assertEqual(leg_fee("美股行业", spec), 0.0015)
        self.assertEqual(leg_fee("A股宽基", spec, carrier="spdr"), 0.0015)
        self.assertEqual(leg_fee("A股宽基", spec, carrier="otc"), spec.fee("A股宽基"))
        self.assertEqual(leg_fee("A股行业", spec, carrier="otc"), spec.fee("A股行业"))
        self.assertEqual(leg_fee("港股", spec), spec.fee("港股"))

    def test_refill_skips_names_already_held_and_caps_at_the_target(self):
        weights = {"keep": 0.6, "other": 0.0, "nxt": 0.0, "cash": 0.4}
        order = {
            "proceeds": 0.4,
            "exclude": {"sold"},
            "target": {"keep": 0.5, "other": 0.25, "nxt": 0.25, "cash": 0.0},
            "filled": {},
            "armed": True,
        }
        refills = [order]
        cost, bought = _fill_due_refills(
            weights, refills, pd.Timestamp("2006-01-10"), "cash",
            {"keep": 0.001, "other": 0.001, "nxt": 0.001, "cash": 0.0005},
            False, None, ["keep", "other", "nxt", "cash"], 1e-12, 1e-6,
            {}, lambda *_args: 1.0, [])
        self.assertAlmostEqual(weights["keep"], 0.6)
        # 目标权重相同，按容器 id 升序：nxt 在 other 前面。
        self.assertAlmostEqual(weights["nxt"], 0.25)
        self.assertAlmostEqual(weights["other"], 0.15)
        self.assertAlmostEqual(weights["cash"], 0.0)
        self.assertAlmostEqual(bought, 0.4)
        self.assertAlmostEqual(cost, 0.4 * 0.001)
        self.assertEqual(refills, [])


class CarrierTable(unittest.TestCase):
    def test_year_end_matches_the_vehicle_table(self):
        if not DB.MARKET_DB.exists() or DB.MARKET_DB.stat().st_size < 1_000_000:
            self.skipTest("market.sqlite 不在这台机器上")
        con = sqlite3.connect(f"file:{DB.MARKET_DB.resolve()}?mode=ro", uri=True)
        try:
            calendar = sse_calendar(con, "2015-12-31")
            listed = raw_dates(con, "510300", "2015-12-31")
            self.assertEqual(str(nth_session_after(listed[0], calendar).date()), "2012-08-21")
            grouped = build_candidates(
                con, [row for row in containers() if row.get("arm") == "main"], calendar, "2015-12-31")
            for year, text in YEARS.items():
                got = choices_on(grouped, pd.Timestamp(text), list(MAIN) + ["chinext", "star50"])
                for identity, expected in TABLE.items():
                    self.assertEqual(_label(got[identity]), expected[year], f"{identity} {year}")
                for identity in NONE_IDS:
                    self.assertEqual(_label(got[identity]), "", f"{identity} {year}")
                # 2011-06-10 起第 2 档是 050021。场内 159915 当天不够第 1 档时落到这只。
                if year < 2011:
                    self.assertEqual(_label(got["chinext"]), "")
                elif year < 2013:
                    self.assertEqual(_label(got["chinext"]), "otc:050021")
                else:
                    self.assertEqual(_label(got["chinext"]), "etf:159915")
                self.assertEqual(_label(got["star50"]), "")
            spots = {
                ("2012-06-29", "csi300"): "otc:050002",
                ("2012-08-21", "csi300"): "etf:510300",
                ("2009-06-30", "csi500"): "",
                ("2009-09-25", "csi500"): "otc:160119",
                ("2014-02-26", "csi500"): "etf:510500",
                ("2014-02-27", "csi500"): "otc:160119",
                ("2014-06-30", "csi500"): "otc:160119",
                ("2010-04-08", "allshare-financials-re"): "",
                ("2010-04-09", "allshare-financials-re"): "near:161211",
                ("2007-04-18", "csi-dividend"): "",
                ("2007-04-19", "csi-dividend"): "near:510880",
                ("2010-02-01", "csi-dividend"): "near:510880",
                ("2010-02-02", "csi-dividend"): "otc:090010",
                ("2012-06-29", "chinext"): "etf:159915",
                ("2012-12-31", "chinext"): "otc:050021",
                ("2013-01-04", "chinext"): "otc:050021",
                ("2013-01-22", "chinext"): "etf:159915",
            }
            for (text, identity), expected in spots.items():
                got = choices_on(grouped, pd.Timestamp(text), [identity])[identity]
                self.assertEqual(_label(got), expected, f"{identity} {text}")
        finally:
            con.close()


class NewPoolRanks(unittest.TestCase):
    def test_month_end_top8_against_manager_r1(self):
        if not DB.MARKET_DB.exists() or DB.MARKET_DB.stat().st_size < 1_000_000:
            self.skipTest("market.sqlite 不在这台机器上")
        if not SELECTION.exists():
            self.skipTest("没有 explore-selections.csv")
        from src.v3.engine.benchmark import _connect
        from src.v3.engine.market import load_market
        from src.v4.engine.pool import added_signals, month_decision, top_names

        spec = load_spec()
        end = pd.Timestamp(spec.design_end)
        self.assertEqual(str(end.date()), "2015-12-31")
        market = load_market(
            DB.MARKET_DB, containers(), "A", "index", end, spec, history_mode="official")
        self.assertLessEqual(market.dates.max(), end)
        con = _connect(DB.MARKET_DB)
        try:
            r1_sig, r1_fresh = added_signals(
                con, market.dates, spec, "2015-12-31", adjusted=False, hk_fx=False, usd_filled=False,
                hk_same_day=False)
            v4_sig, v4_fresh = added_signals(
                con, market.dates, spec, "2015-12-31", adjusted=True, hk_fx=True, usd_filled=True,
                hk_same_day=True)
            fx_sig, fx_fresh = added_signals(
                con, market.dates, spec, "2015-12-31", adjusted=False, hk_fx=True, usd_filled=True,
                hk_same_day=False)
            adj_sig, adj_fresh = added_signals(
                con, market.dates, spec, "2015-12-31", adjusted=True, hk_fx=False, usd_filled=False,
                hk_same_day=False)
            session_sig, session_fresh = added_signals(
                con, market.dates, spec, "2015-12-31", adjusted=False, hk_fx=False, usd_filled=False,
                hk_same_day=True)
        finally:
            con.close()
        for frame in (r1_sig, v4_sig, fx_sig, adj_sig, session_sig):
            if len(frame.index):
                self.assertLessEqual(pd.Timestamp(frame.index.max()), end)

        def joined(extra_sig, extra_fresh):
            signal = market.signal.copy()
            fresh = market.liquidity.copy()
            for name in extra_sig.columns:
                signal[name] = extra_sig[name]
                fresh[name] = extra_fresh[name].reindex(signal.index).fillna(False)
            names = [name for name in signal.columns if name != market.cash_id]
            return signal, fresh, names

        saved = pd.read_csv(SELECTION)
        saved = saved[saved["pool"] == "new"]
        mismatches = []
        method_rows = []
        months = ((2009, 3), (2011, 6), (2013, 6))
        for year, month in months:
            day = month_decision(market.dates, year, month)
            for length in (20, 60, 120, 250):
                want = saved[
                    (saved["date"] == str(day.date())) & (saved["lookback"] == length)
                ].sort_values("rank")
                self.assertLessEqual(len(want), 8, f"{day.date()} {length}")
                expected = want["name"].tolist()
                signal, fresh, names = joined(r1_sig, r1_fresh)
                got = top_names(signal, fresh, market.cash_id, names, spec, day, length)
                if got != expected:
                    mismatches.append(f"{day.date()} L={length} engine={got} csv={expected}")
                v4_signal, v4_gate, v4_names = joined(v4_sig, v4_fresh)
                official = top_names(v4_signal, v4_gate, market.cash_id, v4_names, spec, day, length)
                fx_only = top_names(*_pack(joined(fx_sig, fx_fresh), market, spec, day, length))
                adj_only = top_names(*_pack(joined(adj_sig, adj_fresh), market, spec, day, length))
                session_only = top_names(*_pack(joined(session_sig, session_fresh), market, spec, day, length))
                if official != expected:
                    kind = []
                    if fx_only != got:
                        kind.append("fx")
                    if adj_only != got:
                        kind.append("adjust")
                    if session_only != got:
                        kind.append("session")
                    if not kind:
                        kind.append("combined")
                    method_rows.append(
                        f"{day.date()} L={length} [{'+'.join(kind)}] r1={got} v4={official}")
        self.assertEqual(mismatches, [])
        out = Path("/opt/cursor/artifacts/v4-r2b-rank-diff.txt")
        out.parent.mkdir(parents=True, exist_ok=True)
        text = "\n".join(method_rows) if method_rows else "official top8 matches Manager R1 on the three month-ends"
        out.write_text(text + "\n", encoding="utf-8")
        if any(row.endswith("[other]") or "[other]" in row for row in method_rows):
            self.fail("排名差异不是汇率或后复权造成的:\n" + "\n".join(method_rows))


def _pack(parts, market, spec, day, length):
    signal, fresh, names = parts
    return signal, fresh, market.cash_id, names, spec, day, length


if __name__ == "__main__":
    unittest.main()
