# D37 remain pass 5 — IXY second daily, 1998-12-16 through 2006-04-27 — 2026-11-19 (Asia/Taipei)

Research + file delivery only. No ingest, no git, no market-DB write, no pull-request, and no overwrite of existing official, FT, Xueqiu, or TradingView IXY files under `/workspace/incoming/grok-d37-index-20261116/` (including `d37-longhist-20261118/`, `d37-remain-20261118/`, pass2–pass4, and the TV in-progress files). No invented or interpolated index levels. No paid data, no login bypass, no SPICE. This is not a Quality index and not the S&P 500 Consumer Discretionary (Sector) sibling; S5COND / a broad sector series / XLY were not used as substitutes.

This pass worked only the assigned IXY window. The still-stuck Energy NTR 1996-06-28–1998-12-30, SPAHLVCP 2017-02-20–2017-08-03, SP5CSSUP 2022-11-21/22/23, and SPNCSCUP second daily 2018-12-24–2020-05-13 windows were not rehashed; no new official or allowed-public daily lead for those windows appeared.

No desktop browser was used. Sources: curl, Wayback CDX, and public quote APIs. Official live pages remain Akamai 403 from this box. Official Wayback `id_` page fetches returned HTTP 429; the exact URLs are recorded below for a later browser fetch.

New files:

- `/workspace/incoming/grok-d37-index-20261116/d37-remain-20261119-pass5/`
- matching copy `/workspace/incoming-prep/d37-remain-20261119-pass5/`
- this report also at `/workspace/incoming-prep/d37-remain-20261119-pass5-IXY-REPORT.md`
- checksums: `SHA256SUMS.txt` in both packet folders

Existing IXY files were left untouched and still match the known SHA256s:

- Official ~1y USD PR CSV `c57a3120cd39c674e00985bc0a9f1860fcc72f9a2b378e10a1218a4ec03a6fc6` (2025-11-17 2310.67 → 2026-11-16 2386.14)
- FT daily `4d6e20c943c03b52f703ffd68db9e30ac0f6156b875d5f393bbcc5b45660c890` (1998-12-16 245.12 → 2026-11-16 2386.14)
- Xueqiu daily `7cf8de6ae8362246ab66e0a325d39e3721e87c1f7c7464fed06a77ef38fe4206` (starts 2003-07-01, not used as the completing second source)
- TV in-progress `335c6de6ca73cf8de92ff4c4044f192d745d973c465f8347a3f1c57b44943259` (starts 2006-04-28 340.63; not a delivery file; not recopied)

Times below are **Asia/Taipei**. Core CNBC downloads landed 2026-11-19 15:07–15:11. The seam-inclusive needed+companion request (through 2006-04-28) landed 15:11.

## Outcome summary

| Target | Official publish date | Assigned window | Result |
|---|---|---|---|
| IXY / Consumer Discretionary Select Sector Index, USD Price Return | 1998-12-16 (First Value printed 2003-07-01, recorded as-is, not used as publish_date) | second independent daily, 1998-12-16 through 2006-04-27 (before the existing TV in-progress file) | **Filled from allowed public CNBC daily API** for Reuters `.IXY`. Not official. 1851 daily closes, 1998-12-16 245.12 → 2006-04-27 340.87. Official 1y overlap **251/251 exact**. FT publish-date bar and the 2006-04-28 seam (340.63, also the TV first bar) agree exactly. One interior FT disagreement on 2000-01-21 is disclosed below and was not patched. Official long daily for 1998–2006 was not recovered (live 403; Wayback page fetches 429). |

## 1) Identity

CNBC quote and bars API (no login):

- Bars: `GET https://ts-api.cnbc.com/harmony/app/bars/.IXY/1D/{start}000000/{end}000000/adjusted/GMT.json`
- Quote: `https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols=.IXY&requestMethod=quick&output=json`
- On-page / API identity: name **“Consumer Discretionary Select Sector Index”** (exact official export series name); type INDEX; currency USD; exchange “CME:Index and Options Market”; Reuters / feed symbol **`.IXY`** (the official Price Return ticker); `issue_id` **29686427**.
- The official Tickers table already prints Price Return IXY / `.IXY` (TR IXYTR, NTR IXYNTR were not used).
- `requestDetails.adjusted` on the bar responses is `UNADJUSTED` even though the URL path says `adjusted`.

CNBC `issue_id` **29686427** is **not** the same number as the FT xid **591542** used for `IXY:PSE`. That is disclosed. The series is still identified as the same USD PR IXY index by the official Reuters ticker, the exact name, official 1y **251/251 exact**, and exact FT/TV seams at 1998-12-16 and 2006-04-28. It is not S5COND and not a Quality index.

