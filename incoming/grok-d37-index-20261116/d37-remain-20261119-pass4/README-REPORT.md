# D37 remain pass 4 — SPNCSCUP second daily — 2026-11-19 (Asia/Taipei)

Research + file delivery only. No ingest, no git, no PR, no market-DB write. Existing official ~1y and FT files under `/workspace/incoming/grok-d37-index-20261116/` (including `d37-longhist-20261118/`, `d37-remain-20261118/`, pass2, and pass3) were left untouched. No invented or interpolated index levels. No paid data, no login bypass, no SPICE. No uncapped / Ex-A-Share / NTR `SPNCSCHN` / HKD substitute for the USD Price Return series.

Target: **S&P New China Sectors (A-shares Capped) Index, USD Price Return**, ticker **SPNCSCUP**, official USD widget `indexId` **92366265**. Official publish date **2018-12-24** (already read from official Quick Facts; not inferred from the TradingView start). Needed second independent daily: **2018-12-24 through 2020-05-13 inclusive**. TradingView already covers this window (361 daily closes, 2018-12-24 1551.58 → 2020-05-13 2013.04; seam 2020-05-14 2004.75 matches FT). FT still starts **2020-05-14 2004.75**. CNBC still starts **2020-05-15 2006.63**.

This pass used curl, Wayback CDX, and public quote pages/APIs. No desktop browser was available. If a promising official or allowed-public URL returned 403/429 that a browser might pass, the exact URL is recorded and that branch was stopped.

New files (no date,close CSV — the window was not filled):

- this report: `/workspace/incoming-prep/d37-remain-20261119-pass4-SPNCSCUP-REPORT.md`
- packet: `/workspace/incoming/grok-d37-index-20261116/d37-remain-20261119-pass4/`
- matching copy: `/workspace/incoming-prep/d37-remain-20261119-pass4/`

Times below are **Asia/Taipei**. Core probes landed 2026-11-19 00:07–00:15.

## Outcome

**Not found.** No official or already-allowed public *daily* USD PR close series was retrieved for 2018-12-24 through 2020-05-13. No CSV was written.

## 1) Official pages and widget / export archives

### Official English slug — full CDX, new early snapshot

`https://www.spglobal.com/spdji/en/indices/equity/sp-new-china-sectors-a-shares-capped-index/`

Wayback CDX lists captures starting **2020-12-23** (302). There is **no official-page archive of this slug during 2018-12-24–2020-05-13**. 200-status HTML captures and compressed CDX lengths:

| timestamp | status | CDX length | note |
|---|---|---|---|
| 20210302230954 | 200 | 23090 | earliest 200; fetched this pass |
| 20211208074350 | 200 | 20266 | shell-sized |
| 20211227220338 / 20211230073453 | 200 | ~23700 | |
| 20220628215859 / 20221207092816 / 20230530014635 | 200 | 24816–26557 | |
| 20231123105902 | 403 | 802 | |
| 20251114075332 | 200 | 95088 | already retrieved in pass 3 (~1,234,980 uncompressed bytes, 0 `indexLevels`); not re-fetched |
| 20251217063737 | 200 | 72643 | later modern shell; not fetched |

The earliest 200 snapshot was fetched once (curl HTTP **200**, 162,649 bytes):

- https://web.archive.org/web/20210302230954id_/https://www.spglobal.com/spdji/en/indices/equity/sp-new-china-sectors-a-shares-capped-index/

Title: “S&P New China Sectors (A-shares Capped) Index - S&P Dow Jones Indices”. `indexLevels` count: **0**. `initialFlagStatus = "oneYearFlag"`. Default widget `indexId` **92366266** (HKD, not used). USD factsheet `indexId` **92366265**. Daily history is a JS `datawidget.js` call to `/spdji/en/util/redesign/index-data/get-performance-data-for-datawidget-redesign.dot`. Launch Date / ticker string are not in the static HTML. This is the same modern official shell family as the already-retrieved 2025-11-14 page, not an older `us.spindices.com` page that embeds `indexLevels`.

Raw: `raw/official-SPNCSCUP-spdji-wayback-20210302230954.html` plus `.hdr` and `-NOTE.txt`.

Chinese official slug `.../spdji/zh/indices/equity/sp-new-china-sectors-a-shares-capped-index/` CDX starts 2021-12-30 (200, ~25–27 KB shells), then 2024-07-22 (53 KB). No 2018–2020 captures; not fetched (same widget CMS).

### `us.spindices.com` — capped slug absent; uncapped family checked once

Exact CDX for `us.spindices.com/indices/equity/sp-new-china-sectors-a-shares-capped-index` and `.../sp-new-china-sectors-a-shares-capped`: **[]**. Same empty result for `www.spindices.com` with the capped slug, and for `us.spindices.com/*new-china*` / `*china-new*` / `*SPNCSCUP*` wildcards. `www.spdji.com/*new-china*`, `cn.spindices.com/*new-china*`, and thematic/custom spdji slugs: **[]**.

