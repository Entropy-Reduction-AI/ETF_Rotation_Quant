# D37 remain pass 3 — SPAHLVCP CNY PR Wayback official-page snapshots — 2026-11-18 (Asia/Taipei)

Research + file delivery only. No ingest, no git, no invented or interpolated levels. No HKD tickers (SPAHLVHP / SPAHLVHT), no ETFs, no weekly/quarterly bars, no pre-launch backfill. First Value 2011-01-31 was not used as publish_date.

This pass opened the three official-page Wayback snapshots that previously returned HTTP 429 to curl, in the box browser (`id_` identity captures first). All three official pages loaded. None embeds official daily `indexLevels` or a downloadable official daily series for SPAHLVCP CNY Price Return. The needed window official launch 2017-02-20 through 2017-08-03 is still missing.

Files:

- `/workspace/incoming/grok-d37-index-20261116/d37-remain-20261118-pass3/`
- matching copy `/workspace/incoming-prep/d37-remain-20261118-pass3/`
- this report also at `/workspace/incoming-prep/d37-remain-20261118-pass3-REPORT.md`

## Outcome

| Target | Needed window | Result |
|---|---|---|
| SPAHLVCP CNY Price Return | official launch 2017-02-20 through 2017-08-03 | **Not filled.** All three specified official-page Wayback snapshots loaded in the browser as description/shell pages. No official daily CNY PR `indexLevels` were embedded in the HTML/JS of those snapshots. The widget API that would have supplied them was not archived for indexId `92321367`. No date,close CSV was written. Levels were not invented. |

Return type and currency requested: **CNY Price Return** (SPAHLVCP). Covered 2017-02-20 to 2017-08-03: **no**. Row count / first and last date+close: **n/a** (no series). No later official overlap series was present on these pages either (no 5y/10y daily array starting after 2017-08-03).

## URLs opened (in order)

1. `https://web.archive.org/web/20240503065032id_/https://www.spglobal.com/spdji/en/indices/dividends-factors/sp-access-hong-kong-low-volatility-high-dividend-index/`
   - Browser: loaded. Apparent HTTP **200**. Title: “S&P Access Hong Kong Low Volatility High Dividend Index | S&P Dow Jones Indices”.
   - Identity: Bloomberg Ticker **SPAHLVCP**; header currency **CNY**, “1 Day”. Published value empty (widget not hydrated).
   - HTML ~160–261 KB once complete. `indexLevels` not present. Data widgets (`#data-quick-facts`, characteristics, chart, tickers) were empty placeholders. CNY factsheet link uses `indexId=92321367`; HKD factsheet `indexId=92321370`.
   - `id_` asset requests for `datawidget.js` / `index-detail-data.js` etc. often 503 on relative `/spdji/...` paths (identity capture does not rewrite asset URLs). The same `datawidget.js` was then opened successfully from a nearby identity capture (20240503065141, HTTP 200).
   - Curl of this exact URL from the box still returned **HTTP 429** (620-byte Wayback bot-block body; saved under `raw/`).

2. `https://web.archive.org/web/20250528083613id_/https://www.spglobal.com/spdji/en/indices/dividends-factors/sp-access-hong-kong-low-volatility-high-dividend-index/`
   - Browser: loaded. HTTP **200**. Same official title. HTML ~962 KB (larger site chrome, not a data series).
   - Page root widget attribute: `div#wtqa indexid="92321367"`. Bloomberg Ticker **SPAHLVCP**. Currency **CNY**, published value empty. `indexLevels` not present. Launch Date / Price Return text not in the static HTML (those come from the unhydrated widget).

