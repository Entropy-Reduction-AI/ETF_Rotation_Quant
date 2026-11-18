# D37 long-history search — 2026-11-18

Research + file delivery only. No database ingest, no `cursor/d37-r6`, no git write, no `results/v5/LOCK`, no overwrite of existing files under `/workspace/incoming/grok-d37-index-20261116/`. Official free-account lengthening and SPICE were not retried (path already closed). No S&P account was created or logged into from this run.

Times below are **Asia/Taipei**. Derived `date,close` (and OHLC) CSVs were written 2026-11-18 00:51:39. New files live in:

- `/workspace/incoming-prep/d37-longhist-20261118/` (working copy)
- `/workspace/incoming/grok-d37-index-20261116/d37-longhist-20261118/` (same content, new distinctive names only)

SHA256 of every new file: `d37-longhist-20261118/SHA256SUMS.txt`.

## Source that worked

**Financial Times historical-prices AJAX**, public xids taken from the free tearsheet HTML (the browser historical table itself is behind an FT subscription barrier; the AJAX used here returned daily tables without a login).

- Endpoint: `POST https://markets.ft.com/data/equities/ajax/get-historical-prices`
- Body: `startDate=YYYY/MM/DD&endDate=YYYY/MM/DD&symbol=<xid>`
- Date format that worked: `YYYY/MM/DD` with **xid**, not the ticker string (ticker-as-symbol returned empty `html`).

| Ticker | FT symbol | xid | Tearsheet |
|---|---|---|---|
| SPAHLVCP | SPAHLVCP:IOM | 595451513 | https://markets.ft.com/data/indices/tearsheet/historical?s=SPAHLVCP%3AIOM |
| SPGOGUP | SPGOGUP:REU | 82188483 | https://markets.ft.com/data/indices/tearsheet/historical?s=SPGOGUP%3AREU |
| SP5NENRS / NTR | NTRGSPE:REU | 19793327 | https://markets.ft.com/data/indices/tearsheet/historical?s=NTRGSPE%3AREU |
| SP5CSSUP | SP5CSSUP:IOM | 772262264 | https://markets.ft.com/data/indices/tearsheet/historical?s=SP5CSSUP%3AIOM |
| IXY | IXY:PSE | 591542 | https://markets.ft.com/data/indices/tearsheet/historical?s=IXY%3APSE |
| SPNCSCUP | SPNCSCUP:IOM | 596013092 | https://markets.ft.com/data/indices/tearsheet/historical?s=SPNCSCUP%3AIOM |

A single request spanning ~28–30 years for IXY and NTRGSPE returned an FT HTTP 500 HTML error page (48,108 bytes). Four-year chunks succeeded. Requests that started *before* FT’s first available date did not unlock earlier history; they only returned the first few available days. Raw vendor JSON for each successful request is under `d37-longhist-20261118/raw/`.

**Xueqiu** public kline (anonymous `xueqiu.com` cookies, 2026-11-18 00:45:18–00:45:27) returned long dailies for `.SPAHLVCP` and `.IXY` only. Kept as a second source. A 2026-11-17 IXY bar (close 2362.67) was trimmed: official IXY 1y ends 2026-11-16, and 2026-11-17 was still the US cash session at download time.

## Headline vs official ~1y and vs the needed windows

Overlap is always against the existing official free-export 1y `date,close` files already in the drop. `|rel| = abs(src-official)/abs(official)`.

