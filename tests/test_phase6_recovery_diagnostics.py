import pytest
from phase6.recovery_diagnostics import diagnose


def fixture():
    return {
        "source_session": "2026-10-26",
        "data_denominators": {
            "configured_universe": 2, "fetched": 2, "latest_valid": 2,
            "historical_vendor_window_eligible": 1,
            "independently_validated_historical": 0,
            "historical_backtest_eligible": 0, "signal_eligible": 0,
            "execution_bar_verifiable": 0,
        },
        "strategies": [{"eligible_signals": 0}],
    }


def test_no_unverified_promotion():
    result = diagnose(fixture())
    assert result["decision"] == "KEEP_SHADOW"
    assert result["blockers"] == [
        "NO_INDEPENDENT_FULL_HISTORY",
        "NO_CORROBORATED_EXECUTION_BAR",
        "NO_SIGNAL_ELIGIBLE_STOCKS",
    ]
    assert not result["safety"]["authorizes_live_orders"]


def test_detailed_reasons_and_unique_symbols():
    quality = {"symbols": [
        {"symbol": "1000", "signal_eligible": False,
         "eligibility_reasons": ["missing_required_calendar_sessions", "stale_or_missing_signal_bar"]},
        {"symbol": "1001", "signal_eligible": False,
         "eligibility_reasons": ["missing_required_calendar_sessions"]},
    ]}
    result = diagnose(fixture(), quality)
    assert result["eligibility_reason_counts"]["missing_required_calendar_sessions"] == 2
    assert result["examples_by_reason"]["stale_or_missing_signal_bar"] == ["1000"]


def test_reject_bad_denominators():
    data = fixture()
    data["data_denominators"]["signal_eligible"] = 3
    with pytest.raises(ValueError, match="Invalid denominators"):
        diagnose(data)


def test_reject_quality_count_mismatch():
    with pytest.raises(ValueError, match="Quality symbol count"):
        diagnose(fixture(), {"symbols": [{"symbol": "1000"}]})
