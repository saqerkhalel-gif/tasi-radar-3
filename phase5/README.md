# Phase5 — data integrity and early reversal, shadow only

Read research/PHASE5_PLAN.md and the preregistered protocol.json first. Registration commit:5c7d5279b0a7544d32c7333dcce000e3a41a9a51. The 24 cases and parameters were frozen before new hypothesis evaluation; no winning configuration is selected.

Execution order: data audit → all56 legacy trade diagnostics → exact25/31 reproduction and24 harmonized comparisons → missed-opportunity review → verification → prospective shadow initialization. No production strategy, daily Sunday–Thursday17:35 Riyadh schedule,254-symbol list or existing report automation is changed.

Research commands, using the downloaded phase4 artifact:
- python -m phase5.data --snapshot baseline4/frozen
- python -m phase5.diagnostics --snapshot baseline4/frozen --phase4-results baseline4/output/phase4/current
- python -m phase5.evaluate --snapshot baseline4/frozen --phase4-results baseline4/output/phase4/current
- python -m phase5.review_missed --snapshot baseline4/frozen
- python -m phase5.verify
- python -m phase5.shadow --snapshot baseline4/frozen

The separate phase5 workflow runs research on phase5 changes/manual dispatch. After successful production daily runs it downloads exactly that run/attempt's artifact, restores the phase5 ledger and records fresh shadow hypotheses/outcomes plus daily missed-move review. Output changes are files only, not a second alert channel or ChatGPT task.

Outputs: DATA_PROVENANCE.md, QUARANTINE.csv, TRADE_DIAGNOSTICS.csv, TRADE_EXCURSIONS.csv, HYPOTHESES.md, WALK_FORWARD.md, COMPARISON.csv, DECISION.md, missed-opportunity files and machine JSON. Reports are committed with immutable run histories and uploaded with exact replay inputs as90-day artifacts.

Important distinctions:
- Fetch success ≠ valid last bar ≠ historically eligible vendor window ≠ independently verified series ≠ live Entry authorization.
- Known original25/phase4 early31 trades are separately reproduced exactly. All new comparisons then use common sizing/data/execution screens and may differ from legacy results.
- Causal prefix eligibility never uses a future repair to reject an earlier signal.
- A bad/unavailable execution/exit bar is not invented. Stale marks invalidate a portfolio comparison even if a later bar permits liquidation.
- Wilson/paired-block intervals are descriptive with overlapping trades and a reused historical period. The20-session purge and prior-test/post-test embargo do not make known dates untouched.
- Prospective shadow paper outcomes are individual hypothetical unit-notional returns, not a capital-constrained portfolio claim. No automatic promotion. Insufficient evidence returns INCONCLUSIVE.
