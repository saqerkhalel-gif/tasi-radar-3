"""Read-only diagnosis of completed historical trades. No strategy promotion."""
import argparse
import json
import math
from collections import Counter
from pathlib import Path

def diagnose(report):
    period = report["full_period"]
    trades = period["trades"]
    if not trades:
        raise ValueError("No historical trades to diagnose")
    winners = [t for t in trades if t["net_return_pct"] > 0]
    losers = [t for t in trades if t["net_return_pct"] <= 0]
    avg_win = sum(t["net_return_pct"] for t in winners) / len(winners) if winners else 0
    avg_loss = sum(t["net_return_pct"] for t in losers) / len(losers) if losers else 0
    required_win_rate = abs(avg_loss) / (avg_win + abs(avg_loss)) * 100 if avg_win > 0 and avg_loss < 0 else None
    exits = Counter(t["exit_reason"] for t in trades)
    by_reason = {}
    for reason in sorted(exits):
        subset = [t["net_return_pct"] for t in trades if t["exit_reason"] == reason]
        by_reason[reason] = {"count": len(subset), "average_net_return_pct": round(sum(subset)/len(subset), 4)}
    chronological = sorted(trades, key=lambda t: (t["entry_date"], t["symbol"]))
    midpoint = len(chronological) // 2
    def half(items):
        return {"count": len(items), "wins": sum(t["net_return_pct"] > 0 for t in items),
                "mean_net_return_pct": round(sum(t["net_return_pct"] for t in items)/len(items), 4)}
    return {
        "source_run_utc": report.get("run_utc"),
        "historical_only": True,
        "not_prospective_or_live": True,
        "trade_count": len(trades),
        "win_rate_pct": round(100*len(winners)/len(trades), 4),
        "expectancy_pct": round(sum(t["net_return_pct"] for t in trades)/len(trades), 4),
        "breakeven_win_rate_at_observed_payoffs_pct": round(required_win_rate, 4) if required_win_rate is not None else None,
        "exit_reasons": by_reason,
        "earlier_half": half(chronological[:midpoint]),
        "later_half": half(chronological[midpoint:]),
        "warning": "Descriptive in-sample diagnostics, not an improved strategy or out-of-sample win rate."
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="output/backtest.json")
    p.add_argument("--output", default="output/research/entry_quality_audit.json")
    args = p.parse_args()
    report = json.loads(Path(args.input).read_text())
    result = diagnose(report)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
