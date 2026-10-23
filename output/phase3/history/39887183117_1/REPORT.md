# Phase 3 comparison — research only

Frozen input run: 39870228858; research run: https://github.com/saqerkhalel-gif/tasi-radar-3/actions/runs/39887183117

**Decision: keep the original live strategy. No new rule has been deployed.**

All variants use identical frozen inputs, dates, execution rules and costs. The reused historical holdout is not virgin out-of-sample evidence.

Development: 2026-03-05 through 2026-07-19; 20-session purge; reused temporal test: 2026-08-17 through 2026-10-21.

## full_period

| Variant | Trades | Win % | Mean win % | Mean loss % | Expectancy % | Portfolio % | Max daily DD % | Daily Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 25 | 24.0 | 9.37 | -3.744 | -0.596 | -1.523 | -4.615 | -0.571 |
| tasi_trend | 2 | 0.0 | NA | -1.403 | -1.403 | -0.281 | -0.708 | -0.386 |
| sector_strength | 10 | 0.0 | NA | -3.68 | -3.68 | -3.632 | -4.465 | -2.185 |
| confirmed_breakout | 11 | 9.091 | 3.685 | -4.752 | -3.985 | -4.308 | -4.502 | -2.299 |
| retest | 6 | 16.667 | 3.685 | -5.341 | -3.836 | -2.286 | -2.484 | -1.56 |
| anti_chase | 7 | 57.143 | 10.586 | -3.349 | 4.614 | 3.232 | -0.817 | 2.21 |
| stop_atr_floor | 10 | 30.0 | 5.855 | -4.18 | -1.17 | -0.949 | -2.68 | -0.665 |
| stop_support_buffer | 21 | 23.81 | 9.531 | -4.501 | -1.16 | -1.964 | -4.042 | -0.991 |
| market_sector_anti_chase | 0 | NA | NA | NA | NA | 0.0 | 0.0 | NA |

## development

| Variant | Trades | Win % | Mean win % | Mean loss % | Expectancy % | Portfolio % | Max daily DD % | Daily Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 16 | 31.25 | 5.234 | -3.276 | -0.617 | -1.013 | -3.841 | -0.671 |
| tasi_trend | 2 | 0.0 | NA | -1.403 | -1.403 | -0.281 | -0.708 | -0.513 |
| sector_strength | 9 | 11.111 | 0.038 | -3.477 | -3.086 | -2.756 | -3.692 | -2.54 |
| confirmed_breakout | 6 | 16.667 | 3.685 | -4.757 | -3.35 | -1.994 | -2.193 | -1.879 |
| retest | 3 | 33.333 | 3.685 | -6.424 | -3.054 | -0.913 | -1.256 | -1.117 |
| anti_chase | 4 | 50.0 | 6.125 | -3.552 | 1.287 | 0.509 | -0.817 | 0.726 |
| stop_atr_floor | 9 | 44.444 | 4.401 | -3.59 | -0.039 | -0.01 | -1.914 | 0.001 |
| stop_support_buffer | 14 | 28.571 | 4.401 | -4.01 | -1.607 | -1.802 | -3.396 | -1.491 |
| market_sector_anti_chase | 0 | NA | NA | NA | NA | 0.0 | 0.0 | NA |

## reused_temporal_test

| Variant | Trades | Win % | Mean win % | Mean loss % | Expectancy % | Portfolio % | Max daily DD % | Daily Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 3 | 0.0 | NA | -4.234 | -4.234 | -1.269 | -1.643 | -2.734 |
| tasi_trend | 0 | NA | NA | NA | NA | 0.0 | 0.0 | NA |
| sector_strength | 0 | NA | NA | NA | NA | 0.0 | 0.0 | NA |
| confirmed_breakout | 3 | 0.0 | NA | -4.234 | -4.234 | -1.269 | -1.643 | -2.734 |
| retest | 1 | 0.0 | NA | -2.823 | -2.823 | -0.282 | -0.298 | -2.106 |
| anti_chase | 0 | NA | NA | NA | NA | 0.0 | 0.0 | NA |
| stop_atr_floor | 1 | 0.0 | NA | -5.433 | -5.433 | -0.5 | -0.764 | -1.662 |
| stop_support_buffer | 3 | 0.0 | NA | -4.734 | -4.734 | -1.216 | -1.53 | -2.99 |
| market_sector_anti_chase | 0 | NA | NA | NA | NA | 0.0 | 0.0 | NA |

## Interpretation

No qualified development candidate; retain original.

At least 30 development trades and 20 new unseen test trades are required by the registered governance gates. A higher win rate alone is insufficient. Sector strength uses an unofficial leave-target-out basket; current-universe and adjusted-history biases remain. Costs assume 15.5 bps commission + 5 bps slippage each side, no taxes. Stops cannot guarantee loss limits across gaps.

Loss associations and every original trade are in trade_diagnostics.json/.csv. Source checks are in quality_recheck.json. These audits never retrospectively change the frozen comparison inputs.