The CNBC end timestamp at `000000` is exclusive of that calendar day: a request ending `20060428` returns through 2006-04-27; ending `20060429` returns through 2006-04-28. Dates are the America/New_York session date of `tradeTimeinMills` (05:00 UTC in EST, 04:00 UTC in EDT = midnight ET).

## 2) Needed-window file

From the canonical request 1998-12-16 through 2006-04-29 exclusive (fetched 2026-11-19 15:11 Asia/Taipei; raw `raw/cnbc-IXY-1D-19981216-20060429.json`), trimmed to official publish date 1998-12-16 through 2006-04-27 inclusive. No pre-launch backfill. The needed file does not start at First Value 2003-07-01.

- `theme-IXY-cnbc-usd-pr-daily-19981216-20060427.csv` — **1851** rows, 1998-12-16 245.12 → 2006-04-27 340.87.
- Companion OHLC (same sessions): `theme-IXY-cnbc-usd-pr-ohlc-19981216-20060427.csv`.

Recommended seam companion (same source, through the first TV/FT seam date 2006-04-28 340.63):

- `theme-IXY-cnbc-usd-pr-daily-19981216-20060428.csv` — **1852** rows, 1998-12-16 245.12 → 2006-04-28 340.63.
- Companion OHLC: `theme-IXY-cnbc-usd-pr-ohlc-19981216-20060428.csv`.

Weekdays 1998-12-16 through 2006-04-27: 1922 calendar weekdays, **1851 present, 71 absent**. The 71 absences are the same weekdays already missing from FT, except that FT also carries **2001-09-11 243.97**, which is a repeat of the 2001-09-10 close; NYSE was closed 2001-09-11 through 2001-09-14. CNBC has no bars on those four closure days and this packet does not invent one. The other absences are standard US full-day closures (New Year’s, MLK, Presidents, Good Friday, Memorial, Independence or the observed Monday, Labor, Thanksgiving, Christmas, a few Christmas Eve full closures, and 2004-06-11, the Reagan National Day of Mourning). No unexpected mid-week holes. Levels were not interpolated across those closures.

## 3) Overlap / seams (not invented)

| Check | Result |
|---|---|
| Official ~1y (existing official CSV 2025-11-17 2310.67 → 2026-11-16 2386.14) | **251/251, median \|rel\| = 0, max = 0, every close exact**, including both endpoints. Compared from `raw/cnbc-IXY-1D-20251117-20261118.json` after trimming the 2026-11-17 CNBC bar 2366.25, which is after the official file’s last date and was not written into any delivery CSV. A request that ended 20261116 omitted 2026-11-16 because of the exclusive end timestamp; the extended request includes it at 2386.14. |
| FT publish-date bar 1998-12-16 | FT 245.12 vs CNBC 245.12 exact |
| FT last needed-window bar 2006-04-27 | FT 340.87 vs CNBC 340.87 exact |
| FT / TV seam 2006-04-28 | FT 340.63, TV in-progress first bar 340.63, CNBC 340.63 exact. Neighbors 2006-04-26 338.23 and 2006-05-01 339.43 also exact. |
| FT needed-window overlap | **1851/1851** CNBC dates are in FT. Exact at 2 d.p. on **1849** days. One day is a 0.01 rounding difference: **2002-12-20** CNBC 234.49 vs FT 234.5 (0.004%); OHLC otherwise matches (open 231.99, high 235.08, low 231.76). One day is above the 0.01% threshold: **2000-01-21**, disclosed below. Median \|rel\| = 0. |
| First Value date 2003-07-01 (not publish_date) | CNBC 271.36 = FT 271.36 = Xueqiu first bar 271.36 |
| Xueqiu overlap 2003-07-01 through 2006-04-27 | 711/711 dates present. CNBC agrees with FT; both differ from Xueqiu by more than 0.01% on one day already known from the longhist report (2003-09-23 FT/CNBC 288.07 vs Xueqiu 288.96, 0.308%). Xueqiu still does not complete the second source on its own, because it starts at First Value, not publish date. |

### 2000-01-21 (the only material FT disagreement)

This close was **not** patched and was **not** replaced with the FT value.

| Source | 2000-01-20 | 2000-01-21 | 2000-01-24 |
|---|---|---|---|
| CNBC (delivered as-is) | 293.63 (real OHLC range) | open=high=low=close **293.63** (flat, previous close) | open **288.89**, high 291.62, low 277.00, close **278.83** |
| FT daily close / FT OHLC raw HTML | close 293.63 | open 293.63, high 295.49, low 288.26, close **288.89** | open 288.89, high 291.62, low 277.00, close 278.83 |