| # | Series | Best new source | Rows | First → last close | Official overlap | Needed window / gap |
|---|---|---|---|---|---|---|
| 1 | SPAHLVCP CNY PR | FT | 2251 | 2017-08-04 1231.02 → 2026-11-17 1290.50 | 243/243; median 0; **max 0.1766% on 2025-11-28 only** (n>0.01% = 1) | Launch 2017-02-20 still missing through 2017-08-03. From 2017-08-04 through first_list+30 is covered. **Flag the one-day disagreement; also 13 extra calendar dates in the official 1y window. Not a drop-in official series.** |
| 2 | SPGOGUP USD PR | FT | 3097 | 2014-12-16 1717.69 → 2026-11-16 2650.65 | 261/261; median 0; max 0.00206% (3 days, all << 0.01%) | **Does not cover** launch 2011-07-08 → first_list 2012-05-02+30. FT would not return anything before 2014-12-16. Long history from 2014-12-16 is usable and agrees with the official 1y. |
| 3 | SP5NENRS USD NTR (`.NTRGSPE`) | FT | 6992 | 1998-12-31 100.00 → 2026-11-16 907.74 | 251/251; median 0; max 0.00157% (2 days, rounding) | Launch 1996-06-28 through 1998-12-30 **not available** on FT (a 1996-06-28–1999-01-02 request returned only 1998-12-31). From 1998-12-31 through first_list 2015-02-17+30 is covered. Levels match official **NTR** (not price-return). First FT point is 100.00. |
| 4 | SP5CSSUP USD PR | FT | 994 | 2022-11-25 3033.79 → 2026-11-16 4745.26 | 251/251 **exact** (median 0, max 0) | Launch gap 2022-11-21–2023-10-22: **227** FT days, 2022-11-25 3033.79 → 2023-10-20 3043.99 (21–22 Oct 2023 were a weekend). Still missing **2022-11-21, 2022-11-22, 2022-11-23**. Other weekday gaps in that window are US holidays (2022-11-24 Thanksgiving, 2022-12-26, 2023-01-02, 2023-01-16, 2023-02-20, 2023-04-07, 2023-05-29, 2023-06-19, 2023-07-04, 2023-09-04). |
| 5 | IXY USD PR | FT | 7022 | 1998-12-16 245.12 → 2026-11-16 2386.14 | 251/251 **exact** | Requested 1998-12-16–2012-12-26 is covered (3529 rows). 132 missing weekdays in that span are standard US holidays (Christmas, New Year, MLK, Presidents, Good Friday, Memorial, Independence, Labor, Thanksgiving, etc.), not missing trading days. |
| 6 | SPNCSCUP USD PR | FT | 1687 | 2020-05-14 2004.75 → 2026-11-16 1457.48 | 257/259; median 0; **max 0.4636% on 2026-09-28** (official 1527.23 vs FT 1520.15). Official dates missing in FT: 2025-12-25, 2026-04-01. n>0.01% = 1 | Official 1y already fills “after 2026-06-26”. FT does **not** start at launch 2018-12-24 (nothing before 2020-05-14). TV 2021 weekday holes 73: FT fills **71**, still missing 2021-01-01 and 2021-02-15. TV 2022 weekday holes 96: FT fills **96/96**. **Flag 2026-09-28; not a drop-in official series.** |

## 1) SPAHLVCP — S&P Access Hong Kong Low Volatility High Dividend Index, CNY Price Return

Needed: official launch 2017-02-20 → first_list 2023-12-08 + 30 trading days. Official 1y: 243 rows, 2025-11-17 1389.31 → 2026-11-17 1290.50, SHA256 `7f0d1baadf69b1cd0335cd3a0df1e3e4029626dc4716001c158648415994e373` (untouched).

**FT** (downloaded 2026-11-18 00:49:06, plus earlier-window probes 00:49:36–00:49:37): 2251 rows, 2017-08-04 1231.02 → 2026-11-17 1290.50 (completed close kept; matches official last). Files:

- `theme-SPAHLVCP-ft-cny-pr-daily-20170804-20261117.csv` — SHA256 `6b1222dfe98fd5bfdb75930da999fbe683124cc72c8f22b497ad40516e19d915`
- `theme-SPAHLVCP-ft-cny-pr-ohlc-20170804-20261117.csv` — SHA256 `79e336cb6d2d2b5c9e0949235b05bc25227572185e3ce942692d970695384292`
- raw: `raw/ft-SPAHLVCP_long_20110131_20261117.json`

Overlap 243/243 official dates present. 242 days exact; **2025-11-28 official 1347.7 vs FT 1350.08 (rel 0.1766%)**. Neighbors 2025-11-25/26/27 and 2025-12-01/02 are exact. Xueqiu has the same 1350.08 on that day, so two secondary sources agree with each other against official.

FT also has **13 dates inside the official 1y window that official does not have**: 2026-01-01, 2026-01-02, 2026-02-16, 2026-02-17, 2026-02-18, 2026-02-19, 2026-02-20, 2026-02-23, 2026-04-06, 2026-05-01, 2026-05-04, 2026-05-05, 2026-06-19 (New Year, Lunar New Year, Easter Monday, Labour Day / Golden Week, and Juneteenth). Those extras were left in the vendor file and should not be treated as official closes.

Earlier FT requests starting 2017-02-20 ended at first date 2017-08-04 only. **2017-02-20 through 2017-08-03 is still missing.** 1543 FT rows fall in 2017-02-20..2024-01-31.

