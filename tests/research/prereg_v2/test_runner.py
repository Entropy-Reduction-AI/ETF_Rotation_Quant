"""预注册 v2 的边界。行情是构造的，或只读到 2015-12-31。不跑样本外。"""
import io
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import tests  # noqa: F401
from src.research.prereg_v2.engine import (
    A_SHARE,
    DESIGN_END,
    FROZEN_SHA,
    OVERSEAS,
    ROOT,
    ROUND_TRIP_COST,
    ROUND_TRIP_COST_DOUBLED,
    RunnerError,
    _guard_end,
    b2_both_worse,
    criteria,
    effective_position,
    emas,
    equal_weight_returns,
    haven_total_return,
    in_market,
    judge_real_book,
    ledgers,
    load_haven,
    monthly_blend,
    passes_cagr,
    passes_drawdown,
    path_returns,
    qulla_signal,
    run_design,
    run_oos,
    sha_matches,
    slow_valve_signal,
)
from src.research.prereg_v2.run import main


def _manual_ema(values: pd.Series, span: int) -> pd.Series:
    alpha = 2.0 / (span + 1.0)
    out = []
    prev = None
    for value in values:
        prev = float(value) if prev is None else alpha * float(value) + (1.0 - alpha) * prev
        out.append(prev)
    return pd.Series(out, index=values.index)


def _d4_position(nav: pd.Series) -> pd.Series:
    """d4.py 的慢阀：日历月末记下决策后的状态，ffill 到交易日，再延后一天。"""
    month_end = nav.resample("ME").last()
    state = 1
    hi = float(month_end.iloc[0])
    lo = None
    decided = []
    for level in month_end:
        level = float(level)
        if state:
            hi = max(hi, level)
            if level / hi - 1 < -0.25:
                state = 0
                lo = level
        else:
            lo = min(lo, level)
            if level / lo - 1 > 0.10:
                state = 1
                hi = level
        decided.append(state)
    signal = pd.Series(decided, index=month_end.index).reindex(nav.index, method="ffill").fillna(1.0)
    return signal.shift(1).fillna(1.0)


class EmaAndPosition(unittest.TestCase):
    def test_ema_uses_span_and_adjust_false(self):
        nav = pd.Series(np.linspace(1.0, 2.0, 40), index=pd.bdate_range("2015-01-05", periods=40), dtype=float)
        fast, slow = emas(nav)
        pd.testing.assert_series_equal(fast, _manual_ema(nav, 10), check_names=False)
        pd.testing.assert_series_equal(slow, _manual_ema(nav, 20), check_names=False)
        other = nav.ewm(span=10, adjust=True).mean()
        self.assertFalse(np.allclose(fast.to_numpy(), other.to_numpy()))

    def test_in_market_boundaries(self):
        idx = pd.bdate_range("2015-01-05", periods=4)
        fast = pd.Series([1.0, 2.0, 2.0, 3.0], index=idx)
        slow = pd.Series([0.0, 1.0, 2.0, 2.0], index=idx)
        # 第一天没有涨跌；第二天两条都升且快线更高；第三天两线相等；第四天慢线走平。
        self.assertEqual(list(in_market(fast, slow)), [False, True, False, False])
        falling = pd.Series([5.0, 4.0], index=idx[:2])
        rising = pd.Series([1.0, 2.0], index=idx[:2])
        self.assertEqual(list(in_market(falling, rising)), [False, False])
        self.assertEqual(list(in_market(rising, falling)), [False, False])
        flat = pd.Series(1.0, index=pd.bdate_range("2015-01-05", periods=15))
        signal = qulla_signal(flat)
        self.assertTrue((signal == 0.0).all())
        up = pd.Series(np.linspace(1.0, 2.0, 30), index=pd.bdate_range("2015-01-05", periods=30))
        got = qulla_signal(up)
        self.assertEqual(got.iloc[0], 0.0)
        self.assertGreater(got.sum(), 0)

    def test_fill_is_next_bar_and_does_not_read_the_same_close(self):
        idx = pd.bdate_range("2015-06-01", periods=5)
        asset = pd.Series([0.0, 0.0, 0.5, -0.2, 0.1], index=idx)
        signal = pd.Series([1.0, 1.0, 0.0, 0.0, 1.0], index=idx)
        haven = pd.Series(0.01, index=idx)
        net, pos, switches = path_returns(asset, signal, haven, ROUND_TRIP_COST)
        self.assertEqual(list(pos), [1.0, 1.0, 1.0, 0.0, 0.0])
        self.assertEqual(list(effective_position(signal)), [1.0, 1.0, 1.0, 0.0, 0.0])
        # 信号在大涨当天转为离场，当天仍吃到这根收益，成本落在下一根。
        self.assertAlmostEqual(net.iloc[2], 0.5)
        self.assertAlmostEqual(net.iloc[3], 0.01 - ROUND_TRIP_COST)
        self.assertEqual(switches.iloc[3], 1.0)
        net_x2, _, _ = path_returns(asset, signal, haven, ROUND_TRIP_COST_DOUBLED)
        self.assertAlmostEqual(net_x2.iloc[3], 0.01 - ROUND_TRIP_COST_DOUBLED)
        # 最后一根收盘改掉，只改当天信号，不改任何已生效持仓。
        nav = pd.Series(np.linspace(1.0, 1.5, 60), index=pd.bdate_range("2014-03-03", periods=60))
        crashed = nav.copy()
        crashed.iloc[-1] = 0.2
        self.assertNotEqual(float(qulla_signal(nav).iloc[-1]), float(qulla_signal(crashed).iloc[-1]))
        pd.testing.assert_series_equal(effective_position(qulla_signal(nav)), effective_position(qulla_signal(crashed)))
        self.assertEqual(float(effective_position(qulla_signal(crashed)).iloc[-1]), float(qulla_signal(nav).iloc[-2]))

    def test_slow_valve_matches_d4_including_weekend_month_end(self):
        idx = pd.bdate_range("2015-01-05", "2015-04-30")
        nav = pd.Series(1.0, index=idx)
        nav.loc["2015-02-01":"2015-03-31"] = 0.70
        nav.loc["2015-04-01":] = 0.70 * 1.12
        got = effective_position(slow_valve_signal(nav))
        pd.testing.assert_series_equal(got, _d4_position(nav), check_names=False)
        self.assertEqual(got.min(), 0.0)
        self.assertEqual(got.max(), 1.0)
        self.assertLessEqual(got.index.max(), pd.Timestamp("2015-12-31"))


