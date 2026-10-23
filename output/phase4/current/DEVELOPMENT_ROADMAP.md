# Development Roadmap

## Implemented research controls

- Immutable run-16 snapshot and per-stock hashes; exact reproduction of all original 25 trades and metrics before comparisons.
- Three independent engines, nine one-feature ablations, original/risk-matched original and two simple references: 16 portfolios, base and stress costs, three purged temporal tests; no post-result threshold tuning.
- Entry constraints: 10% target, RR >=2, bullish price and >=1.5x prior-20-session volume, trusted eligible history, synchronized RS, stop <=8% price, >=1.5 ATR initial width, maximum planned 0.5% NAV risk and 3% aggregate for new models. Gap risk is not bounded by the planned stop.
- Original live files and cron remain unchanged. A separate workflow evaluates research and attaches shadow observations to completed daily production runs. No second ChatGPT task or delivery channel.

## Next evidence, before any adoption

1. Obtain a clearly licensed, independently reconciled full OHLCV/corporate-action feed. Public-page availability alone is insufficient. Keep unreconciled quote substitutions quarantined. Archive permitted input vintages and all provider failures.
2. Collect post-registration shadow opportunities and actual future bars. Avoid retrospective seeding into the prospective success denominator; at least 20 new trades per prospective evaluation and sufficient full/fold sample counts are conservative minimums, not proof.
3. Reconstruct historical constituents, suspensions, delistings, splits, rights issues and distributions. Until then, retain explicit survivorship and adjustment-bias flags.
4. Seek more market regimes and independently held-out dates; freeze the next protocol before inspecting outcomes. Keep all failed and zero-trade experiments. Do not loosen gates merely to improve the report.
5. Review execution assumptions with actual exchange tick sizes, auction fills, price-limit queues and broker-specific fees/taxes. Daily OHLC bars cannot resolve intraday stop/target order; use conservative stop-first semantics.
6. Only consider a manually reviewed production change after stable positive base/stress expectancy and risk-adjusted excess evidence with adequate independent samples. Win rate alone, a green workflow, or an attractive in-sample winner is insufficient.

## Explicitly not established

No proven improvement, no verified 40% success claim, no legal permission to redistribute all third-party prices, no eliminated survivorship bias and no virgin historical OOS claim. Original live strategy is retained. Read comparison JSON for actual counts and all failed evidence gates.