**Xueqiu** `.SPAHLVCP` (00:45:18): 1962 rows, 2018-07-11 1149.73 → 2026-11-17 1290.50. Official overlap 243/243, median 0, same single mismatch 2025-11-28 1350.08. Shorter than FT (starts 2018-07-11). File: `theme-SPAHLVCP-xueqiu-cny-pr-daily-20180711-20261117.csv` SHA256 `2c7169753efd8c50f8a927ff59ece9008ec58850378e45a20c070bb9d145e3f7`; raw `raw/xueqiu-SPAHLVCP-kline-raw.json`. Dates interpreted as UTC+8 midnight (all 1962 stamps are 16:00 UTC). FT vs Xueqiu overlap 1960 days, two diffs > 0.01% (max 0.199% on 2023-08-09).

## 2) SPGOGUP — S&P Global Oil Index, USD Price Return

Needed: launch 2011-07-08 → first_list 2012-05-02 + 30 trading days. Official 1y: 261 rows, 2025-11-17 2004.24 → 2026-11-16 2650.65, SHA256 `1c9df0f7b097bc2c971d14633c5d84de12673287b0ee632804c8a0edf932196d` (untouched). TradingView `SP-SPGOGUP` remains 404; SGES was not used.

**FT**: 3097 rows, 2014-12-16 1717.69 → 2026-11-16 2650.65. Overlap 261/261, median 0, max 0.00206% (2026-03-02 official 2427.97 vs FT 2428.02); two further sub-0.001% rounding diffs. No extra dates in the official window.

- `theme-SPGOGUP-ft-usd-pr-daily-20141216-20261116.csv` — SHA256 `f36ace5b424f8806064ea7486401b57eaa7f5395a2af928fd73a16e1e0f84bed`
- raw: `raw/ft-SPGOGUP_long_20000831_20261116.json` (request started 2000-08-31; first returned date is still 2014-12-16)

**The 2011–2012 needed window is not covered.** Chunks ending just after 2014-12-16 did not produce earlier days. Xueqiu has no `.SPGOGUP` / `SPGOGUP` kline.

## 3) SP5NENRS — S&P 500 Energy (Sector) Net TR, USD (Reuters `.NTRGSPE`)

Needed: launch 1996-06-28 → first_list 2015-02-17 + 30 trading days. Official 1y: 251 rows, 2025-11-17 628.31 → 2026-11-16 907.74, SHA256 `2e18ca92aaf0f27da40070ce9591bf40e333f3be8c87ffd6e52850d16644096e` (untouched). Price-return substitutes (S5ENRS, SP500-10, ^GSPE, etc.) were not used.

**FT `NTRGSPE:REU`**: 6992 rows, 1998-12-31 100.00 → 2026-11-16 907.74. Overlap 251/251, median 0, max 0.00157% (2025-12-11 official 638.76 vs FT 638.77; 2026-10-08 929.37 vs 929.38). Last close matches official NTR exactly. This is the net total return series, not price return.

- `theme-SP5NENRS-ft-NTRGSPE-usd-ntr-daily-19981231-20261116.csv` — SHA256 `784c430ae6b89dfbedeb245b5ccd88595f1ceb74208a3715c50eb49a1006545b`
- raw: 4-year chunk JSON under `raw/ft-NTRGSPE_chunk_*.json`

**1996-06-28 through 1998-12-30 is still missing.** A dedicated 1996-06-28–1999-01-02 request returned only 1998-12-31. 4070 FT rows fall in 1996-06-28..2015-04-01. Xueqiu has no NTRGSPE / SP5NENRS symbol. GitHub code search for `SP5NENRS` was 0 hits; `NTRGSPE` hits were unrelated biology CSVs.

## 4) SP5CSSUP — S&P 500 Consumer Select 15/60 Index, USD Price Return

Needed remaining gap: 2022-11-21 through 2023-10-22 (TV already covers 2023-10-23 → 2026-11-16 with official overlap 251/251 exact). Official 1y: 2025-11-17 4280.43 → 2026-11-16 4745.26.

**FT**: 994 rows, 2022-11-25 3033.79 → 2026-11-16 4745.26. Official overlap 251/251 exact. Gap coverage 227 days: 2022-11-25 3033.79 → 2023-10-20 3043.99.

