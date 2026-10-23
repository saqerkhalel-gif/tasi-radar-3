# Research Review — Phase 4

Registration: [d5c64e5](https://github.com/saqerkhalel-gif/tasi-radar-3/commit/d5c64e5e54545f3bc30b2872a963fd9d08dd8daf), before evaluation of the new independent engines. `phase4/plan.json` is the frozen specification; every core engine, ablation and reference is reported, even with zero trades. The previously examined 25 trades are not an independent discovery sample.

| Primary research | Finding relevant to the hypothesis | Limits here |
|---|---|---|
| Jegadeesh & Titman (1993), [Returns to Buying Winners and Selling Losers](https://doi.org/10.1111/j.1540-6261.1993.tb04702.x) | US cross-sectional momentum at 3–12 month horizons motivates testing synchronized relative returns. | Not evidence that Saudi daily signals or these exact 20/60/120-session thresholds are profitable. Long-only retail execution differs from the study portfolio. |
| Moskowitz, Ooi & Pedersen (2012), [Time Series Momentum](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum) | Persistence in a diversified futures/forwards universe motivates the trend/pullback hypothesis. | Different assets, horizon, leverage and shorting; this code is an experimental daily equity translation, not a replication. |
| Lo, Mamaysky & Wang (2000), [Foundations of Technical Analysis](https://www.nber.org/system/files/working_papers/w7613/w7613.pdf) | Computational pattern definitions allow testable conditional-return hypotheses. | Pattern recognition is not a guarantee of after-cost profitability. Our confirmed-pivot heuristics are not the paper's fitted algorithm. |
| Lehmann (1990), [Fads, Martingales, and Market Efficiency](https://www.nber.org/papers/w2533) | Short-horizon reversal motivates examining early reversal separately from momentum. | Weekly US reversal portfolios do not establish volume-based accumulation or daily TASI trading profits; costs and microstructure matter. |
| Bailey et al. (2015), [The Probability of Backtest Overfitting](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253) | Searching many configurations can produce misleading apparent winners. | We register and report all experiments, freeze thresholds, disclose reused tests and require prospective evidence. We do NOT claim to have computed/passed PBO. |

## Independent hypotheses

1. **Early Reversal & Accumulation:** a causal EMA20 reclaim or prior-five-session-high break, improving RSI/MACD, higher confirmed lows, contraction or stronger up-volume and improving relative strength may detect a transition before an EMA200 trend. It can catch bear-market bounces; no assumption that turnover proves institutional buying.
2. **Trend Continuation & Pullback:** rising EMA50 above EMA200, a prior EMA20 touch and a bullish recovery with synchronized positive relative strength may distinguish pullback resumption from extended chasing. It can enter late or miss sharp rebounds.
3. **Breakout & Retest:** a historical close above a frozen prior-20-session level, later narrow retest and recovery, persistent level holds and volume confirmation may avoid first-break failures. Not every breakout retests, and support may fail across a gap.

Each engine independently searches all 254 histories, not merely the original strategy's 25 trades. Ablations remove RS60/120 requirements, extension guard or pattern support ONE AT A TIME, never price/volume, trustworthy-data, minimum-10%-target or RR2 safeguards. Simple EMA50 reclaim and 20-session breakout references use the same causal target/risk framework; they are constrained trading references, not canonical published replications.

EMA, RSI, MACD, ATR and price action describe different aspects but are correlated. More indicators do not establish stronger evidence. Fibonacci retracements are exported as descriptive context only; this review has not established sufficient direct evidence for treating their exact levels as predictive, and they never manufacture a target. Nearest major confirmed overhead zones take priority; a target lacking 10% upside is rejected rather than skipped.

## Evidence limits

Current 254 constituents introduce survivorship bias; delisted names and historical constituent snapshots are unavailable. Vendor-adjusted history is retrospective and corporate-action vintages are incomplete. We cannot remove these biases by chronological splitting alone. Historical repaired dates remain quarantined, and a separate fresh-source audit never rewrites frozen comparison inputs. The independent index history has not been officially reconciled end-to-end. Calendar-complete vendor checks are necessary but not exchange certification.

Three purged chronological folds use fixed parameters, no optimization and no shuffled observations. Previously inspected dates remain reused historical evidence. Only observations recorded after registration and before their future execution session can become genuinely prospective shadow trades. Research objective 40% wins is never an adoption rule by itself; require positive after-cost expectancy, adequate counts, stable folds, risk-adjusted improvement with multiplicity-aware uncertainty and at least 20 new prospective trades. No automatic live promotion is implemented.
