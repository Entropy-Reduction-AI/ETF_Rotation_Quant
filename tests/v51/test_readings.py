"""§2 读数。预热等权，并和画像里的公式对一下。"""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.v3.engine.book import RunnerError
from src.v51.params import RULERS
from src.v51.readings import read_panel, read_series


def _portrait(asset: pd.Series, cash: pd.Series) -> dict[str, pd.Series]:
    """`profile33.py` 的 `state`，只留一条序列。用来对照，不从画像脚本导入。"""
    import bisect

    rulers = list(RULERS)
    long = [n for n in rulers if n >= 60]
    logged = np.log1p(asset.astype(float))
    ready = logged.notna().rolling(250, min_periods=1).sum().ge(250)
    filled = logged.fillna(0.0)
    excess = filled - np.log1p(cash.fillna(0.0))
    sigma = filled.rolling(250).std().shift(1)
    velocity = pd.DataFrame(
        {n: excess.rolling(n).sum() / (sigma * np.sqrt(n)) for n in rulers}
    ).where(ready, axis=0)

    def percentile(values):
        out = np.full(len(values), np.nan)
        history = []
        for i, value in enumerate(values):
            if np.isnan(value):
                continue
            if len(history) >= 250:
                out[i] = bisect.bisect_left(history, value) / len(history)
            bisect.insort(history, value)
        return out

    loudness = pd.DataFrame(
        {n: percentile(velocity[n].abs().rolling(n).mean().to_numpy(dtype=float)) for n in rulers},
        index=velocity.index,
    )
    weight = loudness.div(loudness.sum(axis=1), axis=0)
    warmup = loudness.isna().any(axis=1) & velocity.notna().all(axis=1)
    weight.loc[warmup] = 1.0 / len(rulers)
    slow = velocity[long].mean(axis=1, skipna=False)
    easing = ((slow > slow.shift(20)) & (slow.shift(20) > slow.shift(40))).where(slow.notna() & slow.shift(40).notna())
    return {
        "H": (weight * velocity).sum(axis=1, min_count=len(rulers)),
        "F": (velocity < 0).mean(axis=1).where(velocity.notna().all(axis=1)),
        "E": easing.astype(float),
        "warmup": warmup.fillna(False),
        "weight": weight,
    }


class Readings(unittest.TestCase):
    def _series(self):
        index = pd.bdate_range(end="2015-12-31", periods=820)
        rng = np.random.default_rng(51)
        quiet = rng.normal(0.0, 0.004, 400)
        loud = rng.normal(0.002, 0.02, len(index) - 400)
        asset = pd.Series(np.concatenate([quiet, loud]), index=index)
        cash = pd.Series(0.02 / 252, index=index)
        return asset, cash

    def test_warmup_is_equal_weight_until_every_ruler_has_history(self):
        asset, cash = self._series()
        panel = read_panel(pd.DataFrame({"asset": asset, "cash": cash}), "cash")
        warm = panel.warmup["asset"] & panel.H["asset"].notna() & panel.E["asset"].notna()
        self.assertTrue(warm.any())
        row = panel.weight["asset"].loc[warm].iloc[0]
        self.assertEqual(len(row), 28)
        self.assertTrue(np.allclose(row.to_numpy(dtype=float), np.full(28, 1.0 / 28)))
        later = panel.H["asset"].notna() & ~panel.warmup["asset"]
        self.assertTrue(later.any())
        matured = panel.weight["asset"].loc[later].iloc[-1]
        self.assertAlmostEqual(float(matured.sum()), 1.0, places=12)
        self.assertGreater(float(matured.max() - matured.min()), 1e-6)

    def test_matches_the_portrait_formula(self):
        asset, cash = self._series()
        got = read_series(asset, np.log1p(cash.fillna(0.0)))
        ref = _portrait(asset, cash)
        pd.testing.assert_series_equal(got["H"], ref["H"], check_names=False)
        pd.testing.assert_series_equal(got["F"], ref["F"], check_names=False)
        pd.testing.assert_series_equal(got["E"].astype(float), ref["E"].astype(float), check_names=False)
        pd.testing.assert_series_equal(got["warmup"].astype(bool), ref["warmup"].astype(bool), check_names=False)
        pd.testing.assert_frame_equal(got["weight"], ref["weight"])

    def test_refuses_dates_after_the_design_window(self):
        index = pd.bdate_range("2016-01-04", periods=5)
        frame = pd.DataFrame({"asset": 0.0, "cash": 0.0}, index=index)
        with self.assertRaises(RunnerError):
            read_panel(frame, "cash")
