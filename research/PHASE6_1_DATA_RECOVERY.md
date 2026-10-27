# Phase 6.1 — Data Recovery & Validation

Status: STARTED — diagnostic implementation committed, independent price-source verification pending.
Date: 2026-10-27. Scope: research/measurement only; production and trading rules unchanged.

## Baseline (source session 2026-10-26)
- Configured 254, fetched 254, fresh 248, vendor historical window eligible 244.
- Independently validated historical sequences 0; historical backtest eligible 0.
- Execution-bar independently verifiable 0; signal eligible 0; completed forward trades 0.
- Phase 6 decision KEEP_SHADOW; no promotion.
- Note: signal eligibility is **not** the same as candidate signal count. Both must be reported separately.

## Work completed
- phase6/recovery_diagnostics.py: read-only, fail-closed denominator and per-symbol blocker analysis; no price repair, no promotion, no orders.
- tests/test_phase6_recovery_diagnostics.py: safety, counts, duplicate/mismatch tests.

## Required next tasks (do not mark complete without run evidence)
1. Publish detailed per-symbol eligibility reasons from the existing phase6.quality.inspect report. Prioritize zero-volume 126-session history, adjusted/raw mismatch, stale data and capital actions.
2. Audit suspicious *market-wide* zero-volume dates against exchange trading calendar. Never fill zero-volume or invent sessions.
3. Inventory lawful free independent sources and rights. Record dated full-series OHLCV and action reference with hashes; 403 or missing data means unavailable, not permission to bypass.
4. Separate MONITORING, HISTORICAL_RESEARCH, FORWARD_SIGNAL and EXECUTABLE_PAPER gates. A valid vendor-only history can support labelled exploratory research, but never independently validated claims.
5. Preserve raw decision-time vintage and separately archived next-session open; no retrospective execution and no automatic quarantine release.
6. Add reproducible fixtures for stale, zero-volume, split/rights, mismatch, gaps, absent reference, reruns and no-signal sessions.
7. Compare before/after denominators and sample symbol/date discrepancies. Do not claim Phase 6 is fixed unless verifiable forward bars and data provenance satisfy the registered protocol.

## Acceptance
- New workflow/test run successful and report produced with source run URL and commit.
- Per-reason counts and examples match detailed symbol records.
- Zero unauthorized promotion, trading, fabricated fills, paid access or production schedule changes.
- Explicit statement of unresolved independent-source access and historical survivorship limits.

## Run locally / CI
python -m pytest -q tests/test_phase6_recovery_diagnostics.py
python -m phase6.recovery_diagnostics --summary output/phase6/current/summary.json --output output/phase6/current/recovery_diagnostics.json

The second command uses existing summary only; per-symbol breakdown requires detailed quality JSON from the pipeline's sealed snapshot.
