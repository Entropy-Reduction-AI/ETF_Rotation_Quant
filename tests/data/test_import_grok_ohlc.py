"""import_grok_ohlc：构造的清单与 CSV，不读真实 incoming，不连默认库。"""
import csv
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from src.data import db as DB
from tests.marketdb import open_db, put
import scripts.import_grok_ohlc as imp


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, rows: list[dict]) -> str:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "open", "high", "low", "close", "volume", "amount"])
        writer.writeheader()
        writer.writerows(rows)
    return _sha(path)


class ImportGrokOhlc(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp))
        self.db = self.tmp / "market.sqlite"
        self.incoming = self.tmp / "in"
        self.incoming.mkdir()
        self.con = open_db(self.db)
        self.addCleanup(self.con.close)
        days = ["2024-01-02", "2024-01-03", "2024-01-04"]
        put(self.con, "P", __import__("pandas").DataFrame({
            "date": days, "open": [9, 10, 11], "high": [12, 13, 14], "low": [8, 9, 10],
            "close": [10, 11, 12], "volume": [1, 1, 1]}), "csi")
        put(self.con, "TR", __import__("pandas").DataFrame({
            "date": days, "close": [20, 22, 24], "volume": [1, 1, 1]}), "csi")
        run = DB.start_run(self.con, "backfill")
        DB.write_coverage(self.con, run, [dict(
            theme_id="T01", container="甲", code="P", series_code="TR", series_adj="raw",
            tr_code_used="TR", route_used="csi", status="retained")])
        DB.finish_run(self.con, run)

    def _manifest(self, files):
        (self.incoming / "MANIFEST.json").write_text(json.dumps({"files": files}), encoding="utf-8")

    def _run(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = imp.main(["--db", str(self.db), "--incoming", str(self.incoming)])
        return code, buf.getvalue()

    def _entry(self, name, code, digest):
        return {"file": name, "index_code": code, "source": "中证指数官网", "sha256": digest}

    def test_accepts_matching_closes_skips_flats_and_is_idempotent(self):
        rows = [
            {"date": "2024-01-02", "open": 9, "high": 12, "low": 8, "close": 10, "volume": 3, "amount": 1},
            {"date": "2024-01-03", "open": 11, "high": 11, "low": 11, "close": 11, "volume": 1, "amount": 1},
            {"date": "2024-01-04", "open": 11, "high": 14, "low": 10, "close": 12, "volume": "", "amount": 1},
        ]
        digest = _write_csv(self.incoming / "P.csv", rows)
        self._manifest([self._entry("P.csv", "P", digest), {"file": "tr_closes.csv", "sha256": "0" * 64}])
        before_bars = DB.sha256_file(self.db)
        code, text = self._run()
        self.assertEqual(code, 0, text)
        self.assertIn("不导入 tr_closes.csv", text)
        self.assertIn("平盘跳过 1", text)
        got = imp.existing_rows(self.db)
        self.assertEqual([row[1] for row in got], ["2024-01-02", "2024-01-04"])
        self.assertIsNone(got[1][6])
        self.assertNotEqual(DB.sha256_file(self.db), before_bars)
        again_sha = DB.sha256_file(self.db)
        code, text = self._run()
        self.assertEqual(code, 0, text)
        self.assertIn("不写库", text)
        self.assertEqual(DB.sha256_file(self.db), again_sha)
        con = DB.connect(self.db, readonly=True)
        try:
            self.assertEqual(con.execute("SELECT count(*) FROM bars").fetchone()[0], 6)
        finally:
            con.close()

    def test_rejects_close_mismatch_and_falling_k(self):
        bad = [{"date": d, "open": 90, "high": 110, "low": 80, "close": 100, "volume": 1, "amount": 1}
               for d in ("2024-01-02", "2024-01-03", "2024-01-04")]
        digest = _write_csv(self.incoming / "P.csv", bad)
        self._manifest([self._entry("P.csv", "P", digest)])
        code, text = self._run()
        self.assertEqual(code, 0, text)
        self.assertIn("拒收 P", text)
        self.assertIn("收盘相对差", text)
        self.assertEqual(imp.existing_rows(self.db), [])
        near = [
            {"date": "2024-01-02", "open": 9, "high": 12, "low": 8, "close": 10, "volume": 1, "amount": 1},
            {"date": "2024-01-03", "open": 10, "high": 13, "low": 9, "close": 11, "volume": 1, "amount": 1},
            {"date": "2024-01-04", "open": 1, "high": 2, "low": 0.5, "close": 1, "volume": 1, "amount": 1},
        ]
        # 前两日收盘吻合，第三日收盘 1 对 bars 12，相对差超 0.05%，1/3 通过，低于 99%。
        digest = _write_csv(self.incoming / "P.csv", near)
        self._manifest([self._entry("P.csv", "P", digest)])
        _, text = self._run()
        self.assertIn("低于 99%", text)
        matched = [
            {"date": "2024-01-02", "open": 9, "high": 12, "low": 8, "close": 10, "volume": 1, "amount": 1},
            {"date": "2024-01-03", "open": 10, "high": 13, "low": 9, "close": 11, "volume": 1, "amount": 1},
            {"date": "2024-01-04", "open": 11, "high": 14, "low": 10, "close": 12, "volume": 1, "amount": 1},
        ]
        # 把全收益收盘改成逐日下跌相对价格，k 日变化为负。
        put(self.con, "TR", __import__("pandas").DataFrame({
            "date": ["2024-01-02", "2024-01-03", "2024-01-04"],
            "close": [30, 11, 6], "volume": [1, 1, 1]}), "csi")
        digest = _write_csv(self.incoming / "P.csv", matched)
        self._manifest([self._entry("P.csv", "P", digest)])
        _, text = self._run()
        self.assertIn("拒收 P", text)
        self.assertIn("k 日变化", text)
        self.assertEqual(imp.existing_rows(self.db), [])

    def test_rejects_sha_mismatch_and_broken_ohlc(self):
        digest = _write_csv(self.incoming / "P.csv", [
            {"date": "2024-01-02", "open": 9, "high": 8, "low": 7, "close": 10, "volume": 1, "amount": 1}])
        self._manifest([self._entry("P.csv", "P", "0" * 64)])
        _, text = self._run()
        self.assertIn("sha256", text)
        self._manifest([self._entry("P.csv", "P", digest)])
        _, text = self._run()
        self.assertIn("不满足", text)
        self.assertEqual(imp.existing_rows(self.db), [])