3. `https://web.archive.org/web/20251113121039id_/https://www.spglobal.com/spdji/en/indices/dividends-factors/sp-access-hong-kong-low-volatility-high-dividend-index/`
   - First navigation in this session: HTTP **503**, title “Internet Archive: Temporarily Offline” (outage page, not a captcha/429). Retry in the same browser: HTTP **200**, official title, HTML ~957 KB.
   - `indexid=92321367` present (6 times). Published-value empty. `indexLevels` not present. Bloomberg ticker string `SPAHLVCP` was not in this later snapshot’s static HTML; the page still identifies the official CNY index via `indexid` and the CNY factsheet.
   - Data tab (desktop Chrome, `#data`): “On this page” lists Quick Facts, Characteristics, Constituents, Sector Breakdown, Country Breakdown, Tickers — all empty. Factsheet download links for HKD and CNY are present (monthly PDFs, not a daily series). Constituents table and Sector Breakdown have headers only.
   - A non-`id_` retry was not required after the `id_` retry succeeded.

No sign-in wall, paywall, or captcha blocked the official pages in the browser. The header “Register / Login” form is the ordinary SPDJI chrome; page content was visible without logging in. No password was used.

Desktop Chrome was used (in addition to Playwright) to inspect the styled Data tab of snapshot 3, because Playwright full-page shots of the `id_` captures were narrow / missing CSS. That is a display difference only; the Data widgets were still empty.

## Why official daily CNY PR levels were not filled

Modern spdji official pages do **not** embed the daily series in the page HTML. The performance Graph/Table widget is filled by JS:

- `/spdji/en/app/js/datawidget.js` (opened from Wayback 20240503065141id_, HTTP 200, ~186 KB)
- `$.getJSON` to `/spdji/en/util/redesign/index-data/get-performance-data-for-datawidget-redesign.dot` with `{indexId, getchildindex:true, returntype, currencycode, currencyChangeFlag}`
- The JSON is expected to contain `indexLevelsHolder` / `indexLevels` (the same family of official dailies used on older us.spindices.com snapshots).
- Export href is `/idsexport/file.xls` (free Graph View export; previously observed on the live site to cap at about one year even when 10 Year is selected).

For this index the CNY Price Return id is **92321367**. Wayback sparkline for the exact API URL with `indexId=92321367` returned: **“The Wayback Machine has not archived that URL.”** A browser GET of the 20240503065032id_ API URL with `indexId=92321367&getchildindex=true&returntype=P-&currencycode=CNY` returned **HTTP 404**. The API path without query string has a few 2020–2024 captures, but the 2024 calendarcaptures are all **HTTP 400** (bare URL, missing indexId) and are not this series.

Therefore the snapshots are official description pages only. A 5y/10y official daily series was not present on the page and was not available as an archived widget response. The needed 2017-02-20 through 2017-08-03 window remains unfilled. Existing official ~1-year CNY PR XLS (2025-11-17 through 2026-11-17) was not touched.

## Files in this packet

Evidence screenshots:

- `evidence/wayback-20240503065032id-overview-playwright.png` — snapshot 1 overview (ticker SPAHLVCP visible; widgets empty)
- `evidence/wayback-20251113121039id-overview-desktop.webp` — snapshot 3 styled overview (description, CNY/HKD factsheets, related indices, ETFs listed but not used)
- `evidence/wayback-20251113121039id-overview-playwright.png` — snapshot 3 full-page playwright shot
- `evidence/wayback-20251113121039id-data-tab-empty-quickfacts.webp` — Data tab, empty Quick Facts / Characteristics
- `evidence/wayback-20251113121039id-data-tab-empty-sector.webp` — Data tab, empty Sector Breakdown

Raw notes (not a daily series):

- `raw/wayback-api-lookup.json` — sparkline / calendarcaptures / attempted API URL results
- `raw/curl-20240503065032id.html.429body` and `.hdr` — curl still HTTP 429 on snapshot 1

No `date,close` CSV was written, because no official daily levels were retrieved.

## What was not done

- No merge, ingest, or git.
- No use of HKD tickers, ETFs, CNBC weekly/quarterly bars, FT, or First Value backfill as the needed window.
- Live official spdji Graph View / 10 Year export was not reused (out of this pass’s scoped Wayback URLs; prior notes already recorded that free export is capped at ~1 year and does not cover 2017).
- Official factsheet PDFs were not downloaded (they are monthly factsheets, not an official daily series, and previously 403’d live).
