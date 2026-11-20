# D37 remain pass 3 — four still-open windows — 2026-11-18 (Asia/Taipei)

Research + file delivery only. No ingest, no git clone, no market-DB write, no overwrite of existing official or FT files under `/workspace/incoming/grok-d37-index-20261116/` (including `d37-longhist-20261118/`, `d37-remain-20261118/`, and `d37-remain-20261118-pass2/`). No invented or interpolated index levels. No paid data, no login bypass, no near-substitutes (no IXT / Technology Select Sector for S5INFT; no uncapped / Ex-A-Share / NTR SPNCSCHN or HKD for 中国新经济 USD PR; no Energy price-return / S5ENRS / .GSPE / XLE for NTR SP5NENRS; no official base value 1000 and no weekly bars for SP5CSSUP).

This pass worked the four assigned remaining windows. It did **not** spend time re-fetching the three SPAHLVCP official spdji Wayback snapshots (20240503065032, 20250528083613, 20251113121039); a parallel computerUse pass already wrote those results into this same `d37-remain-20261118-pass3/` folder. Those SPAHLVCP files and `README-REPORT.md` / `d37-remain-20261118-pass3-REPORT.md` were left untouched. This report is the four-window packet only.

No desktop browser was used. Sources: curl, Wayback CDX, and public APIs. If a promising official URL returned 403/429 and needed an interactive browser, the exact URL was recorded and that path was stopped.

New four-window files (do not confuse with the SPAHLVCP evidence already in the same folder):

- `/workspace/incoming/grok-d37-index-20261116/d37-remain-20261118-pass3/` (CSV + `raw/cnbc-*` + official SPNCSCUP snapshot)
- matching copy `/workspace/incoming-prep/d37-remain-20261118-pass3/`
- this report: `/workspace/incoming-prep/d37-remain-20261118-pass3-four-windows-REPORT.md` (also `README-four-windows-REPORT.md` in both packet folders)
- checksums of this pass’s files only: `SHA256SUMS-four-windows.txt` in both packet folders

Existing official ~1-year exports and the pass-2 FT S5INFT fill were left untouched and still match the known SHA256s:

- S5INFT official USD PR CSV `f8603abdf608dca7d62c615edeaf4608985c88a9e23f6e8267d08c6294a260bd`
- S5INFT FT needed-window CSV `c95ed3b892ea0c50db70f6ba35e8e5ac7ec1937c60a9f6a463b1c1b144b0f6fa`
- SP5NENRS official USD NTR CSV `2e18ca92aaf0f27da40070ce9591bf40e333f3be8c87ffd6e52850d16644096e`

Times below are **Asia/Taipei**. Core CNBC downloads landed 2026-11-18 22:50:20–22:50:44. The official SPNCSCUP Wayback page was retrieved 22:55:10.

## Outcome summary

| Target | Official publish date | Assigned window | Result |
|---|---|---|---|
| S5INFT USD PR | 1996-06-28 | HOLE 2001-01-02 through 2001-12-04 (241 weekdays, 0 FT bars) | **Filled from allowed public CNBC daily API** for Reuters `.SPLRCT` (on-page name “S&P 500 Information Technology Sector”; issue_id **603229**, the same FT xid). 230 daily closes, 2001-01-02 444.9235 → 2001-12-04 366.8393. The other 11 weekdays are NYSE holidays / the 2001-09-11–2001-09-14 closure. Official 1y overlap **252/252 exact**. FT seams on both sides of the hole agree at 2 d.p. 2001 levels were not invented. IXT was not used. |
| 中国新经济 / SPNCSCUP USD PR | 2018-12-24 | second independent daily, 2018-12-24 through 2020-05-13 | **Not filled.** Official 2025-11-14 Wayback page retrieved (1,234,980 bytes) but has **no** embedded `indexLevels`; dailies are a JS widget. USD factsheet indexId is **92366265**. Live widget HTTP **403**. Wayback CDX has no archived widget/export captures for 92366265. CNBC/FT still start 2020-05-14/15. No uncapped / Ex-A-Share / NTR / HKD substitute. |
| Energy NTR / SP5NENRS / .NTRGSPE | 1996-06-28 | 1996-06-28 through 1998-12-30 | **Not filled.** CNBC 1D dated-range for `.NTRGSPE` returned **0 bars** (name confirmed “S&P 500 Energy (Sector) (Net TR)”). Official us.spindices.com energy-sector captures still start 2012 (a 10y window would not reach 1996–1998) and the 2013 page already embedded PRICE RETURN only. Price-return substitutes were not used. |
| SP5CSSUP USD PR | 2022-11-21 | only 2022-11-21, 2022-11-22, 2022-11-23 | **Not filled.** CNBC 1D dated-range first bar is **2022-11-25 3033.7884** (= FT start 3033.79); no bars on the three missing days. MarketWatch CSV 0 bytes; Nasdaq “Symbol not exists.”; Yahoo/Investing 403. Official base value 1000 (base date 2012-03-16) was not written. |

