# D37 remain pass — 2026-11-18 (Asia/Taipei)

Research + file delivery only. Scope is the four remaining daily windows after the 2026-11-18 FT pull. No ingest, no git, no `cursor/d37-r6`, no merge of PR #312, no overwrite of existing files under `/workspace/incoming/grok-d37-index-20261116/` (including `d37-longhist-20261118/`). 中国新经济 / SPNCSCUP was excluded from this pass (already has a TradingView series; Manager did not assign it here).

Official sources first, then public quote sources if official long daily was unavailable. No invented levels, no near-substitutes (no HKD SPAHLVHP/SPAHLVHT or ETF in place of SPAHLVCP CNY PR; no price-return GSPE/S5ENRS in place of NTR SP5NENRS / .NTRGSPE; no SPGOGUT total-return in place of SPGOGUP; no 1000 as the SP5CSSUP 2022-11-21 close).

New files are under:

- `/workspace/incoming/grok-d37-index-20261116/d37-remain-20261118/`
- matching copy `/workspace/incoming-prep/d37-remain-20261118/`
- this report: `/workspace/incoming-prep/d37-remain-20261118-REPORT.md`

Existing official ~1-year exports were left untouched and still match the known SHA256s:

- SPAHLVCP CNY PR CSV `7f0d1baadf69b1cd0335cd3a0df1e3e4029626dc4716001c158648415994e373`
- SPGOGUP USD PR CSV `1c9df0f7b097bc2c971d14633c5d84de12673287b0ee632804c8a0edf932196d`
- SP5NENRS USD NTR CSV `2e18ca92aaf0f27da40070ce9591bf40e333f3be8c87ffd6e52850d16644096e`

## Outcome summary

| Target | Assigned window | Result |
|---|---|---|
| SPGOGUP USD PR | 2011-07-08 through 2014-12-15 (full gap before FT 2014-12-16) | **Filled from official** us.spindices.com daily `indexLevels` (indexId 5475707) recovered from Wayback Machine snapshots. 895 official daily closes, 2011-07-08 2294.526743770498 through 2014-12-15 1703.5710706872255. Same snapshot also overlaps FT 2014-12-16 through 2015-01-23 (28 days): `round(official, 2)` matches FT exactly. |
| SP5NENRS / NTRGSPE USD NTR | 1996-06-28 through 1998-12-30 | **Not filled.** No official or permitted public *daily net-total-return* series found before FT’s first bar 1998-12-31 100.00. Price-return substitutes were not used. |
| SPAHLVCP CNY PR | official launch 2017-02-20 through 2017-08-03 | **Not filled.** No official or permitted public daily CNY PR series found before FT 2017-08-04 1231.02. HKD tickers and ETFs were not used. |
| SP5CSSUP USD PR | 2022-11-21, 2022-11-22, and 2022-11-23 only | **Not filled.** FT still starts 2022-11-25 3033.79. The value 1000 is the base on 2012-03-16, not a launch-day close, and was not written. |

## 1) SPGOGUP USD PR — official daily fill

### Source

Official S&P Dow Jones Indices page, not a vendor typo-feed:

- Live URL (as of the 2015 snapshot): `http://us.spindices.com/indices/equity/sp-global-oil-index`
- Page title: “S&P Global Oil Index - S&P Dow Jones Indices”
- Embedded attributes: `indexCode` SPGOGUP, `indexId` 5475707, `indexName` “S&P Global Oil Index”, `indexReturnType` P / `indexReturnTypeDescription` “PRICE RETURN”, `currencyCode` USD, `inceptionDate` 2011-07-08 (epoch 1310097600000 = 2011-07-08 00:00 EDT).

The same HTML also contains a **total-return** object for SPGOGUT (`indexId` 5475708, return type T). That series was not extracted and is not a substitute for SPGOGUP.

The daily series is the page’s `indexLevels` array. Every element in the delivered snapshots has `indexId` 5475707 (PR only).

### Snapshots fetched (Asia/Taipei)

