# Data quality

{
  "configured_universe": 254,
  "fetched": 254,
  "latest_valid": 238,
  "historical_vendor_window_eligible": 14,
  "independently_validated_historical": 0,
  "historical_backtest_eligible": 0,
  "signal_eligible": 0,
  "published_raw_bar_valid": 252,
  "independent_current_bar_matched": 0,
  "execution_bar_verifiable": 0,
  "quarantined": 239
}

Whole historical independent coverage remains0. Published latest validity, causal historical screening, point-in-time decision vintage, signal eligibility and independently executable raw bars are separate denominators. Look-ahead adjusted history is not replayed as new evidence. Current raw bars and candidate source windows are content-addressed objects; past predictions are never rescaled on revisions.

{
  "decision_feed": "Yahoo via production yfinance auto-adjusted; archived vintage only; no claim of historical PIT availability",
  "execution_feed": {
    "provider": "Yahoo Finance",
    "status": "RAW_DOWNLOAD_COMPLETED",
    "fetched_utc": "2026-10-27T07:20:32.331689+00:00",
    "basis": "published raw OHLCV, no auto adjustment/repair",
    "stock_raw_fetch_success": 254
  },
  "independent_probes": [
    {
      "source": "Saudi Exchange historical reports",
      "url": "https://www.saudiexchange.sa/wps/portal/saudiexchange/newsandreports/reports-publications/historical-reports",
      "http_status": 403,
      "response_sha256": "a5db30fc3505cd94b18b354a9e36a6fdb65c9830aa5d15820bdda51042bb0ccf",
      "status": "access_denied",
      "stock_ohlcv_coverage_count": 0,
      "access_wall_bypassed": false
    },
    {
      "source": "Saudi Exchange market watch",
      "url": "https://www.saudiexchange.sa/wps/portal/saudiexchange/ourmarkets/main-market-watch",
      "http_status": 403,
      "response_sha256": "afeb4cfd36aabacc0891822dc946764a383e852d85cbdf828162fe7eae658ec9",
      "status": "access_denied",
      "stock_ohlcv_coverage_count": 0,
      "access_wall_bypassed": false
    },
    {
      "source": "Mubasher public stock page",
      "url": "https://www.mubasher.info/markets/TDWL/stocks/7200/",
      "http_status": 200,
      "response_sha256": "89345fec8a73481c1391816b93de922b9b744745b5be5bcf194f5062c1359540",
      "status": "no_complete_dated_OHLCV_feed_verified",
      "stock_ohlcv_coverage_count": 0,
      "access_wall_bypassed": false
    },
    {
      "source": "Stooq TASI CSV",
      "url": "https://stooq.com/q/d/l/?s=%5Etasi&i=d&d1=20250501&d2=20261022",
      "http_status": 200,
      "response_sha256": "99ed86c4e596856007a53991dd8e68b77160d82d01a261fb351f7f596b0b6449",
      "status": "no_validated_machine_readable_index_history",
      "reason": "",
      "observed_overlap_sessions": 0,
      "stock_ohlcv_coverage_count": 0,
      "access_wall_bypassed": false
    }
  ],
  "independent_references_accepted": 0,
  "rights": "Yahoo personal/research-only notice: https://ranaroussi.github.io/yfinance/ ; no source wall/403/paywall/rate-limit bypass. Public quote page does not establish a licensed historical feed. Saudi Exchange public historical/market-watch and Mubasher/Stooq probes report actual coverage, not assumed entitlement. Twelve Data XSAU paid entitlement is not a verified free alternative.",
  "limits": "One bounded Yahoo batch (internal4 threads,240s timeout); four public probes20s each, no retry on denied access; no paid data. Complete raw download hashes retained, current raw bars sealed; full inputs in artifact90days.",
  "corporate_actions": "Raw dividends/splits and factor changes inspected; full rights/capital-action/PIT vintages unavailable; active position freezes on an action/revision."
}

Market-wide zero-volume dates:
[
  {
    "date": "2025-07-17",
    "observed": 243,
    "zero_volume": 222
  },
  {
    "date": "2025-09-25",
    "observed": 246,
    "zero_volume": 246
  },
  {
    "date": "2026-05-04",
    "observed": 251,
    "zero_volume": 251
  },
  {
    "date": "2026-08-16",
    "observed": 252,
    "zero_volume": 251
  }
]
