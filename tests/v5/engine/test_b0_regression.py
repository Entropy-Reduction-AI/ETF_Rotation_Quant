"""用改过的 `simulate_path` 重跑 v4 B0。日净收益须与已登记序列逐日相同。

显式 `listed_only=False`：D35 场内口径关闭时，两个池仍与冻结设计期逐位一致。
不写 ledger，不写 LOCK，不读 2016-01-01 及以后。
"""
from __future__ import annotations

import json
import unittest

import pandas as pd

from src.data import db as DB
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets, execute_job, read_net, run_dir, series_sha256, single_jobs


def _lines(series: pd.Series) -> list[str]:
    return [
        f"{pd.Timestamp(day).date().isoformat()},{float(value):.12g}"
        for day, value in series.items()
    ]


class B0Regression(unittest.TestCase):
    def test_both_pools_match_the_registered_daily_net(self):
        if not DB.MARKET_DB.exists() or DB.MARKET_DB.stat().st_size < 1_000_000:
            self.fail("market.sqlite 不是登记的行情库（Git LFS 未拉取），无法回归 B0")
        spec = load_spec()
        markets = Markets(spec)
        jobs = {(job.case, job.pool): job for job in single_jobs()}
        for pool in ("index", "tradable"):
            with self.subTest(pool=pool):
                net, dropped = execute_job(
                    job := jobs[("B0", pool)],
                    markets.get(pool, t4=False, listed_only=False),
                    spec,
                )
                registered = read_net("B0", pool)
                summary = json.loads((run_dir("B0", pool) / "summary.json").read_text(encoding="utf-8"))
                self.assertEqual(dropped, [])
                self.assertEqual(job.decision_delay, 0)
                got = _lines(net)
                have = _lines(registered)
                self.assertEqual(len(got), len(have), pool)
                if got != have:
                    mismatch = next(
                        (i, left, right) for i, (left, right) in enumerate(zip(got, have)) if left != right
                    )
                    self.fail(f"{pool} 日净收益不一致：{mismatch}")
                self.assertEqual(series_sha256(net), summary["net_sha256"])
                self.assertLessEqual(str(net.index.max().date()), "2015-12-31")


if __name__ == "__main__":
    unittest.main()
