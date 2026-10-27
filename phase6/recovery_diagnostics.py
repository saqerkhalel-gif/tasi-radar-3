"""Phase 6.1: conservative eligibility blocker diagnostics (no data repair or trading).

Usage: python -m phase6.recovery_diagnostics --summary output/phase6/current/summary.json
       python -m phase6.recovery_diagnostics --summary ... --quality path/to/quality_report.json
All input is read-only. Reports never promote a symbol or invent independent evidence.
"""
from __future__ import annotations
import argparse
import collections
import json
from pathlib import Path


def diagnose(summary, quality=None):
    d = summary["data_denominators"]
    required = ("configured_universe", "fetched", "latest_valid",
                "historical_vendor_window_eligible",
                "independently_validated_historical", "historical_backtest_eligible",
                "signal_eligible", "execution_bar_verifiable")
    missing = [key for key in required if key not in d]
    if missing:
        raise ValueError("Missing required denominator(s): " + ", ".join(missing))
    universe = d["configured_universe"]
    if not isinstance(universe, int) or universe <= 0:
        raise ValueError("Invalid universe")
    if any(not isinstance(d[k], int) or not 0 <= d[k] <= universe for k in required):
        raise ValueError("Invalid denominators")
    result = {
        "phase": "6.1",
        "source_session": summary.get("source_session"),
        "denominators": {k: d[k] for k in required},
        "latest_coverage_pct": round(100 * d["latest_valid"] / universe, 2),
        "independent_history_validated": d["independently_validated_historical"] > 0,
        "historical_backtest_proven": d["historical_backtest_eligible"] > 0,
        "paper_execution_proven": d["execution_bar_verifiable"] > 0,
        "forward_signal_count": sum(s.get("eligible_signals", 0) for s in summary.get("strategies", [])),
        "blockers": [],
        "next_actions": [],
        "decision": "KEEP_SHADOW",
    }
    if d["independently_validated_historical"] == 0:
        result["blockers"].append("NO_INDEPENDENT_FULL_HISTORY")
        result["next_actions"].append(
            "Obtain lawful, independently dated historical OHLCV and corporate-action reference; "
            "verify complete series, not just last close. Do not bypass access controls.")
    if d["execution_bar_verifiable"] == 0:
        result["blockers"].append("NO_CORROBORATED_EXECUTION_BAR")
        result["next_actions"].append(
            "Match dated raw OHLCV including next-session open and volume against an independent permitted source; "
            "unmatched paper fills remain NOT_EXECUTABLE.")
    if d["signal_eligible"] == 0:
        result["blockers"].append("NO_SIGNAL_ELIGIBLE_STOCKS")
        result["next_actions"].append(
            "Inspect per-symbol eligibility_reasons and distinguish source mismatch, stale bars, "
            "corporate actions, missing sessions and zero-volume history before changing any gate.")
    if quality is not None:
        symbols = quality.get("symbols")
        if not isinstance(symbols, list):
            raise ValueError("quality.symbols must be a list")
        if len(symbols) != universe:
            raise ValueError("Quality symbol count differs from configured universe")
        if len({row["symbol"] for row in symbols}) != len(symbols):
            raise ValueError("Duplicate symbol in quality report")
        counts = collections.Counter(
            reason for row in symbols for reason in set(row.get("eligibility_reasons", []))
        )
        result["eligibility_reason_counts"] = dict(sorted(counts.items(), key=lambda x: (-x[1], x[0])))
        result["examples_by_reason"] = {
            reason: [row["symbol"] for row in symbols if reason in row.get("eligibility_reasons", [])][:10]
            for reason in result["eligibility_reason_counts"]
        }
        reported = sum(bool(row.get("signal_eligible")) for row in symbols)
        if reported != d["signal_eligible"]:
            raise ValueError("Signal eligibility denominator mismatch")
    else:
        result["eligibility_reason_counts"] = None
        result["next_actions"].append("Supply the detailed quality symbols report to identify actual root causes.")
    result["safety"] = {
        "changes_production": False,
        "releases_quarantine": False,
        "substitutes_prices": False,
        "claims_validated_data": False,
        "authorizes_live_orders": False,
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default="output/phase6/current/summary.json")
    parser.add_argument("--quality", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    summary = json.loads(Path(args.summary).read_text())
    quality = json.loads(Path(args.quality).read_text()) if args.quality else None
    result = diagnose(summary, quality)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
