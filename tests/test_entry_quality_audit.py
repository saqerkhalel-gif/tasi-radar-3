import unittest
from scripts.entry_quality_audit import diagnose

class TestAudit(unittest.TestCase):
    def test_breakeven_and_exit_reasons(self):
        report = {"full_period": {"trades": [
            {"symbol":"A","entry_date":"2026-01-01","net_return_pct":10,"exit_reason":"target"},
            {"symbol":"B","entry_date":"2026-01-02","net_return_pct":-5,"exit_reason":"stop"},
            {"symbol":"C","entry_date":"2026-01-03","net_return_pct":-5,"exit_reason":"stop"}
        ]}}
        result=diagnose(report)
        self.assertAlmostEqual(result["win_rate_pct"],33.3333,places=3)
        self.assertAlmostEqual(result["breakeven_win_rate_at_observed_payoffs_pct"],33.3333,places=3)
        self.assertEqual(result["exit_reasons"]["stop"]["count"],2)
        self.assertTrue(result["historical_only"])

if __name__ == "__main__":
    unittest.main()
