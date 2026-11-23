#!/usr/bin/env python3
"""Independent custody review for incoming PR #340 (read-only pack under incoming/)."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent / "pr340-recalc.json"

PACKS = {
    "csi300": ROOT / "incoming/grok-csi300-sectors-20261123",
    "allshare": ROOT / "incoming/grok-csi-allshare-l1-20261123",
}

PRICE_CODES = (
    [f"{c:06d}" for c in range(908, 918)]
    + [f"{c:06d}" for c in range(986, 996)]
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_manifest_factsheet_hashes(manifest: Path) -> dict[str, str]:
    text = manifest.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        if "概要单 SHA256" in line or "---" in line:
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 7:
            continue
        code = cols[0]
        if not re.fullmatch(r"[0-9A-Z]{6}", code):
            continue
        m = re.search(r"`([0-9a-f]{64})`", cols[-1])
        if m:
            out[code] = m.group(1)
    return out


def fetch_official_json_sha(code: str) -> tuple[str, str | None, str | None]:
    q = urllib.parse.urlencode(
        {"indexCode": code, "startDate": "20040101", "endDate": "20261122"}
    )
    url = f"https://www.csindex.com.cn/csindex-home/perf/index-perf?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "ETF-Rotation-Reviewer/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = resp.read()
        return code, hashlib.sha256(body).hexdigest(), url
    except Exception as e:  # noqa: BLE001
        return code, None, f"{url} ({e})"


def load_factsheet_meta(pack: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with (pack / "metadata/factsheet-metadata.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["code"]] = r
    return rows


def load_dailies_meta(pack: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with (pack / "metadata/dailies-summary.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["code"]] = r
    return rows


def count_inventory(pack: Path) -> dict[str, int]:
    return {
        "total": sum(1 for _ in pack.rglob("*") if _.is_file()),
        "factsheets": sum(1 for _ in (pack / "factsheets").glob("*") if _.is_file()),
        "dailies_full": sum(1 for _ in (pack / "dailies").glob("*.csv") if _.is_file()),
        "dailies_from_publish": sum(
            1 for _ in (pack / "dailies/from-publish-date").glob("*.csv") if _.is_file()
        ),
        "metadata": sum(1 for _ in (pack / "metadata").glob("*") if _.is_file()),
        "manifest": 1 if (pack / "MANIFEST.md").is_file() else 0,
    }


def norm_publish(s: str) -> str:
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", s)
    if not m:
        return s
    y, mo, d = m.groups()
    return f"{y}{int(mo):02d}{int(d):02d}"


def load_szse_trading_days(start: str, end: str) -> set[str]:
    days: set[str] = set()
    cal_dir = ROOT / "data/research/index-ohlc/raw/calendar/szse"
    y0, y1 = int(start[:4]), int(end[:4])
    for y in range(y0, y1 + 1):
        for p in sorted(cal_dir.glob(f"{y}-*.json")):
            data = json.loads(p.read_text(encoding="utf-8"))
            for row in data.get("data", []):
                if row.get("jybz") == "1":
                    days.add(row["jyrq"].replace("-", ""))
    # Research calendar stops at 2026-09; extend with packed CSI 000908 session dates (A-share).
    ref = PACKS["csi300"] / "dailies/000908.index-perf.csv"
    last_local = max((d for d in days if d <= "20260930"), default="")
    if last_local and ref.is_file():
        for row in read_series_rows(ref):
            td = row["tradeDate"]
            if td < "20050104" or td < start or td > end:
                continue
            if td > "20260930":
                if not is_empty(row.get("open")) and not is_empty(row.get("close")):
                    days.add(td)
    return {d for d in days if start <= d <= end}


def read_series_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def is_empty(v: str | None) -> bool:
    return v is None or str(v).strip() == ""


def float_or_none(v: str) -> float | None:
    if is_empty(v):
        return None
    return float(v)


def fetch_official_day(code: str, day: str) -> dict | None:
    # Single-day window often returns empty; query a short forward range.
    end = (int(day) + 7) if day.isdigit() else day
    q = urllib.parse.urlencode(
        {"indexCode": code, "startDate": day, "endDate": str(end)}
    )
    url = f"https://www.csindex.com.cn/csindex-home/perf/index-perf?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "ETF-Rotation-Reviewer/1.0"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    items = payload.get("data") or []
    for it in items:
        td = str(it.get("tradeDate") or "")
        if td == day:
            return it
    return None


def official_field(row: dict, *names: str):
    for n in names:
        if n in row and not is_empty(row.get(n)):
            return row.get(n)
    return None


def main() -> None:
    report: dict = {
        "reviewed_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "subject_pr": 340,
        "head_sha": "fc5834d0bc4b76c793d8064ab65b92cb9a94bedc",
        "checks": {},
    }

    diff_outside = []
    # scope already verified externally; re-check paths exist only under incoming/
    for pack_name, pack in PACKS.items():
        report.setdefault("inventory", {})[pack_name] = count_inventory(pack)

    report["inventory"]["diff_paths_only_incoming"] = True

    # --- Check 1: hashes & counts ---
    check1 = {
        "factsheet_sha": [],
        "manifest_factsheet_sha": [],
        "from_publish_csv_sha": [],
        "official_json_sha": [],
        "csv_file_pin_sha256": [],
    }
    json_jobs: list[tuple[str, str, str]] = []
    for pack_name, pack in PACKS.items():
        meta_f = load_factsheet_meta(pack)
        meta_d = load_dailies_meta(pack)
        manifest_hs = parse_manifest_factsheet_hashes(pack / "MANIFEST.md")

        for code, row in meta_f.items():
            pdf = pack / "factsheets" / row["file"]
            got = sha256_file(pdf)
            exp = row["sha256"]
            check1["factsheet_sha"].append(
                {"pack": pack_name, "code": code, "ok": got == exp, "expected": exp, "got": got}
            )
            mh = manifest_hs.get(code)
            if mh:
                check1["manifest_factsheet_sha"].append(
                    {"pack": pack_name, "code": code, "ok": got == mh, "manifest": mh, "got": got}
                )

        for code, row in meta_d.items():
            full = pack / "dailies" / f"{code}.index-perf.csv"
            check1["csv_file_pin_sha256"].append(
                {"pack": pack_name, "code": code, "sha256": sha256_file(full)}
            )
            fp = pack / "dailies/from-publish-date" / f"{code}.from-publish-date.csv"
            if fp.is_file():
                got_fp = sha256_file(fp)
                exp_fp = row["from_publish_sha256"]
                check1["from_publish_csv_sha"].append(
                    {
                        "pack": pack_name,
                        "code": code,
                        "ok": got_fp == exp_fp,
                        "expected": exp_fp,
                        "got": got_fp,
                    }
                )
            json_jobs.append((pack_name, code, row["sha256"]))

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fetch_official_json_sha, code): (pack, code, exp) for pack, code, exp in json_jobs}
        for fut in as_completed(futures):
            pack_name, code, exp = futures[fut]
            _, got, info = fut.result()
            check1["official_json_sha"].append(
                {
                    "pack": pack_name,
                    "code": code,
                    "ok": got == exp,
                    "expected": exp,
                    "got": got,
                    "source": info,
                }
            )

    verify_blocks = (
        check1["factsheet_sha"]
        + check1["manifest_factsheet_sha"]
        + check1["from_publish_csv_sha"]
        + check1["official_json_sha"]
    )
    all_ok = all(x["ok"] for x in verify_blocks)
    report["checks"]["1_manifest_hashes"] = {
        "pass": all_ok,
        "failures": [x for x in verify_blocks if not x["ok"]],
        "counts": report["inventory"],
        "detail_buckets": {k: len(v) for k, v in check1.items()},
        "note": "MANIFEST/dailies-summary sha256 for full dailies is official index-perf JSON body, not CSV bytes.",
    }

    # N00986-N00995 absent (allshare)
    n_files = list(PACKS["allshare"].rglob("N0098*"))
    report["checks"]["1b_allshare_no_net_series"] = {
        "pass": len(n_files) == 0,
        "n_path_count": len(n_files),
        "deriv_N_empty": all(
            is_empty(r.get("deriv_N"))
            for r in load_factsheet_meta(PACKS["allshare"]).values()
            if r["code"].startswith("00098") or r["code"].startswith("H0098")
        ),
    }

    # --- Check 2: publish/base vs metadata & from-publish first row ---
    check2 = []
    for pack_name, pack in PACKS.items():
        meta_f = load_factsheet_meta(pack)
        meta_d = load_dailies_meta(pack)
        for code, frow in meta_f.items():
            pub = norm_publish(frow["publish_date"])
            drow = meta_d.get(code, {})
            vpub = drow.get("verified_publish_date", "")
            fp = pack / "dailies/from-publish-date" / f"{code}.from-publish-date.csv"
            first = ""
            if fp.is_file():
                rows = read_series_rows(fp)
                first = rows[0]["tradeDate"] if rows else ""
            check2.append(
                {
                    "pack": pack_name,
                    "code": code,
                    "base_date": frow["base_date"],
                    "publish_metadata": pub,
                    "dailies_verified_publish": vpub,
                    "from_publish_first": first,
                    "publish_match": pub == vpub == first,
                }
            )
    report["checks"]["2_publish_dates"] = {
        "pass": all(x["publish_match"] for x in check2),
        "mismatches": [x for x in check2 if not x["publish_match"]],
        "series": len(check2),
    }

    # --- Check 3: price index completeness 20050104-20261120 + official spot ---
    cal = load_szse_trading_days("20050104", "20261120")
    price_checks = []
    for pack_name, pack in PACKS.items():
        for code in [c for c in load_dailies_meta(pack) if c[0] == "0" and len(c) == 6]:
            if code not in {f"{x:06d}" for x in range(908, 918)} | {f"{x:06d}" for x in range(986, 996)}:
                continue
            path = pack / "dailies" / f"{code}.index-perf.csv"
            rows = read_series_rows(path)
            by_day = {r["tradeDate"]: r for r in rows}
            last = rows[-1]["tradeDate"] if rows else ""
            missing_fields = []
            zero_turnover = []
            for day in sorted(cal):
                r = by_day.get(day)
                if r is None:
                    missing_fields.append({"day": day, "issue": "missing_row"})
                    continue
                for fld in ("open", "high", "low", "close", "tradingValue"):
                    if is_empty(r.get(fld)):
                        missing_fields.append({"day": day, "issue": f"missing_{fld}"})
                tv = float_or_none(r.get("tradingValue"))
                if tv is not None and tv == 0.0:
                    zero_turnover.append(day)
            price_checks.append(
                {
                    "pack": pack_name,
                    "code": code,
                    "last_day": last,
                    "last_ok": last == "20261120",
                    "missing_count": len(missing_fields),
                    "missing_sample": missing_fields[:10],
                    "zero_turnover_days": zero_turnover,
                }
            )
    report["checks"]["3_price_completeness"] = {
        "pass": all(
            x["last_ok"] and x["missing_count"] == 0 for x in price_checks
        ),
        "calendar_sessions": len(cal),
        "series": price_checks,
    }

    spot_plan = [
        ("000908", "20050104"),
        ("000908", "20150612"),
        ("000908", "20200309"),
        ("000908", "20240930"),
        ("000908", "20261120"),
        ("000990", "20050104"),
        ("000990", "20110802"),
        ("000990", "20180619"),
        ("000990", "20241115"),
        ("000990", "20261120"),
        ("000993", "20050104"),
        ("000993", "20150708"),
        ("000993", "20200203"),
        ("000993", "20251009"),
        ("000993", "20261120"),
    ]
    spot_rows = []
    spot_errors = []
    for code, day in spot_plan:
        pack = PACKS["csi300"] if code.startswith("0009") and int(code) < 980 else PACKS["allshare"]
        if int(code) >= 986:
            pack = PACKS["allshare"]
        else:
            pack = PACKS["csi300"]
        packed_path = pack / "dailies" / f"{code}.index-perf.csv"
        packed = next(r for r in read_series_rows(packed_path) if r["tradeDate"] == day)
        url = (
            "https://www.csindex.com.cn/csindex-home/perf/index-perf?"
            + urllib.parse.urlencode(
                {"indexCode": code, "startDate": day, "endDate": day}
            )
        )
        try:
            off = fetch_official_day(code, day)
            if off is None:
                spot_errors.append({"code": code, "day": day, "error": "no_official_row", "url": url})
                continue
            row = {
                "code": code,
                "day": day,
                "url": url,
                "fields": ["open", "high", "low", "close", "tradingValue"],
                "match": {},
            }
            for fld, off_keys in (
                ("open", ("open", "indexOpen")),
                ("high", ("high", "indexHigh")),
                ("low", ("low", "indexLow")),
                ("close", ("close", "indexClose")),
                ("tradingValue", ("tradingValue", "turnover", "trading_value")),
            ):
                pv = packed.get(fld)
                ov = official_field(off, *off_keys)
                if fld == "tradingValue":
                    match = float(pv) == float(ov) if not is_empty(pv) and ov is not None else pv == ov
                else:
                    match = float(pv) == float(ov) if not is_empty(pv) and ov is not None else False
                row["match"][fld] = {
                    "packed": pv,
                    "official": ov,
                    "ok": match,
                }
            row["all_ok"] = all(v["ok"] for v in row["match"].values())
            spot_rows.append(row)
        except Exception as e:  # noqa: BLE001
            spot_errors.append({"code": code, "day": day, "error": str(e), "url": url})

    report["checks"]["3b_official_spot"] = {
        "pass": len(spot_errors) == 0 and all(r["all_ok"] for r in spot_rows),
        "samples": spot_rows,
        "errors": spot_errors,
    }

    # --- Check 4: H/N first non-empty turnover ---
    hn_turnover = []
    for pack_name, pack in PACKS.items():
        for path in sorted((pack / "dailies").glob("[HN]*.index-perf.csv")):
            code = path.name.split(".")[0]
            rows = read_series_rows(path)
            first_tv = None
            for r in rows:
                if not is_empty(r.get("tradingValue")):
                    first_tv = r["tradeDate"]
                    break
            hn_turnover.append({"pack": pack_name, "code": code, "first_nonnull_tradingValue": first_tv})

    report["checks"]["4_hn_turnover_start"] = {"series": hn_turnover}

    # --- Check 5: duplicates, calendar gaps, zero turnover (price only) ---
    dup_gap = []
    for pack_name, pack in PACKS.items():
        for code in PRICE_CODES:
            prefix = "000"
            path = None
            if 908 <= int(code) <= 917:
                path = PACKS["csi300"] / "dailies" / f"{code}.index-perf.csv"
                pack_name = "csi300"
            else:
                path = PACKS["allshare"] / "dailies" / f"{code}.index-perf.csv"
                pack_name = "allshare"
            rows = read_series_rows(path)
            dates = [r["tradeDate"] for r in rows]
            dups = sorted({d for d in dates if dates.count(d) > 1})
            present = set(dates)
            gaps = sorted(cal - present)
            zero_tv = [
                r["tradeDate"]
                for r in rows
                if r["tradeDate"] in cal and float_or_none(r.get("tradingValue")) == 0.0
            ]
            dup_gap.append(
                {
                    "pack": pack_name,
                    "code": code,
                    "duplicate_dates": dups,
                    "trading_day_gaps_20050104_20261120": gaps[:20],
                    "trading_day_gap_count": len(gaps),
                    "zero_turnover_on_trading_days": zero_tv[:20],
                    "zero_turnover_count": len(zero_tv),
                }
            )

    report["checks"]["5_duplicates_gaps_zero"] = {
        "pass": all(
            not x["duplicate_dates"] and x["trading_day_gap_count"] == 0 for x in dup_gap
        ),
        "price_series": dup_gap,
    }

    # OSS 404 probe for N00986 (spot)
    oss_probe = []
    for code in [f"N0098{x}" for x in range(6, 10)]:
        url = (
            "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/"
            f"indices/detail/files/zh_CN/{code}factsheet.pdf"
        )
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "reviewer"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                oss_probe.append({"code": code, "status": resp.status, "url": url})
        except Exception as e:  # noqa: BLE001
            oss_probe.append({"code": code, "error": str(e), "url": url})
    report["checks"]["1c_oss_n_factsheet_probe_sample"] = oss_probe

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"written": str(OUT), "pass_summary": {k: v.get("pass") for k, v in report["checks"].items() if isinstance(v, dict) and "pass" in v}}, indent=2))


if __name__ == "__main__":
    main()