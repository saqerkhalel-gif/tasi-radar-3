# Walk-Forward Results

These are three purged, chronological REUSED temporal tests, not virgin OOS. Parameters were registered before this run and remain fixed; no best fold/configuration is selected. Each test starts with fresh cash, closes at fold end and is reported independently; do not sum fold returns as a continuous portfolio. Training is an expanding observed prefix, separated by 20 sessions. Feature warm-up uses only the known prefix; there is no future fit.

## Fold 1
Train 2025-04-21–2026-02-03 (202 sessions); purge 2026-02-04–2026-03-04; test 2026-03-05–2026-05-31.

| Strategy | Trades | Win % | Mean win % | Mean loss % | Expectancy % | Portfolio % | Max DD % | Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| early_reversal | 12 | 33.3333 | 7.3429 | -4.8715 | -0.8001 | -1.0556 | -2.9664 | -1.1154 |
| trend_pullback | 0 | NA | NA | NA | NA | 0.0 | 0.0 | NA |
| breakout_retest | 1 | 0.0 | NA | -3.9881 | -3.9881 | -0.3988 | -0.3988 | -2.3195 |
| early_reversal__rs20_only | 14 | 35.7143 | 3.7409 | -5.0251 | -1.8944 | -3.0219 | -3.0219 | -2.762 |
| early_reversal__no_extension_guard | 23 | 34.7826 | 10.1093 | -5.1567 | 0.1532 | -2.4796 | -2.5873 | -1.9213 |
| early_reversal__no_pattern_support | 19 | 36.8421 | 5.6787 | -4.6402 | -0.8385 | -1.1892 | -2.6099 | -0.7254 |
| trend_pullback__rs20_only | 0 | NA | NA | NA | NA | 0.0 | 0.0 | NA |
| trend_pullback__no_extension_guard | 0 | NA | NA | NA | NA | 0.0 | 0.0 | NA |
| trend_pullback__no_pattern_support | 0 | NA | NA | NA | NA | 0.0 | 0.0 | NA |
| breakout_retest__rs20_only | 6 | 16.6667 | 2.3669 | -5.0462 | -3.8107 | -2.0682 | -2.4587 | -3.0843 |
| breakout_retest__no_extension_guard | 1 | 0.0 | NA | -3.9881 | -3.9881 | -0.3988 | -0.3988 | -2.3195 |
| breakout_retest__no_pattern_support | 1 | 0.0 | NA | -3.9881 | -3.9881 | -0.3988 | -0.3988 | -2.3195 |
| simple_breakout20 | 13 | 30.7692 | 4.4504 | -4.9463 | -2.055 | -2.6027 | -2.7718 | -2.4301 |
| simple_ema50 | 10 | 10.0 | 10.5153 | -4.9633 | -3.4154 | -3.2992 | -3.7324 | -3.4334 |
| original | 7 | 42.8571 | 7.7655 | -3.1872 | 1.5068 | 1.0407 | -1.6922 | 1.5197 |
| original_risk_matched | 7 | 42.8571 | 7.7655 | -3.1872 | 1.5068 | 1.0767 | -1.6553 | 1.5943 |

## Fold 2
Train 2025-04-21–2026-04-26 (254 sessions); purge 2026-04-27–2026-05-31; test 2026-06-01–2026-08-10.