Neighbors 2000-01-18/19/20 and 2000-01-24/25/26 are exact at 2 d.p. CNBC’s Monday 2000-01-24 **open 288.89** equals the FT Friday close, which is consistent with a stale CNBC close on Friday (carried-forward Thursday close) and a real Monday session that both sources agree on. Rel vs FT on 2000-01-21 is 1.641%. MarketWatch’s IXY download CSV returned 0 bytes, Nasdaq said “Symbol not exists.”, and Yahoo `query1` returned HTTP 403, so no third public close was obtained for that Friday. The rest of the series, including official 1y and both seams, still identifies this as USD PR IXY.

## 4) Official long daily for 1998-12-16–2006-04-27 — not retrieved

Live official product page `https://www.spglobal.com/spdji/en/indices/equity/consumer-discretionary-select-sector-index/` is Akamai HTTP **403** from this box (prior probe kept as `raw/official-live-spdji-ixy-403.hdr`). The official free “10 Year” graph export remains capped at about one year (path already closed).

Wayback CDX for `http://us.spindices.com/indices/equity/consumer-discretionary-select-sector-index` returned **43** HTTP 200 captures, first **20130803161339**, last 20190313180341 (`raw/cdx-us-spindices-consumer-discretionary-select-sector-index.json`). The same path used for the official SPSIBI / SPGOGUP `indexLevels` fills. A ~10-year window on the earliest capture would start about 2003-08 and **would not reach official publish date 1998-12-16**. CDX for the current spdji URL has 9 captures from 20210125111003 (JS-widget era).

Curl fetches of the raw `id_` pages, including a retry, all returned HTTP **429** (“suspected abusive bot traffic”):

- `https://web.archive.org/web/20130803161339id_/http://us.spindices.com/indices/equity/consumer-discretionary-select-sector-index`
- `https://web.archive.org/web/20141216121600id_/http://us.spindices.com/indices/equity/consumer-discretionary-select-sector-index`
- `https://web.archive.org/web/20150116043712id_/http://us.spindices.com/indices/equity/consumer-discretionary-select-sector-index`

Bodies and headers are under `raw/wayback-*.429body`. No official `indexLevels` and no official IXY `indexId` were recovered; an indexId was not guessed, and widget/export CDX was not queried with a fabricated id. Those three Wayback URLs still need the box browser (or a later unblocked curl) if an official long daily is to be attempted. Even if a 2013–2015 snapshot embeds a 10-year series, it is unlikely to cover 1998-12-16.

CDX queries for `www.spindices.com` on the same slug, and for `standardandpoors.com/*consumer-discretionary-select*`, returned empty 200 `[]` result sets.

No official 1998–2006 daily file is delivered. The CNBC fill is the allowed public daily source, not an official series.

## 5) Other public sources tried (no additional delivery)

- MarketWatch `.../investing/index/ixy/downloaddatapartial?...` HTTP 200, `content-length: 0`. Quote URL `/investing/index/ixy` HTTP 302 to search.
- Nasdaq `api.nasdaq.com/api/quote/IXY/historical` and `/.IXY/historical` (`assetclass=index`) HTTP 200, “Symbol not exists.”
- Yahoo Finance `query1` chart for `^IXY` HTTP **403**. The public history page `https://finance.yahoo.com/quote/%5EIXY/history` was not opened (no browser; box egress is treated as CN and has previously shown a mainland access wall). Tried once, not looped.
- EODData long IXY history remains a paid product (already recorded in the 2026-11-18 longhist report) and was not purchased.
- TradingView was not manually recopied.

## 6) Stuck windows

No new official or allowed-public daily lead appeared this pass for Energy NTR 1996-06-28–1998-12-30, SPAHLVCP 2017-02-20–2017-08-03, SP5CSSUP 2022-11-21/22/23, or SPNCSCUP second daily 2018-12-24–2020-05-13. Those windows were not reworked.

Raw evidence: `raw/cnbc-IXY-quote.json`, `raw/cnbc-IXY-1D-19981216-20060429.json` (canonical needed+seam), `raw/cnbc-IXY-1D-19981216-20060428.json` (through 2006-04-27 only), `raw/cnbc-IXY-1D-20251117-20261118.json`, `raw/cnbc-IXY-1D-20251117-20261116.json` (end-exclusive, misses 2026-11-16), `raw/cnbc-IXY-1D-20060420-20060510.json`, CDX JSON, official 403 probe, Wayback 429 bodies, Yahoo 403 body, and `raw/SOURCES-TRIED.txt`.
