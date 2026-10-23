# Phase5 execution-data review

This supplements the machine execution-validity flags and EXECUTION_DATA_ISSUES.csv from phase5 research. It is a descriptive post-run input inspection, not an optimized trading filter or a corrected price feed.

Frozen input run39870228858, archived in phase4 run39941086262 artifact12495971995. All254 frozen CSV histories were checked; denominators below include only stocks with an observed row on that date.

| Date | Observed stocks | Zero-volume stocks | Zero-volume share |
|---|---:|---:|---:|
| 2025-07-17 | 243 | 222 | 91.358% |
| 2025-09-25 | 246 | 246 | 100.0% |
| 2026-05-04 | 251 | 251 | 100.0% |
| 2026-08-16 | 252 | 251 | 99.603% |

The listing rule(>=80% of>=50 observed names) is descriptive only. No independent official explanation or dated full OHLCV reconciliation was obtained; a zero-volume row is not assumed to prove a market holiday, a real suspension or a vendor placeholder. We do not invent fills, replace volume or auto-release quarantine.

The core failed-breakdown sample has unusable holding bars for4193 and4210 on2026-05-04 and4280 on2026-08-16. Its nominal3/5 wins(60%) are therefore NOT valid execution evidence, in addition to being far too few independent trades. The5-trade Wilson interval is approximately23.1%–88.2%; the last reused temporal fold lost money. No improvement can be inferred.

Other harmonized references and the controlled-pullback core also have invalid holding-bar comparisons. Read the explicit validity column, per-case stale-day count and symbol/date/reason CSV. A YES execution flag only passes internal checks; it does not establish independent full-history provenance.

The source audit separately reports239 quarantined frozen histories,14 internally eligible current historical windows and zero independently validated full series. Current vendor latest-bar passes are a separate denominator and cannot rehabilitate full history. Reused2026 tests remain exploratory, and prospective closed-trade count starts at zero.

Decision:KEEP SHADOW / INCONCLUSIVE. Production strategy,254-symbol list and existing daily schedule remain unchanged. No entry, order or new alert channel was authorized by this review.

Final verified research run: https://github.com/saqerkhalel-gif/tasi-radar-3/actions/runs/39945542819 ; artifact12498506164.97tests passed and24comparisons/56legacy trade diagnostics verified. The wording rows marked NO in the comparison warning refers to the table execution-validity column. The original run artifact retains its run-generated wording; this addendum clarifies the meaning without changing any metrics, input data, parameters or decisions.