class DatesAndHaven(unittest.TestCase):
    def test_future_row_does_not_enter_the_return(self):
        def frame(extra):
            rows = [
                ("2015-12-30", "甲", 10.0, 0),
                ("2015-12-31", "甲", 11.0, 0),
                ("2015-12-30", "乙", 10.0, 0),
                ("2015-12-31", "乙", 10.0, 1),
            ]
            if extra:
                rows.append(("2016-01-04", "甲", 50.0, 0))
                rows.append(("2016-01-04", "乙", 10.0, 0))
            out = pd.DataFrame(rows, columns=["date", "container", "close", "data_hole"])
            out["date"] = pd.to_datetime(out["date"])
            return out

        end = pd.Timestamp("2015-12-31")
        base = equal_weight_returns(frame(False), ["甲", "乙"], end)
        more = equal_weight_returns(frame(True), ["甲", "乙"], end)
        pd.testing.assert_series_equal(base, more)
        self.assertLessEqual(base.index.max(), end)
        # 乙在 12-31 是断档，不参与平均。甲从 10 到 11。
        self.assertAlmostEqual(base.iloc[-1], 0.10)
        self.assertNotIn(pd.Timestamp("2016-01-04"), set(base.index))

    def test_guard_and_run_design_stop_before_a_missing_panel(self):
        with self.assertRaises(RunnerError) as caught:
            _guard_end(pd.Timestamp("2016-01-01"), False)
        self.assertIn("2015-12-31", str(caught.exception))
        self.assertEqual(_guard_end(DESIGN_END, False), DESIGN_END)
        with self.assertRaises(RunnerError) as caught:
            run_design(Path("/tmp/no-such-panel.sqlite"), Path("/tmp/no-such-market.sqlite"),
                       Path("/tmp/no-such.toml"), pd.Timestamp("2016-01-04"))
        self.assertIn("2015-12-31", str(caught.exception))

    def test_haven_return_and_clip(self):
        idx = pd.to_datetime(["2015-03-02", "2015-03-03", "2015-03-04"])
        closes = pd.Series([100.0, 99.0], index=idx[:2])
        divs = pd.DataFrame({"ex_date": [idx[1]], "amount": [8.0], "prev_close": [80.0]})
        got = haven_total_return(closes, divs, pd.DatetimeIndex(idx), 0.02 / 252)
        self.assertAlmostEqual(got.iloc[0], 0.02 / 252)
        self.assertAlmostEqual(got.iloc[1], 99.0 / 100.0 - 1.0 + 8.0 / 80.0)
        self.assertAlmostEqual(got.iloc[2], 0.02 / 252)
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "market.sqlite"
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE bars (code TEXT, adj TEXT, date TEXT, close REAL)")
            con.execute("CREATE TABLE cash_dividends (code TEXT, ex_date TEXT, amount REAL, prev_close REAL)")
            con.executemany("INSERT INTO bars VALUES (?,?,?,?)", [
                ("511880", "raw", "2015-12-30", 100.0),
                ("511880", "raw", "2015-12-31", 100.2),
                ("511880", "raw", "2016-01-04", 50.0),
            ])
            con.executemany("INSERT INTO cash_dividends VALUES (?,?,?,?)", [
                ("511880", "2015-12-31", 1.0, 100.0),
                ("511880", "2016-01-04", 9.0, 50.0),
            ])
            con.commit()
            con.close()
            loaded, dividends = load_haven(db, "511880", pd.Timestamp("2015-12-31"))
        self.assertEqual(list(loaded.index), [pd.Timestamp("2015-12-30"), pd.Timestamp("2015-12-31")])
        self.assertEqual(list(dividends["ex_date"]), [pd.Timestamp("2015-12-31")])


