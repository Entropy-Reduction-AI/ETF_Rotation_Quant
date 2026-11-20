# D37 remain pass 2 — 2026-11-18 (Asia/Taipei)

Research + file delivery only. No ingest, no git clone, no market-DB write, no overwrite of existing official or FT files under `/workspace/incoming/grok-d37-index-20261116/` (including `d37-longhist-20261118/` and `d37-remain-20261118/`). No invented or interpolated index levels. No paid data, no login bypass, no near-synonym substitutes (no IXT Technology Select Sector for S5INFT; no SPSIBITR / NTR / HKD series; no uncapped / Ex-A-Share / SPNCSCHN for 中国新经济; DJSOEP and SPSIOP were not swapped).

This pass followed the tightened priority: S5INFT, SPSIBI, DJSOEP, SPSIOP, then a second independent daily for 中国新经济 / SPNCSCUP after verifying the official publish date from an official S&P page. The three previously stuck windows (Energy NTR, SPAHLVCP, SP5CSSUP) were notes-only; no new fill.

Official launch / publish dates were read from official S&P Dow Jones Indices Quick Facts screenshots already in this incoming packet (captures of the official `www.spglobal.com/spdji` pages). They were copied into `evidence/` as page evidence. Live official pages from this box this pass returned Akamai **HTTP 403** (title “Error | S&P”). First Value dates were not used as publish dates (rule D36-4).

New files:

- `/workspace/incoming/grok-d37-index-20261116/d37-remain-20261118-pass2/`
- matching copy `/workspace/incoming-prep/d37-remain-20261118-pass2/`
- this report: `/workspace/incoming-prep/d37-remain-20261118-pass2-REPORT.md` and `README-REPORT.md` in both packet folders

Existing official ~1-year exports were left untouched and still match the known SHA256s:

- S5INFT USD PR CSV `f8603abdf608dca7d62c615edeaf4608985c88a9e23f6e8267d08c6294a260bd`
- SPSIBI USD PR CSV `bd38dd5ac4d449e5f1aea1d71ba9e242bc54a6478bce0335476457572622aae0`
- DJSOEP USD PR CSV `21692108deceec9c63b3c315e7163724f8bf2807d80b37b57ea2e25e1b635c4a`
- SPSIOP USD PR CSV `a9f23ea3ac9ade2e69b05bdf27684d304c7dcfbcbbb195ac217b3b41b63c3944`

Times below are **Asia/Taipei**. Core downloads landed 2026-11-18 21:53:20–21:53:25.

## Outcome summary

