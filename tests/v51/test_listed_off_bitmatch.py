"""开关关闭时，设计期两个池与已冻结结果逐位一致。

B0 在 `tests/v5/engine/test_b0_regression.py`（显式 `listed_only=False`）。
这里核对 v5.1 与 A1、A2。不写账本，不写 LOCK，不读 2016-01-01 及以后的组合收益。
"""
from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from src.data import db as DB
from src.v3.engine.spec import load_spec
from src.v4.engine.carriers import build_candidates, listed_carriers, sse_calendar
from src.v4.peers import load_peer, run_peer
from src.v4.r5.design import read_net, series_sha256
from src.v4.r5.peers import research_panel
from src.v51.design import _signal, eligible_frame
from src.v51.execute import open_market, run_book, universe_for

ROOT = Path(__file__).resolve().parents[2]


def _ready() -> bool:
    return DB.MARKET_DB.exists() and DB.MARKET_DB.stat().st_size >= 1_000_000


def _ordered(series: pd.Series) -> pd.Series:
    ordered = pd.Series(series, dtype=float).sort_index()
    ordered.index = pd.DatetimeIndex(pd.to_datetime(ordered.index)).normalize()
    return ordered


def _lines(series: pd.Series) -> list[str]:
    return [
        f"{pd.Timestamp(day).date().isoformat()},{float(value):.12g}"
        for day, value in _ordered(series).items()
    ]


def _same(case: unittest.TestCase, got: pd.Series, frozen: pd.Series, label: str) -> None:
    left = _lines(got)
    right = _lines(frozen)
    case.assertEqual(len(left), len(right), label)
    if left != right:
        mismatch = next(
            (i, one, other) for i, (one, other) in enumerate(zip(left, right)) if one != other
        )
        case.fail(f"{label} 日净收益不一致：{mismatch}")
    case.assertEqual(series_sha256(_ordered(got)), series_sha256(_ordered(frozen)))


class ListedUniverse(unittest.TestCase):
    def test_design_end_filter_drops_otc_and_keeps_510880(self):
        if not _ready():
            self.fail("market.sqlite 不是登记的行情库（Git LFS 未拉取）")
        from src.v3.data.universe import containers as load_containers
        from src.v4.r5.design import _connect

        end = "2015-12-31"
        con = _connect()
        try:
            calendar = sse_calendar(con, end)
            grouped = build_candidates(con, load_containers(), calendar, end)
        finally:
            con.close()
        filtered = listed_carriers(grouped)
        off_codes = {row.code for rows in grouped.values() for row in rows}
        on_codes = {row.code for rows in filtered.values() for row in rows}
        self.assertIn("161211", off_codes)
        self.assertNotIn("161211", on_codes)
        self.assertTrue(any(row.tier == 2 for rows in grouped.values() for row in rows))
        self.assertFalse(any(row.tier == 2 for rows in filtered.values() for row in rows))
        off = next(row for row in grouped["csi-dividend"] if row.code == "510880")
        on = next(row for row in filtered["csi-dividend"] if row.code == "510880")
        self.assertIs(on, off)
        self.assertEqual(on.tier, 3)
        self.assertLessEqual(str(pd.Timestamp(calendar.max()).date()), end)


class OffPathNets(unittest.TestCase):
    def test_v51_both_pools_match_when_listed_only_is_off(self):
        if not _ready():
            self.fail("market.sqlite 不是登记的行情库（Git LFS 未拉取）")
        from src.v51.allocate import target_weights

        spec = load_spec()
        for pool in ("index", "tradable"):
            with self.subTest(pool=pool):
                market = open_market(pool, spec, listed_only=False)
                signal = _signal(market)
                allocation = target_weights(
                    signal, universe_for(market),
                    eligible=eligible_frame(pool, market.liquidity, signal.index),
                )
                book = run_book(market, spec, allocation.decisions)
                frozen = pd.read_csv(
                    ROOT / "results" / "v5.1" / "design" / pool / "daily.csv",
                    parse_dates=["date"], index_col="date",
                )["net"]
                _same(self, book.net, frozen, f"v5.1/{pool}")
                self.assertLessEqual(str(pd.Timestamp(book.net.index.max()).date()), "2015-12-31")

    def test_peers_both_pools_match_when_listed_only_is_off(self):
        if not _ready():
            self.fail("market.sqlite 不是登记的行情库（Git LFS 未拉取）")
        spec = load_spec()
        panel = research_panel(spec, listed_only=False)
        for peer_id in ("A1", "A2"):
            for pool in ("index", "tradable"):
                with self.subTest(peer=peer_id, pool=pool):
                    peer = load_peer(peer_id, pool)
                    carriers = panel["carriers"] if pool == "tradable" else None
                    quotes = panel["tradable_quotes"] if pool == "tradable" else panel["index_quotes"]
                    levels = panel["tradable_levels"] if pool == "tradable" else panel["levels"]
                    signal_levels = panel["levels"] if pool == "tradable" else None
                    result = run_peer(
                        peer, panel["calendar"], levels, signal_levels=signal_levels,
                        cash=panel["cash"], carriers=carriers, quotes=quotes, calendar_closed=True,
                    )
                    _same(self, result.net, read_net(peer_id, pool), f"{peer_id}/{pool}")
                    self.assertLessEqual(str(result.net.index.max().date()), "2015-12-31")


if __name__ == "__main__":
    unittest.main()