## 1) S5INFT USD PR — 2001 hole filled from public CNBC daily

### Identity

CNBC quote and bars API (no login):

- Bars: `GET https://ts-api.cnbc.com/harmony/app/bars/.SPLRCT/1D/{start}000000/{end}000000/adjusted/GMT.json`
- Quote: `https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols=.SPLRCT&requestMethod=quick&output=json`
- On-page / API identity: name **“S&P 500 Information Technology Sector”**; altName “S&P 500 Information Tech(Sector)”; type INDEX; currency USD; Reuters / feed symbol **`.SPLRCT`**; `issue_id` **603229**. Official Tickers table already records Bloomberg S5INFT / Reuters `.SPLRCT` as USD Price Return (not IXT / Technology Select Sector).
- Previous close on the 2026-11-18 quote: 6,187.41, matching official 2026-11-17 6187.41.

The FT pass-2 fill used the same numeric xid (603229) on `SP500-45:IOM`. That is disclosed. CNBC’s dated 1D endpoint still returns the 2001 sessions that a dedicated FT 2001 request did not. Official 1y overlap independently confirms the series.

`.S5INFT` as a CNBC symbol errored. `.SP500-45` on CNBC opened 2001-01-02 at 1283.27, which is the **broad S&P 500** scale, not this sector index, and was **not used**. IXT was not used.

### Hole file

From the dedicated request 2001-01-02 through 2001-12-04 (fetched 2026-11-18 22:50:20 Asia/Taipei):

- `theme-S5INFT-cnbc-SPLRCT-usd-pr-daily-20010102-20011204.csv` — 230 rows, 2001-01-02 444.9235 → 2001-12-04 366.8393. SHA256 `9463cf2e4c271bb95222ed5634853a6885a439275f78299fdb84892fd3eba75f`
- Companion OHLC (same sessions): `theme-S5INFT-cnbc-SPLRCT-usd-pr-ohlc-20010102-20011204.csv` SHA256 `359c5eee437803e7fa9cb4fd4e6d3d0177c3ba25baf5448b0bb05506e5eec032`. Several early sessions are close-only (open=high=low=close).

Weekdays 2001-01-02 through 2001-12-04: 241 calendar weekdays, **230 present, 11 absent**, all expected NYSE closures and none unexpected:

- 2001-01-15 MLK, 2001-02-19 Presidents, 2001-04-13 Good Friday, 2001-05-28 Memorial, 2001-07-04 Independence, 2001-09-03 Labor, 2001-09-11 through 2001-09-14 NYSE closure, 2001-11-22 Thanksgiving.

No weekend or holiday extras. Levels were not interpolated across those closures.

### Overlap / seams (not invented)

Recommended seam companion (same source, trimmed 2000-12-15 through 2001-12-31):

- `theme-S5INFT-cnbc-SPLRCT-usd-pr-daily-20001215-20011231.csv` — 258 rows, 2000-12-15 531.1132 → 2001-12-31 352.70. SHA256 `5912df837ed2ff9c257fcee23abac01a9a87976879d4b3c9705b898c4c9e46f0`

| Check | Result |
|---|---|
| Official 1y (existing official CSV 2025-11-17 5654.5 → 2026-11-17 6187.41) | **252/252, median \|rel\| = 0, max = 0, every close exact** |
| FT needed-window file, all overlapping dates in the CNBC pulls (1996 start + late-2000 + Dec 2001 + early 2002) | **175/175**; exact at 2 d.p. on 174 days; median \|rel\| ≈ 0.00099%; max 0.00317% on 1996-07-19 (CNBC 148.2747 vs FT 148.27, rounding) |
| FT seam immediately before the hole | 2000-12-29 FT 476.64 vs CNBC 476.6363 |
| FT first bar after the hole | 2001-12-05 FT 386.36 vs CNBC 386.3557; 2001-12-06 386.26 vs 386.2552; 2001-12-07 and 2001-12-31 exact |
| Official publish-date bar | 1996-06-28 FT 159.84 vs CNBC 159.8402 |