| Target | Official publish date | Assigned window | Result |
|---|---|---|---|
| S5INFT USD PR | **1996-06-28** (official Quick Facts; First Value 1989-09-11 not used) | 1996-06-28 through 2012-09-24 | **Mostly filled from allowed public FT**, not official long daily. FT `SP500-45:IOM` (xid 603229) has 3864 daily closes 1996-06-28 159.84 → 2012-09-24 502.22. Official 1y overlap **252/252 exact**. **Hole remains: 2001-01-02 through 2001-12-04** (241 weekdays, 0 bars; a dedicated 2001 FT request only returned 2001-12-05–2001-12-31). Official us.spindices.com Wayback pages that likely embed ~10y official dailies (~2004–2014, *not* 2001) returned **HTTP 429**. 2001 levels were not invented. |
| SPSIBI USD PR | **2006-01-27** (official Quick Facts; First Value 1999-12-17 not used) | 2006-01-27 through 2014-05-05 | **Filled from official** us.spindices.com daily `indexLevels` (indexId 2331, PRICE RETURN, code SPSIBI) recovered from Wayback snapshot 20141221042442. 2081 official daily closes, 2006-01-27 1238.8078683824 through 2014-05-05 3362.112364091737. Same snapshot vs existing TV 2014-05-06–2014-12-19: 160/160, `round(official, 2)` matches TV exactly. |
| DJSOEP USD PR | **2006-04-28** (official Quick Facts; First Value 1991-12-31 not used) | 2006-04-28 through 2006-05-04 | **Filled from allowed public FT** `DJSOEP:DJI` (xid 4701290). Five sessions: 2006-04-28 6355.52, 2006-05-01 6457.29, 2006-05-02 6588.88, 2006-05-03 6505.97, 2006-05-04 6438.07. TV seam 2006-05-05 6523.51 exact. Official 1y overlap 251/251 exact. Official long daily for 2006 was not retrieved (no historic us.spindices slug in CDX; live official page 403). |
| SPSIOP USD PR | **2006-06-19** (official Quick Facts; First Value 1999-12-17 not used) | 2006-06-19 through 2006-06-22 | **Filled from allowed public FT** `SPSIOP:IOM` (xid 6655170). Four sessions: 2006-06-19 5070.13, 2006-06-20 5025.75, 2006-06-21 5151.87, 2006-06-22 5187.6. TV seam 2006-06-23 5448.8 exact. Official 1y overlap **252/252 exact**, including 2026-03-09 where TV disagreed by ~3.29%. Official us.spindices.com Wayback (which should hold a 10y official window covering June 2006) returned **HTTP 429**. |
| 中国新经济 / SPNCSCUP USD PR | **2018-12-24** (official Quick Facts on the A-shares Capped page; First Value 2010-12-31 not used). Not assumed from the TV start. | official publish date through 2020-05-13 (second independent daily; TV already covers this window) | **Official publish date verified; second daily not filled.** FT still starts 2020-05-14 2004.75. Xueqiu has no `SPNCSCUP` / `.SPNCSCUP` symbol or kline. Live official page 403. No uncapped / Ex-A-Share / NTR substitute. Levels were not invented. |
| Energy NTR / SPAHLVCP / SP5CSSUP | (unchanged from pass 1) | previously stuck windows | **No new fill.** Notes only; no invented levels. |

## 1) S5INFT USD PR — public FT fill with a 2001 hole

### Official publish date

Official page: https://www.spglobal.com/spdji/en/indices/equity/sp-500-information-technology-sector/

Quick Facts on the official S&P 500 Information Technology page (USD Price Return, screenshot `evidence/official-S5INFT-launch.png`): **Launch Date Jun 28, 1996**; First Value Date Sep 11, 1989 (not used as publish_date). Headline on that capture: 6,187.41 USD Price Return.

### Official long daily (preferred) — not retrieved

Wayback CDX lists many 200-status snapshots of `http://us.spindices.com/indices/equity/sp-500-information-technology-sector` from 2013–2018. The fat 2014–2015 snapshots (same family that embedded official `indexLevels` for SPGOGUP and, this pass, SPSIBI) are the right official target, for example:

- https://web.archive.org/web/20141223050341id_/http://us.spindices.com/indices/equity/sp-500-information-technology-sector (CDX length 67652)
- https://web.archive.org/web/20150127084807id_/http://us.spindices.com/indices/equity/sp-500-information-technology-sector (CDX length 67792)

Fetches of both from this box on 2026-11-18 21:53 and 21:54 were **HTTP 429** (620-byte Wayback block body; saved under `raw/wb_S5INFT_*.429*`). These pages almost certainly embed a ~10-year official daily PRICE RETURN series ending at the snapshot date (≈2004–2014/2015). That would officially cover 2004–2012 of the assigned window, **but would not cover 2001**. A browser retry of those exact `id_` URLs is the best official next step. No official snapshot on this host is early enough for a 10-year window that includes 1996–2001 (us.spindices.com CDX starts in 2013).

### Allowed public source that was delivered

Financial Times historical-prices AJAX (public xid from the free tearsheet; the browser historical table is behind an FT subscription wall). Same endpoint as the 2026-11-18 long-history pass:

