# Entry blocker root-cause audit — 2026-10-31

Status: RESEARCH ONLY. No production strategy changes or trade promotion.

## Confirmed source-level defects and risks
1. radar.py: target starts as previous 90-session high when > current close. For breakout setups the trigger is the prior 20-session high, often near the target. Expected return is then computed from the current close, not a realistically executable post-confirmation fill. This produces zero/negative expected reward at the actual trigger.
2. radar.py: only if no prior high exists does it consider the Fibonacci 127.2% extension. A nearer prior high suppresses exploration of a *conditional* second objective. The nearest overhead pivot is also used as the terminal target instead of first resistance hurdle.
3. radar.py: a single trend requirement (close>EMA20>EMA50 and close>EMA200) is applied to all entries, including early reversals; that may systematically block reversal setups. This is a hypothesis about effectiveness, not a reason to relax safeguards without testing.
4. radar.py: stop is sometimes overridden by structural_invalidation. Confirm that the invalidation is below executable entry and compare ATR, swing-low and gap risk.
5. Current production counts: 254 scanned; 90 Early Watch, 164 Wait, zero qualified Entry/Partial Entry as of 2026-10-29. Phase6 remains KEEP_SHADOW, 0 independently verifiable execution bars, so no win-rate claim is justified.

## Required research changes (do not deploy untested)
- Calculate executable entry *after* confirmation, including next-open/slippage assumptions. Keep the trigger separate from entry price.
- Treat prior high/nearest resistance as hurdle T1, not automatically final target. A later T2 may use a confirmed measured move or Fibonacci extension, but require path viability and price/volume evidence. Never simply replace targets to force 10% upside.
- Compare independent entry gates for breakout+retest, trend pullback, and early reversal; preserve price/volume confirmation, >=10% executable upside, R:R>=2, and data QA.
- Emit per-symbol blocker funnel and counterfactual pass rates: data, price, volume, trend, upside, R:R, ATR, each independently and jointly.
- Audit signal timestamp vs data availability; eliminate lookahead, corporate-action errors, stale benchmark and duplicated cases.
- Walk-forward evaluation with untouched chronological holdout, next-open fills, trading costs/slippage, gaps, failed breakouts, and comparison with benchmark and no-trade baseline.
- Fix Phase6 immutability failures by diagnosing original object/manifest mismatches without editing sealed history. Keep shadow until provenance and forward ledger verifiable.

## Acceptance gates
- No production promotion without passing tests and verified source data.
- No trade if entry upside <10% or R:R <2.
- Positive net expectancy after fees and stress costs on out-of-sample test, and independent forward evidence.
- Record missed 8-10% moves only when a pre-move timestamped signal can be proven.