The **uncapped** parent slug does exist historically (`us.spindices.com/indices/equity/sp-new-china-sectors-index`), including a mid-window capture 20200610144527. It was fetched once to see whether the capped USD PR series was linked or embedded on the family page, then not used:

- https://web.archive.org/web/20200610144527id_/https://us.spindices.com/indices/equity/sp-new-china-sectors-index
- HTTP **200**, 163,437 bytes. Title is the uncapped “S&P New China Sectors Index”. `indexLevels`: **0** (already a widget shell). **No** `indexId` 92366265, **no** ticker SPNCSCUP, **no** “A-shares Capped” heading. Other China-family indexIds / SPNCSHP only.

Uncapped / HKD / NTR levels were not written. 2017 fat captures of that uncapped slug predate the 2018-12-24 launch of the capped index and were not fetched.

### Official widget and factsheet / export API

Live official widget was **not** retried (pass 3: HTTP 403 Akamai):

- https://www.spglobal.com/spdji/en/util/redesign/index-data/get-performance-data-for-datawidget-redesign.dot?indexId=92366265&language_id=1

CDX for that endpoint **with** `indexId=92366265` (and idsexport / factsheet URLs with `indexId=92366265`): **[]**.

CDX of the bare widget path `get-performance-data-for-datawidget-redesign.dot` (no query string) has 19 captures, including three HTTP 200 JSON snapshots of ~830–970 bytes. The first of those was fetched once:

- https://web.archive.org/web/20200925003920id_/https://www.spglobal.com/spdji/en/util/redesign/index-data/get-performance-data-for-datawidget-redesign.dot
- HTTP **200**, 831 bytes: `Index [0] was not found!`, `indexLevels: null`. Not a daily series and not this indexId.

Archived `idsenhancedfactsheet/file.pdf` captures are likewise the bare PDF path (378–602 bytes), with no `indexId=92366265` in the CDX originals. Factsheet links on the 2021-03-02 official page use `calcFrequency=M` (monthly) and were not treated as a daily source.

`www.spglobal.com/*SPNCSCUP*` CDX: **[]**. `www.spglobal.com/spdji/en/documents/*new-china*`: **[]**.

## 2) Allowed public quote sources — no bars in the needed window