- `POST https://markets.ft.com/data/equities/ajax/get-historical-prices`
- Body: `startDate=YYYY/MM/DD&endDate=YYYY/MM/DD&symbol=603229`
- Tearsheet: https://markets.ft.com/data/indices/tearsheet/summary?s=SP500-45%3AIOM (also `/historical?s=SP500-45%3AIOM`)
- On-page identity: title **“S&P 500 Information Tech(Sector), SP500-45:IOM”**, quote bar **Price (USD) 6,187.41**. This is the same official USD price-return sector index (TARGETS lists `SP500-45`; official tickers S5INFT / Reuters `.SPLRCT`). **IXT / Technology Select Sector Index** resolved on FT (`IXT:PSE`, xid 574183) and was **not used**.

Needed-window file (as available; 2001 hole not filled and not invented):

- `theme-S5INFT-ft-SP500-45-usd-pr-daily-19960628-20120924.csv` — 3864 rows, 1996-06-28 159.84 → 2012-09-24 502.22. SHA256 `c95ed3b892ea0c50db70f6ba35e8e5ac7ec1937c60a9f6a463b1c1b144b0f6fa`
- Companion OHLC (same sessions): `theme-S5INFT-ft-SP500-45-usd-pr-ohlc-19960628-20120924.csv` SHA256 `066cd753c1e592700f51374e9e0dccb6310f76ccf38c7580ad9499ca72fea635`. Early years are close-only (open=high=low=close).

**2001 hole (not filled):** FT has 2000-12-29, then nothing until 2001-12-05 386.36, then 2001-12-05–2001-12-31 (18 sessions, last 2001-12-31 352.7). A dedicated request `2001/01/01`–`2001/12/31` returned only those same 18 December days. Weekdays 2001-01-02 through 2001-12-04: **241 missing, 0 present** (this span includes the 2001-09-11–2001-09-14 NYSE closure; those four days would not be expected, but the rest of the year is a real hole). Other weekday gaps in 1996–2000 and 2002–2012 are standard NYSE holidays (New Year, MLK, Presidents, Good Friday, Memorial, Independence including observed days, Labor, Thanksgiving, Christmas, plus 2004-06-11 Reagan funeral and 2007-01-02 Ford mourning).

Official ~1y overlap (existing official CSV 2025-11-17 5654.5 → 2026-11-17 6187.41): **252/252, median |rel| = 0, max = 0, every close exact**.

TV overlap 2012-09-25 through 2016-12-30: 1074/1074, median 0, max |rel| 0.001504% on 2014-09-12 (FT 664.9 vs TV 664.91), 1073/1074 equal at 2 d.p. FT has three extra dates in that later window that are not trading days (2012-10-29 and 2012-10-30, Hurricane Sandy closures; 2012-12-25 Christmas). Those dates are after the assigned window and are not in the delivered needed-window file.

Other 2001 attempts this pass, none delivered: Yahoo `query1` for `^SP500-45` / `^SPLRCT` / `S5INFT` **403** “sad panda”; Stooq CSV JS-check stub; FRED search HTTP/2 failure and no series confirmed; Xueqiu lists `.SP500-45` (“标普500信息科技指数”, live 6187.410 = official 2026-11-17) but `type=before` from 2012-09-25 was empty, and paged history reached 2018-05-10 1229.46 → 2026-11-17 6187.41, **no 2001**. CDX for `www.standardandpoors.com/*information-technology*` and `us.spindices.com/idsexport/*` returned no 200 snapshots here.

## 2) SPSIBI USD PR — official daily fill

### Official publish date

Official page: https://www.spglobal.com/spdji/en/indices/equity/sp-biotechnology-select-industry-index/

Quick Facts (`evidence/official-SPSIBI-launch.png`): **Launch Date Jan 27, 2006**; First Value Date Dec 17, 1999 (not used). Headline 11,369.98 USD Price Return.

### Official source

Official S&P Dow Jones Indices page recovered from Wayback, same pattern as the delivered SPGOGUP fill:

