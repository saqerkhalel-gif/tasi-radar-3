# Phase 4: registered shadow research

Production radar, symbols, cron and report task are unchanged. No new engine places orders or modifies daily classifications. Research was registered in commit `d5c64e5e54545f3bc30b2872a963fd9d08dd8daf` before evaluation.

- `python -m pytest -q`: live plus research causality/execution tests.
- `python -m phase4.research --snapshot frozen`: fixed run-16 reconstruction and all 16 portfolios, three purged tests, base/stress costs; reports under `output/phase4/current/`.
- `python -m phase4.data_audit --snapshot frozen`: all 254 frozen OHLCV histories and bounded public source probes. `--offline` explicitly reports fresh-source coverage as unknown.
- `python -m phase4.verify`: validates actual metrics, counts, risk admission gates and original production blob hashes.
- `python -m phase4.shadow --snapshot <completed-daily-artifact>`: prospective observations under `output/phase4/shadow/`. Old snapshot observations never count as new prospective trades. Paper observations are unit-notional, not a portfolio return claim.

`.github/workflows/phase4.yml` runs full registered research on changes to phase4 or manual dispatch. After each successful existing `TASI Radar 3.0` daily workflow, it downloads exactly that run/attempt artifact and records new shadow observations. It does not rescan or reschedule production. Concurrent phase4 runs serialize. Snapshot identities and price dates accompany reports. Outputs are committed with immutable run histories and uploaded as 90-day artifacts, including fixed input files and original output for replay.

The risk engine matches original execution for unmodified sizing. It corrects the *admission-risk metric* to exclude rejected zero-budget orders; 3% applies when admitting orders. Changes in NAV and market gaps can subsequently exceed planned percentages; no continuous loss guarantee is asserted. No model threshold was optimized after outcomes were inspected.

Read `RESEARCH_REVIEW.md`, `DATA_QUALITY.md`, `STRATEGY_COMPARISON.md`, `WALK_FORWARD_RESULTS.md`, `DEVELOPMENT_ROADMAP.md` in the published output. Current-universe survivorship and retrospective corporate-action biases remain unresolved. Reused historical folds are not new OOS evidence. No automatic strategy promotion.