| Wayback timestamp (UTC) | Retrieved | Snapshot `indexLevels` range | Role |
|---|---|---|---|
| 201306121… / 20131215… (earlier session files under `/tmp`) | already on disk | ~5y windows ending 2013-06-11 / 2013-12-13 | Cross-check only |
| 20141018194835 | 2026-11-18 11:34:35 | 2004-10-18 → 2014-10-17 (2606 days) | Cross-check; stops ~2 months short of 2014-12-15 |
| 20141223033856 | 2026-11-18 11:37:15 | 2004-12-22 → 2014-12-22 (2605 days) | Confirms the assigned window and the first FT days |
| **20150126100537** | **2026-11-18 11:37:27** | **2005-01-24 → 2015-01-23 (2605 days)** | **Primary extract** — full assigned window plus ~1 month of FT overlap |

Wayback raw (`id_`) URLs:

- https://web.archive.org/web/20150126100537id_/http://us.spindices.com/indices/equity/sp-global-oil-index
- https://web.archive.org/web/20141223033856id_/http://us.spindices.com/indices/equity/sp-global-oil-index

CSV files were written 2026-11-18 11:39:01 Asia/Taipei.

### Consistency

- 2013-06, 2013-12, 2014-10, 2014-12, and 2015-01 official snapshots agree on every overlapping date to floating-point noise or better. 20141018 vs 20141223 vs 20150126: max \|rel\| = 0 (exact) on 2,559 / 2,582 / 2,536 overlapping dates respectively.
- Assigned window in the primary snapshot: **895** daily rows, 2011-07-08 through 2014-12-15. The only weekdays in that calendar span with no official level are **2013-01-01** and **2014-01-01** (New Year’s Day; markets closed). Not treated as holes.

### Overlap vs existing FT series

Compared to first-pass `theme-SPGOGUP-ft-usd-pr-daily-20141216-20261116.csv` (starts 2014-12-16 1717.69), using the official Jan 2015 snapshot through its last date 2015-01-23:

- n = **28 / 28** dates 2014-12-16 through 2015-01-23
- Official values keep the published full precision (e.g. 2014-12-16 = 1717.691423477022)
- raw official vs FT (2 decimal): median \|rel\| ≈ 1.24e-6, max \|rel\| ≈ 2.68e-6 (0.000268%), n days > 0.01% = 0
- `round(official, 2)` vs FT: **28/28 exact** (max \|rel\| = 0)

This is consistent with official daily USD PR, not a disagreeing vendor series. The first-pass FT file can be prepended with the official 2011-07-08 through 2014-12-15 rows (or used from the overlap-extended file below). Official ~1y (2025–2026) does not overlap this early window.

### Delivered files

Primary for the assigned gap:

- `theme-SPGOGUP-usspindices-wayback-usd-pr-daily-20110708-20141215.csv` — 895 rows, date,close, full official precision. SHA256 `43534668fced8de43b7cec9eb250ce5e025eebbd9da2c9ea882e84bf3f0bc990`. First 2011-07-08 2294.526743770498, last 2014-12-15 1703.5710706872255.

Recommended companion for validation against FT:

- `theme-SPGOGUP-usspindices-wayback-usd-pr-daily-20110708-20150123.csv` — 923 rows, same source, through 2015-01-23 1816.2226957702212. SHA256 `63253ed9f63de50f88ec201e10dc27721739075a64236005207da663359cba23`.

Complete official 10-year window embedded in the 2015-01-26 snapshot (includes official pre-launch back-history; official first-value date is 2000-08-31, which this snapshot does not fully reach). Not required for the assigned gap; provided only as the untrimmed official extract from the same page:

- `theme-SPGOGUP-usspindices-wayback-usd-pr-daily-20050124-20150123.csv` — 2605 rows, 2005-01-24 1335.5808015206535 → 2015-01-23 1816.2226957702212. SHA256 `da55af55720f70f73618909c0886f2fb75044b370a38a4e0bb15cefaf6be71d7`.

Raw:

- `raw/spgogup-usspindices-wayback-20150126100537.html` SHA256 `0b92137bbae12626e7316f689d77687a0ded9f21c80d28bdd3c56984b319776b`
- `raw/spgogup-usspindices-wayback-20150126100537-indexLevels.json` — metadata plus the full 2605-level PR array. SHA256 `f7b13fb6343322ffa245c213368427f1631aeb54e4ed7bc9385632b3e9601ba9`
- `raw/spgogup-usspindices-wayback-20141223033856.html` SHA256 `d53ffe62f73f92097d70dddee2706b246d9a29773ea49a420dbbe461c9d8b206`