- Live URL as of the snapshot: `http://us.spindices.com/indices/equity/sp-biotechnology-select-industry-index`
- Wayback (raw `id_`): https://web.archive.org/web/20141221042442id_/http://us.spindices.com/indices/equity/sp-biotechnology-select-industry-index
- Fetched 2026-11-18 21:53:25 Asia/Taipei, HTTP 200, 814,619 bytes
- Embedded `indexDetail`: `indexId` 2331, `indexCode` SPSIBI, `indexName` “S&P Biotechnology Select Industry Index”, `indexReturnType` P / `indexReturnTypeDescription` “PRICE RETURN”, `currencyCode` USD, `inceptionDate` 1138338000000 = 2006-01-27 00:00 EST
- Daily series is `indexLevels`. Every element has `indexId` 2331 (PR only). The same HTML also contains **total-return** SPSIBITR; that series was not extracted and is not a substitute.

Needed-window file (publish date through the day before existing TV):

- `theme-SPSIBI-usspindices-wayback-usd-pr-daily-20060127-20140505.csv` — 2081 official daily closes, 2006-01-27 1238.8078683824 → 2014-05-05 3362.112364091737. SHA256 `356b3fb9a3c977b0ad2d4298324d5259b745c864df9dbf74ed458a12adc7a324`
- Weekday gaps in the assigned window: 76, all standard NYSE holidays (Presidents, Good Friday, Memorial, July 4, Labor, Thanksgiving, Christmas, New Year, MLK, etc.). No unexplained hole.

Recommended companion for validation against existing TV (TV starts 2014-05-06 3272.55; official snapshot value that day 3272.5517357062045):

- `theme-SPSIBI-usspindices-wayback-usd-pr-daily-20060127-20141219.csv` — 2241 rows through 2014-12-19 4935.4961218492535. SHA256 `d91dc8dd0910b2a379f585108a31601bb2a88772f15fb95a19b099722f744f04`
- Overlap with existing TV 2014-05-06 through 2014-12-19: **160/160, median |rel| ≈ 0.00006%, max 0.00015% on 2014-05-08, `round(official, 2)` equals TV on all 160 days**.

Untrimmed official 10-year window in the same snapshot (includes official pre-launch back-history; official first-value date is 1999-12-17, which this 10y window does not fully reach). **Not required for the assigned gap; do not use pre-launch bars as the needed window:**

- `theme-SPSIBI-usspindices-wayback-usd-pr-daily-20041220-20141219.csv` — 2519 rows, 2004-12-20 1062.61537542466 → 2014-12-19 4935.4961218492535. SHA256 `a156b3faac74a15675997f3dc726d2f5cbb0b3e586bc30ca503961a0a5daebd6`

Raw:

- `raw/spsibi-usspindices-wayback-20141221042442.html` SHA256 `fe6f62a892f6c661350962e7c528b7f3087fd362abfebae4d60dc2d62d3dc49c`
- `raw/spsibi-usspindices-wayback-20141221042442-indexLevels.json` — metadata plus the full 2519-level PR array. SHA256 `bf773b96b75ffc347b9ff931d8bbf40e84171844b5977baee9751c7e02a4763a`

FT `SPSIBI:IOM` (xid 6655155) is a secondary check only: history starts 2007-02-02 (a 2006-01-27–2009-12-31 request did not unlock January 2006). Overlap vs this official snapshot 1986/1986 official dates present, but **not drop-in**: 3 days > 0.01%, worst 2009-03-26 FT 1267.06 vs official 1294.7078764323 (2.135%); also 2008-12-19 (1.56%) and 2009-03-24 (0.123%). Neighbors of 2009-03-26 agree at 2 d.p. FT also has an extra 2011-09-05 bar (Labor Day) that official does not. Prefer the official Wayback series.

## 3) DJSOEP USD PR — public FT fill of the five launch sessions

### Official publish date

Official page: https://www.spglobal.com/spdji/en/indices/equity/dow-jones-us-select-oil-exploration-production-index/

Quick Facts (`evidence/official-DJSOEP-launch.png`): **Launch Date Apr 28, 2006**; First Value Date Dec 31, 1991 (not used). Official name: Dow Jones U.S. Select Oil Exploration & Production Index. Headline 17,479.27 USD Price Return.

### Official long daily — not retrieved

