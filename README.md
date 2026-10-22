# TASI Radar 3.0 — auditable end-of-day research

## Schedule and reliable outputs

GitHub Actions runs **Sunday–Thursday at 14:35 UTC = 17:35 Riyadh (UTC+3, no DST)**, after continuous trading, closing auction and trade-at-last (15:20 Riyadh). It can also be dispatched manually, and runs after changes to analysis/configuration/tests. GitHub schedules may be delayed; inspect `run_utc`, `completed_utc` and `expected_session`, not just the green workflow badge. This repository supplies data for the existing ~19:00 ChatGPT task; no additional task or notification channel is created.

Every successful run commits these UTF-8 files to `main`:

- `output/benchmark.csv`: accumulated observed TASI closes for subsequent runs.
- `output/manifest.json`: latest run identity, expected session, actual counts, history location.
- `output/latest.json` and `.csv`: all analyzed companies, classifications, missing indicators, freshness and failures.
- `output/top20.json` and `.csv`: up to 20 ranked **technical candidates**, including unconfirmed Early Watch/Wait; not 20 guaranteed entries.
- `output/watchlist.json`: 7200, 2350, 1150, 1321, 7201, 3008; classification/freshness changes, prior trigger/invalidation crossings and >=5% price changes across distinct price dates. The first observation is a baseline.
- `output/history/<run_id>_<attempt>/`: immutable copies for that run.

All outputs are also uploaded as `tasi-radar-results-<run_id>-<attempt>` Actions artifacts for **90 days**, including when output validation/persistence fails. `source_commit` identifies the analysis revision; `run_url`, `run_id` and `run_attempt` identify the producing run. Output-only commits do not trigger another scan. Concurrent jobs queue instead of overwriting each other mid-publication. Repository write failures fail the workflow, while artifact upload still runs. The prior stored report remains visibly dated if a later scan fails before publication.

### Reading from the existing ChatGPT task

Fetch `output/manifest.json`, then `output/history/<run_id>_<attempt>/latest.json`, `top20.json`, and `watchlist.json` from the **same history directory** to avoid mixing two runs. Compare `expected_session` and every stock's `last_bar` before discussing entries. A successful calculation on stale history is not fresh-session coverage. `coverage_pct` and `fresh_coverage_pct` are separate. Benchmark errors are separate from stock failures.

## Freshness and Relative Strength

`exchange_calendars` XSAU defines weekends/holidays; add announced exceptional closures to `extra_closed_dates`. Its continuous-session close is extended locally to **15:20 Riyadh** so an incomplete session is excluded. A missing/out-of-range calendar fails rather than assuming weekdays. Keep calendar dependencies updated as exchange announcements change.

Yahoo history is requested through an **explicit exclusive end date one day after the completed session**. Future/incomplete/off-calendar rows are removed. When Yahoo supplies a completed daily OHLCV row with a null Close, its own `regularMarketPrice` can repair only that Close: quote date must match the expected session, timestamp must be 10:00–15:20 Riyadh, exchange timezone must be Riyadh, volume positive and quote within the raw High/Low. This quote is read only after the completed-session gate. Every such repair is recorded per stock with timestamp/value/source; a previous-day or out-of-range quote is rejected. Historical OHLC prices are adjusted by their published Adj Close / Close ratios; the current final-session quote has factor 1. Each stock reports `first_bar`, `last_bar`, `bars`, `expected_session`, and `data_fresh`. Stale data can be inspected but **cannot yield Entry/Partial Entry**. If Yahoo has not published the completed session, the report discloses this; it does not invent a candle or relabel old data as current.

TASI first requests `^TASI.SR`. Historical daily TASI closes from Investing.com instrument **11319**, verified against the Yahoo current close, are bootstrapped in `data/tasi_benchmark_seed.csv` with source metadata. The scanner merges this observed history with the prior run's `output/benchmark.csv` and new Yahoo index observations, then saves the extended benchmark history. If dates are still missing or stale it attempts the public Investing.com API. This lets GitHub continue to compute RS even if the vendor blocks GitHub's direct historical request. Every source used is disclosed; missing observations are never filled. Any overlapping closes must agree within 0.5%, otherwise the fallback is rejected. This is the same TASI index, not an ETF or synthetic benchmark. Benchmark ingestion validates **Close alone**, avoiding accidental rejection of index rows because of missing/zero Volume or OHLC. RS20/RS60 are **percentage-point excess returns**: 100 × (stock end/start − TASI end/start), on exactly 21/61 synchronized XSAU dates. There is **no forward fill or fabricated zero**. A missing date returns null plus a reason. Each horizon includes start/end dates and both component returns. Missing/stale TASI or missing synchronized RS blocks entry.

