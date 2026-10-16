"""Unit & Integration Tests for SET-QuantAI (Executable with standard Python)
"""

import unittest
import sys
from pathlib import Path
from datetime import datetime, date
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from set_quantai.core.compliance import SETCompliance
from set_quantai.core.models import FundamentalStatement, OHLCVBar, MarketDirection
from set_quantai.fundamental_screener.piotroski import PiotroskiCalculator
from set_quantai.fundamental_screener.altman_z import AltmanZCalculator
from set_quantai.technical_analyser.wyckoff_structure import WyckoffEngine
from set_quantai.technical_analyser.vsa import VSAEngine
from set_quantai.technical_analyser.confluence import ConfluenceEngine
from set_quantai.risk_guard.risk_manager import RiskGuard
from set_quantai.watchlist_manager.manager import WatchlistManager
from set_quantai.core.pipeline import QuantAIPipeline


class TestSETQuantAI(unittest.TestCase):
    def test_set_tick_sizes(self):
        # SET Tick ladder
        self.assertEqual(SETCompliance.get_tick_size(1.50), 0.01)
        self.assertEqual(SETCompliance.get_tick_size(3.50), 0.02)
        self.assertEqual(SETCompliance.get_tick_size(8.00), 0.05)
        self.assertEqual(SETCompliance.get_tick_size(18.00), 0.10)
        self.assertEqual(SETCompliance.get_tick_size(45.00), 0.25)
        self.assertEqual(SETCompliance.get_tick_size(150.00), 0.50)
        self.assertEqual(SETCompliance.get_tick_size(250.00), 1.00)
        self.assertEqual(SETCompliance.get_tick_size(500.00), 2.00)

    def test_board_lot_rounding(self):
        # Must round down to multiples of 100
        self.assertEqual(SETCompliance.round_board_lot(99), 0)
        self.assertEqual(SETCompliance.round_board_lot(100), 100)
        self.assertEqual(SETCompliance.round_board_lot(189), 100)
        self.assertEqual(SETCompliance.round_board_lot(2350), 2300)

    def test_ceiling_floor(self):
        ceiling, floor = SETCompliance.calculate_ceiling_floor(10.00)
        self.assertEqual(ceiling, 13.00)
        self.assertEqual(floor, 7.00)

    def test_piotroski_score(self):
        base_stmt1 = FundamentalStatement(
            symbol="TEST",
            period_date=date(2023, 12, 31),
            revenue=100.0,
            gross_profit=40.0,
            operating_profit_ebit=15.0,
            net_income=10.0,
            total_assets=100.0,
            working_capital=20.0,
            retained_earnings=30.0,
            book_value_equity=50.0,
            total_liabilities=50.0,
            long_term_debt=20.0,
            current_assets=40.0,
            current_liabilities=20.0,
            shares_outstanding=100,
            cfo=15.0,
        )
        base_stmt2 = FundamentalStatement(
            symbol="TEST",
            period_date=date(2024, 12, 31),
            revenue=120.0,
            gross_profit=55.0,
            operating_profit_ebit=20.0,
            net_income=15.0,
            total_assets=110.0,
            working_capital=25.0,
            retained_earnings=45.0,
            book_value_equity=65.0,
            total_liabilities=45.0,
            long_term_debt=15.0,
            current_assets=50.0,
            current_liabilities=20.0,
            shares_outstanding=100,
            cfo=25.0,
        )
        result = PiotroskiCalculator.calculate([base_stmt1, base_stmt2])
        self.assertGreaterEqual(result.f_score, 8)
        self.assertTrue(result.passed)

    def test_altman_z_score(self):
        safe_stmt = FundamentalStatement(
            symbol="TEST",
            period_date=date(2024, 12, 31),
            revenue=100.0,
            gross_profit=40.0,
            operating_profit_ebit=20.0,
            net_income=15.0,
            total_assets=100.0,
            working_capital=30.0,
            retained_earnings=30.0,
            book_value_equity=60.0,
            total_liabilities=40.0,
            long_term_debt=10.0,
            current_assets=50.0,
            current_liabilities=20.0,
            shares_outstanding=100,
            cfo=20.0,
        )
        res = AltmanZCalculator.calculate(safe_stmt)
        self.assertFalse(res.is_disqualified)
        self.assertIn(res.zone, ["SAFE", "GREY"])

    def test_risk_guard_position_sizing(self):
        rg = RiskGuard(account_capital=1_000_000.0, risk_per_trade_percent=1.5)
        bars = [
            OHLCVBar(timestamp=datetime.now(), open=49.0, high=51.0, low=49.0, close=50.0, volume=1000000)
            for _ in range(30)
        ]
        res = rg.calculate_risk_parameters(entry_price=50.0, bars=bars, target_price=65.0)
        self.assertEqual(res.shares_allocated % 100, 0)
        self.assertGreaterEqual(res.reward_risk_ratio, 2.0)

    def test_watchlist_manager(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_yaml = Path(tmp_dir) / "test_watchlist.yaml"
            wm = WatchlistManager(config_file=test_yaml)
            item = wm.add_symbol("SCB", notes="ธนาคารขนาดใหญ่", priority=1, target_price=120.0)
            self.assertEqual(item.symbol, "SCB")
            self.assertIn("SCB", wm.get_symbols())

            wm.remove_symbol("SCB")
            self.assertNotIn("SCB", wm.get_symbols())

    def test_pipeline_integration(self):
        pipeline = QuantAIPipeline()
        report = pipeline.analyze_symbol("PTT")
        self.assertEqual(report.symbol, "PTT")
        self.assertGreater(report.f_score.f_score, 0)
        self.assertGreaterEqual(report.risk.shares_allocated, 100)
        self.assertNotEqual(report.ai_explainer.headline_th, "")


if __name__ == "__main__":
    unittest.main()