Hashes are also in `SHA256SUMS.txt`.

## 2) SP5NENRS / NTRGSPE USD NTR — negative

Assigned window 1996-06-28 through 1998-12-30 still has no official or permitted public **daily NTR** source. First-pass FT `.NTRGSPE` remains the earliest public daily, starting **1998-12-31 100.00**.

Tried this pass (plus prior-pass negatives still in force):

- Live official spdji/us.spindices: Akamai 403 from this box. Manager already closed the free official 10 Year export path (~1 year only). Official 1y NTR (251 rows, 2025-11-17 628.31 → 2026-11-16 907.74) does not reach 1996–1998.
- FT historical-prices AJAX for xid 19793327 (NTRGSPE:REU): nothing before 1998-12-31. Long windows and earlier-than-first-date requests did not extend the start.
- CNBC `ts-api` `.NTRGSPE`: 1Y is ~2y daily (recent only). 5Y/10Y are weekly. ALL is quarterly and starts **1998-10-01 close 100.00**, consistent with the FT daily start at 100.00, not a pre-1998-12-31 history. `.SP5NENRS` as a CNBC symbol errors; `.NTRGSPE` is the NTR symbol.
- Wayback official `us.spindices.com/indices/equity/sp-500-energy-sector` snapshot 20130627232056 (fetched 2026-11-18, HTTP 200): page is “S&P 500 Energy Index”. Embedded daily `indexLevels` are **PRICE RETURN** only (`indexCode` “10”, `indexId` 25, returnType P), 2008-06-27 640.802… → 2013-06-27 579.777…. A total-return object (`10TR`) is also present. **No NET TOTAL RETURN / SP5NENRS / NTRGSPE.** The “NTR” strings on the page are “CoNTRibution”. This PR series was not delivered and is not a substitute. Its date range also does not cover 1996–1998.
- CDX query-string variants of the energy-sector URL (hoping for a net-return parameter) returned no 200 snapshots. Further Wayback CDX in this window hit timeouts / “Temporarily Offline”.
- YCharts lists `^SPXNRGSNTR` as “S&P 500 Energy (Sector) Net Total Return”, but `ycharts.com` returned CloudFront 403 from this box and was not retrieved. S&P Global Marketplace / Xpressfeed is paid and was not used.
- East Money / Sina search: no NTRGSPE, no SP5NENRS, no 标普500能源 NTR quote. Yahoo `^GSPE` is price return (and Yahoo history was 403 from this box in the prior pass) — not used.
- Prior-pass walls still apply: Yahoo sad-panda 403, Stooq JS stub, FRED HTML/API unusable here and no evidence FRED hosts this ticker, Investing.com 403, Macrotrends 403, Reuters captcha, FT research webservices MissingAPIKey, no public GitHub daily dump.

## 3) SPAHLVCP CNY PR — negative

Assigned window official launch 2017-02-20 through 2017-08-03 still has no official or permitted public **daily CNY PR** source. First-pass FT remains the earliest public daily, starting **2017-08-04 1231.02**. Xueqiu still starts later (2018-07-11). HKD tickers and ETFs were not used as substitutes.

Tried this pass:

- Live official page `https://www.spglobal.com/spdji/en/indices/dividends-factors/sp-access-hong-kong-low-volatility-high-dividend-index/` is reachable as a description page (no long daily table in the fetched text). Factsheet / education / methodology PDFs on spdji returned Akamai 403. The closed official 10 Year export path was not reused.
- Wayback CDX for that current official URL found only three 200 snapshots, all far after the gap: 20240503065032, 20250528083613, 20251113121039. CDX for older `us.spindices.com` “access” / “low-volatility-high-dividend” patterns was empty or timed out. A fetch of the 2024-05-03 snapshot was **HTTP 429** (Wayback bot block) and was not retrieved. Those later official pages *might* embed a 5y/10y `indexLevels` array that would cover 2017, but that is unconfirmed and no file is delivered.
- CNBC `.SPAHLVCP`: 5Y/10Y weekly first bar 2017-07-30 close 1231.02 equals FT 2017-08-04 1231.02 (week-start label of the first Friday already in FT) — not a daily fill of the gap. ALL is **quarterly**. The first bar is labeled 2017-07-01 close 1212.04, but that close equals FT **2017-09-29** 1212.04 (Q3 2017 quarter-end, *after* the gap). Across later bars, CNBC’s YYYY-MM-01 label is the quarter *start*, and the close is the quarter *end* already in FT (e.g. 2017-10-01 close 1198.13 = FT 2017-12-29). The quarterly open on the 2017-07-01 bar (1227.37) is **not** a dated official daily close and was not written.
- East Money knows the index itself (`166.SPAHLVCP`, 标普港股通低波红利指数), not only an ETF. A live quote was returned (f60 previous 1290.50 matches official 2026-11-17 1290.50; f43 1293.42 is a 2026-11-18 live/intraday figure and was trimmed / not delivered). Historical kline APIs returned `rc` 102 or `klines: []` / `dktotal: 0`. No 2017 daily history.
- Sina suggest was empty. 同花顺 search TLS-failed or returned generic/404 pages, not this index.
- Tracking ETFs (e.g. 513630, listed 2023) are later than the gap and were not used as index substitutes. Official education material describes performance vs Hang Seng but does not publish a 2017 daily close table (and the PDF itself 403’d from this box).
- Prior-pass walls still apply: official spdji 403 for exports, Yahoo 403, Investing 403, FT no earlier than 2017-08-04, Xueqiu 2018-07-11.

## 4) SP5CSSUP USD PR — negative (three days only)

Still missing only **2022-11-21, 2022-11-22, and 2022-11-23**. First-pass FT starts **2022-11-25 3033.79**. Official 1y vs FT remains 251/251 exact in the recent window and does not include these three dates. Other weekday gaps in the FT file are US holidays.

Do **not** treat 1000 as the 2022-11-21 close. That is the official **base value** on **base date 2012-03-16**, not the launch-day close. Some secondary listings (e.g. a 159529 product page stating 指数基点 0, or search-snippet synthesis) are wrong or do not actually quote a 2022-11-21 close. Nothing was invented.

Tried this pass:

- Official page `https://www.spglobal.com/spdji/en/indices/equity/sp-500-consumer-select-15-60-index/` is a description page (linked product 159529 is noted; the ETF was not used as an index substitute). Enhanced factsheet PDF 403 Akamai. Wayback CDX for this URL and for a guessed `us.spindices.com/.../sp-500-consumer-select-15-60-index` URL returned empty (and some CDX calls timed out / were offline).
- CNBC `.SP5CSSUP` 5Y weekly first bar 2022-11-20 close 3033.7884 equals FT 2022-11-25 3033.79 — that is the Friday of the week containing the missing Mon–Wed, not the three missing daily closes. ALL first bar 2022-10-01 close 2841.6094 equals the weekly 2022-12-25 close and must not be treated as October 2022 or as 11-21/22/23.
- East Money search for SP5CSSUP / 标普500消费精选指数 returns only fund 159529 (listed 2024-02), not the index series. No prospectus table with the three official index closes was retrieved. ETF NAV is not a substitute.
- Xueqiu had no SP5CSSUP in the prior pass. Yahoo history 403. Investing 403. FT no bars on 2022-11-21/22/23 (other weekdays in that week are the Thanksgiving holiday 2022-11-24, then FT 2022-11-25).

## Other paths still closed or unusable (all four)

These were re-encountered or remain valid negatives from the earlier remain work and are not drop-in official long dailies: official spdji Akamai 403; Yahoo query/history 403 “sad panda”; Stooq JS browser-check stub; FRED stream/API without a key and no evidence these tickers are hosted; FT research webservices 400 MissingAPIKey; Investing.com 403; MarketWatch index URLs resolving to generic Search pages; WSJ SPGOGUP historical 404; Reuters 401 captcha; Macrotrends 403 Cloudflare; Nasdaq redirect to a generic Market Activity page; CNBC history downsampled as described above (weekly/quarterly, not early enough daily). No official S&P account was created, and SPICE / paid Marketplace data were not used.

## What was not done

- No merge or update of unmerged PR #312; files are staged in `d37-remain-20261118/` for Manager to append.
- No ingest, no git, no `cursor/d37-r6`, no `results/v5/LOCK`.
- No work on SPNCSCUP / 中国新经济, and no re-scrape of TradingView IXY.
- No overwrite of first-pass FT/Xueqiu files or of the original official 1y exports.

SHA256SUMS for the new packet are in both the incoming and incoming-prep remain folders.