## Entry gates and ranking

Entry requires a close above the previous 20-session resistance; Partial Entry requires an EMA20 reclaim. Both additionally require volume >=1.5 times the **prior** 20-session mean (today excluded), Close > EMA20 > EMA50 and Close > EMA200, >=200 actual bars, all required indicators and both synchronized RS horizons, fresh stock and benchmark, potential upside >=10%, reward/risk >=2, and ATR/Close <=12%. Each blocked condition is listed in `entry_blockers`.

Support/resistance exclude the current bar. Invalidation uses the closer of prior support and Close−2×ATR, below the current close. First objective is the prior 90-session high above price; after that has been cleared, one conditional 127.2% swing extension may be used, only within 30% upside. These are mechanical conditional scenarios, not validated forecasts. No target is forced merely to pass the 10% filter. Forecast window: next 5–20 sessions, conditional on confirmation; recomputation is not proof that a previous trade thesis was invalidated.

Ranking first separates fresh/stale, then Entry/Partial Entry/Early Watch/Wait, then technical score, with a deterministic symbol tie-break. Score weights: trend 25, breakout 15, reclaim 8, volume 15, MACD above signal 8, RSI 45–70 7, contraction 5, higher lows 5, positive RS20/60 6 each; stale penalty 30 and low-history penalty 15. Rankings are not probability estimates or backtested returns. Price, date, volume, prior average, RSI, MACD/signal/histogram, EMA20/50/200, support/resistance, triggers, invalidation, target, upside and reward/risk appear in both formats.

## Short histories and coverage

The unchanged CSV contains **254 unique company symbols**. Validation rejects duplicate/invalid/Nomu symbols and fund ranges/names. This is a fixed universe snapshot, not a claim that it is a continuously refreshed official constituent list.

A company with even one valid completed daily OHLCV bar receives a partial analysis; unavailable indicators are null, never filled from invented history. `confidence` is low below 60 bars, medium with incomplete history/benchmark/freshness, and high only when the full indicator and freshness checks pass. Analyzed does not mean entry-eligible. Source/normalization/calculation failures are reported separately; they are not silently removed from the denominator.

## Validation

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python radar.py
python scripts/verify_output.py
```

Tests cover synchronized RS windows and missing dates, weekends/holidays/preclose, short listings, price/volume/reward/freshness entry gates, malformed OHLCV, no future-bar leakage, fixed universe, watchlist baselines and an end-to-end output audit. The workflow uses **pytest**, not unittest discovery. Output validation checks producing run identity, 254 unique accounted-for stocks, real success/failure/freshness counts and every published entry gate. Inspect the JSON for actual scan coverage; a green workflow is not 254 successful fresh analyses.

## Sources and limits

- Investing.com TASI history: https://www.investing.com/indices/tasi-historical-data (public historical API instrument 11319, no credentials).
- Yahoo Finance/yfinance: unofficial adjusted daily OHLCV; availability, accuracy and publication delays are outside the scanner's control. Prices are adjusted, not necessarily the unadjusted exchange last-trade quote.
- XSAU calendar: https://github.com/gerrymanoim/exchange_calendars/blob/master/exchange_calendars/exchange_calendar_xsau.py
- Exchange hours: https://www.saudiexchange.sa/wps/portal/saudiexchange/rules-guidance/capital-market-overview/trading-cycle-and-times
- yfinance exclusive end-date semantics: https://ranaroussi.github.io/yfinance/reference/yfinance.functions.html

No orders, notification delivery, news scoring, Elliott Wave, intraday volume profile or return guarantees are implemented. Technical outputs are research scenarios and require price/date verification before use.
