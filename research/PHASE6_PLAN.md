# Phase 6 — Trustworthy Forward Validation & Data Recovery
Status: KICKOFF — implementation pending, no production rule change
Created: 2026-10-23
Reference runs: Phase 5 39945542819, Phase 4 39941086262, frozen baseline 39870228858

## Objective
Demonstrate repeatable **positive net expectancy after costs** on new, timestamped, eligible Saudi stock signals. Do not optimize for win rate alone. No live orders, no paid data, no unsupported claim of full historical coverage. Preserve production radar, 254-symbol snapshot, and Sunday–Thursday 17:35 Asia/Riyadh workflow.

## Gate 0: audit actual repository state
Read phase5/protocol.json, phase5/shadow.py, phase5/execution.py, phase5/data.py, phase5/evaluate.py, output/phase5/current/{DECISION.md,DATA_PROVENANCE.md,WALK_FORWARD.md}, radar.py, .github/workflows/radar.yml. Capture commit, current output schema, exact run IDs and existing signal tracking. Do not duplicate already implemented functionality.

## Workstream 1 — Provenance and data repair
- Build source-by-source inventory for daily OHLCV, date/timezone, corporate-action adjustment, gaps, zero volume, stale/repaired quotes, index and sector reference data, permitted automated usage, free tiers and historical coverage.
- Reassess 239 quarantined series. Validate historical *sequences*, not just 252 latest candles. Record eligible-for-signal and eligible-for-backtest independently.
- Seek only lawful free alternatives; never bypass 403, authentication, vendor terms or paywalls. Reconcile at least one independent reference for high-confidence series; otherwise quarantine and explicitly report coverage.
- Reject look-ahead adjusted values that would not have been available at decision time where point-in-time vintages are unavailable. Clearly state residual limitations.
- Do not promote any model if benchmark or execution price histories cannot be validated adequately.

## Workstream 2 — Immutable forward paper ledger
- At each real scheduled scan, create an append-only record of every eligible shadow hypothesis and every actual production Entry/Partial Entry, with UTC and Saudi session timestamp, unique event id, commit and source run id, symbol, strategy version, raw source/date/hash, OHLCV eligibility, trigger, entry rule, invalidation, stop, target, technical upside >=10%, R:R >=2, volume >=1.5x prior20 average, market regime, sector context, reason and status.
- Log no-signal days and eligibility counts, so selective recording is impossible. Preserve original predictions forever; changes must be separate events, not rewrites.
- Next-session execution uses a verifiable open and explicit transaction costs; if no reliable open, record NOT_EXECUTABLE rather than guessing. Distinguish signal quality from execution feasibility. Simulate gaps and stop-first ambiguity on daily bars.
- Advance positions only on new real session bars; mark pending, rejected, opened, closed, timed out, or data-unverifiable; avoid duplicate orders/positions and hindsight.
- Ensure atomic idempotent writes and stable identifiers across GitHub reruns; persist history in repo and/or artifacts with verifiable manifests and hashes. No secrets in outputs.
- No live trading.

## Workstream 3 — Evaluation and reporting
- Keep production, phase4 reversal and phase5 A/B/C variants distinct. Publish each version's signal count, eligible universe, new trades, completed trades, wins/losses, win rate with Wilson 95% interval, net expectancy, profit factor, payoff, max drawdown, turnover, exposure, average holding sessions, slippage sensitivity, gap losses, and returns by market regime.
- Separate historical reused tests from *new* prospective tests; never call historical folds unseen after prior examination. Include benchmark and a simple equal-risk baseline.
- No promotion solely because 5 trades show 60% wins. Research target >=100 completed reasonably independent forward trades over diverse regimes; statistical uncertainty and robustness matter more than a fixed count.
- Detect missing outcomes, stale series, delistings, survivorship, selection bias, overlapping correlated positions, capital actions and data revisions. Disclose any inability to establish independence.
- Daily missed-opportunity review based only on previous-session valid information; flag >=8–10% moves and missed conditions, but never count hindsight picks as genuine prior alerts.
- Emit stable machine-readable JSON/CSV and concise Arabic Markdown dashboard in output/phase6/current and versioned output/phase6/history/<run_id>_<attempt>.

## Workstream 4 — Automation and alerts
- Integrate with existing scheduled GitHub Actions run, preserving existing schedule and production decisions. Run tests and shadow ledger every valid session; record a successful no-trade day.
- Alert only for *new confirmed production actionable opportunities* or material changes; Shadow Mode signals are research-only and should not be labeled Entry.
- Report operational failure/data degradation separately from stock opportunities. Do not imply the existing ChatGPT automation is integrated with GitHub without testing it.
- Produce deterministic fixtures/tests for calendar holidays, weekend, reruns, missing open, stale volume, gap through stop, target+stop same candle, corporate actions, idempotency, invalid source, and no-signal days.

## Acceptance criteria
1. Tests pass and scheduled workflow completes with exact GitHub run URL.
2. Immutable prospective ledger records one or more genuinely new session snapshots (a no-signal day is valid); never backfill hypothetical predictions as prospective.
3. Explicit and accurate denominators: fetched, latest-valid, historical-eligible, independently validated, signal-eligible, and executable.
4. Side-by-side strategy report with uncertainty and realistic after-cost outcomes, including zero completed trades where applicable.
5. All variants remain Shadow Mode and production rules unchanged unless a future independent evidence gate is met.
6. Deliver links to code, tests, data quality, forward ledger, and decision report; clearly state remaining blockers.

## Research decision
Phase 5 did not establish an independently validated improvement. Phase 6 is a *measurement infrastructure* milestone; do not promise improved win rate or positive returns from infrastructure alone.