class Criteria(unittest.TestCase):
    def test_thresholds_and_doubled_cost(self):
        self.assertTrue(passes_drawdown(-0.70, -0.60))
        self.assertFalse(passes_drawdown(-0.70, -0.6001))
        self.assertTrue(passes_cagr(0.20, 0.18))
        self.assertFalse(passes_cagr(0.20, 0.18 - 1e-6))
        base_b0 = {"cagr": 0.20, "max_drawdown": -0.50}
        base_b1 = {"cagr": 0.19, "max_drawdown": -0.30}
        doubled_b1 = {"cagr": 0.10, "max_drawdown": -0.30}
        judge = criteria(base_b0, base_b1, base_b0, doubled_b1)
        self.assertTrue(judge["drawdown_shallower_by_10pp"])
        self.assertTrue(judge["cagr_giveup_at_most_2pp"])
        self.assertFalse(judge["still_holds_at_doubled_cost"])
        self.assertFalse(judge["pass"])
        self.assertFalse(b2_both_worse(base_b0, {"cagr": 0.19, "max_drawdown": -0.40}))
        self.assertTrue(b2_both_worse(base_b0, {"cagr": 0.19, "max_drawdown": -0.60}))

    def test_monthly_blend_resets_on_the_new_month(self):
        idx = pd.to_datetime(["2015-01-30", "2015-02-02", "2015-02-03"])
        a_ret = pd.Series([0.10, 0.00, 0.00], index=idx)
        o_ret = pd.Series([0.00, 0.10, 0.00], index=idx)
        blend = monthly_blend(a_ret, o_ret, 0.70)
        self.assertAlmostEqual(blend.iloc[0], 0.07)
        self.assertAlmostEqual(blend.iloc[1], 0.03)
        self.assertAlmostEqual(blend.iloc[2], 0.0)