| Source | URL / endpoint | Result |
|---|---|---|
| Yahoo query2 v8 chart | `https://query2.finance.yahoo.com/v8/finance/chart/%5ESPNCSCUP?period1=1545609600&period2=1589414400&interval=1d` | HTTP **403** “sad panda”. Stopped; not looped. |
| Yahoo query1 v8 chart | same path on `query1.finance.yahoo.com` | HTTP **403** sad panda. Stopped. |
| Yahoo v7 download | `https://query1.finance.yahoo.com/v7/finance/download/%5ESPNCSCUP?period1=1545609600&period2=1589414400&interval=1d&events=history&includeAdjustedClose=true` | HTTP **403** sad panda. Stopped. |
| Yahoo Wayback | `finance.yahoo.com/quote/%5ESPNCSCUP/*`, `/history`, `query1/query2.finance.yahoo.com/*SPNCSCUP*` | CDX empty or only 2025-08-09 `warc/revisit` of the quote page. No archived history/chart JSON. |
| Aktiespot (Yahoo-style public page) | `https://aktiespot.dk/aktier/%5ESPNCSCUP` | HTTP **200**. Identity: symbol `^SPNCSCUP`, currency USD, instrumentType INDEX, name “S&P New China Sectors (A-shares…”. Embedded `historicalData.quotes` is **[]**. `fiftyTwoWeekLow/High` equal the latest session (1414.29–1436.08), not a real 52-week series. No 2018–2020 dailies on the page. |
| MarketWatch download | `.../investing/index/spncscup/downloaddatapartial?...startdate=12/24/2018&enddate=05/13/2020` (with and without `countrycode=xx`) | HTTP **200**, **0 bytes**. |
| MarketWatch quote `?countrycode=xx` | `https://www.marketwatch.com/investing/index/spncscup?countrycode=xx` | HTTP **200**, title “Search - MarketWatch” (symbol not resolved). |
| Nasdaq historical / info | `https://api.nasdaq.com/api/quote/SPNCSCUP/historical?assetclass=index&fromdate=2018-12-24&todate=2020-05-13` | HTTP **200**, `rCode` 400, “Symbol not exists.” |
| WSJ historical | `https://www.wsj.com/market-data/quotes/index/XX/SPNCSCUP/historical-prices` | HTTP **404**. |
| Reuters quote | `https://www.reuters.com/markets/quote/.SPNCSCUP` | HTTP **401**, captcha / “enable JS”. Stopped. |
| Google Finance | `https://www.google.com/finance/quote/SPNCSCUP:INDEXSP` | HTTP **403**. Stopped. Identity of `INDEXSP` was not confirmed. |
| Investing.com search | `https://www.investing.com/search/?q=SPNCSCUP` | HTTP **403**, 3-byte body. Stopped. |
| Barchart overview | `https://www.barchart.com/stocks/quotes/SPNCSCUP/overview` | HTTP **202**, **0 bytes**. |
| FRED search | `https://fred.stlouisfed.org/searchresults?st=SPNCSCUP` and `New+China+Sectors` | HTTP/2 internal error, then HTTP/1.1 **timeout, 0 bytes**. No series retrieved. |
| CNBC / FT | not re-used as a new fill | Already known: CNBC `.SPNCSCUP` (xid 596013092) has no bars 2018-12-24–2020-05-14; first bar 2020-05-15 2006.63. FT first bar 2020-05-14 2004.75. |

Yahoo Finance does list `^SPNCSCUP` as this index (USD). Because curl is 403, the history page may still be loadable in the box browser. **Caveat from Aktiespot’s Yahoo-shaped payload:** historical quotes were empty and the “52-week” range was only the latest session, so Yahoo may not actually hold 2018-12-24–2020-05-13 dailies even if the page opens. URLs for a browser pass (do not invent rows if the table is empty or starts in 2020):

- https://finance.yahoo.com/quote/%5ESPNCSCUP/history?period1=1545609600&period2=1589414400&interval=1d&filter=history&frequency=1d
- https://query1.finance.yahoo.com/v8/finance/chart/%5ESPNCSCUP?period1=1545609600&period2=1589414400&interval=1d
- https://query2.finance.yahoo.com/v8/finance/chart/%5ESPNCSCUP?period1=1545609600&period2=1589414400&interval=1d
- https://query1.finance.yahoo.com/v7/finance/download/%5ESPNCSCUP?period1=1545609600&period2=1589414400&interval=1d&events=history&includeAdjustedClose=true

Reuters quote (401/captcha) if a browser session is already available:

- https://www.reuters.com/markets/quote/.SPNCSCUP

Official live widget remains 403 from this box (not retried): see URL in section 1. The early official Wayback pages needed this pass were retrieved as HTTP 200 with curl; they do **not** need the browser.

CSOP 3167 / 159822 ETF NAVs were not used (the CSOP product tracks the **net total return** underlying index, not USD PR). Unexplained dumps and SPICE were not used.

## 3) Stuck windows (no new lead)

No new official or allowed-public *daily* lead appeared this pass for:

- Energy NTR (`SP5NENRS` / Reuters `.NTRGSPE`) 1996-06-28–1998-12-30 — price-return substitutes were not used.
- SPAHLVCP CNY PR (`indexId` 92321367) official launch 2017-02-20–2017-08-03.
- SP5CSSUP 2022-11-21/22/23 — official base value 1000 was not written.

## 4) Box browser pass — Yahoo history (2026-11-19 00:16–00:19 Asia/Taipei)

Opened the exact history URL in the box browser:

https://finance.yahoo.com/quote/%5ESPNCSCUP/history?period1=1545609600&period2=1589414400&interval=1d&filter=history&frequency=1d

The quote/history page never loaded. Yahoo served a mainland-China access wall (page title “Yahoo”) with language switchers English / 繁體中文 / 简体中文. On-screen English text: “As of November 1st, 2021 Yahoo’s suite of services will no longer be accessible from mainland China. Yahoo products and services remain unaffected in all other global locations. We thank you for your support and readership.” Clicking English only switched the on-page language; it did not grant access. Final URL after that click was the same history URL plus `#`.

Identity was not confirmed (no symbol, USD label, or index name). No history table, so no daily bars in 2018-12-24–2020-05-13 could be inspected. No CSV was downloaded. Optional query1 fallbacks were not requested. No login or captcha. Reuters was not opened.

Evidence (only in `raw/`; existing files were not overwritten):

- `raw/yahoo-SPNCSCUP-history-mainland-china-block-initial-20261119.png` SHA256 `88db9cd2a370baa81b3e57e1cf41fce9240ff270899cf195a801c4b468234bed`
- `raw/yahoo-SPNCSCUP-history-mainland-china-block-20261119.png` SHA256 `035145e38c060fa8f96e6f2cf140777701a03d931f2e976933652f3d4dfbf809`
- `raw/yahoo-SPNCSCUP-history-mainland-china-block-20261119.html`
- `raw/yahoo-SPNCSCUP-history-mainland-china-block-20261119-NOTE.txt`

This box egress appears to be treated as mainland China, so Yahoo Finance is not reachable from this browser session. A later pass from a non-CN egress would be needed to check whether `^SPNCSCUP` actually has official-window daily closes. Aktiespot’s earlier Yahoo-shaped payload still suggests Yahoo may not hold this window even if the page opens.

## What was not done

- No date,close CSV for the needed SPNCSCUP window.
- No ingest, no git, no PR update (#312 left alone).
- No overwrite of official ~1y CSV/XLS, FT 2020-05-14+ files, TV files, or pass2/pass3 packets.
- Live official widget 403 was not looped. Yahoo / Google / Investing 403 and Reuters 401 were tried once and stopped.

SHA256 of staged raw evidence is in `SHA256SUMS.txt` in both packet folders.
