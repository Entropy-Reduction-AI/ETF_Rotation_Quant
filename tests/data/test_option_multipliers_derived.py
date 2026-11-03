"""派生合约单位只靠表内数字重算，不出网，不读 market.sqlite。"""
import csv
import hashlib
import unittest
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DERIVED = ROOT / "data" / "options" / "derived"
CONTRACTS = ROOT / "data" / "options" / "raw" / "sse" / "contracts.csv"
SEED = "20261103"


def rows(name):
    with (DERIVED / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def q_int(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def q3(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def contract_rows():
    with CONTRACTS.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class DerivedMultiplierTests(unittest.TestCase):
    def test_ninety_two_class_a_rows_share_one_ex_div(self):
        derived = rows("multipliers-derived.csv")
        contracts = contract_rows()
        expected = {
            row["contract_id"]
            for row in contracts
            if row["underlying"] == "510050"
            and row["adjustment_flag"] == "A"
            and row["first_risk_date"] == "2021-11-29"
        }
        self.assertEqual(len(derived), 92)
        self.assertEqual({row["contract_id"] for row in derived}, expected)
        known = {row["contract_id"]: row for row in contracts}
        for row in derived:
            self.assertEqual(row["flag"], "derived")
            self.assertEqual(row["ex_div_event_id"], "510050-2021-11-29")
            self.assertEqual(row["ex_div_date"], "2021-11-29")
            self.assertEqual(row["record_date"], "2021-11-26")
            self.assertEqual(row["dividend_amount"], "0.0410")
            self.assertEqual(row["dividend_per_10_shares"], "0.41")
            self.assertEqual(row["prev_close_date"], "2021-11-26")
            self.assertEqual(row["prev_close"], "3.223")
            self.assertEqual(row["prior_unit"], "10000")
            self.assertEqual(row["derived_unit"], "10129")
            self.assertEqual(row["share_change_ratio"], "0")
            self.assertEqual(row["rights_price"], "0")
            self.assertIn("510050_20211122_1_7Qnnvi3l.pdf", row["dividend_source"])
            self.assertIn(row["security_id"], row["prior_unit_source"])
            self.assertIn(row["prior_contract_id"], row["prior_unit_source"])
            prior = row["contract_id"][:11] + "M" + row["contract_id"][12:]
            self.assertEqual(row["prior_contract_id"], prior)
            self.assertIn(prior, known)
            raw = Decimal(row["prior_unit"]) * Decimal(row["prev_close"]) / (
                Decimal(row["prev_close"]) - Decimal(row["dividend_amount"])
            )
            self.assertEqual(q_int(raw), int(row["derived_unit"]))
            strike = q3(
                Decimal(row["org_exercise_price"]) * Decimal(row["prior_unit"]) / Decimal(row["derived_unit"])
            )
            self.assertEqual(strike, Decimal(row["recomputed_exercise_price"]))
            self.assertEqual(strike, Decimal(row["symbol_exercise_price"]))
            self.assertIn(
                f"round_half_up({row['prior_unit']} * {row['prev_close']} / ({row['prev_close']} - {row['dividend_amount']}))",
                row["formula"],
            )

    def test_spot_checks_match_published_units(self):
        checks = rows("spot-checks.csv")
        seeds = [row for row in checks if row["check_kind"] == "seed-contract"]
        events = [row for row in checks if row["check_kind"] == "published-event"]
        self.assertEqual(
            [row["contract_id"] for row in seeds],
            ["510300P2206A04400", "510300P2401A03900", "588080C2603A01250"],
        )
        self.assertEqual(len(events), 20)
        self.assertEqual(sum(int(row["n_contracts"]) for row in events), 2164)
        for row in checks:
            self.assertEqual(row["unit_match"], "exact")
            self.assertEqual(row["exercise_price_match"], "exact")
            self.assertEqual(row["published_unit"], row["recomputed_unit"])
            raw = Decimal(row["prior_unit"]) * Decimal(row["prev_close"]) / (
                Decimal(row["prev_close"]) - Decimal(row["dividend_amount"])
            )
            self.assertEqual(q_int(raw), int(row["recomputed_unit"]))
            strike = q3(
                Decimal(row["org_exercise_price"])
                * Decimal(row["prior_unit"])
                / Decimal(row["recomputed_unit"])
            )
            self.assertEqual(strike, Decimal(row["published_exercise_price"]))
            self.assertEqual(strike, Decimal(row["recomputed_exercise_price"]))
        for row in seeds:
            digest = hashlib.sha256(f"{SEED}:{row['contract_id']}".encode()).hexdigest()
            self.assertEqual(row["pick_key"], digest)

    def test_two_standard_listings_stay_blocked(self):
        blocked = rows("blocked-attempts.csv")
        self.assertEqual(
            [row["contract_id"] for row in blocked],
            ["510050C2201M02900", "510050P2201M02900"],
        )
        contracts = {row["contract_id"]: row for row in contract_rows()}
        for row in blocked:
            self.assertEqual(row["reason"], "not_ex_div_adjustment")
            self.assertEqual(row["adjustment_flag"], "M")
            self.assertEqual(row["strike_yuan"], "2.900")
            self.assertEqual(contracts[row["contract_id"]]["adjustment_flag"], "M")
            self.assertEqual(contracts[row["contract_id"]]["first_risk_date"], "2021-11-29")

    def test_manifest_hashes_match_files(self):
        listed = rows("manifest.csv")
        names = [row["path"] for row in listed]
        self.assertEqual(
            names,
            [
                "data/options/derived/README.md",
                "data/options/derived/multipliers-derived.csv",
                "data/options/derived/spot-checks.csv",
                "data/options/derived/blocked-attempts.csv",
            ],
        )
        for row in listed:
            digest = hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest()
            self.assertEqual(row["sha256"], digest)
            self.assertEqual(int(row["line_count"]), len((ROOT / row["path"]).read_text(encoding="utf-8").splitlines()))


if __name__ == "__main__":
    unittest.main()
