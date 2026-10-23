# Phase 5 — Data Integrity & Early Reversal Research Plan
Status: KICKOFF / RESEARCH ONLY — no strategy promoted to production
Baseline: phase4 run 39941086262; phase3 run 39887183117; frozen input 39870228858
Date: 2026-10-23

## Purpose and guardrails
Improve **out-of-sample net expectancy** and risk-adjusted returns, not win rate alone. A 45–50% win rate is a research aspiration, not a promised outcome. Preserve Predict → Confirm → Act → Invalidate; Entry/Partial Entry require credible >=10% technical upside, R:R >=2, independent price+volume confirmation, and validated OHLCV. Preserve the current 254-symbol scheduled scanner and existing production strategy. Run all new variants in Shadow Mode. Never issue orders.

## Workstream A — Data provenance and recovery (highest priority)
1. Inventory raw daily OHLCV for each symbol, dates, vendor, timezone, adjustment basis, missing sessions, zero volume, duplicate bars, quote-repaired closes, and split/capital-action anomalies. Publish symbol-level eligibility and an honest denominator.
2. Re-check the 239 quarantined historical series. A valid most-recent candle does NOT rehabilitate a full series. Require consistent adjusted historical OHLCV and adequate lookback for each tested feature.
3. Explore free sources only where access and automated usage are lawful. Log source terms, coverage, timestamps, rate limits, reproducibility and cross-source agreement. Do not circumvent 403, paywalls, or rate limits. Where no acceptable source exists, retain quarantine.
4. Keep separate statuses: fetch success, latest-bar validity, historical-series validity, backtest eligibility, live Entry eligibility. Never equate 252 latest valid bars with 252 historically validated symbols.
5. Explicitly validate benchmark ^TASI and sector proxy provenance; avoid current-constituent survivorship in historical sector calculations where possible.

## Workstream B — Explain all trades
For the 25 baseline trades and 31 Phase-4 early-reversal trades, export trade-level entry/exit dates, net returns, MFE/MAE, bar-level excursion sequence (when identifiable), stop gap, entry distance to EMA20/50 in ATR, trailing 5/10/20-session returns, relative strength, volume ratio, volatility contraction, breakout age, base length, market regime, sector proxy, holding time, and exit reason. Separate observational associations from causal claims. Highlight failure modes: 18/25 extended entries (16 losses); 8/25 breakouts failing within 3 sessions (8 losses); 19/25 stops <1.5 ATR (15 losses). Avoid leakage in labels and entry-time features.

## Workstream C — Three early-reversal hypotheses, independently tested
A. Failed-breakdown reclaim: support break followed by reclaim, rising relative strength and validated volume.
B. Base contraction: >= configurable consolidation length, shrinking normalized ATR/range, higher lows, then price+volume trigger.
C. Controlled pullback after initial reversal: established higher low, pullback into support/EMA, reversal confirmation without chasing.
For each: preregister feature definitions, trigger, invalidation, horizon, expected target, stop, R:R, market/sector conditioning and transaction costs. Compare individually to phase4 early-reversal, baseline, buy-and-hold and simple momentum. No cherry-picking best historical parameter.

## Workstream D — Scientific evaluation
- Same universe, sessions, position sizing, fees, slippage and gap handling across variants. Respect real trading-calendar next-session execution and no future-bar knowledge.
- Purged/embargoed chronological walk-forward; report development and truly untouched forward data separately. Existing reused 2026 holdout is NOT virgin evidence.
- Report per variant: eligible universe, signals, completed trades, wins, win rate with uncertainty intervals, net expectancy, average gain/loss, payoff ratio, portfolio return, drawdown, turnover, exposure, median hold, performance by regime, and sensitivity to higher costs.
- Log all tested variants, parameters and negative results. Test stability across reasonable parameter neighborhoods; no approval on four or five trades. If samples remain small, explicitly return INCONCLUSIVE.
- Candidate promotion requires positive net expectancy and robust performance in fresh unseen tests with enough independent trades; do not promote solely for win rate.

## Workstream E — Deployment and monitoring
- Maintain daily Sunday–Thursday 17:35 Riyadh workflow and 254-symbol snapshot, with separate confirmed coverage counts.
- Shadow Mode logs every candidate's hypothesis, timestamped source bars, trigger, invalidation, target, 10% upside check, >=2 R:R check, and later outcomes.
- Daily missed-opportunity review: flag >=8–10% moves that had valid *prior-session* data and record why a candidate was missed, without hindsight labeling as a guaranteed entry.
- Alerts only for newly confirmed actionable opportunities or material changes; do not promote shadow signals to Entry.
- Generate versioned reports: DATA_PROVENANCE.md, QUARANTINE.csv, TRADE_DIAGNOSTICS.csv, HYPOTHESES.md, WALK_FORWARD.md, DECISION.md, and machine-readable JSON; attach to Actions artifacts.

## Phase-5 completion checklist
[ ] Source inventory and historical eligibility audited
[ ] Baseline and early-reversal trade-level diagnostic files
[ ] Three independent hypotheses implemented in research/shadow mode
[ ] Tests passing, with reproducible run ID and comparison report
[ ] Honest independent-evidence decision: PROMOTE / KEEP SHADOW / REJECT
[ ] No production entry rule or schedule changed without evidence
