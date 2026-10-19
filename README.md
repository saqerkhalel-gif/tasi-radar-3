# TASI Radar 3.0 — free-data prototype

**Status: working prototype source code; NOT deployed to GitHub; NOT a complete TASI scan; NOT backtested.**

## How to run

```bash
python -m pip install -r requirements.txt
pytest -q
python radar.py
```

`output/latest.json`, `output/latest.csv` and a dated JSON file document successful symbols, missing symbols, actual date range, failures, source and coverage **relative to the supplied CSV**. The sample CSV has 14 example symbols, **not the full TASI constituent universe**. Coverage over the CSV must not be described as coverage of the entire Saudi market.

To deploy: create a GitHub repository, upload all files including `.github/workflows/radar.yml`, enable Actions, then run `TASI Radar 3.0 EOD` using `Run workflow`. Scheduled scans are attempted Sun–Thu 16:30 Saudi time, but GitHub may delay or skip scheduled workflows. Results are downloadable as Actions artifacts for 90 days. This setup **does not send phone notifications or sync reports into ChatGPT**.

## Data sources and limitations

- Yahoo Finance via `yfinance` (`NNNN.SR`): unofficial free source. Ticker availability, history, adjusted prices and volume may vary. Verify against Saudi Exchange before relying on signals.
- `data/tasi_symbols.csv`: hand-written starter sample, NOT maintained automatically. For full-market scans, replace with an authoritative dated Saudi Exchange main-market constituents CSV. Verify symbols and distinguish REITs from operating companies. Record universe snapshot and date.
- Benchmark `^TASI.SR` may be unavailable; relative strength is omitted if missing.
- Technical scan needs >=220 valid daily bars per symbol. A short history (e.g. newly transferred stocks) is logged as a failure, not a valid scan.
- Volume Profile cannot be inferred reliably from daily OHLCV; Elliott Wave is not scored.
- Fibonacci uses the 90-session extrema and their chronological order, a **mechanical approximation** of a swing, not a validated discretionary pivot; manually verify any resulting setup.
- The target is a **conditional mathematical scenario** and not a prediction; extension targets may be unrealistic. No automated order placement.
- Event Radar (filings, capital actions, market transfers), sector leadership, comprehensive historical backtest, forward outcome tracking, alert deduplication and notification integrations **are not implemented**. They must be built and tested separately before claiming full feature compliance.
- The daily workflow does not run in this chat. Uploading the files and enabling GitHub Actions is required.

## Data audit

The report's `scanned_successfully` counts only tickers with enough valid OHLCV data and completed indicator calculations. `coverage_pct` denominator is the provided CSV only. `failures` gives the reason per rejected symbol. For an actual TASI coverage claim, first establish an authoritative, dated, complete main-market symbol list and compare it with successful scans.

## Risk controls

Entry and Partial Entry require an independent price + volume trigger, EMA trend, upside >=10%, reward/risk >=2, and ATR <=12% of price. These are preliminary research rules, not optimized or backtested. `Early Watch` and `Wait` are **not** entry recommendations. Alerts should only be implemented after deduplication and validation.