class RealBookVerdict(unittest.TestCase):
    """§4 和 §5 读 511880 真实账本。合成数据让两本账的输赢相反。日期停在 2015-12-31。"""

    def test_selector_keeps_the_real_verdict_when_the_cash_book_disagrees(self):
        b0 = {"cagr": 0.10, "max_drawdown": -0.50}
        cash_b1 = {"cagr": 0.09, "max_drawdown": -0.30}
        real_b1 = {"cagr": 0.07, "max_drawdown": -0.45}
        cash_b1_x2 = {"cagr": 0.085, "max_drawdown": -0.32}
        real_b1_x2 = {"cagr": 0.05, "max_drawdown": -0.48}
        cash_b2 = {"cagr": 0.11, "max_drawdown": -0.40}
        real_b2 = {"cagr": 0.04, "max_drawdown": -0.70}
        empty = {"B0": {}, "B1": {}, "B2": {}}

        def book(b1, b2):
            return {"arms": {"B0": b0, "B1": b1, "B2": b2}, "portfolio": empty}

        cash_pass = criteria(b0, cash_b1, b0, cash_b1_x2)
        real_pass = criteria(b0, real_b1, b0, real_b1_x2)
        self.assertTrue(cash_pass["pass"])
        self.assertFalse(real_pass["pass"])
        self.assertTrue(all(cash_pass[key] and not real_pass[key] for key in (
            "drawdown_shallower_by_10pp", "cagr_giveup_at_most_2pp", "still_holds_at_doubled_cost")))
        self.assertFalse(b2_both_worse(b0, cash_b2))
        self.assertTrue(b2_both_worse(b0, real_b2))

        packed = ledgers(
            book(cash_b1, cash_b2), book(cash_b1_x2, cash_b2),
            book(real_b1, real_b2), book(real_b1_x2, real_b2),
            design=False,
        )
        judge = packed["haven_511880"]["criteria"]
        for key, value in real_pass.items():
            self.assertEqual(judge[key], value)
        self.assertEqual(judge["book"], "511880")
        self.assertTrue(packed["haven_511880"]["b2_vs_b0"]["both_worse"])
        self.assertEqual(packed["cash_assumption"]["label"], "对照，不用于判定")
        self.assertEqual(packed["portfolio"]["cash_assumption"]["label"], "对照，不用于判定")
        self.assertNotIn("criteria", packed["cash_assumption"])
        self.assertNotIn("b2_vs_b0", packed["cash_assumption"])
        self.assertEqual(packed["cash_assumption"]["arms"]["B1"], cash_b1)
        self.assertEqual(packed["haven_511880"]["doubled_cost"]["arms"]["B1"], real_b1_x2)

        designed = judge_real_book(
            packed["haven_511880"]["arms"], packed["haven_511880"]["doubled_cost"]["arms"], design=True)
        self.assertFalse(designed["criteria"]["pass"])
        self.assertIn("不是 §4", designed["criteria"]["label"])
        self.assertIn("不能当作 §4 结论", designed["criteria"]["verdict"])
        self.assertTrue(designed["b2_vs_b0"]["both_worse"])

    def _paths(self):
        idx = pd.bdate_range("2014-01-02", "2015-12-31")
        n = len(idx)
        price = np.empty(n)
        price[0] = 100.0
        for i in range(1, n):
            if i <= 40:
                price[i] = price[i - 1] * 1.01
            elif i <= 70:
                price[i] = price[i - 1] * 0.97
            else:
                price[i] = price[i - 1]
        haven = 100.0 * (0.99 ** np.arange(n))
        return idx, price, haven

    def _write_fixture(self, root: Path):
        idx, price, haven = self._paths()
        panel = root / "panel.sqlite"
        market = root / "market.sqlite"
        names = list(A_SHARE) + list(OVERSEAS)
        rows = []
        for day, close in zip(idx, price):
            for name in names:
                rows.append((day.strftime("%Y-%m-%d"), name, float(close), float(close), float(close),
                             float(close), "NEUTRAL", 0.0, 1.0, None, 0))
        con = sqlite3.connect(panel)
        con.execute(
            "CREATE TABLE panel (date TEXT, container TEXT, open REAL, high REAL, low REAL, close REAL, "
            "state TEXT, rs_1m REAL, atr20 REAL, z_month REAL, data_hole INTEGER)")
        con.executemany("INSERT INTO panel VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.commit()
        con.close()
        con = sqlite3.connect(market)
        con.execute("CREATE TABLE bars (code TEXT, adj TEXT, date TEXT, close REAL)")
        con.execute("CREATE TABLE cash_dividends (code TEXT, ex_date TEXT, amount REAL, prev_close REAL)")
        con.executemany("INSERT INTO bars VALUES (?,?,?,?)", [
            ("511880", "raw", day.strftime("%Y-%m-%d"), float(close)) for day, close in zip(idx, haven)])
        con.commit()
        con.close()
        return panel, market

    def _assert_real_book(self, result):
        real = result["haven_511880"]
        cash = result["cash_assumption"]
        self.assertEqual(cash["label"], "对照，不用于判定")
        self.assertNotIn("criteria", cash)
        self.assertNotIn("b2_vs_b0", cash)
        self.assertGreater(cash["arms"]["B1"]["cagr"], 0.15)
        self.assertLess(real["arms"]["B1"]["cagr"], -0.8)
        self.assertGreater(cash["doubled_cost"]["arms"]["B1"]["cagr"], 0.15)
        self.assertLess(real["doubled_cost"]["arms"]["B1"]["cagr"], -0.8)
        self.assertAlmostEqual(real["arms"]["B0"]["cagr"], cash["arms"]["B0"]["cagr"])
        expected = criteria(
            real["arms"]["B0"], real["arms"]["B1"],
            real["doubled_cost"]["arms"]["B0"], real["doubled_cost"]["arms"]["B1"])
        control = criteria(
            cash["arms"]["B0"], cash["arms"]["B1"],
            cash["doubled_cost"]["arms"]["B0"], cash["doubled_cost"]["arms"]["B1"])
        self.assertFalse(expected["pass"])
        self.assertTrue(control["pass"])
        for key in ("drawdown_shallower_by_10pp", "cagr_giveup_at_most_2pp", "still_holds_at_doubled_cost", "pass"):
            self.assertEqual(real["criteria"][key], expected[key])
            self.assertNotEqual(expected[key], control[key])
        self.assertEqual(real["criteria"]["book"], "511880")
        self.assertEqual(real["b2_vs_b0"]["book"], "511880")
        self.assertEqual(real["b2_vs_b0"]["both_worse"], b2_both_worse(real["arms"]["B0"], real["arms"]["B2"]))
        self.assertTrue(real["b2_vs_b0"]["both_worse"])
        self.assertFalse(b2_both_worse(cash["arms"]["B0"], cash["arms"]["B2"]))
        self.assertLessEqual(pd.Timestamp(real["arms"]["B1"]["last"]), pd.Timestamp("2015-12-31"))
        self.assertTrue(all(int(year) <= 2015 for year in real["arms"]["B1"]["yearly"]))
        self.assertTrue(all(int(year) <= 2015 for year in real["doubled_cost"]["arms"]["B1"]["yearly"]))

    def test_design_and_oos_wiring_read_the_real_book(self):
        config = ROOT / "config" / "portfolio.toml"
        with tempfile.TemporaryDirectory() as tmp:
            panel, market = self._write_fixture(Path(tmp))
            design = run_design(panel, market, config, pd.Timestamp("2015-12-31"))
            self._assert_real_book(design)
            self.assertEqual(design["window"], "design")
            self.assertEqual(design["oos"], "未运行")
            self.assertIn("不是 §4", design["haven_511880"]["criteria"]["label"])
            self.assertIn("不能当作 §4 结论", design["haven_511880"]["criteria"]["verdict"])
            # 只测 run_oos 选哪本账。窗口改到设计期，避免算出 2016-01-01 及之后的收益。不走 --oos。
            with patch("src.research.prereg_v2.engine.OOS_START", pd.Timestamp("2014-01-02")), \
                    patch("src.research.prereg_v2.engine.OOS_END", pd.Timestamp("2015-12-31")):
                oos = run_oos(panel, market, config)
            self.assertEqual(oos["start"], "2014-01-02")
            self.assertEqual(oos["end"], "2015-12-31")
            self._assert_real_book(oos)
            self.assertEqual(oos["haven_511880"]["criteria"]["label"], "样本外判定")
            self.assertEqual(
                oos["haven_511880"]["criteria"]["pass"],
                design["haven_511880"]["criteria"]["pass"],
            )
            self.assertEqual(
                oos["haven_511880"]["b2_vs_b0"]["both_worse"],
                design["haven_511880"]["b2_vs_b0"]["both_worse"],
            )


class CliGuards(unittest.TestCase):
    def _run(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(argv)
        return code, buf.getvalue()

    def test_sha_rule(self):
        self.assertTrue(sha_matches(FROZEN_SHA))
        self.assertTrue(sha_matches("1ad86ac"))
        self.assertFalse(sha_matches("1ad86ad"))
        self.assertFalse(sha_matches("deadbeef"))
        self.assertFalse(sha_matches("1ad86a"))
        self.assertFalse(sha_matches(None))

    def test_oos_rejects_bad_sha_or_existing_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "LOCK"
            code, text = self._run(["--oos", "--prereg-sha", "deadbeef", "--lock", str(lock),
                                    "--panel", str(Path(tmp) / "missing.sqlite")])
            self.assertNotEqual(code, 0)
            self.assertIn("SHA", text)
            self.assertFalse(lock.exists())
            lock.write_text("keep\n", encoding="utf-8")
            code, text = self._run(["--oos", "--prereg-sha", FROZEN_SHA, "--lock", str(lock),
                                    "--panel", str(Path(tmp) / "missing.sqlite")])
            self.assertNotEqual(code, 0)
            self.assertIn("锁", text)
            self.assertEqual(lock.read_text(encoding="utf-8"), "keep\n")

    def test_end_after_design_without_oos_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "LOCK"
            code, text = self._run(["--end", "2016-01-01", "--panel", str(Path(tmp) / "missing.sqlite"),
                                    "--lock", str(lock)])
            self.assertNotEqual(code, 0)
            self.assertIn("2015-12-31", text)
            self.assertFalse(lock.exists())
            code, text = self._run(["--end", "2015-12-31", "--panel", str(Path(tmp) / "missing.sqlite"),
                                    "--market-db", str(Path(tmp) / "missing.sqlite"), "--lock", str(lock)])
            self.assertNotEqual(code, 0)
            self.assertNotIn("样本外需要", text)
            self.assertFalse(lock.exists())
