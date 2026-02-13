import unittest
import pandas as pd
from datetime import datetime, time
from unittest.mock import patch

# Import the class to be tested
from equity_backtesting_framework.stage_breakouts import StageBreakoutsManager
from equity_backtesting_framework import config

class TestStageBreakouts(unittest.TestCase):

    def setUp(self):
        """Set up a manager instance and base candle data for tests."""
        self.manager = StageBreakoutsManager()

        # Base data for a candle that passes all filters
        self.base_candle = {
            'symbol': 'TEST-EQ',
            'open': 99,
            'high': 105,
            'low': 98,
            'close': 102, # open < pdh, close >= pdh
            'volume': 2000, # > 1.8 * 1000
            'pdh': 100,
            'avg20_volume': 1000,
            'atr14': 5, # body |102-99|=3 > 0.3*5=1.5
        }

        # Set config for predictability
        config.STAGE_BREAKOUTS_CONFIG['wick_threshold'] = 0.5
        config.STAGE_BREAKOUTS_CONFIG['vol_multiplier'] = 1.8
        config.STAGE_BREAKOUTS_CONFIG['atr_body_threshold'] = 0.3
        config.STAGE_BREAKOUTS_CONFIG['cool_off_minutes'] = 30
        config.STAGE_BREAKOUTS_CONFIG['stage_monitoring_end_time'] = "13:00"
        config.STAGE_BREAKOUTS_CONFIG['late_cutoff_time'] = "14:30"

    @patch('equity_backtesting_framework.stage_breakouts.intraday_equity_spurts_monitor')
    def test_pass_with_retest_confirmation(self, mock_spurts_monitor):
        """Test the full lifecycle: pending -> confirmed."""
        config.STAGE_BREAKOUTS_CONFIG['require_retest_confirmation'] = True

        # --- Candle 1: The breakout candle ---
        candle1_time = datetime(2023, 1, 3, 10, 30)
        candle1_df = pd.DataFrame([self.base_candle], index=[candle1_time])

        result1 = self.manager.process_new_data(candle1_df)

        # Assert that the breakout is pending and not yet confirmed
        self.assertTrue(result1.empty)
        self.assertIn('TEST-EQ', self.manager.pending_confirmation)
        self.assertTrue(self.manager.stage_breakers_df.empty)
        mock_spurts_monitor.assert_not_called()

        # --- Candle 2: The confirmation candle ---
        candle2_time = datetime(2023, 1, 3, 10, 35)
        candle2_data = self.base_candle.copy()
        candle2_data['open'] = 101
        candle2_data['close'] = 103 # Stays above PDH of 100
        candle2_df = pd.DataFrame([candle2_data], index=[candle2_time])

        result2 = self.manager.process_new_data(candle2_df)

        # Assert that the breakout is now confirmed
        self.assertEqual(len(result2), 1)
        self.assertEqual(result2['symbol'].iloc[0], 'TEST-EQ')
        self.assertNotIn('TEST-EQ', self.manager.pending_confirmation)
        self.assertEqual(len(self.manager.stage_breakers_df), 1)
        mock_spurts_monitor.assert_called_once()

    @patch('equity_backtesting_framework.stage_breakouts.intraday_equity_spurts_monitor')
    def test_fail_on_retest(self, mock_spurts_monitor):
        """Test the case where the confirmation candle fails the retest."""
        config.STAGE_BREAKOUTS_CONFIG['require_retest_confirmation'] = True

        # --- Candle 1: The breakout candle ---
        candle1_time = datetime(2023, 1, 3, 10, 30)
        candle1_df = pd.DataFrame([self.base_candle], index=[candle1_time])
        self.manager.process_new_data(candle1_df)
        self.assertIn('TEST-EQ', self.manager.pending_confirmation)

        # --- Candle 2: The failing confirmation candle ---
        candle2_time = datetime(2023, 1, 3, 10, 35)
        candle2_data = self.base_candle.copy()
        candle2_data['close'] = 99 # Closes back below PDH of 100
        candle2_df = pd.DataFrame([candle2_data], index=[candle2_time])

        result2 = self.manager.process_new_data(candle2_df)

        # Assert that the breakout was rejected and put into cool-off
        self.assertTrue(result2.empty)
        self.assertNotIn('TEST-EQ', self.manager.pending_confirmation)
        self.assertTrue(self.manager.stage_breakers_df.empty)
        self.assertIn('TEST-EQ', self.manager.cooled_off_stocks)
        mock_spurts_monitor.assert_not_called()

    def test_fail_on_volume_filter(self):
        """Test that a breakout is rejected if volume is too low."""
        candle_data = self.base_candle.copy()
        candle_data['volume'] = 500 # Less than 1.8 * 1000
        candle_df = pd.DataFrame([candle_data], index=[datetime(2023, 1, 3, 10, 30)])

        self.manager.process_new_data(candle_df)

        self.assertTrue(self.manager.stage_breakers_df.empty)
        self.assertIn('TEST-EQ', self.manager.cooled_off_stocks)

    def test_cool_off_mechanism(self):
        """Test that a stock in cool-off is ignored."""
        # First, fail a breakout to put the stock in cool-off
        candle1_data = self.base_candle.copy()
        candle1_data['volume'] = 500 # Fail volume
        candle1_time = datetime(2023, 1, 3, 10, 30)
        candle1_df = pd.DataFrame([candle1_data], index=[candle1_time])
        self.manager.process_new_data(candle1_df)
        self.assertIn('TEST-EQ', self.manager.cooled_off_stocks)

        # Second, try another breakout within the cool-off period
        candle2_time = datetime(2023, 1, 3, 10, 45) # 15 mins later < 30 min cool-off
        candle2_df = pd.DataFrame([self.base_candle], index=[candle2_time])
        self.manager.process_new_data(candle2_df)

        # Assert it's still not a breaker because it should have been ignored
        self.assertTrue(self.manager.stage_breakers_df.empty)

if __name__ == '__main__':
    unittest.main()
