"""复现 prem_episodes.py。事件日期必须和那份脚本、以及冻结清单一致。

单标的价格变化是诊断字段，不是组合收益。
"""
from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from src.v3.premium.episodes import scan_explore, scan_frames
from src.v3.premium.load import connect_readonly

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "prem_episodes.csv"
DB = ROOT / "data" / "market.sqlite"


def _script_scan(frames: dict[str, tuple[pd.DataFrame, pd.DataFrame]]) -> pd.DataFrame:
    """operations/reviews/diag/v3-explore/prem_episodes.py 的循环，原样搬过来做对照。"""
    out = []
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
                    "code": str(code),
                    "start": str(segment.index[0].date()),
                    "peak": str(peak_at.date()),
                    "peak_prem": round(float(peak_premium) * 100),
                    "base": round(float(base) * 100),
                    "rise_days": int((peak_at - segment.index[0]).days),
                    "half_revert_days": (reverted - peak_at).days if reverted is not None else None,
                    "px_chg": None,
                    "nav_chg": None,
                }
                if reverted is not None:
                    record["px_chg"] = round((joined["close"][reverted] / joined["close"][peak_at] - 1) * 100, 1)
                    record["nav_chg"] = round((joined["navl"][reverted] / joined["navl"][peak_at] - 1) * 100, 1)
                out.append(record)
                cursor = end
            else:
                cursor += 1
    return pd.DataFrame(out)


def _canon(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["code"] = out["code"].map(lambda value: str(value).zfill(6))
    for column in ("peak_prem", "base", "rise_days"):
        out[column] = pd.to_numeric(out[column]).astype(int)
    for column in ("half_revert_days", "px_chg", "nav_chg"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    return out.sort_values(["code", "start", "peak"]).reset_index(drop=True)


class SyntheticEpisode(unittest.TestCase):
    def test_a_ten_percent_spike_opens_and_closes(self):
        dates = pd.bdate_range("2021-01-04", periods=200)
        nav = pd.DataFrame({"nav": 1.0}, index=dates)
        close = pd.Series(1.0, index=dates)
        close.iloc[160:170] = 1.2
        price = close.to_frame("close")
        found = scan_frames({"demo": (price, nav)})
        self.assertEqual(len(found), 1)
        row = found.iloc[0]
        self.assertEqual(row["start"], str(dates[160].date()))
        self.assertEqual(row["peak"], str(dates[160].date()))
        self.assertEqual(int(row["peak_prem"]), 20)
        self.assertEqual(int(row["base"]), 0)
        self.assertEqual(row["half_revert_days"], int((dates[170] - dates[160]).days))
        self.assertAlmostEqual(float(row["px_chg"]), round((1.0 / 1.2 - 1.0) * 100, 1), places=6)


class ExploreList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DB.exists() or DB.stat().st_size < 1000:
            raise unittest.SkipTest("market.sqlite 不在这台机器上")
        cls.con = connect_readonly(DB)

    @classmethod
    def tearDownClass(cls):
        con = getattr(cls, "con", None)
        if con is not None:
            con.close()

    def test_dates_match_the_original_script_and_the_frozen_list(self):
        from src.v3.premium.episodes import load_explore_frames
        frames = load_explore_frames(self.con)
        module = _canon(scan_explore(self.con))
        script = _canon(_script_scan(frames))
        fixture = _canon(pd.read_csv(FIXTURE, dtype={"code": str}))
        self.assertEqual(len(module), 49)
        self.assertEqual(len(fixture), 49)
        pd.testing.assert_frame_equal(module, script, check_dtype=False, rtol=0.0, atol=1e-9)
        pd.testing.assert_frame_equal(module, fixture, check_dtype=False, rtol=0.0, atol=1e-9)
        crude = module[(module["code"] == "161129") & (module["start"] == "2025-04-10")]
        self.assertEqual(len(crude), 1)
        self.assertEqual(crude.iloc[0]["peak"], "2025-04-23")
        self.assertEqual(int(crude.iloc[0]["peak_prem"]), 70)
        still_open = module[(module["code"] == "513100") & (module["start"] == "2026-06-01")]
        self.assertEqual(len(still_open), 1)
        self.assertTrue(pd.isna(still_open.iloc[0]["half_revert_days"]))


if __name__ == "__main__":
    unittest.main()