CDX for `us.spindices.com/indices/equity/dow-jones-us-select-oil-exploration-production-index` was empty. Live official page HTTP 403 from this box. A few later `www.spglobal.com/spdji/...` snapshots exist (2020–2023, ~22 kB HTML) and were not fetched; pages of that size are description shells, not the 2014-style embedded 10y `indexLevels`. No other oil-and-gas index was used.

### Allowed public source that was delivered

FT `DJSOEP:DJI`, xid 4701290, tearsheet https://markets.ft.com/data/indices/tearsheet/summary?s=DJSOEP%3ADJI (title **“DJ USSELOILEQPPR, DJSOEP:DJI”**, quote bar Price (USD) 17,479.27). AJAX on 2026-11-18 21:53:21.

- `theme-DJSOEP-ft-usd-pr-daily-20060428-20060504.csv` — 5 rows. SHA256 `d4236d5699019de1eca1c73b403f123eefe1ddce2e54c8869b2ed0e320813b3f`

| date | close |
|---|---|
| 2006-04-28 | 6355.52 |
| 2006-05-01 | 6457.29 |
| 2006-05-02 | 6588.88 |
| 2006-05-03 | 6505.97 |
| 2006-05-04 | 6438.07 |

Companion including the first existing TV bar (exact match 6523.51): `theme-DJSOEP-ft-usd-pr-daily-20060428-20060505-incl-tv-seam.csv` SHA256 `b06f5b91d86c4f5101c91ca5b13f9c1f2e6e2e1209ea96ca472fadcb50fee506`.

FT also returned 2006-04-27 6314.19 (the session before official launch). That pre-launch bar is **not** in the needed-window file.

Official ~1y overlap 2025-11-17 12083.88 → 2026-11-17 17479.27: **251/251 exact**. Official has one extra date in that window, 2026-04-24 (Friday), that this FT chunk does not; that does not affect the 2006 fill.

## 4) SPSIOP USD PR — public FT fill of the four launch sessions

### Official publish date

Official page: https://www.spglobal.com/spdji/en/indices/equity/sp-oil-gas-exploration-production-select-industry-index/

Quick Facts (`evidence/official-SPSIOP-launch.png`): **Launch Date Jun 19, 2006**; First Value Date Dec 17, 1999 (not used). Official name: S&P Oil & Gas Exploration & Production Select Industry Index. Headline 6,822.63 USD Price Return. This is not DJSOEP.

### Official long daily — not retrieved

Fat 2014–2015 us.spindices.com snapshots exist and should contain official 10y dailies covering June 2006, for example:

- https://web.archive.org/web/20141219223917id_/http://us.spindices.com/indices/equity/sp-oil-gas-exploration-production-select-industry-index
- https://web.archive.org/web/20150120135401id_/http://us.spindices.com/indices/equity/sp-oil-gas-exploration-production-select-industry-index

Fetches from this box were **HTTP 429**. A browser retry of those `id_` URLs is the best official next step.

### Allowed public source that was delivered

FT `SPSIOP:IOM`, xid 6655170, tearsheet https://markets.ft.com/data/indices/tearsheet/summary?s=SPSIOP%3AIOM (title is the official index name; Price (USD) 6,822.63). AJAX on 2026-11-18 21:53:21.

- `theme-SPSIOP-ft-usd-pr-daily-20060619-20060622.csv` — 4 rows. SHA256 `f6e2fc0ef13500a7b627f8047ef78715eba6ca0ca1a32d0d982ec48d1781fc88`

| date | close |
|---|---|
| 2006-06-19 | 5070.13 |
| 2006-06-20 | 5025.75 |
| 2006-06-21 | 5151.87 |
| 2006-06-22 | 5187.6 |

Companion including the first existing TV bar (exact match 5448.8): `theme-SPSIOP-ft-usd-pr-daily-20060619-20060623-incl-tv-seam.csv` SHA256 `3b9aaa9b72cc42239f28b31bc094278dbea1e1217c98effb93fccc73a767dd80`.

Official ~1y overlap 2025-11-17 5056.28 → 2026-11-17 6822.63: **252/252 exact**. This includes **2026-03-09 official 6226.42**, the day TradingView was ~3.29% away (6430.97). FT agrees with official on that date.