The 2001-01-02 close 444.9235 follows 2000-12-29 476.6363; 2001-01-03 is 522.5232 (the 3 January 2001 session). These are sourced closes, not filled gaps.

### Official long daily for 2001 — still not retrieved

Pass 2 already recorded that us.spindices.com CDX starts in 2013, so a ~10y official `indexLevels` snapshot (the 20141223050341 / 20150127084807 pages, previously HTTP 429) would cover ≈2004–2014 and **would not cover 2001**. Those two URLs were not re-fetched. This pass’s CDX of `www.standardandpoors.com`, `www2.standardandpoors.com`, and `www.spindices.com` `*information-technology*` returned no 200 captures. `us.spindices.com/idsexport/*` has later Graph exports, but none in the first 100 hits used indexId **307** (the official widget id for this index), and a 2013–2016 ten-year export would still start after 2001. Yahoo `query1` chart/history remained HTTP 403 “sad panda”. No official 2001 daily file is delivered; the CNBC fill is the public daily source.

Raw: `raw/cnbc-SPLRCT-1D-20010102-20011204.json`, `raw/cnbc-SPLRCT-1D-20001215-20020115.json`, `raw/cnbc-SPLRCT-1D-20251117-20261117.json`, `raw/cnbc-SPLRCT-1D-19960628-19961231.json`, `raw/cnbc-SPLRCT-quote.json`.

## 2) 中国新经济 / SPNCSCUP USD PR — second daily not filled

Needed second independent daily: official publish **2018-12-24** through 2020-05-13. Existing TradingView already covers that window. FT still starts **2020-05-14 2004.75**.

Official page snapshot (allowed official source; live pages are 403 from this box):

- https://web.archive.org/web/20251114075332id_/https://www.spglobal.com/spdji/en/indices/equity/sp-new-china-sectors-a-shares-capped-index/
- Fetched 2026-11-18 22:55:10, HTTP 200, 1,234,980 bytes. Title: “S&P New China Sectors (A-shares Capped) Index | S&P Dow Jones Indices”.
- Default headline on the archived shell is **HKD** (not used). Default widget `indexId` **92366266** (HKD). USD factsheet `indexId` **92366265** (label: “S&P New China Sectors (A-shares Capped) Index (USD) Factsheet”).
- `indexLevels` count in the HTML: **0**. `initialFlagStatus = "oneYearFlag"`. Daily history is loaded by JS from `/spdji/en/util/redesign/index-data/get-performance-data-for-datawidget-redesign.dot`.
- Wayback CDX for that widget URL with `indexId=92366265` or `92366266`, and for exports/factsheets with `indexId=92366265`, returned **no captures**.
- Live official widget, path stopped after HTTP **403** (Akamai, title “Error | S&P”):  
  https://www.spglobal.com/spdji/en/util/redesign/index-data/get-performance-data-for-datawidget-redesign.dot?indexId=92366265&language_id=1

CNBC 1D dated-range `.SPNCSCUP` (name “S&P Nw China Sct(A-shr Cp)Indx(USD)”, xid 596013092, same as FT):

- 2018-12-24 through 2020-05-14: **priceBars: []**
- 2020-05-01 through 2020-06-01: first bar **2020-05-15 2006.63**, then later May sessions; no pre-2020-05-14 daily, and 2020-05-14 itself was not in this pull (FT’s first bar).

Also negative this pass: East Money suggest `TotalCount: 0` for SPNCSCUP / 标普新中国; Sina suggest empty; Xueqiu search 400; MarketWatch download `Content-Length: 0`; us.spindices.com `*new-china*` CDX empty; FRED search timed out (0 bytes). Uncapped / Ex-A-Share / NTR / HKD were not used. No second daily file is delivered.

Raw: `raw/official-SPNCSCUP-spdji-wayback-20251114075332.html` plus `-NOTE.txt`, `raw/official-live-widget-indexId-92366265-403.html`, `raw/cnbc-SPNCSCUP-1D-20181224-20200514.json`, `raw/cnbc-SPNCSCUP-1D-20200501-20200601.json`.

