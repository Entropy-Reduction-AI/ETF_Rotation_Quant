"""同结构随机的两个比较式。不读行情。"""

from __future__ import annotations

import unittest

import numpy as np

from src.v6.health_random import SEED, TRIALS, beat_median_share, rank_percentile


class RandomStatTests(unittest.TestCase):
    def test_locked_count_and_seed(self):
        self.assertEqual(SEED, 20261122)
        self.assertEqual(TRIALS, 1000)

    def test_percentile_counts_paths_at_or_below_the_rule_cagr(self):
        self.assertAlmostEqual(rank_percentile(0.10, np.array([0.09, 0.10, 0.11])), 100.0 * 2 / 3)

    def test_beat_median_is_strict(self):
        rule = np.array([0.02, 0.01])
        random = np.array([
            [0.00, 0.01],
            [0.03, 0.01],
            [0.01, 0.01],
        ])
        self.assertAlmostEqual(beat_median_share(rule, random), 0.5)