- `theme-SP5CSSUP-ft-usd-pr-daily-20221125-20261116.csv` — SHA256 `e3761c88aee8b7f70c57784bd75f764d7fc26fd90e9787c3a5588046e5f56f0b`
- raw: `raw/ft-SP5CSSUP_long_20170101_20261116.json`

FT would not return 2022-11-21/22/23 (a 2022-11-21–2022-11-30 request still starts 2022-11-25). Those three launch-week sessions remain the only non-holiday hole. Xueqiu has no `.SP5CSSUP` kline.

## 5) IXY — S&P Consumer Discretionary Select Sector Index, USD Price Return

Needed remaining gap: 1998-12-16 through 2012-12-26 (Manager is already copying pre-2012 from TradingView; this run did not re-scrape TradingView). Official 1y: 2025-11-17 2310.67 → 2026-11-16 2386.14.

**FT**: 7022 rows, 1998-12-16 245.12 → 2026-11-16 2386.14. Official overlap 251/251 exact. The requested early gap is filled (3529 rows); leftover weekday gaps are US holidays.

- `theme-IXY-ft-usd-pr-daily-19981216-20261116.csv` — SHA256 `4d6e20c943c03b52f703ffd68db9e30ac0f6156b875d5f393bbcc5b45660c890`
- raw: `raw/ft-IXY_chunk_*.json`

**Xueqiu** `.IXY` (00:45:27): 5872 rows after trimming the 2026-11-17 in-session bar, 2003-07-01 271.36 → 2026-11-16 2386.14. Official overlap 251/251 exact. Starts later than FT, so it does not help 1998-12-16–2003-06-30. File: `theme-IXY-xueqiu-usd-pr-daily-20030701-20261116.csv` SHA256 `7cf8de6ae8362246ab66e0a325d39e3721e87c1f7c7464fed06a77ef38fe4206`; raw kept untrimmed as `raw/xueqiu-IXY-kline-raw.json` (the raw file still contains the 2026-11-17 bar). Dates interpreted in America/New_York (stamps at 04:00 or 05:00 UTC = midnight ET).

FT vs Xueqiu IXY: 5871 overlapping days, mostly exact, but 4 days > 0.01%, worst **2018-03-26 FT 1041.14 vs Xueqiu 1029.07 (1.16%)**. Prefer FT (longer, exact official 1y overlap). Xueqiu remains a useful 2003–2026 cross-check.

EODData lists IXY history from 1998-11-02 but the long download is a paid product; only a short recent table is free. It was not purchased.

## 6) SPNCSCUP — S&P New China Sectors (A-shares Capped) Index, USD Price Return

Official 1y already covers 2025-11-17 → 2026-11-16 (1457.47), so the “after 2026-06-26” gap is already closed officially. TV: 1784 rows, 2018-12-24 1551.58 → 2026-06-26 1463.21, with 73 weekday holes in 2021 and 96 in 2022. Uncapped / Ex-A-Share / NTR `SPNCSCHN` / HKD were not used.

**FT**: 1687 rows, 2020-05-14 2004.75 → 2026-11-16 1457.48. Official overlap 257/259, median 0.

Material / notable disagreements vs official 1y:

- **2026-09-28 official 1527.23 vs FT 1520.15 (0.4636%)**. FT OHLC that day is 1527.37 / 1527.37 / 1516.19 / 1520.15; the next day 2026-09-29 has the **same open/high/low** and close 1519.90, which *does* match official 1519.90. Looks like a possible FT bar defect. **Do not treat this series as drop-in official.**
- Official dates absent from FT: **2025-12-25** (official 1896.50, also in the existing TV table) and **2026-04-01** (official 1741.67, also in TV).
- Other official-window diffs are small: 2026-08-28 0.0087%, 2026-06-23 0.0086%, 2025-12-26 official 1898.13 vs FT/TV 1898.24 (0.0058%), 2026-09-08 0.0025%, 2026-11-16 official 1457.47 vs FT 1457.48 (0.00069%).
- On 2026-06-05 (TV’s previously noted ~0.0207% official disagreement) FT equals official 1638.70 (TV 1639.04).

2021–2022 TV weekday holes: FT fills 71 of 73 (2021) and 96 of 96 (2022). Still empty on FT and TV: 2021-01-01 and 2021-02-15. **Launch 2018-12-24 through 2020-05-13 is still only on the existing TV table**, not on FT (earlier-window requests still started 2020-05-14).

