"""附表 A 的 A1 / A2。只用手造序列，不读行情库，不算 2016 年以后的收益。"""
from __future__ import annotations

import ast
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from src.v3.engine.book import RunnerError, leg_cost
from src.v3.engine.limits import FillQuote
from src.v3.engine.sessions import decision_dates
from src.v4.peers import MONTH_END_RULE, SF6_STATUS, load_peer, load_runs, month_end_sessions, run_peer
from src.v4.peers.config import PeerError
from src.v4.peers.signals import trailing_cash_return, trailing_price_return

ROOT = Path(__file__).resolve().parents[2]
PEERS = ROOT / "src" / "v4" / "peers"


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
    """每月 10 日和 20 日。20 日是该月最后一笔。2006-04 只有 10 日，用来截断。"""
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


class Calendar(unittest.TestCase):
    def test_month_end_is_the_last_sse_session_not_the_calendar_day(self):
        # 2006-01-31 是交易日；2006-04 的日历停在 28 日，30 日不在日历里。
        dates = pd.to_datetime([
            "2006-01-30", "2006-01-31", "2006-02-01",
            "2006-04-27", "2006-04-28", "2006-05-08",
        ])
        ends = month_end_sessions(dates, calendar_closed=False)
        # 1 月 30 日不是月末，因为 31 日仍是这个月的交易日。
        # 2 月只有 1 日这一笔，下一笔已经到 4 月，所以 2 月 1 日就是 2 月的月末。
        # 4 月的月末是日历里的 28 日，不是自然月的 30 日。5 月被截断，不算。
        self.assertEqual(
            [str(day.date()) for day in ends],
            ["2006-01-31", "2006-02-01", "2006-04-28"],
        )
        self.assertNotIn(pd.Timestamp("2006-01-30"), ends)
        self.assertNotIn(pd.Timestamp("2006-04-27"), ends)
        self.assertNotIn(pd.Timestamp("2006-05-08"), ends)
        closed = month_end_sessions(dates, calendar_closed=True)
        self.assertEqual(list(closed), list(decision_dates(dates, "month")))
        self.assertEqual(SF6_STATUS, "confirmed")
        self.assertEqual(MONTH_END_RULE, "sse-last-session-of-calendar-month")

    def test_partial_month_does_not_decide_or_trade(self):
        dates = pd.to_datetime(["2006-03-10", "2006-03-16", "2006-03-21"])
        peer = load_peer("A1", "index")
        levels = _levels(dates, ["spx", "csi300", "cgb-10y"])
        result = run_peer(peer, dates, levels, cash=_zero_cash(dates), calendar_closed=False)
        self.assertTrue(result.decisions.empty)
        self.assertTrue((result.signal["cash"] == 1.0).all())
        self.assertTrue((result.close_held["cash"] == 1.0).all())
        self.assertTrue((result.cost == 0.0).all())


class Config(unittest.TestCase):
    def test_four_runs_share_v4_costs_and_leave_switches_off(self):
        runs = load_runs()
        self.assertEqual(
            [(item.peer_id, item.pool) for item in runs],
            [("A1", "index"), ("A1", "tradable"), ("A2", "index"), ("A2", "tradable")],
        )
        fees = {
            "spx": 0.0005,
            "csi300": 0.0005,
            "cgb-10y": 0.0005,
            "hsi": 0.0010,
            "gold": 0.0010,
        }
        for item in runs:
            self.assertFalse(item.exit_module)
            self.assertFalse(item.premium_module)
            self.assertFalse(item.t1_turn)
            self.assertFalse(item.t2_state_weights)
            self.assertFalse(item.t3_refill)
            self.assertFalse(item.t4_pool)
            self.assertEqual(item.cash_annual, 0.02)
            self.assertEqual(item.trading_days, 252)
            self.assertEqual(item.cash_fee, 0.0005)
            self.assertEqual(item.month_end_rule, MONTH_END_RULE)
            for leg in item.legs:
                self.assertEqual(leg.fee, fees[leg.leg_id])
        a1 = load_peer("A1", "tradable")
        a2 = load_peer("A2", "index")
        self.assertEqual([leg.series_code for leg in a1.legs], ["^SP500TR", "H00300", "CBA04501"])
        self.assertEqual(
            [leg.series_code for leg in a2.legs],
            ["^SP500TR", "HSI", "H00300", "CBA04501", "Au99.99"],
        )
        self.assertEqual(a2.sleeve_weight, 0.2)
        with self.assertRaises(PeerError):
            replace(a1, exit_module=True)
        with self.assertRaises(PeerError):
            replace(a2, t4_pool=True)

    def test_sources_do_not_import_exit_premium_or_the_market_db(self):
        forbidden = ("src.v3.engine.exit", "src.v3.premium", "src.v4.engine.apply", "sqlite3")
        for path in PEERS.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                for name in names:
                    for item in forbidden:
                        self.assertNotIn(item, name, f"{path.name} imports {name}")


