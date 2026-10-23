# DATA PROVENANCE — Phase 5

Audit 2026-10-23T11:15:59.616221+00:00; source run 39870228858; price session 2026-10-22.

## Separate denominators

| Status | Stocks /254 |
|---|---:|
| universe | 254 |
| quarantined_frozen | 239 |
| frozen_fetch_success | 254 |
| frozen_latest_bar_valid | 252 |
| historical_vendor_window_eligible | 14 |
| independently_validated_historical_series | 0 |
| live_entries_authorized | 0 |
| fresh_stock_fetch_success | 254 |
| fresh_latest_valid | 251 |

## Recovery decision

**No historical quarantine released.** Fresh published closes, even when they now match an old quote replacement, are same-vendor evidence and do not establish an independently reconciled entire history. Every old repair is rechecked by date when available; disagreements remain visible in JSON. Missing data stays missing. No interpolation or price invention.

## Historical eligibility

QUARANTINE.csv contains all254 names, observed date range, vendor/basis/timezone, normalization, missing sessions, zero volume, duplicate dates, repairs, jumps and separate statuses. Zero-volume historical sessions are recorded, not invented trades. Causal backtests assess the known prefix at each signal; a future repair must not retroactively disqualify an earlier signal. This remains a vendor-screened exploration, not independent validation.

## Sources and reproducibility

- Yahoo: yfinance is unofficial; research/personal-use only notice, provider terms control; access not redistribution permission. https://ranaroussi.github.io/yfinance/
- Saudi Exchange: Official historical and corporate-action reference sought; no WAF/paywall/authentication bypass. Public site does not establish bulk automation entitlement.
- Stooq: Public index CSV probe only; no assumed stock coverage or redistribution licence. https://stooq.com/q/d/?s=%5Etasi
- Mubasher: Public quote page is not an established licensed historical OHLCV feed; no full-history claim.
- Twelve Data: XSAU requires paid Pro+/Venture+ entitlement; no verified free Saudi EOD access. https://twelvedata.com/exchanges/XSAU

- Saudi Exchange historical reports: HTTP 403; access_denied; verified full stock histories: 0.
- Saudi Exchange market watch: HTTP 403; access_denied; verified full stock histories: 0.
- Mubasher public stock page: HTTP 200; no_complete_dated_OHLCV_feed_verified; verified full stock histories: 0.
- Stooq TASI CSV: HTTP 200; no_validated_machine_readable_index_history; verified full stock histories: 0.

Each response/download is hashed and timestamped; frozen per-stock hashes bind every comparison. All access failures and unknown coverage remain explicit. No paid access or denied-page circumvention.

## TASI and sector provenance

TASI uses the frozen observed seed/cache and sparse Yahoo quote merge. Recent121-session completeness is True. Full history has NOT been independently exchange-reconciled. Sector proxies use current membership, not historical constituents; exclusion of the target and missing/quarantined peer observations reduces contamination but cannot remove survivorship bias. Core hypotheses report sectors without making this uncertain proxy mandatory; a separate registered gate tests sensitivity.

## Remaining limits

Delisted/point-in-time universe and complete historical corporate-action vintages are unavailable. Fresh raw OHLC, Adj Close factors and reported split/dividend counts are audited, but rights issues and all adjustment revisions remain unverified. Independent full-series denominator is zero; no promotion is possible from this audit.