- `theme-SPNCSCUP-ft-usd-pr-daily-20200514-20261116.csv` — SHA256 `0ada0dd1f2b68ff19dca853984e05ffe1237e8ea472515e9eb6f770e63778d52`
- raw: `raw/ft-SPNCSCUP_long_20181224_20261116.json`

Xueqiu `.SPNCSCUP` / `SPNCSCUP` kline returned empty; symbol search for the ticker string also returned no stocks.

## Negative results and rejected paths

- **Official spdji.com** index pages (all six URLs in the brief): HTTP **403** Akamai from this box at 2026-11-18 00:43:51–00:43:52. Methodology/ticker PDFs were not retried as a lengthening path. No S&P login, no SPICE, no official API/OAuth.
- **Yahoo Finance** quote/chart/download (`query1`/`query2`, `finance.yahoo.com`, `sg.finance.yahoo.com`, with and without `fc.yahoo.com` consent cookie): HTTP **403** “sad panda” bot wall from this box. Public pages *exist* for at least `^SPAHLVCP` and `^IXY` (web search snippets), but history could not be downloaded here. Not pursued via a sign-in.
- **Stooq** `https://stooq.com/q/d/l/?s=...` for IXY, SPAHLVCP, SPGOGUP, SP5CSSUP, SPNCSCUP, SP5NENRS, NTRGSPE: HTTP 200 but a JavaScript “verify your browser” stub (796 bytes), not a CSV.
- **FRED**: HTML search failed (HTTP/2 stream error); `api.stlouisfed.org` series search returned 400 “api_key is not set”. No evidence FRED hosts these six tickers. No FRED key was created.
- **FT research webservices** `historical-series-quotes`: HTTP 400 `MissingAPIKey` (paid/research API, not used).
- **FT** `SP5NENRS` as a symbol (no exchange suffix): generic equities landing page, not this index. The working Energy NTR tearsheet is `NTRGSPE:REU`.
- **GitHub public code search** (cursor-github `search_code`): no ready-made official daily dumps.
  - `SPAHLVCP` / `SP5CSSUP`: ticker maps and a Wind *weekly PE* cache in `Leon-Huang001208/ResearchWorkbench` (wrong series; paid Wind cache; not used).
  - `SPGOGUP`: fund/QDII references (e.g. palmmicro, Jillax `qdii-indices/data.js` — AUM only, no index levels), plus unrelated hits.
  - `SPNCSCUP`: only a Xueqiu ID map in `1dot75cm/xueqiu`.
  - `SP5NENRS`: 0 hits. `NTRGSPE`: unrelated proteomics CSVs.
  - No raw official daily file was downloaded from GitHub.
- **Jillax/Jillax.github.io** `qdii-indices/data.js`: fund-size catalogue only, not index dailies.
- **Xueqiu** search/kline: no usable series for SPGOGUP, SP5CSSUP, SPNCSCUP, SP5NENRS/NTRGSPE. Chinese-name search for 标普全球石油 returned **fund** `F160416` (华安标普全球石油指数); ETF NAV was not used as an index substitute.
- **EODData IXY**: long history is a paid purchase from Nov 02, 1998; not used.
- Excluded near-substitutes were not downloaded: SGES, DJUSRE, New China uncapped / Ex-A-Share, GPCSP007, SPAHLVHP/SPAHLVHT, SPGOGUT, S5ENRS / GSPE / other Energy price-return series, or any ETF as an index substitute.

## Still missing after this run

1. SPAHLVCP: 2017-02-20 through 2017-08-03 (and treat FT/Xueqiu as flagged secondary because of 2025-11-28 and extra holiday-like dates).
2. SPGOGUP: entire needed window 2011-07-08 through ~2012-06 (FT only from 2014-12-16).
3. SP5NENRS / NTRGSPE: 1996-06-28 through 1998-12-30.
4. SP5CSSUP: 2022-11-21, 2022-11-22, 2022-11-23 only.
5. IXY: no remaining trading-day hole in 1998-12-16–2012-12-26 on FT; official/other confirmation of pre-2012 levels is still useful because this is a secondary vendor.
6. SPNCSCUP: 2018-12-24–2020-05-13 still only on the existing TV table; TV 2021-01-01 and 2021-02-15 still empty; FT 2026-09-28 disagrees materially with official and should not be patched in blindly.

No levels were invented. No in-session bar after 2026-11-16 was kept except SPAHLVCP’s completed official close 2026-11-17 1290.50 (FT and Xueqiu both have it).