## 5) 中国新经济 / SPNCSCUP USD PR — official publish date verified; no second daily

### Official publish date (not taken from TV)

Official page: https://www.spglobal.com/spdji/en/indices/equity/sp-new-china-sectors-a-shares-capped-index/

Official Quick Facts screenshot already in the incoming packet, copied to `evidence/official-SPNCSCUP-quickfacts-launch.png`: page title **“S&P New China Sectors (A-shares Capped) Index”**; **Launch Date Dec 24, 2018**; First Value Date Dec 31, 2010 (not used as publish_date). The headline on that particular screenshot is the page-default **1,470.99 HKD Price Return**; official USD PR is SPNCSCUP after switching currency (already exported as the official ~1y file). The launch date is a property of this official index page, not an inference from `theme-标普中国新经济行业指数-tradingview.csv` (which also happens to start 2018-12-24 1551.58). Live official page this pass: HTTP 403.

Needed second independent daily: **2018-12-24 through 2020-05-13**. Existing TV already covers that window. This pass did not invent any levels and did not use uncapped, Ex-A-Share, or NTR **SPNCSCHN**.

Tried for a second source:

- FT `SPNCSCUP:IOM` xid 596013092 (already used in the long-history pass). A request 2018/12/01–2020/05/20 returned only five sessions, first bar **2020-05-14 2004.75**, then 05-15/18/19/20. No pre-2020-05-14 daily. Raw: `raw/ftajax_SPNCSCUP_2018-12-01_2020-05-20.json`.
- Xueqiu symbol search: `SPNCSCUP` returned `stocks: []`. Direct kline for `.SPNCSCUP` and `SPNCSCUP` returned empty `data`. (Prior long-history pass had the same negative.)
- Official Wayback CDX for the current official URL has 200 snapshots from 2021-03-02 through 2025-12-17 (20–95 kB). Those later official shells were not fetched this pass (Wayback was already 429 on the more valuable 2014 us.spindices pages; these sizes are not the 800 kB embedded-`indexLevels` pattern). A browser look at a 2024–2025 official snapshot remains a possible official lead if it still embeds 5y/10y dailies.

No second independent daily file is delivered.

## 6) Previously stuck windows — no new fill (notes only)

No new official or permitted public *daily* source was found, and no levels were invented.

- **Energy NTR / SP5NENRS / .NTRGSPE, 1996-06-28 through 1998-12-30.** Pass 1 already established: official 1y NTR does not reach 1996–1998; FT xid 19793327 starts 1998-12-31 100.00; 2013 official energy-sector Wayback embeds PRICE RETURN only (no NTR); CNBC ALL is quarterly; YCharts 403; price-return substitutes were not used. This pass did not spend primary time retrying those paths and has no new NTR lead.
- **SPAHLVCP CNY PR, official launch 2017-02-20 through 2017-08-03.** Pass 1: FT starts 2017-08-04 1231.02; CNBC weekly/quarterly bars were misaligned and not used; official spa/spdji Wayback 20240503065032 was HTTP 429 and might still embed official 5y/10y dailies if a snapshot can be retrieved in a browser. Not retried as a primary path here. HKD tickers / ETFs not used.
- **SP5CSSUP USD PR, only 2022-11-21/22/23.** Pass 1: FT starts 2022-11-25 3033.79; CNBC weekly 2022-11-20 close 3033.7884 is Friday, not Mon–Wed; official base value 1000 on 2012-03-16 is not a launch-day close and was not written. No new daily source this pass.

## What was not done

- No merge or update of unmerged PR #312; files are staged in `d37-remain-20261118-pass2/` for Manager / Dev to append.
- No ingest, no git, no `cursor/d37-r6`, no `results/v5/LOCK`.
- No overwrite of first-pass FT/Xueqiu/official 1y exports or of the D38 / D37-remain-pass-1 packets.
- Official S&P “10 Year” export / SPICE were not reused (path already closed).

SHA256SUMS for the new packet (data, raw, and evidence; not this report) are in both the incoming and incoming-prep pass2 folders.

