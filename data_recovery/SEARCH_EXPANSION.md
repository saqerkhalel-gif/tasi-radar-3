# Expanded free-source search —2026-10-23

The previous search was insufficient to conclude that no suitable free candidate exists. This extension investigates additional candidates and records actual access/schema evidence. No production/phase6 execution, ledger or strategy version is changed.

## Tasilab — promising free research candidate, not approved independent reference

Actual GET https://api.tasilab.com/v1/config/tiers returned200. The current canonical matrix reports sandbox mode, a zero-price public free tier, historical_years:null and120 requests/minute. The currently published homepage describes unlimited historical research during its founding period without a card. An older historical guide instead describes a1-year free limit. The discrepancy is recorded, not resolved by assuming the most generous entitlement. User-specific account limits still require an authenticated test.

Actual GET https://api.tasilab.com/openapi.json returned200 and documents /v1/historical/{symbol}, start/end parameters, X-API-Key or bearer authentication, a count and bars response with symbol/date/open/high/low/close/adj_close/volume/data_version. Actual unauthenticated GET /v1/historical/7200?start=2026-04-22&end=2026-10-22 returned401 MISSING_CREDENTIALS. No signup, identity submission, credential guessing, orders, paid calls or authentication bypass occurred.

The published candidate probe reads public tier/schema metadata and makes a single unauthenticated sample request. It never reads account credentials, environment keys or GitHub secrets, and does not implement authenticated provider access. The initial proposed secret-enabled workflow was rejected by automatic approval review because authorization to send a credential to the external provider was not explicit. That feature was removed entirely; it is not bypassed by this metadata-only probe. Authenticated integration remains a separate approval and account-access step.

The offline sample parser checks identity, dates, counts, duplicate dates and finite OHLCV/volume in deterministic fixtures. It is not evidence that actual provider bars were retrieved. No successful fixture or metadata response is an independent-price release: upstream lineage, historical row matching, capital actions/PIT and permitted usage still need validation. No orders or account signup are performed.

Research use is permitted in the service's terms; raw-provider redistribution is subject to provider conditions. Do not publish a bulk raw feed or assume a commercial/data-resale licence. No notifications or paper-trading accounts are used.

Primary sources:
- https://tasilab.com/
- https://api.tasilab.com/v1/config/tiers
- https://api.tasilab.com/openapi.json
- https://tasilab.com/guides/tasi-historical-data
- https://tasilab.com/about
- https://tasilab.com/terms

## Zenodo60-company research dataset — actual input inspected, not a complete OHLCV feed

Mazin Alahmadi, Saudi Tadawul Post-Earnings Announcement Drift (PEAD) Dataset, v1, July19,2026, DOI10.5281/zenodo.21439356, CC BY4.0. Metadata retrieved from https://zenodo.org/api/records/21439356. The publicly downloadable archive is392,628,268bytes. Standard HTTP Range requests read its ZIP directory and selected README/input workbook; no access wall was bypassed. Each extracted entry's size/CRC and SHA256 were checked and recorded in evidence/zenodo_entries.json. A complete archive MD5 was not verified because only selected entries were downloaded.

Actual Inputs/Copy of Data.xlsx:15,818 event-window rows,60 symbols, dates2019-12-31 through2026-01-04,4 duplicate symbol/date rows. Columns include Open and Close but not High, Low or Volume. This is an event-centered table with engineered metrics, not a continuous daily full OHLCV panel. It cannot certify missing volumes, next-open execution or full254-symbol current coverage. Upstream independence is not established. Machine schema evidence: evidence/zenodo_schema_audit.json. No selection of hindsight event windows as a prospective universe.

## StockAnalysis — public history visible, no programmatic entitlement established

https://stockanalysis.com/quote/tadawul/7200/history/ exposes a dated OHLCV table and separate adjusted close. Its help article https://stockanalysis.com/help/faq/api-access/ explicitly says it offers no programmatic API and its provider licences cover display rather than programmatic redistribution. https://stockanalysis.com/data-sources/ identifies multiple providers but does not unambiguously establish the upstream Saudi OHLCV feed. It is a useful human spot-check candidate, not an assumed authorized automated bulk independent history. No hidden API or bulk crawler was implemented.

## Investing public historical tables

Public historical7200 tables exist at https://www.investing.com/equities/al-moammar-info-historical-data. A visible dated row can still disagree with later completed quotes. The site's https://www.investing.com/about-us/terms-and-conditions requires prior written permission for data use/storage/redistribution. No bulk automated ingestion is added. The existing production fallback is protected and was not modified in this research extension; its data provenance remains a separate review item.

## Saudi Exchange daily detailed report

New official candidate: https://www.saudiexchange.sa/Resources/Reports-v2/DetailedDaily_en.html. A direct bounded HTTP request and the research browser both returned403 in this environment. Search-indexed versions show report dates, but cached results cannot certify the latest session. No proxy, alternate-host, CAPTCHA or access-wall bypass attempted. Do not equate inaccessible with nonexistent.

## Other sources investigated

- SouqData https://souqdata.com/data-sources explicitly uses Yahoo for daily OHLCV, so it cannot count as an independent corroborator merely because its domain differs.
- CMA https://cma.gov.sa/en/AboutCMA/ResearchAndReports/opendata/Pages/default.aspx lists quarterly/annual market statistics. No complete daily stock OHLCV panel verified from that library.
- EODHD https://eodhd.com/ describes a free20-call plan whose stated included historical access is US exchanges. Saudi full-history entitlement is unverified, not assumed free.
- Marketstack https://marketstack.com/ and https://marketstack.com/faq advertise a free EOD plan, with conflicting100/1000 monthly-count text across pages. Exact Saudi ticker coverage and free entitlement have not been verified; no account was created. Batched tickers still consume per-symbol quota according to its FAQ.
- R tasi package https://github.com/Hussain-Alsalman/tasi examined: get_company_records and get_index_records call legacy Tadawul website routes via parseURL. It is not an independent market-data owner. No old route/token was used to bypass the observed Saudi Exchange denial.
- Kaggle2020–2026 snapshot https://www.kaggle.com/datasets/abdulmalekx/saudi-stocks-prediction-data-tadawul-2020-2026 is linked by its downstream project https://github.com/RawanSaudAL/saudi-stock-market-optimal-investment as originally yfinance; do not presume source independence from a new dataset filename.

## Decision

Continue the free Tasilab candidate route with an authorized account key and one bounded sample before scaling. Do not pay or subscribe on the basis of marketing coverage. Do not claim this source already recovered239 histories or independently proved profitable trading. Until the authentication, lineage and sample gates pass, existing source quarantines and Shadow Mode remain unchanged.
