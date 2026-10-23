# Independent-source and recovery decision —2026-10-23

No data-source subscription, account, paid request, access-wall bypass or production rule change is authorized or performed by this implementation. This audit does not release quarantines or change phase6 execution/quality/version fingerprints.

| Source | Actual current evidence | Coverage that can be claimed | Remaining requirement |
|---|---|---|---|
| Yahoo/yfinance | Existing raw full-history download, now retained as raw OHLCV and separate Adj Close, no quote restore | Per-run candidate internal coverage only | Same vendor is not independent; rights/PIT capital action review unresolved |
| Saudi Exchange public history and market watch | Prior phase6 actual probes returned403 |0 validated automated histories in that probe | Obtain an authorized accessible feed/export; never bypass denial |
| Mubasher public stock page | Prior actual200 page, no complete dated OHLCV feed verified |0 validated complete histories | Date, raw open/high/low/close/volume and permitted usage must be established |
| Stooq TASI public CSV | Prior probe no validated overlapping index history |0 validated index history | Complete dated corroboration required |
| SAHMK developer API | Official docs list free delayed quotes,100requests/day; historical OHLCV is Starter+; API key needed |0 retrieved or independently reconciled by this audit | User account/entitlement and provenance review; free single quotes cannot cover254 per day or repair126-session histories |
| Argaam market-data API | Official developer docs list historical OHLCV and index/sector history, apikey authentication |0 retrieved | Authorized key/plan and rights; no assumption of free full coverage |

Primary documentation reviewed:
- https://www.sahmk.sa/en/developers
- https://github.com/sahmk-sa/sahmk-python (official SDK: Free has no historical access; no entitlement bypass)
- https://developer.argaam.com/market-data-overview
- https://ranaroussi.github.io/yfinance/

A provider's own licensing claim is not our independent verification of its full history, ownership or upstream feed. No example data from docs is used as market observations.

## Specific original blocking conditions
All254 archived securities failed the126-session positive-volume requirement.239 carried unverified repair/jump/current-zero-volume blocks,37 had a raw-vs-adjusted current-bar disagreement,16 lacked a fresh archived current bar, and3 failed internal historical OHLCV. These are overlapping denominators, not additive stock counts.

Raw vs adjusted close must be compared on the same basis. The new recovery audit explicitly distinguishes raw agreement, adjustment-only difference and unresolved price difference. A same-vendor new match is evidence of a candidate reconstruction, never independent proof of the old quote replacement. Widespread zero-volume sessions cannot be removed or treated as holidays without dated independent evidence. This audit re-fetches the entire540-calendar-day window; previous phase6 acquisition retained only65 bars plus full-series hashes. It retains complete fresh raw CSVs and action fields in the run artifact for reproduction.

## Optional independent CSV import (no secrets or provider credentials)
When authorized independent exports exist, put raw canonical CSVs under data/independent/<symbol>.csv with Date,Open,High,Low,Close,Volume. Include manifest.json: {"series":[{"symbol":"7200","provider":"REAL PROVIDER","upstream_provider":"REAL UPSTREAM","source_url":"SOURCE URL","retrieved_utc":"UTC ISO8601","basis":"raw","timezone":"Asia/Riyadh","usage_authorization":"ACTUAL PERMITTED USAGE","independence_attested":true,"csv_sha256":"ACTUAL SHA256 OF EXACT CSV BYTES"}]}.

Do not fill the manifest with placeholder assertions. The loader rejects missing provenance, Yahoo upstream, changed hashes, ambiguous adjusted basis and duplicate dates. A single current quote cannot pass126-session corroboration. Attestation/CSV matching does not by itself establish PIT action correctness, independence or an execution entitlement. Even a full match here does not authorize production/phase6 changes: register a new prospective cohort after a separate review; existing sealed events and original strategy version remain unchanged.

## Daily operation
The separate data-recovery workflow follows the existing daily scan and has no cron. It can also run on code/reference changes or manual dispatch. Its publisher writes only output/data_recovery/current and immutable per-run history. Raw full inputs remain in the90-day v4 artifact. Existing production and phase6 ledger paths are not edited. No ChatGPT task, notification channel or trade order is created.