class DualMomentum(unittest.TestCase):
    def test_signal_waits_for_twelve_months_then_holds_until_the_next_session(self):
        dates = _calendar({(2006, 2): [15]})
        peer = load_peer("A1", "index")
        levels = _levels(dates, [leg.leg_id for leg in peer.legs])
        cash = _zero_cash(dates)
        result = run_peer(peer, dates, levels, cash=cash)
        early = pd.Timestamp("2005-12-20")
        decision = pd.Timestamp("2006-01-20")
        execute = pd.Timestamp("2006-02-10")
        mid = pd.Timestamp("2006-02-15")
        nxt = pd.Timestamp("2006-02-20")
        self.assertEqual(result.month_end_rule, MONTH_END_RULE)
        self.assertNotIn(pd.Timestamp("2006-04-10"), result.decisions.index)
        self.assertIn(decision, result.decisions.index)
        # 平的价格、零现金：12 个月收益都是 0，不高于现金，全仓国债。
        self.assertEqual(float(result.signal.loc[early, "cash"]), 1.0)
        self.assertEqual(float(result.decisions.loc[decision, "cgb-10y"]), 1.0)
        self.assertEqual(float(result.signal.loc[decision, "cgb-10y"]), 1.0)
        self.assertEqual(float(result.close_held.loc[decision, "cash"]), 1.0)
        self.assertEqual(float(result.held.loc[execute, "cash"]), 1.0)
        self.assertEqual(float(result.close_held.loc[execute, "cgb-10y"]), 1.0)
        self.assertEqual(float(result.signal.loc[execute, "cgb-10y"]), 1.0)
        self.assertEqual(float(result.signal.loc[mid, "cgb-10y"]), 1.0)
        self.assertEqual(float(result.close_held.loc[mid, "cgb-10y"]), 1.0)
        self.assertTrue(result.signal.loc[execute].equals(result.signal.loc[mid]))
        self.assertEqual(float(result.close_held.loc[nxt, "cgb-10y"]), 1.0)
        self.assertEqual(float(result.cost.loc[decision]), 0.0)
        fees = peer.fees()
        expected, _buy, _sell = leg_cost(
            {"spx": 0.0, "csi300": 0.0, "cgb-10y": 0.0, "cash": 1.0},
            {"spx": 0.0, "csi300": 0.0, "cgb-10y": 1.0, "cash": 0.0},
            fees, peer.trade_eps)
        self.assertAlmostEqual(float(result.cost.loc[execute]), expected)
        self.assertAlmostEqual(expected, 0.001)
        self.assertEqual(float(result.cost.loc[mid]), 0.0)

    def test_relative_winner_flips_on_the_next_month_and_not_the_same_day(self):
        dates = _calendar()
        peer = load_peer("A1", "index")
        levels = _levels(
            dates, [leg.leg_id for leg in peer.legs],
            jumps=(
                ("2006-01-20", "spx", 130.0),
                ("2006-02-20", "csi300", 200.0),
            ),
        )
        result = run_peer(peer, dates, levels, cash=_zero_cash(dates))
        first = pd.Timestamp("2006-01-20")
        first_fill = pd.Timestamp("2006-02-10")
        second = pd.Timestamp("2006-02-20")
        second_fill = pd.Timestamp("2006-03-10")
        ends = result.decisions.index
        self.assertAlmostEqual(trailing_price_return(levels["spx"], ends, first, 12), 0.30)
        self.assertAlmostEqual(trailing_price_return(levels["csi300"], ends, first, 12), 0.0)
        self.assertEqual(float(result.signal.loc[first, "spx"]), 1.0)
        self.assertEqual(float(result.close_held.loc[first, "cash"]), 1.0)
        self.assertEqual(float(result.close_held.loc[first_fill, "spx"]), 1.0)
        self.assertEqual(float(result.signal.loc[first_fill, "spx"]), 1.0)
        # 2 月 20 日才改信号。当天收盘仍是标普，沪深300 要到 3 月 10 日才成交。
        self.assertEqual(float(result.signal.loc[second, "csi300"]), 1.0)
        self.assertEqual(float(result.close_held.loc[second, "spx"]), 1.0)
        self.assertEqual(float(result.held.loc[second_fill, "spx"]), 1.0)
        self.assertEqual(float(result.close_held.loc[second_fill, "csi300"]), 1.0)
        self.assertEqual(float(result.cost.loc[second]), 0.0)

    def test_fill_day_that_is_also_a_new_month_end_does_not_trade_the_new_signal(self):
        # 每个月只有一笔。下一笔既是上月的成交日，也是这个月的月末决策日。
        dates = pd.DatetimeIndex([
            pd.Timestamp(year, month, 28)
            for year, month in _months((2005, 1), (2006, 4))
        ])
        peer = load_peer("A1", "index")
        levels = _levels(
            dates, [leg.leg_id for leg in peer.legs],
            jumps=(("2006-02-28", "spx", 130.0),),
        )
        result = run_peer(peer, dates, levels, cash=_zero_cash(dates))
        january = pd.Timestamp("2006-01-28")
        february = pd.Timestamp("2006-02-28")
        march = pd.Timestamp("2006-03-28")
        self.assertEqual(float(result.signal.loc[january, "cgb-10y"]), 1.0)
        self.assertEqual(float(result.close_held.loc[january, "cash"]), 1.0)
        self.assertEqual(float(result.signal.loc[february, "spx"]), 1.0)
        self.assertEqual(float(result.held.loc[february, "cash"]), 1.0)
        self.assertEqual(float(result.close_held.loc[february, "cgb-10y"]), 1.0)
        self.assertEqual(float(result.close_held.loc[march, "spx"]), 1.0)

    def test_missing_bond_or_missing_relative_return_stays_in_cash(self):
        dates = _calendar()
        peer = load_peer("A1", "index")
        levels = _levels(dates, [leg.leg_id for leg in peer.legs])
        levels["cgb-10y"] = np.nan
        cash = _zero_cash(dates)
        result = run_peer(peer, dates, levels, cash=cash)
        decision = pd.Timestamp("2006-01-20")
        self.assertEqual(float(result.decisions.loc[decision, "cash"]), 1.0)

        levels = _levels(dates, [leg.leg_id for leg in peer.legs], jumps=(("2006-01-20", "spx", 130.0),))
        levels["csi300"] = np.nan
        result = run_peer(peer, dates, levels, cash=cash)
        self.assertEqual(float(result.decisions.loc[decision, "cash"]), 1.0)

    def test_tie_keeps_spx_and_equal_hurdle_keeps_the_bond(self):
        dates = _calendar()
        peer = load_peer("A1", "index")
        levels = _levels(
            dates, [leg.leg_id for leg in peer.legs],
            jumps=(
                ("2006-01-20", "spx", 120.0),
                ("2006-01-20", "csi300", 120.0),
            ),
        )
        result = run_peer(peer, dates, levels, cash=_zero_cash(dates))
        decision = pd.Timestamp("2006-01-20")
        self.assertEqual(float(result.decisions.loc[decision, "spx"]), 1.0)
        flat = _levels(dates, [leg.leg_id for leg in peer.legs])
        bonded = run_peer(peer, dates, flat, cash=_zero_cash(dates))
        self.assertEqual(float(bonded.decisions.loc[decision, "cgb-10y"]), 1.0)

    def test_no_exit_when_the_held_leg_drops(self):
        dates = _calendar({(2006, 2): [15, 16]})
        peer = load_peer("A1", "index")
        levels = _levels(
            dates, [leg.leg_id for leg in peer.legs],
            jumps=(
                ("2006-01-20", "spx", 130.0),
                ("2006-02-15", "spx", 70.0),
                ("2006-02-16", "spx", 130.0),
            ),
        )
        result = run_peer(peer, dates, levels, cash=_zero_cash(dates))
        crash = pd.Timestamp("2006-02-15")
        restored = pd.Timestamp("2006-02-16")
        self.assertEqual(float(result.close_held.loc[crash, "spx"]), 1.0)
        self.assertEqual(float(result.signal.loc[crash, "spx"]), 1.0)
        self.assertEqual(float(result.cost.loc[crash]), 0.0)
        self.assertAlmostEqual(float(result.net.loc[crash]), 70.0 / 130.0 - 1.0)
        self.assertEqual(float(result.close_held.loc[restored, "spx"]), 1.0)
        self.assertEqual(float(result.signal.loc[restored, "spx"]), 1.0)

    def test_limit_up_defers_the_buy_to_the_next_session(self):
        dates = _calendar({(2006, 2): [15]})
        peer = load_peer("A1", "index")
        levels = _levels(
            dates, [leg.leg_id for leg in peer.legs],
            jumps=(
                ("2006-01-20", "csi300", 150.0),
                ("2006-01-20", "spx", 110.0),
            ),
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
        result = run_peer(peer, dates, levels, cash=_zero_cash(dates), quotes=quotes)
        decision = pd.Timestamp("2006-01-20")
        self.assertEqual(float(result.signal.loc[decision, "csi300"]), 1.0)
        self.assertEqual(float(result.close_held.loc[blocked, "cash"]), 1.0)
        self.assertEqual(float(result.cost.loc[blocked]), 0.0)
        self.assertEqual(float(result.signal.loc[retry, "csi300"]), 1.0)
        self.assertEqual(float(result.close_held.loc[retry, "csi300"]), 1.0)
        self.assertAlmostEqual(float(result.cost.loc[retry]), 0.001)

    def test_tradable_without_a_carrier_holds_cash_until_the_mask_allows_it(self):
        dates = _calendar()
        levels = _levels(
            dates, ["spx", "csi300", "cgb-10y"],
            jumps=(("2006-01-20", "spx", 130.0),),
        )
        decision = pd.Timestamp("2006-01-20")
        fill = pd.Timestamp("2006-02-10")
        blocked = pd.DataFrame(True, index=dates, columns=["spx", "csi300", "cgb-10y"])
        blocked.loc[decision, "spx"] = False
        tradable = run_peer(
            load_peer("A1", "tradable"), dates, levels, cash=_zero_cash(dates), carriers=blocked)
        index = run_peer(load_peer("A1", "index"), dates, levels, cash=_zero_cash(dates))
        self.assertEqual(float(index.decisions.loc[decision, "spx"]), 1.0)
        self.assertEqual(float(tradable.decisions.loc[decision, "cash"]), 1.0)
        self.assertEqual(float(tradable.close_held.loc[fill, "cash"]), 1.0)
        with self.assertRaises(PeerError):
            run_peer(load_peer("A1", "index"), dates, levels, carriers=blocked)
        with self.assertRaises(PeerError):
            run_peer(load_peer("A1", "tradable"), dates, levels)

    def test_refuses_dates_after_the_design_window(self):
        dates = pd.to_datetime(["2015-12-31", "2016-01-04"])
        peer = load_peer("A1", "index")
        levels = _levels(dates, [leg.leg_id for leg in peer.legs])
        with self.assertRaises(RunnerError):
            run_peer(peer, dates, levels)


class TenMonth(unittest.TestCase):
    def test_each_sleeve_turns_on_after_ten_closes_and_stays_put_inside_the_month(self):
        dates = _calendar()
        peer = load_peer("A2", "index")
        columns = [leg.leg_id for leg in peer.legs]
        # 前 9 个月收盘是 1，从 2005-10-20 起标普、恒生、黄金升到 2。沪深300 和国债保持 1，不高于均值。
        levels = _levels(dates, columns, start=1.0, jumps=(
            ("2005-10-20", "spx", 2.0),
            ("2005-10-20", "hsi", 2.0),
            ("2005-10-20", "gold", 2.0),
            ("2006-01-20", "spx", 0.5),
        ))
        result = run_peer(peer, dates, levels, cash=_zero_cash(dates))
        too_soon = pd.Timestamp("2005-09-20")
        decision = pd.Timestamp("2005-10-20")
        fill = pd.Timestamp("2005-11-10")
        still = pd.Timestamp("2005-11-20")
        drop = pd.Timestamp("2006-01-20")
        drop_fill = pd.Timestamp("2006-02-10")
        self.assertEqual(float(result.decisions.loc[too_soon, "cash"]), 1.0)
        for name in ("spx", "hsi", "gold"):
            self.assertEqual(float(result.decisions.loc[decision, name]), 0.2)
        self.assertEqual(float(result.decisions.loc[decision, "csi300"]), 0.0)
        self.assertEqual(float(result.decisions.loc[decision, "cgb-10y"]), 0.0)
        self.assertAlmostEqual(float(result.decisions.loc[decision].sum()), 1.0)
        self.assertEqual(float(result.close_held.loc[decision, "cash"]), 1.0)
        self.assertEqual(float(result.close_held.loc[fill, "spx"]), 0.2)
        self.assertEqual(float(result.close_held.loc[fill, "hsi"]), 0.2)
        self.assertEqual(float(result.close_held.loc[fill, "gold"]), 0.2)
        self.assertAlmostEqual(float(result.close_held.loc[fill, "cash"]), 0.4)
        self.assertTrue(result.close_held.loc[fill].equals(result.close_held.loc[still]))
        self.assertTrue(result.signal.loc[fill].equals(result.signal.loc[still]))
        # 标普在 1 月决策日跌破均线，但仓位要到 2 月 10 日才减掉。
        self.assertEqual(float(result.signal.loc[drop, "spx"]), 0.0)
        self.assertGreater(float(result.close_held.loc[drop, "spx"]), 0.0)
        self.assertEqual(float(result.close_held.loc[drop_fill, "spx"]), 0.0)
        self.assertEqual(float(result.close_held.loc[drop_fill, "hsi"]), 0.2)
        self.assertEqual(float(result.close_held.loc[drop_fill, "gold"]), 0.2)
        fees = peer.fees()
        expected, _buy, _sell = leg_cost(
            {name: 0.0 for name in columns} | {"cash": 1.0},
            {"spx": 0.2, "hsi": 0.2, "csi300": 0.0, "cgb-10y": 0.0, "gold": 0.2, "cash": 0.4},
            fees, peer.trade_eps)
        self.assertAlmostEqual(float(result.cost.loc[fill]), expected)
        # 现金卖出的是 0.6，不是剩下的 0.4。
        self.assertAlmostEqual(expected, 0.2 * 0.0005 + 0.2 * 0.0010 + 0.2 * 0.0010 + 0.6 * 0.0005)

    def test_tradable_sleeve_without_a_carrier_stays_cash(self):
        dates = _calendar()
        peer = load_peer("A2", "tradable")
        columns = [leg.leg_id for leg in peer.legs]
        levels = _levels(dates, columns, start=1.0, jumps=(
            ("2005-10-20", "spx", 2.0),
            ("2005-10-20", "hsi", 2.0),
            ("2005-10-20", "gold", 2.0),
        ))
        mask = pd.DataFrame(True, index=dates, columns=columns)
        decision = pd.Timestamp("2005-10-20")
        mask.loc[decision, "gold"] = False
        result = run_peer(peer, dates, levels, cash=_zero_cash(dates), carriers=mask)
        fill = pd.Timestamp("2005-11-10")
        self.assertEqual(float(result.decisions.loc[decision, "gold"]), 0.0)
        self.assertEqual(float(result.decisions.loc[decision, "spx"]), 0.2)
        self.assertAlmostEqual(float(result.close_held.loc[fill, "cash"]), 0.6)
        self.assertEqual(float(result.close_held.loc[fill, "gold"]), 0.0)

    def test_default_cash_hurdle_uses_the_v4_daily_rate(self):
        dates = _calendar()
        peer = load_peer("A1", "index")
        levels = _levels(
            dates, [leg.leg_id for leg in peer.legs],
            jumps=(("2006-01-20", "spx", 130.0),),
        )
        result = run_peer(peer, dates, levels)
        decision = pd.Timestamp("2006-01-20")
        cash = pd.Series(0.02 / 252, index=dates)
        hurdle = trailing_cash_return(cash, result.decisions.index, decision, 12)
        self.assertGreater(0.30, hurdle)
        self.assertEqual(float(result.decisions.loc[decision, "spx"]), 1.0)
        self.assertGreater(hurdle, 0.0)


class TradableResearchSignal(unittest.TestCase):
    def test_a1_holds_csi300_when_spx_has_no_carrier_but_csi300_is_stronger(self):
        """月末判断用研究序列。标普没有载体、沪深300 更强且当天有载体时，持有沪深300。

        持有之后的日收益用载体水平，不用研究序列上的价格。
        """
        dates = _calendar()
        peer = load_peer("A1", "tradable")
        names = [leg.leg_id for leg in peer.legs]
        research = _levels(
            dates, names,
            jumps=(
                ("2006-01-20", "spx", 130.0),
                ("2006-01-20", "csi300", 200.0),
            ),
        )
        carrier = _levels(dates, names, jumps=(("2006-02-20", "csi300", 110.0),))
        mask = pd.DataFrame(False, index=dates, columns=names)
        mask["csi300"] = True
        result = run_peer(
            peer, dates, carrier, signal_levels=research,
            cash=_zero_cash(dates), carriers=mask)
        decision = pd.Timestamp("2006-01-20")
        fill = pd.Timestamp("2006-02-10")
        later = pd.Timestamp("2006-02-20")
        self.assertEqual(float(result.decisions.loc[decision, "csi300"]), 1.0)
        self.assertEqual(float(result.decisions.loc[decision, "spx"]), 0.0)
        self.assertEqual(float(result.decisions.loc[decision, "cash"]), 0.0)
        self.assertEqual(float(result.close_held.loc[fill, "csi300"]), 1.0)
        self.assertEqual(float(result.close_held.loc[fill, "cash"]), 0.0)
        self.assertAlmostEqual(float(result.net.loc[later]), 0.10)
        self.assertEqual(float(result.cost.loc[later]), 0.0)


if __name__ == "__main__":
    unittest.main()