## 3) Energy NTR / SP5NENRS / .NTRGSPE — not filled

Assigned window 1996-06-28 through 1998-12-30 still has no official or permitted public **daily net-total-return** source. FT remains the earliest public daily, starting **1998-12-31 100.00**, with official 1y overlap already 251/251 (not re-ingested).

This pass:

- CNBC `https://ts-api.cnbc.com/harmony/app/bars/.NTRGSPE/1D/19960628000000/19981231000000/adjusted/GMT.json` — HTTP 200, companyName “S&P 500 Energy (Sector) (Net TR)”, symbol 19793327, **priceBars: []**. `.SP5NENRS` as a CNBC symbol errored.
- Wayback CDX for `us.spindices.com/indices/equity/sp-500-energy-sector` still starts **2012-08-23**. A ~10y official window from those pages would start ~2002 and would not cover 1996–1998. Query-string `returntype=*` CDX was empty. The already-fetched 2013 official page embedded PRICE RETURN only (`indexId` 25); it was not re-used as a substitute. Fat 2015 snapshots were not fetched for that reason.
- CDX for `*NTRGSPE*` and `*SP5NENRS*` returned no captures. FRED search timed out. Price-return series (S5ENRS / .GSPE / XLE / MacroMicro S5ENRS) were not used.

No NTR daily file is delivered. Raw: `raw/cnbc-NTRGSPE-1D-19960628-19981231.json`.

## 4) SP5CSSUP USD PR — three days still missing

Still missing only **2022-11-21, 2022-11-22, and 2022-11-23**. FT still starts **2022-11-25 3033.79**. Official base value **1000** on **base date 2012-03-16** is not a launch-day close and was not written. Weekly bars were not written.

This pass:

- CNBC 1D `.SP5CSSUP` 2022-11-21 through 2022-11-26, and 2022-11-01 through 2022-12-31: first bar **2022-11-25 close 3033.7884** (= FT 3033.79). No daily closes on 11-21/22/23 (11-24 was Thanksgiving).
- MarketWatch `downloaddatapartial` CSV: HTTP 200, **0 bytes**.
- Nasdaq historical API: HTTP 200, `rCode` 400, “Symbol not exists.”
- Yahoo `query1` chart for `^SP5CSSUP`: HTTP 403 sad-panda. Investing.com historical page: HTTP 403 (3-byte body).
- East Money / Sina suggest: no index series. Official spdji CDX for this slug remains empty. WSJ historical-prices URL HTTP 404.

No three-day file is delivered. Raw: `raw/cnbc-SP5CSSUP-1D-20221121-20221126.json`, `raw/cnbc-SP5CSSUP-1D-20221101-20221231.json`, `raw/nasdaq-SP5CSSUP-historical-20221121-20221125.json`.

## Other paths still closed or unusable

Re-encountered and still not drop-in official long dailies: live official spdji / widget Akamai 403; Yahoo query/chart 403 “sad panda”; Stooq not retried as a primary path (prior JS browser-check stub); FRED HTML timed out (HTTP/2 internal error or 50s timeout, 0 bytes); Investing.com 403; MarketWatch empty/zero-byte index downloads; Nasdaq symbol-not-exists for SP5CSSUP; Centralcharts search 403; Xueqiu 400 on this box this pass. Official S&P account / SPICE / paid Marketplace data were not used. No levels were invented.

## What was not done

- No merge or update of unmerged PR #312; four-window files are staged in `d37-remain-20261118-pass3/` for Manager / Dev to append.
- No ingest, no git, no `cursor/d37-r6`, no `results/v5/LOCK`.
- No overwrite of first-pass / pass-2 FT, official 1y, or D38 files.
- No re-fetch of the three SPAHLVCP official Wayback snapshots assigned to the parallel computerUse pass, and no overwrite of that pass’s `README-REPORT.md`, `d37-remain-20261118-pass3-REPORT.md`, evidence screenshots, or raw 429/API notes.

SHA256SUMS for this four-window packet (CSV + this pass’s raw files; not the SPAHLVCP evidence and not this report) are in `SHA256SUMS-four-windows.txt` in both the incoming and incoming-prep pass3 folders.
