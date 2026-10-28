"""v4-R2 引擎开关。关闭时必须与 v3.1 冻结路径逐日一致。

不跑任何 v4 候选的组合收益，也不计算 2016-01-01 及以后的组合收益。
涨跌停生效日的幅度只用报价函数检查，不把 2016 年以后的行情放进 `simulate_path`。
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import unittest

import numpy as np
import pandas as pd

from src.v3.data.universe import containers
from src.v3.engine.arms import execute, group_decisions
from src.v3.engine.costs import PLACEHOLDER_COSTS, CrossBorderCosts, withheld_dividend
from src.v3.engine.exit import simulate_path
from src.v3.engine.limits import (
    FillQuote,
    blocked,
    board_of,
    executable_weights,
    limit_ratio,
    session_tradable,
)
from src.v3.engine.market import load_market, market_from_returns
from src.v3.engine.regime import daily_ranks, split_speed, trend_efficiency
from src.v3.engine.score import Lookback
from src.v3.engine.spec import load_spec
from src.v3.engine.switches import T2_WINDOW_PLACEHOLDER, EngineSwitches
from src.v3.engine.universe import execution_code, pool_members

from src.data import db as DB

FEE = 0.001
CASH_FEE = 0.0005
# PYTHONHASHSEED=0 下，milestone/v3-code-freeze 的 P1（A / index / official，至 2015-12-31）。
# 费用按集合遍历，跨进程的哈希盐会改最后一比特；固定盐之后与冻结引擎逐日相同。
# 0eb25e2 在这次改动之前，src/v3/engine 与该标签逐字相同。
FREEZE_P1 = {
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


def _days(*text):
    return pd.to_datetime(list(text))


def _quote(board, dates, closes):
    return FillQuote(close=pd.Series(closes, index=pd.to_datetime(dates)), board=board)


def _book(names, levels, rets, targets, quotes=None, **kwargs):
    columns = [*names, "cash"]
    days = levels.index
    frame = pd.DataFrame({name: levels[name].to_numpy(dtype=float) for name in names}, index=days)
    frame["cash"] = 1.0
    pnl = pd.DataFrame({name: rets[name].to_numpy(dtype=float) for name in names}, index=days)
    pnl["cash"] = 0.0
    fees = {name: FEE for name in names}
    fees["cash"] = CASH_FEE
    tgt = None
    if targets:
        tgt = pd.DataFrame.from_dict(targets, orient="index", dtype=float).reindex(columns=columns).fillna(0.0)
        tgt.index = pd.to_datetime(list(targets))
    fill = quotes is not None or kwargs.get("fill_limits", False)
    return simulate_path(
        pnl, frame, fees, "cash", targets=tgt, exit_drawdown=0.10,
        fill_limits=fill, fill_quotes=quotes, **kwargs,
    )


def _flat(days, names, price=100.0):
    levels = pd.DataFrame({name: price for name in names}, index=days)
    rets = pd.DataFrame({name: 0.0 for name in names}, index=days)
    return levels, rets


def _panel(days, names, ok, score, total, rankable):
    index = pd.DatetimeIndex(days)

    def frame(mapping, default):
        data = {
            name: [mapping.get((day, name), default) for day in index]
            for name in names
        }
        return pd.DataFrame(data, index=index)

    return Lookback(
        total=frame(total, 0.0),
        score=frame(score, 0.0),
        ok=frame(ok, False),
        rankable=frame(rankable, False),
    )


def _sha(values) -> str:
    array = np.ascontiguousarray(values, dtype=np.float64)
    return hashlib.sha256(array.tobytes()).hexdigest()


class SwitchDefaults(unittest.TestCase):
    def test_defaults_are_off_and_t2_window_is_a_placeholder(self):
        switches = EngineSwitches()
        self.assertTrue(switches.idle())
        self.assertFalse(switches.fill_limits)
        self.assertFalse(switches.t1_turn)
        self.assertFalse(switches.t2_state_weights)
        self.assertFalse(switches.t3_refill)
        self.assertIsNone(switches.cross_border)
        self.assertEqual(switches.t2_window, T2_WINDOW_PLACEHOLDER)
        self.assertEqual(T2_WINDOW_PLACEHOLDER, 60)
        self.assertEqual(PLACEHOLDER_COSTS.trade_surcharge(), 0.002)
        self.assertAlmostEqual(withheld_dividend(0.02, 0.10), 0.018)

    def test_explicit_off_matches_the_untouched_call(self):
        days = pd.bdate_range("2006-01-02", periods=30)
        signal = pd.DataFrame({"a": 0.0, "cash": 0.0}, index=days)
        market = market_from_returns(signal, {"a": FEE, "cash": CASH_FEE})
        spec = load_spec()
        plain = execute(market, spec, "A", n=3, freq="week")
        idle = execute(market, spec, "A", n=3, freq="week", switches=EngineSwitches())
        self.assertTrue(np.array_equal(plain.net.to_numpy(), idle.net.to_numpy()))
        self.assertTrue(np.array_equal(plain.held.to_numpy(), idle.held.to_numpy()))
        self.assertTrue(np.array_equal(plain.cost.to_numpy(), idle.cost.to_numpy()))


class LimitBands(unittest.TestCase):
    def test_board_follows_the_tracking_etf(self):
        members = {row["id"]: row for row in pool_members(containers(), "A", "index")}
        chinext = members["chinext"]
        star = members["star50"]
        csi = members["csi300"]
        self.assertEqual(board_of(chinext["execution"][0]["track"], execution_code(chinext)), "chinext")
        self.assertEqual(board_of(star["execution"][0]["track"], execution_code(star)), "star")
        self.assertEqual(board_of(csi["execution"][0]["track"], execution_code(csi)), "main")
        self.assertEqual(execution_code(chinext), "159915")
        self.assertEqual(execution_code(star), "588000")
        self.assertEqual(board_of("纳斯达克100指数", "QQQ"), "none")

    def test_ratio_changes_on_the_exchange_effective_date(self):
        self.assertEqual(limit_ratio("main", "2015-08-24"), limit_ratio("main", "2020-08-24"))
        self.assertEqual(limit_ratio("chinext", "2020-08-21"), limit_ratio("main", "2020-08-21"))
        self.assertEqual(limit_ratio("chinext", "2020-08-24"), limit_ratio("star", "2020-08-21"))
        self.assertEqual(limit_ratio("star", "2020-08-20"), limit_ratio("main", "2020-08-20"))
        self.assertIsNone(limit_ratio("none", "2020-08-24"))
        # 10% 档：10 → 11 是涨停，10 → 9 是跌停。20% 档里 11 不是涨停，12 才是。
        band10 = limit_ratio("chinext", "2020-08-21")
        band20 = limit_ratio("chinext", "2020-08-24")
        self.assertTrue(blocked(10.0, 11.0, "buy", band10))
        self.assertFalse(blocked(10.0, 11.0, "sell", band10))
        self.assertTrue(blocked(10.0, 9.0, "sell", band10))
        self.assertFalse(blocked(10.0, 9.0, "buy", band10))
        self.assertFalse(blocked(10.0, 11.0, "buy", band20))
        self.assertTrue(blocked(10.0, 12.0, "buy", band20))
        self.assertFalse(blocked(10.0, 12.0, "buy", limit_ratio("none", "2020-08-24")))
        self.assertTrue(blocked(10.0, None, "buy", band10))
        self.assertTrue(blocked(None, None, "sell", band20))

    def test_session_uses_the_etf_board_not_the_index_level(self):
        # 计价可以是平的指数。成交看创业板 ETF 的原始收盘和 20% 档。
        quote = _quote("chinext", ["2020-08-21", "2020-08-24"], [10.0, 11.0])
        before = session_tradable({"chinext": quote}, "2020-08-21", ["chinext"])
        after = session_tradable(
            {"chinext": _quote("chinext", ["2020-08-21", "2020-08-24"], [10.0, 11.0])},
            "2020-08-24", ["chinext"])
        self.assertEqual(before["chinext"], (True, True))  # 当天就是 10，前一日不在序列里
        # 前收 10、收盘 11：生效日前是涨停，生效日当天 11 仍在 20% 以内。
        prior = _quote("chinext", ["2020-08-20", "2020-08-21"], [10.0, 11.0])
        later = _quote("chinext", ["2020-08-21", "2020-08-24"], [10.0, 11.0])
        self.assertFalse(session_tradable({"asset": prior}, "2020-08-21", ["asset"])["asset"][0])
        self.assertTrue(session_tradable({"asset": later}, "2020-08-24", ["asset"])["asset"][0])


class FillLimitPaths(unittest.TestCase):
    def test_clear_quotes_match_the_off_switch(self):
        days = _days("2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09")
        levels, rets = _flat(days, ["asset"])
        targets = {
            "2006-01-04": {"asset": 1.0, "cash": 0.0},
            "2006-01-06": {"asset": 0.0, "cash": 1.0},
        }
        quotes = {"asset": _quote("main", ["2006-01-03", *days.strftime("%Y-%m-%d")], [10, 10, 10, 10, 10])}
        off = _book(["asset"], levels, rets, targets)
        on = _book(["asset"], levels, rets, targets, quotes)
        self.assertTrue(np.array_equal(off.net.to_numpy(), on.net.to_numpy()))
        self.assertTrue(np.array_equal(off.held.to_numpy(), on.held.to_numpy()))
        self.assertTrue(np.array_equal(off.cost.to_numpy(), on.cost.to_numpy()))

    def test_consecutive_limit_up_defers_the_buy(self):
        days = _days("2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09")
        levels, rets = _flat(days, ["asset"])
        targets = {"2006-01-04": {"asset": 1.0, "cash": 0.0}}
        quotes = {"asset": _quote("main", ["2006-01-03", "2006-01-04", "2006-01-05", "2006-01-06"], [10, 11, 12.1, 12.1])}
        book = _book(["asset"], levels, rets, targets, quotes)
        off = _book(["asset"], levels, rets, targets)
        self.assertAlmostEqual(float(book.held.loc[days[0], "asset"]), 0.0)
        self.assertAlmostEqual(float(book.held.loc[days[1], "asset"]), 0.0)
        self.assertAlmostEqual(float(book.held.loc[days[2], "asset"]), 0.0)
        self.assertAlmostEqual(float(book.cost.loc[days[0]]), 0.0)
        self.assertAlmostEqual(float(book.cost.loc[days[1]]), 0.0)
        self.assertAlmostEqual(float(book.cost.loc[days[2]]), FEE + CASH_FEE)
        self.assertAlmostEqual(float(book.held.loc[days[3], "asset"]), 1.0)
        self.assertAlmostEqual(float(off.cost.loc[days[0]]), FEE + CASH_FEE)
        reasons = set(book.deferred_exits["reason"]) if book.deferred_exits is not None and not book.deferred_exits.empty else set()
        self.assertNotIn("limit_or_no_price", reasons)

    def test_consecutive_limit_down_defers_the_sell(self):
        days = _days("2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09", "2006-01-10")
        levels, rets = _flat(days, ["asset"])
        targets = {
            "2006-01-04": {"asset": 1.0, "cash": 0.0},
            "2006-01-05": {"asset": 0.0, "cash": 1.0},
        }
        quotes = {"asset": _quote(
            "main",
            ["2006-01-03", "2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09"],
            [10, 10, 9, 8.1, 8.1],
        )}
        book = _book(["asset"], levels, rets, targets, quotes)
        off = _book(["asset"], levels, rets, targets)
        self.assertAlmostEqual(float(off.held.loc[days[2], "asset"]), 0.0)
        self.assertAlmostEqual(float(book.held.loc[days[1], "asset"]), 1.0)
        self.assertAlmostEqual(float(book.held.loc[days[2], "asset"]), 1.0)
        self.assertAlmostEqual(float(book.held.loc[days[3], "asset"]), 1.0)
        self.assertAlmostEqual(float(book.cost.loc[days[1]]), 0.0)
        self.assertAlmostEqual(float(book.cost.loc[days[2]]), 0.0)
        self.assertAlmostEqual(float(book.cost.loc[days[3]]), FEE + CASH_FEE)
        self.assertAlmostEqual(float(book.held.loc[days[4], "asset"]), 0.0)
        self.assertAlmostEqual(float(book.held.loc[days[4], "cash"]), 1.0)

    def test_exit_sell_waits_through_consecutive_limit_down(self):
        days = _days("2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09", "2006-01-10", "2006-01-11", "2006-01-12")
        levels = pd.DataFrame({"asset": [100, 100, 80, 80, 80, 80, 80]}, index=days, dtype=float)
        rets = pd.DataFrame({"asset": [0, 0, -0.2, 0, 0, 0, 0]}, index=days, dtype=float)
        quotes = {"asset": _quote(
            "main",
            ["2006-01-03", "2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09", "2006-01-10", "2006-01-11"],
            [10, 10, 10, 9, 8.1, 7.29, 7.29],
        )}
        book = _book(["asset"], levels, rets, {"2006-01-04": {"asset": 1.0, "cash": 0.0}}, quotes)
        off = _book(["asset"], levels, rets, {"2006-01-04": {"asset": 1.0, "cash": 0.0}})
        self.assertEqual(
            [str(pd.Timestamp(day).date()) for day in off.exits.loc[off.exits["kind"].eq("exit"), "date"]],
            ["2006-01-09"],
        )
        self.assertEqual(
            [str(pd.Timestamp(day).date()) for day in book.exits.loc[book.exits["kind"].eq("exit"), "date"]],
            ["2006-01-11"],
        )
        self.assertAlmostEqual(float(book.exits.loc[book.exits["kind"].eq("exit"), "price"].iloc[0]), 80.0)
        self.assertAlmostEqual(float(book.cost.loc[days[5]]), FEE)
        self.assertAlmostEqual(float(book.cost.loc[days[3]]), 0.0)
        self.assertAlmostEqual(float(book.cost.loc[days[4]]), 0.0)
        self.assertAlmostEqual(float(book.held.loc[days[6], "cash"]), 1.0)
        deferred = [str(pd.Timestamp(day).date()) for day in book.deferred_exits["date"]]
        self.assertEqual(deferred, ["2006-01-09", "2006-01-10"])

    def test_halt_spanning_rebalance_retries_the_whole_leg(self):
        days = _days("2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09", "2006-01-10")
        levels, rets = _flat(days, ["aaa", "bbb"])
        targets = {
            "2006-01-04": {"aaa": 1.0, "bbb": 0.0, "cash": 0.0},
            "2006-01-05": {"aaa": 0.0, "bbb": 1.0, "cash": 0.0},
        }
        quotes = {
            "aaa": _quote("main", ["2006-01-03", "2006-01-04", "2006-01-09"], [10, 10, 10]),
            "bbb": _quote("main", ["2006-01-03", *days.strftime("%Y-%m-%d")], [20, 20, 20, 20, 20, 20]),
        }
        locked = executable_weights(
            {"aaa": 1.0, "bbb": 0.0, "cash": 0.0},
            {"aaa": 0.0, "bbb": 1.0, "cash": 0.0},
            {"aaa": (False, False), "bbb": (True, True)},
            "cash", 1e-12,
        )
        self.assertAlmostEqual(locked["aaa"], 1.0)
        self.assertAlmostEqual(locked["bbb"], 0.0)
        book = _book(["aaa", "bbb"], levels, rets, targets, quotes)
        off = _book(["aaa", "bbb"], levels, rets, targets)
        self.assertAlmostEqual(float(off.held.loc[days[2], "bbb"]), 1.0)
        self.assertAlmostEqual(float(book.held.loc[days[1], "aaa"]), 1.0)
        self.assertAlmostEqual(float(book.held.loc[days[2], "aaa"]), 1.0)
        self.assertAlmostEqual(float(book.held.loc[days[3], "aaa"]), 1.0)
        self.assertAlmostEqual(float(book.cost.loc[days[1]]), 0.0)
        self.assertAlmostEqual(float(book.cost.loc[days[2]]), 0.0)
        self.assertAlmostEqual(float(book.cost.loc[days[3]]), FEE + FEE)
        self.assertAlmostEqual(float(book.held.loc[days[4], "aaa"]), 0.0)
        self.assertAlmostEqual(float(book.held.loc[days[4], "bbb"]), 1.0)


class CrossBorderHook(unittest.TestCase):
    def test_placeholder_surcharge_and_withholding_change_only_when_set(self):
        days = _days("2006-01-04", "2006-01-05", "2006-01-06")
        levels = pd.DataFrame({"qdii": [100, 100, 105]}, index=days, dtype=float)
        rets = pd.DataFrame({"qdii": [0.0, 0.0, 0.05]}, index=days, dtype=float)
        targets = {"2006-01-04": {"qdii": 1.0, "cash": 0.0}}
        fees = {"qdii": 0.0015, "cash": CASH_FEE}
        pnl = pd.DataFrame({"qdii": rets["qdii"], "cash": 0.0}, index=days)
        frame = pd.DataFrame({"qdii": levels["qdii"], "cash": 1.0}, index=days)
        tgt = pd.DataFrame.from_dict(targets, orient="index", dtype=float)
        tgt.index = pd.to_datetime(list(targets))
        plain = simulate_path(pnl, frame, fees, "cash", targets=tgt)
        zeros = simulate_path(
            pnl, frame, fees, "cash", targets=tgt,
            cross_border=CrossBorderCosts(), cross_border_names={"qdii"},
            dividend_yield=pd.DataFrame({"qdii": [0.0, 0.0, 0.02]}, index=days),
        )
        hooked = simulate_path(
            pnl, frame, fees, "cash", targets=tgt,
            cross_border=PLACEHOLDER_COSTS, cross_border_names={"qdii"},
            dividend_yield=pd.DataFrame({"qdii": [0.0, 0.0, 0.02]}, index=days),
        )
        self.assertTrue(np.array_equal(plain.net.to_numpy(), zeros.net.to_numpy()))
        self.assertTrue(np.array_equal(plain.cost.to_numpy(), zeros.cost.to_numpy()))
        self.assertAlmostEqual(float(hooked.cost.loc[days[0]]), 0.0015 + PLACEHOLDER_COSTS.trade_surcharge() + CASH_FEE)
        self.assertAlmostEqual(float(plain.cost.loc[days[0]]), 0.0015 + CASH_FEE)
        self.assertAlmostEqual(float(hooked.gross.loc[days[2]]), 0.05 - 0.02 * 0.10)
        self.assertAlmostEqual(float(plain.gross.loc[days[2]]), 0.05)
        self.assertAlmostEqual(float(hooked.net.loc[days[2]]), 0.048)


class TurnAndRefill(unittest.TestCase):
    def _prepared(self, days, names, flags):
        """flags[length][day][name] = (ok, score, total, rankable)."""
        prepared = {}
        for length, table in flags.items():
            ok, score, total, rankable = {}, {}, {}, {}
            for day in days:
                for name in names:
                    bit = table.get(day, {}).get(name, (False, 0.0, 0.0, False))
                    ok[(day, name)] = bit[0]
                    score[(day, name)] = bit[1]
                    total[(day, name)] = bit[2]
                    rankable[(day, name)] = bit[3]
            prepared[length] = _panel(days, names, ok, score, total, rankable)
        return prepared

    def test_t1_off_keeps_each_group_on_its_own_filter(self):
        days = _days("2006-01-31")
        names = ["rebound"]
        row = (True, 1.0, 0.1, True)
        slow = (False, 3.0, -0.05, True)
        flags = {20: {days[0]: {"rebound": row}}, 60: {days[0]: {"rebound": row}},
                 120: {days[0]: {"rebound": slow}}, 250: {days[0]: {"rebound": slow}}}
        prepared = self._prepared(days, names, flags)
        off = group_decisions(prepared, days, "month", 1, names, "cash", {"rebound": "rebound"}, None, (20, 60, 120, 250))
        idle = group_decisions(
            prepared, days, "month", 1, names, "cash", {"rebound": "rebound"}, None, (20, 60, 120, 250),
            switches=EngineSwitches())
        on = group_decisions(
            prepared, days, "month", 1, names, "cash", {"rebound": "rebound"}, None, (20, 60, 120, 250),
            switches=EngineSwitches(t1_turn=True))
        self.assertTrue(np.array_equal(off.to_numpy(), idle.to_numpy()))
        self.assertAlmostEqual(float(off.loc[days[0], "rebound"]), 0.5)
        self.assertAlmostEqual(float(on.loc[days[0], "rebound"]), 1.0)

    def test_t1_pullback_blocks_a_new_buy_and_keeps_a_held_name(self):
        days = _days("2006-01-31", "2006-02-28")
        names = ["old", "fresh"]
        own = (True, 1.0, 0.2, True)
        quiet = (False, 0.0, 0.0, True)
        flags = {length: {days[0]: {"old": own, "fresh": quiet}} for length in (20, 60, 120, 250)}
        for length in (20, 60):
            flags[length][days[1]] = {"old": (False, 0.0, 0.0, True), "fresh": (False, 0.0, 0.0, True)}
        for length in (120, 250):
            flags[length][days[1]] = {
                "old": (True, 1.0, 0.1, True),
                "fresh": (True, 5.0, 0.3, True),
            }
        prepared = self._prepared(days, names, flags)
        kwargs = dict(prepared=prepared, dates=days, freq="month", n=1, names=names, cash_id="cash",
                      sort_ids={"old": "old", "fresh": "fresh"}, liquidity=None, lookbacks=(20, 60, 120, 250))
        off = group_decisions(**kwargs)
        on = group_decisions(**kwargs, switches=EngineSwitches(t1_turn=True))
        self.assertAlmostEqual(float(off.loc[days[1], "fresh"]), 0.5)
        self.assertAlmostEqual(float(off.loc[days[1], "old"]), 0.0)
        self.assertAlmostEqual(float(on.loc[days[1], "old"]), 0.5)
        self.assertAlmostEqual(float(on.loc[days[1], "fresh"]), 0.0)
        self.assertEqual(split_speed((20, 60, 120, 250)), ((20, 60), (120, 250)))

    def test_t2_tilts_fast_when_the_market_trends_and_slow_when_it_chops(self):
        names = ["f20", "f60", "s120", "s250"]
        trend_index = pd.bdate_range("2006-01-03", periods=31)
        chop_index = pd.bdate_range("2006-03-01", periods=31)
        trend_day = pd.Timestamp(trend_index[-1])
        chop_day = pd.Timestamp(chop_index[-1])
        lookbacks = (20, 60, 120, 250)
        mapping = {20: "f20", 60: "f60", 120: "s120", 250: "s250"}

        def prepared(day):
            flags = {}
            for length, name in mapping.items():
                flags[length] = {day: {item: ((item == name), 1.0 if item == name else 0.0, 0.1, True) for item in names}}
            return self._prepared(pd.DatetimeIndex([day]), names, flags)

        trend_level = pd.Series(np.arange(1, 32, dtype=float), index=trend_index)
        self.assertEqual(trend_efficiency(trend_level, trend_day, 10), 1.0)
        chop_level = pd.Series(
            [10.0 if i % 2 == 0 else 12.0 for i in range(31)], index=chop_index)
        self.assertEqual(trend_efficiency(chop_level, chop_day, 4), 0.0)
        sort_ids = {name: name for name in names}
        trend = group_decisions(
            prepared(trend_day), pd.DatetimeIndex([trend_day]), "month", 1, names, "cash", sort_ids, None,
            lookbacks, switches=EngineSwitches(t2_state_weights=True, t2_window=10), market_level=trend_level)
        chop_book = group_decisions(
            prepared(chop_day), pd.DatetimeIndex([chop_day]), "month", 1, names, "cash", sort_ids, None,
            lookbacks, switches=EngineSwitches(t2_state_weights=True, t2_window=4), market_level=chop_level)
        even = group_decisions(
            prepared(trend_day), pd.DatetimeIndex([trend_day]), "month", 1, names, "cash", sort_ids, None, lookbacks)
        self.assertAlmostEqual(float(even.loc[trend_day, "f20"]), 0.25)
        self.assertAlmostEqual(float(trend.loc[trend_day, "f20"]), 0.5)
        self.assertAlmostEqual(float(trend.loc[trend_day, "f60"]), 0.5)
        self.assertAlmostEqual(float(trend.loc[trend_day, "s120"]), 0.0)
        self.assertAlmostEqual(float(chop_book.loc[chop_day, "s120"]), 0.5)
        self.assertAlmostEqual(float(chop_book.loc[chop_day, "s250"]), 0.5)
        self.assertAlmostEqual(float(chop_book.loc[chop_day, "f20"]), 0.0)
        short = pd.Series([1.0, 2.0, 3.0], index=pd.to_datetime(["2006-01-04", "2006-01-05", "2006-01-06"]))
        self.assertIsNone(trend_efficiency(short, short.index[-1], 10))

    def test_t3_refills_the_next_name_on_the_exit_day_and_off_leaves_cash(self):
        days = _days("2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09", "2006-01-10")
        levels = pd.DataFrame({"asset": [100, 100, 80, 80, 80], "nxt": 50.0}, index=days)
        rets = pd.DataFrame({"asset": [0, 0, -0.2, 0, 0], "nxt": 0.0}, index=days)
        rank = pd.DataFrame({"asset": np.nan, "nxt": 0.0}, index=days)
        targets = {"2006-01-04": {"asset": 1.0, "nxt": 0.0, "cash": 0.0}}
        off = _book(["asset", "nxt"], levels, rets, targets)
        on = _book(["asset", "nxt"], levels, rets, targets, refill_rank=rank)
        self.assertAlmostEqual(float(off.held.loc[days[4], "cash"]), 1.0)
        self.assertAlmostEqual(float(off.held.loc[days[4], "nxt"]), 0.0)
        self.assertAlmostEqual(float(on.held.loc[days[4], "nxt"]), 1.0)
        self.assertAlmostEqual(float(on.held.loc[days[4], "asset"]), 0.0)
        self.assertAlmostEqual(float(on.cost.loc[days[3]]), FEE + FEE)
        self.assertAlmostEqual(float(on.net.loc[days[3]]), -(FEE + FEE))

    def test_t3_rebalance_wins_and_limit_up_defers_the_refill(self):
        days = _days("2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09", "2006-01-10", "2006-01-11")
        levels = pd.DataFrame({"asset": [100, 100, 80, 80, 80, 80], "nxt": 50.0}, index=days)
        rets = pd.DataFrame({"asset": [0, 0, -0.2, 0, 0, 0], "nxt": 0.0}, index=days)
        rank = pd.DataFrame({"asset": np.nan, "nxt": 0.0}, index=days)
        targets = {
            "2006-01-04": {"asset": 1.0, "nxt": 0.0, "cash": 0.0},
            "2006-01-09": {"asset": 0.0, "nxt": 0.0, "cash": 1.0},
        }
        booked = _book(["asset", "nxt"], levels, rets, targets, refill_rank=rank)
        self.assertAlmostEqual(float(booked.held.loc[days[4], "cash"]), 1.0)
        self.assertAlmostEqual(float(booked.held.loc[days[4], "nxt"]), 0.0)
        self.assertAlmostEqual(float(booked.cost.loc[days[3]]), FEE + CASH_FEE)
        quotes = {
            "asset": _quote("main", ["2006-01-03", *days.strftime("%Y-%m-%d")], [10, 10, 10, 10, 10, 10, 10]),
            "nxt": _quote("main", ["2006-01-06", "2006-01-09", "2006-01-10"], [10, 11, 11]),
        }
        delayed = _book(
            ["asset", "nxt"], levels, rets,
            {"2006-01-04": {"asset": 1.0, "nxt": 0.0, "cash": 0.0}},
            quotes, refill_rank=rank,
        )
        self.assertAlmostEqual(float(delayed.held.loc[days[4], "cash"]), 1.0)
        self.assertAlmostEqual(float(delayed.held.loc[days[5], "nxt"]), 1.0)
        blocked_rows = delayed.deferred_exits
        self.assertIn("refill_blocked", set(blocked_rows["reason"]))

    def test_daily_ranks_puts_the_eligible_name_first(self):
        day = pd.Timestamp("2006-01-31")
        names = ["aaa", "bbb"]
        flags = {
            20: {day: {"aaa": (True, 2.0, 0.2, True), "bbb": (True, 1.0, 0.1, True)}},
            60: {day: {"aaa": (False, 0.0, 0.0, True), "bbb": (False, 0.0, 0.0, True)}},
        }
        prepared = self._prepared(pd.DatetimeIndex([day]), names, flags)
        ranks = daily_ranks(prepared, pd.DatetimeIndex([day]), names, (20, 60), {"aaa": "aaa", "bbb": "bbb"}, None)
        self.assertEqual(float(ranks.loc[day, "aaa"]), 0.0)
        self.assertEqual(float(ranks.loc[day, "bbb"]), 1.0)


class FreezeP1(unittest.TestCase):
    def test_switches_off_match_freeze_p1_day_by_day(self):
        if os.environ.get("PYTHONHASHSEED") != "0":
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = "0"
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            proc = subprocess.run(
                [sys.executable, "-m", "unittest",
                 "tests.v3.engine.test_v4_r2.FreezeP1.test_switches_off_match_freeze_p1_day_by_day"],
                cwd=root, env=env, capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + "\n" + proc.stderr)
            return
        db = DB.MARKET_DB
        if not db.exists() or db.stat().st_size < 1_000_000:
            self.skipTest("market.sqlite 不在这台机器上")
        spec = load_spec()
        market = load_market(db, containers(), "A", "index", pd.Timestamp(spec.design_end), spec, history_mode="official")
        book = execute(market, spec, "A", switches=EngineSwitches())
        self.assertEqual(str(book.net.index[0].date()), "2005-01-04")
        self.assertEqual(str(book.net.index[-1].date()), "2015-12-31")
        self.assertEqual(len(book.net), 2671)
        self.assertEqual(_sha(book.net.to_numpy()), FREEZE_P1["net"])
        self.assertEqual(_sha(book.held.to_numpy()), FREEZE_P1["held"])
        self.assertEqual(_sha(book.cost.to_numpy()), FREEZE_P1["cost"])
        for n, freq in ((3, "week"), (3, "month"), (5, "week"), (5, "month"), (8, "week"), (8, "month")):
            series = book.paths[(n, freq)].net
            self.assertEqual(_sha(series.to_numpy()), FREEZE_P1[f"{n}-{freq}"])
            self.assertTrue(series.index.equals(book.net.index))


if __name__ == "__main__":
    unittest.main()
