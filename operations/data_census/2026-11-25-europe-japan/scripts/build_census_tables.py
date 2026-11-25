#!/usr/bin/env python3
"""Date/provenance census tables. Stdlib only. Run: python3 -I scripts/build_census_tables.py

Prints identifiers, dates, row counts, and status codes. Does not print
index levels, prices, NAVs, yields, or returns.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
OUT = ROOT / "tables"
OUT.mkdir(parents=True, exist_ok=True)

# Post-September 2020 ICB supersectors (STOXX methodology guide, Nov 2026, §7.5).
# Names are the vendor-sheet "Index Full Name" after the "STOXX Europe 600 " prefix.
ICB20 = [
    "Automobiles & Parts",
    "Banks",
    "Basic Resources",
    "Chemicals",
    "Construction & Materials",
    "Consumer Products and Services",
    "Energy",
    "Financial Services",
    "Food Beverage and Tobacco",
    "Health Care",
    "Industrial Goods & Services",
    "Insurance",
    "Media",
    "Personal Care Drug and Grocery Stores",
    "Real Estate",
    "Retail",
    "Technology",
    "Telecommunications",
    "Travel & Leisure",
    "Utilities",
]
# §7.8: kept under the pre-September 2020 definitions. Not substitutes for the new names.
LEGACY = [
    "Food & Beverage",
    "Oil & Gas",
    "Personal & Household Goods",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def load_vendor() -> list[dict]:
    path = RAW / "vendor_codes_sheet.csv"
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def europe_indexes(rows: list[dict]) -> list[dict]:
    wanted = {"STOXX Europe 600": "benchmark"}
    for name in ICB20:
        wanted["STOXX Europe 600 " + name] = "icb20_supersector"
    for name in LEGACY:
        wanted["STOXX Europe 600 " + name] = "legacy_supersector_pre_2020_09"
    out = []
    for r in rows:
        name = r["Index Full Name"]
        role = wanted.get(name)
        if role is None or r["Curr"] != "EUR":
            continue
        if r["Type"] not in ("Price", "Net Return", "Gross Return"):
            continue
        out.append(
            {
                "geography": "Europe",
                "role": role,
                "official_name": name,
                "symbol": r["Symbol"],
                "isin": r["ISIN"],
                "currency": r["Curr"],
                "value_type": r["Type"],
                "bloomberg": r["Bloomberg"],
                "reuters": r["Reuters"],
                "launch_date": r["Launch Date"],
                "base_date": r["Base Date"],
                "stated_base_value": r["Base Value"],
                "dissemination_calendar": r["Dissemination Calendar"],
                "weighting_scheme": r["Weighting Scheme"],
                "vendor_super_type_label": r["Super Type"],
                "esma_registered": r["Esma Registered"],
                "index_website": r["Index Website Link"],
                "free_daily_level_file": "未找到",
                "daily_first": "未找到",
                "daily_last": "未找到",
                "missing_sessions": "未核实",
                "volume_or_turnover": "未找到",
                "access": "identifier_sheet_free; index_level_history_licensed",
                "source_url": "https://www.stoxx.com/documents/stoxxnet/Documents/Resources/Data_Vendor_Codes/vendor_codes_sheet.csv",
            }
        )
    out.sort(key=lambda x: (x["role"], x["official_name"], x["value_type"]))
    return out


def _listings(html: str) -> dict[str, list[str]]:
    pat = re.compile(
        r'"value":(\[[^\]]{0,1200}\]),.{0,160}?"fullName":"(listings\.[A-Za-z0-9_.]+)"'
    )
    found: dict[str, list[str]] = {}
    for raw, name in pat.findall(html):
        if any(x in name.lower() for x in ("return", "nav", "perf", "price", "yield")):
            continue
        try:
            val = json.loads(raw)
        except json.JSONDecodeError:
            continue
        found[name] = ["" if v is None else str(v) for v in val]
    return found


def _prop(html: str, label: str) -> str:
    m = re.search(
        r'"@type":"PropertyValue","name":"%s","value":"([^"]*)"' % re.escape(label),
        html,
    )
    return m.group(1) if m else ""


def _objective_index(html: str) -> str:
    # Keep the index phrase only. Drop sentences that are performance commentary.
    hits = re.findall(
        r"STOXX(?:&reg;|®)? Europe 600[^<\"\\]{0,90}\((?:Preisindex|Net Return|Gross Return|Price)\)",
        html,
    )
    cleaned = []
    for h in hits:
        h = h.replace("&amp;", "&").replace("&reg;", "").replace("®", "").replace("\\u0026", "&")
        h = re.sub(r"\s+", " ", h).strip()
        if h not in cleaned:
            cleaned.append(h)
    return " | ".join(cleaned)


def europe_etfs() -> list[dict]:
    products = json.loads((RAW / "ishares-products.json").read_text())
    selected = []
    for o in products.values():
        name = o.get("fundName") or ""
        if "STOXX" in name.upper() and "600" in name:
            selected.append(o)
    rows = []
    for o in sorted(selected, key=lambda x: (x.get("fundName") or "", x.get("isin") or "")):
        url = o.get("productPageUrl") or ""
        m = re.search(r"/produkte/(\d+)/", url)
        pid = m.group(1) if m else ""
        page = RAW / "ishares-pages" / f"{pid}.html"
        html = ""
        if page.exists():
            html = page.read_text(errors="replace").replace("&quot;", '"').replace("&amp;", "&").replace("\\u0026", "&")
        lists = _listings(html) if html else {}
        n = 0
        for key in ("listings.exchange", "listings.ticker", "listings.listingDate"):
            n = max(n, len(lists.get(key, [])))
        exchanges = lists.get("listings.exchange", [])
        tickers = lists.get("listings.ticker", [])
        dates = lists.get("listings.listingDate", [])
        rics = lists.get("listings.ric", [])
        wk = lists.get("listings.wkn", [])
        bb = lists.get("listings.BBEQTICK", [])
        listing_bits = []
        for i in range(n):
            listing_bits.append(
                "|".join(
                    [
                        exchanges[i] if i < len(exchanges) else "",
                        tickers[i] if i < len(tickers) else "",
                        dates[i] if i < len(dates) else "",
                        rics[i] if i < len(rics) else "",
                        wk[i] if i < len(wk) else "",
                        bb[i] if i < len(bb) else "",
                    ]
                )
            )
        inc = o.get("inceptionDate") or {}
        inc_r = inc.get("r") if isinstance(inc, dict) else ""
        rows.append(
            {
                "provider": "iShares / BlackRock",
                "screener_site": "de-ishares-v2 individual",
                "fund_name": o.get("fundName") or "",
                "isin": o.get("isin") or "",
                "screener_ticker": o.get("localExchangeTicker") or "",
                "share_class": o.get("useOfProfits") or "",
                "domicile": o.get("domicile") or "",
                "currency": o.get("seriesBaseCurrency") or "",
                "inception_yyyymmdd": inc_r or "",
                "vergleichsindex": _prop(html, "Vergleichsindex") if html else "未找到",
                "objective_index_phrase": _objective_index(html) if html else "未找到",
                "listings_exchange_ticker_date_ric_wkn_bb": " || ".join(listing_bits) if listing_bits else "未找到",
                "page_has_historical_nav_or_price_chart_label": "yes_not_downloaded" if html and "Historische NAV" in html else "未找到",
                "daily_price_first": "未核实",
                "daily_price_last": "未核实",
                "missing_sessions": "未核实",
                "volume": "未核实",
                "product_url": "https://www.ishares.com" + url,
                "access": "free_product_page",
            }
        )
    return rows


def japan_etfs_nomura() -> list[dict]:
    allow_th = {
        "銘柄コード",
        "銘柄正式名",
        "愛称・略称",
        "対象指標",
        "上場日",
        "上場市場",
        "分配金支払い基準日",
        "税法上の分類",
        "売買単位",
    }
    rows = []
    for path in sorted((RAW / "nomura").glob("*.html")):
        if not path.stem.isdigit() and not re.fullmatch(r"\d+[A-Z]?", path.stem):
            # 1306 and 1615-1633 are numeric stems. Skip next.html.
            if not re.fullmatch(r"\d+", path.stem):
                continue
        html = path.read_text(errors="replace")
        fields = {}
        for a, b in re.findall(r"<th[^>]*>([\s\S]*?)</th>\s*<td[^>]*>([\s\S]*?)</td>", html, re.I):
            a = re.sub(r"<[^>]+>", " ", a)
            b = re.sub(r"<[^>]+>", " ", b)
            a = re.sub(r"\s+", " ", a).strip()
            b = re.sub(r"\s+", " ", b).strip()
            if a in allow_th and a not in fields:
                fields[a] = b
        isin = ""
        m = re.search(r"ISIN\s*</[^>]+>\s*<[^>]+>\s*(JP[0-9A-Z]{10})", html)
        if not m:
            m = re.search(r">\s*(JP[0-9A-Z]{10})\s*<", html)
        if m:
            isin = m.group(1)
        rows.append(
            {
                "provider": "Nomura Asset Management NEXT FUNDS",
                "code": fields.get("銘柄コード", path.stem),
                "official_name": fields.get("銘柄正式名", ""),
                "short_name": fields.get("愛称・略称", ""),
                "benchmark_as_stated": fields.get("対象指標", ""),
                "listing_date_as_stated": fields.get("上場日", ""),
                "exchange_as_stated": fields.get("上場市場", ""),
                "distribution_date_rule": fields.get("分配金支払い基準日", ""),
                "tax_classification": fields.get("税法上の分類", ""),
                "board_lot": fields.get("売買単位", ""),
                "isin": isin,
                "source_url": f"https://nextfunds.jp/en/lineup/{path.stem}/",
                "daily_price_first": "未核实",
                "daily_price_last": "未核实",
                "missing_sessions": "未核实",
                "volume": "未核实",
                "access": "free_product_page",
            }
        )
    return rows


def japan_etfs_jpx() -> list[dict]:
    html = (RAW / "jpx" / "etf-issues.html").read_text(errors="replace")
    rows = []
    for block in re.findall(r"<tr>([\s\S]*?)</tr>", html):
        text = re.sub(r"<[^>]+>", "\n", block)
        lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
        lines = [ln for ln in lines if ln and ln not in {"Indicative NAV"}]
        if len(lines) < 4:
            continue
        blob = " ".join(lines)
        if "TOPIX" not in blob:
            continue
        # First cell is listing date, then benchmark, code, fund name, manager.
        # Fee cells are numeric and are not copied.
        listing = lines[0]
        benchmark = lines[1] if len(lines) > 1 else ""
        code = lines[2] if len(lines) > 2 else ""
        fund = lines[3] if len(lines) > 3 else ""
        manager = ""
        for ln in lines[4:]:
            if re.fullmatch(r"[\d.]+", ln) or ln in {"●", "★", "○"}:
                continue
            manager = ln
            break
        rows.append(
            {
                "exchange_source": "JPX ETF issues list",
                "listing_date_as_stated": listing,
                "benchmark_as_stated": benchmark,
                "code": code,
                "fund_name": fund,
                "manager": manager,
                "source_url": "https://www.jpx.co.jp/english/equities/products/etfs/issues/01.html",
            }
        )
    return rows


def _ymd_ok(s: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s))


def ecb_coverage(path: Path, label: str) -> dict:
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        dates = []
        statuses = Counter()
        keys = Counter()
        titles = Counter()
        freqs = Counter()
        for row in reader:
            key = row.get("KEY") or ""
            keys[key] += 1
            title = row.get("TITLE") or row.get("TITLE_COMPL") or ""
            if title:
                titles[title.split(",")[0][:120]] += 1
            freq = row.get("FREQ") or row.get("TIME_FORMAT") or ""
            if freq:
                freqs[freq] += 1
            d = row.get("TIME_PERIOD") or ""
            if _ymd_ok(d):
                dates.append(d)
            statuses[row.get("OBS_STATUS") or ""] += 1
    dates.sort()
    # Title text only: drop anything after a digit run that could be a level.
    title_text = ""
    if titles:
        title_text = titles.most_common(1)[0][0]
    return {
        "series": label,
        "file": str(path.relative_to(ROOT)),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "n_rows": sum(keys.values()),
        "n_distinct_keys": len(keys),
        "key": keys.most_common(1)[0][0] if len(keys) == 1 else "MULTIPLE",
        "title_prefix": title_text,
        "freq_token": freqs.most_common(1)[0][0] if freqs else "",
        "first_date": dates[0] if dates else "未找到",
        "last_date": dates[-1] if dates else "未找到",
        "n_dated_rows": len(dates),
        "obs_status_counts": dict(statuses),
        "missing_sessions_vs_calendar": "未核实",
    }


def bundesbank_coverage(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    meta = {}
    dated = []
    missing = 0
    present = 0
    for ln in text:
        if ln.startswith("last update,"):
            meta["last_update"] = ln.split(",", 1)[1].strip().strip('"')
        if ln.startswith("unit,"):
            meta["unit"] = ln.split(",", 1)[1].strip().strip('"')
        if not re.match(r"\d{4}-\d{2}-\d{2},", ln):
            continue
        parts = next(csv.reader([ln]))
        d = parts[0]
        val = parts[1] if len(parts) > 1 else ""
        flag = parts[2] if len(parts) > 2 else ""
        if val in ("", "."):
            missing += 1
            if flag and "flag_example" not in meta:
                meta["missing_flag_example"] = flag
        else:
            present += 1
        dated.append(d)
    dated.sort()
    return {
        "series": "Bundesbank daily yield of the current 10 year federal bond",
        "series_id": "BBSSY.D.REN.EUR.A630.000000WT1010.A",
        "file": str(path.relative_to(ROOT)),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "unit": meta.get("unit", ""),
        "provider_last_update": meta.get("last_update", ""),
        "first_date": dated[0] if dated else "未找到",
        "last_date": dated[-1] if dated else "未找到",
        "n_dated_rows": len(dated),
        "n_present": present,
        "n_provider_marked_missing": missing,
        "missing_flag_text": meta.get("missing_flag_example", ""),
        "missing_sessions_vs_calendar": "未核实",
        "source_url": "https://api.statistiken.bundesbank.de/rest/data/BBSSY/D.REN.EUR.A630.000000WT1010.A?format=csv&lang=en",
        "page_label": "Daily yield of the current 10 year federal bond",
    }


def mof_10y(path: Path) -> dict:
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        # File may include a title row before the header.
        raw_lines = f.read().splitlines()
    header_i = None
    for i, ln in enumerate(raw_lines[:5]):
        if ln.startswith("Date,"):
            header_i = i
            break
    if header_i is None:
        raise SystemExit("MOF header not found")
    reader = csv.DictReader(raw_lines[header_i:])
    all_dates = []
    present_dates = []
    missing = 0
    for row in reader:
        d = (row.get("Date") or "").strip()
        if not d:
            continue
        all_dates.append(d)
        cell = (row.get("10Y") or "").strip()
        if cell in ("", "-"):
            missing += 1
        else:
            present_dates.append(d)
    return {
        "series": "MOF JGB interest rate, constant maturity, 10Y column",
        "definition": "semiannual compound yield, constant maturity, from JSDA reference prices at 15:00, released 09:30 next business day",
        "definition_url": "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/qa.htm",
        "file": str(path.relative_to(ROOT)),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "source_url": "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv",
        "first_date_any_column": all_dates[0] if all_dates else "未找到",
        "last_date_any_column": all_dates[-1] if all_dates else "未找到",
        "n_rows": len(all_dates),
        "first_date_10y_populated": present_dates[0] if present_dates else "未找到",
        "last_date_10y_populated": present_dates[-1] if present_dates else "未找到",
        "n_10y_populated": len(present_dates),
        "n_10y_dash_or_blank": missing,
        "missing_sessions_vs_calendar": "未核实",
        "sibling_ja_file_rowcount_note": "Japanese jgbcm_all.csv has the same line count; dates there are era labels and were not used for the count",
    }


def main() -> None:
    vendor_path = RAW / "vendor_codes_sheet.csv"
    indexes = europe_indexes(load_vendor())
    etfs = europe_etfs()
    nomura = japan_etfs_nomura()
    jpx = japan_etfs_jpx()
    rates = {
        "estr": ecb_coverage(RAW / "ecb" / "estr-wt.csv", "ECB €STR volume-weighted trimmed mean"),
        "pre_estr": ecb_coverage(RAW / "ecb" / "preestr-wt.csv", "ECB pre-€STR volume-weighted trimmed mean"),
        "eonia": ecb_coverage(RAW / "ecb" / "eonia-rate.csv", "EONIA rate EON.D.EONIA_TO.RATE"),
        "yc_aaa_10y": ecb_coverage(RAW / "ecb" / "yc-aaa-10y.csv", "ECB yield curve AAA spot 10Y"),
        "yc_all_10y": ecb_coverage(RAW / "ecb" / "yc-all-10y.csv", "ECB yield curve all-bonds spot 10Y"),
        "bund": bundesbank_coverage(RAW / "bbk" / "de10y.csv"),
        "jgb": mof_10y(RAW / "mof" / "jgbcme_all.csv"),
    }
    write_csv(OUT / "europe_indexes.csv", indexes)
    write_csv(OUT / "europe_etfs.csv", etfs)
    write_csv(OUT / "japan_etfs_nomura.csv", nomura)
    write_csv(OUT / "japan_etfs_jpx.csv", jpx)
    # Flat rate table without embedding any level.
    rate_rows = []
    for key, rec in rates.items():
        rate_rows.append({"id": key, **{k: (json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v) for k, v in rec.items()}})
    write_csv(OUT / "rates_coverage.csv", rate_rows)
    names = sorted({r["official_name"] for r in indexes if r["role"] == "icb20_supersector"})
    summary = {
        "built_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vendor_sha256": sha256(vendor_path),
        "vendor_bytes": vendor_path.stat().st_size,
        "n_europe_index_rows": len(indexes),
        "icb20_names_found": names,
        "icb20_missing": [n for n in ("STOXX Europe 600 " + x for x in ICB20) if n not in names],
        "n_europe_etf_shareclasses": len(etfs),
        "n_nomura_pages": len(nomura),
        "n_jpx_topix_rows": len(jpx),
        "rates": rates,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("europe_index_rows", len(indexes))
    print("icb20_missing", summary["icb20_missing"])
    print("europe_etf", len(etfs))
    print("nomura", len(nomura))
    print("jpx_topix_rows", len(jpx))
    for k, rec in rates.items():
        print(
            k,
            rec.get("first_date") or rec.get("first_date_10y_populated"),
            rec.get("last_date") or rec.get("last_date_10y_populated"),
            "rows",
            rec.get("n_dated_rows") or rec.get("n_rows"),
            "keys",
            rec.get("n_distinct_keys", ""),
        )


if __name__ == "__main__":
    main()
