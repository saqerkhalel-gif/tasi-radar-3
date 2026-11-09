# TASI Radar — evidence-led improvement investigation (2026-11-09)

Status: RESEARCH ONLY / SHADOW MODE. No production strategy change and no new win-rate claim.

## Verified baseline
Source: output/backtest.json (read 2026-11-09). Phase2.0 historical simulation: 27 trades, win rate 22.222222%, average win +9.137489%, average loss -3.753805%, expectancy -0.889073% per trade, simulated portfolio return -2.414458%. This is NOT forward performance or live recommendations.

## Market case studies (not confirmed missed signals)
- 2026-11-05 Tawuniya +9.98%, reported alongside Q3 results: earnings event + price response.
- 2026-11-04 GASCO +9.98%, Alamar +9.96%: catalysts not independently established by price report.
- 2026-11-09 Al-Babtain +7.44% with Q3 reporting and volume about 7.25x three-month average (4,439,742 / 538,273).
- 2026-11-09 Anaam ~+10%, catalyst unverified.
Sources: https://www.argaam.com/en/market-daily-report/3/63161 ; https://www.argaam.com/en/market-daily-report/3/63238 ; https://www.argaam.com/en/market-daily-report/3/63337

## Findings and hypotheses to test
1. Event-driven signals need separate timestamped disclosures (earnings surprise, guidance, contracts, capital actions), not a retrospective news label. Require announcement timestamp <= signal timestamp.
2. Distinguish post-event drift from event-day gaps: enter only at a realistically available next-session price, not at the prior close.
3. Test trend-continuation/pullback separately from early reversal and breakout/retest; do not combine performance until each is evaluated.
4. Regime and sector-relative-strength gates may reduce low-quality entries; evaluate both precision AND recall (missed opportunities).
5. Use ATR-normalized stops, liquidity/spread constraints, volume relative to trailing median, and gap filters as independent ablations; avoid optimizing many parameters on 27 trades.
6. Data quality: corporate actions, split adjustments, stale bars, delistings, and survivorship bias must be resolved before drawing conclusions.
7. Early Watch classifying 243/254 symbols is not a useful selective alert: separate broad candidate universe from ranked actionable shortlist.
8. Fix immutable forward ledger failures without rewriting prior snapshots. Measure forward results after fees and slippage.

## Evaluation contract
Use expanding walk-forward windows with embargo for overlapping holding periods, out-of-sample holdout, unchanged costs and next-open execution, frozen code/config hashes, and timestamped signals. Compare baseline vs each single change with trade counts, win rate, expectancy, profit factor, drawdown, coverage, recall on >=8% moves, and confidence intervals. Require a materially larger sample before claiming improvement. Keep Shadow Mode until validated.

## Research
Boussaidi & AlSaggaf, Post-Earnings Announcement Drift, Momentum, and Contrarian Strategies in the Saudi Stock Market (2010-2019), https://ideas.repec.org/a/spr/jknowl/v15y2024i3d10.1007_s13132-023-01648-4.html
