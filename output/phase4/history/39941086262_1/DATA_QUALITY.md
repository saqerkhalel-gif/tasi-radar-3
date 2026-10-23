# Data Quality — Phase 4

Frozen run 39870228858; price session 2026-10-22; audit UTC 2026-10-23T10:44:58.667057+00:00.
254 current stocks; 239 quarantined; 15 pass existing vendor gates. Passing internal checks is not independent exchange certification. No quarantined price has been released by this research.

## Fresh independent provider probes

| Source | HTTP | Result | Verified stock histories /254 |
|---|---:|---|---:|
| Saudi Exchange historical reports | 403 | access_denied | 0 |
| Saudi Exchange market watch | 403 | access_denied | 0 |
| Mubasher public stock page | 200 | no_complete_dated_OHLCV_feed_verified | 0 |
| Stooq TASI CSV | 200 | no_validated_machine_readable_index_history | 0 |

Fresh Yahoo checks: 254/254 attempted with results; valid expected-session bars 252; among the 239 quarantined names, 237 currently pass raw checks. These are SAME-provider checks, not independent releases. Status: fresh_checks_completed.

## Audit scope and rights

- Yahoo: Unofficial yfinance research/personal-use access; Yahoo terms govern data use. Free access is not a redistribution licence. No automated repairs or quote substitutions in this fresh audit.
- Saudi Exchange: Official source; public availability does not establish permission for a bulk automated historical feed. No authentication/WAF bypass.
- Mubasher: Public quote page is not a verified, licensed full OHLCV historical feed; zero verified stock-history coverage in these probes.
- Stooq: Index-only public CSV probe; site access/terms and dated overlap must pass. No assumed Saudi equity coverage.
- Twelve Data: XSAU catalog requires Pro+/Venture+ entitlement; Basic free tier is not verified Saudi historical coverage. No entitlement or data downloaded; validated coverage unknown, not a proven alternative.

Official historical: https://www.saudiexchange.sa/wps/portal/saudiexchange/newsandreports/reports-publications/historical-reports
yfinance rights notice: https://ranaroussi.github.io/yfinance/ ; Saudi Twelve Data entitlement: https://twelvedata.com/exchanges/XSAU

## Index and corporate actions

Benchmark 368 observed rows; latest 2026-10-22; recent 121 synchronized sessions complete: True. Existing merged Yahoo/Investing history carries source metadata in JSON. A single current overlapping quote cannot certify the whole history. Stooq overlap results, if accessible, are in data_quality.json. No forward-filled index values.
Raw Yahoo dividend/split event counts are recorded when the fresh download succeeds; rights issues, complete exchange actions and historical adjustment vintages remain unverified. Existing repaired closes are logged per symbol/date; no interpolation, invented close or retrospective override.

Fresh same-vendor passes do not independently resolve earlier quarantined repairs or corporate actions.
A provider access failure means no validated coverage in this audit, not proof the provider has no data.
Previously adjusted history lacks point-in-time corporate-action vintages; survivorship bias remains.
Input hashes bind the research to the old frozen snapshot; fresh probes cannot improve its historical results.
