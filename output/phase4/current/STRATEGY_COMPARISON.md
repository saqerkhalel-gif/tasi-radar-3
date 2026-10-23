# Strategy Comparison — Phase 4, shadow research

https://github.com/saqerkhalel-gif/tasi-radar-3/actions/runs/39941086262

Original 25 trades reproduced exactly. All 16 registered portfolios use identical dates, frozen inputs and execution costs. Original retains original sizing; the separately reported original_risk_matched isolates the effect of new risk caps.

| Strategy | Trades | Win % | Mean win % | Mean loss % | Expectancy % | Portfolio % | Max DD % | Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| early_reversal | 31 | 35.4839 | 7.7905 | -4.0441 | 0.1553 | 0.0605 | -2.9664 | 0.0446 |
| trend_pullback | 5 | 40.0 | 6.122 | -4.746 | -0.3988 | -0.4526 | -1.4918 | -0.4045 |
| breakout_retest | 4 | 0.0 | NA | -2.8789 | -2.8789 | -1.1481 | -1.5337 | -1.6536 |
| early_reversal__rs20_only | 35 | 34.2857 | 6.2523 | -4.2697 | -0.6621 | -2.8054 | -4.9566 | -0.8413 |
| early_reversal__no_extension_guard | 56 | 33.9286 | 11.2495 | -4.4029 | 0.9077 | -1.0537 | -3.7613 | -0.2326 |
| early_reversal__no_pattern_support | 59 | 35.5932 | 6.3806 | -4.0589 | -0.3431 | -1.4923 | -5.6312 | -0.3174 |
| trend_pullback__rs20_only | 7 | 42.8571 | 5.7754 | -3.9551 | 0.2151 | -0.1029 | -1.4919 | -0.0682 |
| trend_pullback__no_extension_guard | 5 | 40.0 | 6.122 | -4.746 | -0.3988 | -0.4526 | -1.4918 | -0.4045 |
| trend_pullback__no_pattern_support | 7 | 42.8571 | 8.6818 | -4.6856 | 1.0433 | 0.6531 | -1.5132 | 0.4482 |
| breakout_retest__rs20_only | 16 | 25.0 | 6.4572 | -4.8754 | -2.0422 | -2.4625 | -3.411 | -1.2961 |
| breakout_retest__no_extension_guard | 6 | 0.0 | NA | -2.9436 | -2.9436 | -1.6826 | -1.786 | -2.019 |
| breakout_retest__no_pattern_support | 5 | 20.0 | 15.4394 | -2.8789 | 0.7848 | 0.3774 | -1.3836 | 0.376 |
| simple_breakout20 | 37 | 29.7297 | 7.2089 | -4.2463 | -0.8407 | -3.0816 | -5.6805 | -0.9203 |
| simple_ema50 | 33 | 21.2121 | 9.255 | -4.3581 | -1.4705 | -4.5683 | -7.0094 | -1.6905 |
| original | 25 | 24.0 | 9.3703 | -3.7439 | -0.5965 | -1.5228 | -4.6152 | -0.5711 |
| original_risk_matched | 25 | 24.0 | 9.3703 | -3.7439 | -0.5965 | -1.2544 | -4.5911 | -0.481 |

## Higher-cost sensitivity

| Strategy | Trades | Win % | Mean win % | Mean loss % | Expectancy % | Portfolio % | Max DD % | Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| early_reversal | 31 | 35.4839 | 7.5751 | -4.2358 | -0.0448 | -0.5048 | -3.0629 | -0.1419 |
| trend_pullback | 5 | 40.0 | 5.9099 | -4.9364 | -0.5978 | -0.5451 | -1.5115 | -0.4958 |
| breakout_retest | 4 | 0.0 | NA | -3.073 | -3.073 | -1.223 | -1.5659 | -1.7492 |
| early_reversal__rs20_only | 35 | 34.2857 | 6.04 | -4.4609 | -0.8606 | -3.349 | -5.3015 | -1.0378 |
| early_reversal__no_extension_guard | 56 | 33.9286 | 11.0272 | -4.5939 | 0.7061 | -2.3352 | -3.9154 | -0.5701 |
| early_reversal__no_pattern_support | 59 | 33.8983 | 6.7481 | -4.2924 | -0.5498 | -2.5303 | -5.7799 | -0.5822 |
| trend_pullback__rs20_only | 7 | 42.8571 | 5.564 | -4.147 | 0.0149 | -0.2363 | -1.5116 | -0.1726 |
| trend_pullback__no_extension_guard | 5 | 40.0 | 5.9099 | -4.9364 | -0.5978 | -0.5451 | -1.5115 | -0.4958 |
| trend_pullback__no_pattern_support | 7 | 42.8571 | 8.4647 | -4.8761 | 0.8414 | 0.5162 | -1.5556 | 0.3596 |
| breakout_retest__rs20_only | 16 | 25.0 | 6.2445 | -5.0654 | -2.238 | -2.6576 | -3.4785 | -1.4079 |
| breakout_retest__no_extension_guard | 6 | 0.0 | NA | -3.1375 | -3.1375 | -1.7767 | -1.867 | -2.1279 |
| breakout_retest__no_pattern_support | 5 | 20.0 | 15.2088 | -3.073 | 0.5834 | 0.2683 | -1.4161 | 0.2699 |
| simple_breakout20 | 37 | 29.7297 | 6.9947 | -4.4377 | -1.0389 | -3.7064 | -6.0141 | -1.1205 |
| simple_ema50 | 33 | 21.2121 | 9.0367 | -4.5492 | -1.6673 | -5.1108 | -7.1931 | -1.9237 |
| original | 25 | 24.0 | 9.1518 | -3.9362 | -0.7951 | -2.0108 | -4.8474 | -0.7602 |
| original_risk_matched | 25 | 24.0 | 9.1518 | -3.9362 | -0.7951 | -1.6819 | -4.8078 | -0.656 |

TASI net buy/hold: -8.261781845946036%; cash: 0%. Trade expectancy is the mean net trade return; portfolio return uses daily marked equity, ten position slots, maximum 0.5% planned NAV risk/trade and 3% aggregate for new engines. No leverage. Gaps can exceed planned risk.

## Recommendations

- early_reversal: Shadow only; no promotion. minimum_50_trades, win_rate_40pct, positive_base_and_stress_expectancy, minimum_10_trades_each_fold, at_least_two_profitable_folds, adjusted_excess_ci_positive, new_prospective_20_trades
- trend_pullback: Shadow only; no promotion. minimum_50_trades, positive_base_and_stress_expectancy, minimum_10_trades_each_fold, at_least_two_profitable_folds, adjusted_excess_ci_positive, new_prospective_20_trades
- breakout_retest: Shadow only; no promotion. minimum_50_trades, win_rate_40pct, positive_base_and_stress_expectancy, minimum_10_trades_each_fold, at_least_two_profitable_folds, adjusted_excess_ci_positive, new_prospective_20_trades

Bootstrap intervals are descriptive, multiplicity-adjusted for 15 variants, dependent and based on a small reused sample; they do not establish a fresh out-of-sample result. No thresholds were retuned after these results.
