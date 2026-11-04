"""一次性检验的门禁和判据。不连行情库，也不写 results/v5/oneshot。"""
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.v3.engine.book import RunnerError
from src.v3.eval.common import EvalError
from src.v3.eval.selection import walk_forward
from src.v3.eval.windows import rolling_windows
from src.v4.peers import load_peer, run_peer
from src.v4.r5.design import prepare_market, reference_frame
from src.v51.oneshot import (
    FREEZE_SHA,
    PRIMARY,
    WINDOW_END,
    WINDOW_START,
    OneshotError,
    arm_dir,
    attempt_report,
    authorize,
    criterion_1_on_window,
    criterion_6,
    is_formal,
    scored,
)


def _calendar(start: str, end: str) -> pd.DatetimeIndex:
    return pd.bdate_range(start, end)


class Gate(unittest.TestCase):
    def test_missing_lock_refuses_the_window(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(OneshotError):
                authorize(root / "LOCK", root / "oneshot")

    def test_lock_must_name_the_freeze_and_the_window(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            lock = root / "LOCK"
            lock.write_text("没有冻结提交\n", encoding="utf-8")
            with self.assertRaises(OneshotError):
                authorize(lock, root / "oneshot")
            lock.write_text(f"{FREEZE_SHA}\n只有起点 {WINDOW_START}\n", encoding="utf-8")
            with self.assertRaises(OneshotError):
                authorize(lock, root / "oneshot")

    def test_a_finished_run_is_not_repeated(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            lock = root / "LOCK"
            lock.write_text(f"{FREEZE_SHA}\n{WINDOW_START} → {WINDOW_END}\n", encoding="utf-8")
            out = root / "oneshot"
            out.mkdir()
            authorize(lock, out)
            (out / "ran.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaises(OneshotError):
                authorize(lock, out)

    def test_does_not_target_the_lock_file(self):
        with tempfile.TemporaryDirectory() as folder:
            lock = Path(folder) / "LOCK"
            lock.write_text(f"{FREEZE_SHA}\n{WINDOW_START} {WINDOW_END}\n", encoding="utf-8")
            with self.assertRaises(OneshotError):
                authorize(lock, lock)

    def test_names_keep_v51_as_comparison_only(self):
        self.assertTrue(is_formal(PRIMARY, "index"))
        self.assertFalse(is_formal(PRIMARY, "tradable"))
        self.assertFalse(is_formal("v5.1-对照", "index"))
        self.assertFalse(is_formal("A1", "index"))
        folder = arm_dir(Path("/tmp/oneshot"), "tradable", "v5.1-对照")
        self.assertEqual(folder, Path("/tmp/oneshot/tradable/v5.1-对照"))
        with self.assertRaises(OneshotError):
            arm_dir(Path("/tmp/oneshot"), "china", PRIMARY)


class WindowMath(unittest.TestCase):
    def test_default_rolling_windows_stay_inside_2015(self):
        days = _calendar("2016-01-04", "2019-12-31")
        self.assertEqual(rolling_windows(days, 36), [])
        opened = rolling_windows(days, 36, end_limit=WINDOW_END)
        self.assertTrue(opened)
        self.assertGreaterEqual(pd.Timestamp(opened[0][0]), pd.Timestamp(WINDOW_START))

    def test_scored_slice_must_reach_the_last_session(self):
        last = pd.Timestamp("2026-09-30")
        index = _calendar("2016-01-04", "2026-09-30")
        series = pd.Series(0.0, index=index)
        got = scored(series, last)
        self.assertEqual(pd.Timestamp(got.index.max()), last)
        self.assertGreaterEqual(pd.Timestamp(got.index.min()), pd.Timestamp(WINDOW_START))
        short = series.loc[: "2026-09-01"]
        with self.assertRaises(OneshotError):
            scored(short, last)
        late = pd.concat([series, pd.Series({pd.Timestamp("2026-10-08"): 0.0})])
        with self.assertRaises(OneshotError):
            scored(late, last)

    def test_positive_window_passes_criterion_1(self):
        index = _calendar(WINDOW_START, WINDOW_END)
        report = criterion_1_on_window(pd.Series(0.001, index=index), pd.Series(0.0, index=index))
        self.assertGreater(report["n_60"], 0)
        self.assertGreater(report["median_60"], 0.0)
        self.assertGreaterEqual(report["fraction_positive_60"], 0.60)
        self.assertTrue(report["pass"])

    def test_rebound_uses_the_t_hurdle(self):
        index = _calendar("2016-01-04", "2016-04-29")
        states = pd.Series(
            ["牛市", "牛市", "反弹", "反弹"],
            index=pd.to_datetime(["2016-01-31", "2016-02-29", "2016-03-31", "2016-04-30"]),
        )
        up = criterion_6(pd.Series(0.001, index=index), pd.Series(0.0, index=index), states)
        self.assertGreaterEqual(up["牛市"], 0.0)
        self.assertGreaterEqual(up["rebound_t"], -2.0)
        self.assertTrue(up["pass"])
        down = pd.Series(0.001, index=index)
        down.loc["2016-03-01":] = -0.02
        lost = criterion_6(down, pd.Series(0.0, index=index), states)
        self.assertLess(lost["rebound_t"], -2.0)
        self.assertFalse(lost["pass"])
        bear = criterion_6(pd.Series(-0.001, index=index), pd.Series(0.0, index=index), states)
        self.assertLess(bear["牛市"], 0.0)
        self.assertFalse(bear["pass_bull"])
        self.assertFalse(bear["pass"])

    def test_attempt_count_skips_v51_and_a1(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)

            def write(name: str, rows: list[dict]) -> None:
                with (root / name).open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=["arm", "params", "segment"])
                    writer.writeheader()
                    writer.writerows(rows)

            write("v3.csv", [
                {"arm": "A", "params": "{}", "segment": "design"},
                {"arm": "C1-shadow", "params": "{}", "segment": "design"},
            ])
            write("v4.csv", [{"arm": "B0", "params": "{}", "segment": "design"}])
            write("v51.csv", [
                {"arm": "v5.1", "params": "{}", "segment": "design"},
                {"arm": "A1", "params": "{}", "segment": "design"},
            ])
            missing = attempt_report(root / "v3.csv", root / "v4.csv", root / "missing.csv")
            # L3=2, L4=1, L5=0, C=1, +28+35+1 → 2+1+0-1+64 = 66
            self.assertEqual(missing["L5"], 0)
            self.assertFalse(missing["v5_ledger_present"])
            self.assertEqual(missing["attempts"], 66)
            self.assertEqual(missing["excluded_from_L5"], ["v5.1", "A1"])


class ClosedByDefault(unittest.TestCase):
    def test_market_load_rejects_the_oneshot_end(self):
        with self.assertRaises(RunnerError):
            prepare_market("index", t4=False, allow_substitute=True, spec=object(), end=WINDOW_END)

    def test_reference_frame_rejects_the_oneshot_end(self):
        with self.assertRaises(RunnerError):
            reference_frame(end=WINDOW_END)

    def test_peer_dates_after_2015_need_the_flag(self):
        dates = pd.to_datetime(["2015-12-31", "2016-01-04"])
        peer = load_peer("A1", "index")
        levels = pd.DataFrame(1.0, index=dates, columns=[leg.leg_id for leg in peer.legs])
        with self.assertRaises(RunnerError):
            run_peer(peer, dates, levels)
        result = run_peer(peer, dates, levels, allow_after=True)
        self.assertEqual(len(result.net), 2)

    def test_walk_forward_rejects_2016_unless_opened(self):
        dates = pd.bdate_range("2016-01-04", periods=5)
        series = pd.Series(0.0, index=dates)
        kwargs = {
            "train_start": "2006-01-01",
            "first_apply_year": 2011,
            "dates": dates,
        }
        with self.assertRaises(EvalError):
            walk_forward({(120, 0.1): series}, series, **kwargs)
        picked = walk_forward({(120, 0.1): series}, series, allow_after=True, **kwargs)
        self.assertIn(2016, picked["choices"])


if __name__ == "__main__":
    unittest.main()