| Strategy | Trades | Win % | Mean win % | Mean loss % | Expectancy % | Portfolio % | Max DD % | Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| early_reversal | 12 | 41.6667 | 6.1288 | -3.2021 | 0.6858 | 0.7347 | -1.8165 | 0.6882 |
| trend_pullback | 2 | 50.0 | 2.9157 | -3.8673 | -0.4758 | -0.1698 | -0.8424 | -0.4738 |
| breakout_retest | 0 | NA | NA | NA | NA | 0.0 | 0.0 | NA |
| early_reversal__rs20_only | 13 | 38.4615 | 6.1288 | -3.5915 | 0.1471 | 0.2288 | -2.2072 | 0.2255 |
| early_reversal__no_extension_guard | 23 | 39.1304 | 11.6334 | -3.8632 | 2.2007 | 2.6916 | -2.4174 | 1.6557 |
| early_reversal__no_pattern_support | 23 | 43.4783 | 6.1684 | -3.7734 | 0.5491 | 1.825 | -2.6007 | 1.3593 |
| trend_pullback__rs20_only | 4 | 50.0 | 4.7447 | -2.7247 | 1.01 | 0.3281 | -0.8224 | 0.6359 |
| trend_pullback__no_extension_guard | 2 | 50.0 | 2.9157 | -3.8673 | -0.4758 | -0.1698 | -0.8424 | -0.4738 |
| trend_pullback__no_pattern_support | 3 | 66.6667 | 7.4656 | -3.8673 | 3.688 | 1.1069 | -1.3111 | 1.8295 |
| breakout_retest__rs20_only | 5 | 40.0 | 5.5904 | -5.8142 | -1.2524 | -0.2765 | -0.9764 | -0.3801 |
| breakout_retest__no_extension_guard | 2 | 0.0 | NA | -4.7601 | -4.7601 | -0.8765 | -0.8765 | -4.8082 |
| breakout_retest__no_pattern_support | 1 | 100.0 | 9.2816 | NA | 9.2816 | 0.9282 | -0.2588 | 3.0641 |
| simple_breakout20 | 16 | 37.5 | 6.6745 | -3.9191 | 0.0535 | 0.1631 | -3.0376 | 0.1732 |
| simple_ema50 | 15 | 33.3333 | 6.8646 | -4.279 | -0.5645 | -0.7321 | -3.8923 | -0.7154 |
| original | 14 | 21.4286 | 7.9516 | -3.9112 | -1.3692 | -1.9176 | -3.9367 | -1.7932 |
| original_risk_matched | 14 | 21.4286 | 7.9516 | -3.9112 | -1.3692 | -1.7541 | -3.9057 | -1.6687 |

## Fold 3
Train 2025-04-21–2026-07-13 (305 sessions); purge 2026-07-14–2026-08-10; test 2026-08-11–2026-10-21.

| Strategy | Trades | Win % | Mean win % | Mean loss % | Expectancy % | Portfolio % | Max DD % | Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| early_reversal | 7 | 28.5714 | 7.3909 | -4.0663 | -0.7928 | -0.5702 | -2.734 | -0.5804 |
| trend_pullback | 3 | 33.3333 | 1.596 | -5.1854 | -2.9249 | -0.8533 | -1.4722 | -2.026 |
| breakout_retest | 3 | 0.0 | NA | -2.5092 | -2.5092 | -0.7523 | -1.5337 | -2.0666 |
| early_reversal__rs20_only | 9 | 33.3333 | 4.9278 | -4.1802 | -1.1442 | -0.9524 | -3.3019 | -0.8155 |
| early_reversal__no_extension_guard | 12 | 25.0 | 9.059 | -3.8828 | -0.6473 | -0.8241 | -3.6663 | -0.6359 |
| early_reversal__no_pattern_support | 17 | 23.5294 | 6.374 | -3.7217 | -1.3462 | -1.0962 | -2.9856 | -1.0495 |
| trend_pullback__rs20_only | 3 | 33.3333 | 1.596 | -5.1854 | -2.9249 | -0.8533 | -1.4722 | -2.026 |
| trend_pullback__no_extension_guard | 3 | 33.3333 | 1.596 | -5.1854 | -2.9249 | -0.8533 | -1.4722 | -2.026 |
| trend_pullback__no_pattern_support | 4 | 25.0 | 4.9564 | -4.9584 | -2.4797 | -1.0504 | -1.5138 | -2.3396 |
| breakout_retest__rs20_only | 5 | 20.0 | 12.2811 | -3.9577 | -0.71 | -0.1264 | -1.1819 | -0.2304 |
| breakout_retest__no_extension_guard | 3 | 0.0 | NA | -2.5092 | -2.5092 | -0.7523 | -1.5337 | -2.0666 |
| breakout_retest__no_pattern_support | 3 | 0.0 | NA | -2.5092 | -2.5092 | -0.7523 | -1.5337 | -2.0666 |
| simple_breakout20 | 8 | 12.5 | 3.06 | -3.9334 | -3.0592 | -2.3031 | -3.6608 | -2.415 |
| simple_ema50 | 9 | 22.2222 | 8.7399 | -3.693 | -0.9302 | -0.7029 | -1.7141 | -0.759 |
| original | 4 | 0.0 | NA | -3.9109 | -3.9109 | -1.5582 | -1.5582 | -2.8006 |
| original_risk_matched | 4 | 0.0 | NA | -3.9109 | -3.9109 | -1.4432 | -1.5339 | -2.8272 |
