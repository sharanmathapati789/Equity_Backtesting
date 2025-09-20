import unittest
import pandas as pd
from datetime import time, datetime
from unittest.mock import patch, MagicMock

# Import the function to be tested
from equity_backtesting_framework.initial_breakouts import initial_breakouts
from equity_backtesting_framework import config

class TestInitialBreakouts(unittest.TestCase):

    def setUp(self):
        """Set up common data for tests."""
        self.b_q_df = pd.DataFrame({'symbol': ['BQ-PASS-EQ']})
        self.pre_filtered_df = pd.DataFrame({'symbol': ['PF-PASS-EQ']})

        # Daily data to provide PDH
        self.daily_data_map = {
            'BQ-PASS-EQ': pd.DataFrame({'high': [100, 105]}, index=pd.to_datetime(['2023-01-01', '2023-01-02'])),
            'PF-PASS-EQ': pd.DataFrame({'high': [200, 205]}, index=pd.to_datetime(['2023-01-01', '2023-01-02']))
        }

        # --- Pass Case Candle (Bullish, Small Wick) ---
        self.pass_candle_data = {
            'symbol': ['BQ-PASS-EQ', 'PF-PASS-EQ'],
            'open': [106, 206],
            'high': [112, 212],
            'low': [105, 205],
            'close': [111, 211], # Wick = 1, Range = 7. 1/7 < 0.3. Pass.
            'volume': [1000, 1000]
        }
        self.pass_monitoring_df = pd.DataFrame(
            self.pass_candle_data,
            index=[pd.to_datetime('2023-01-03 09:20:00')]*2
        )

        # --- Fail Case Candle (Long Wick) ---
        self.fail_wick_candle_data = self.pass_candle_data.copy()
        self.fail_wick_candle_data['high'] = [120, 220] # Wick = 9, Range = 15. 9/15 > 0.3. Fail.
        self.fail_wick_monitoring_df = pd.DataFrame(
            self.fail_wick_candle_data,
            index=[pd.to_datetime('2023-01-03 09:20:00')]*2
        )

        config.INITIAL_BREAKOUTS_CONFIG['wick_threshold'] = 0.3

    @patch('equity_backtesting_framework.initial_breakouts.intraday_equity_spurts_monitor')
    def test_pass_case_at_0920(self, mock_spurts_monitor):
        """Test the pass case at 09:20, evaluating both BQ and Pre-filtered stocks."""
        result_df = initial_breakouts(
            self.b_q_df,
            self.pre_filtered_df,
            self.pass_monitoring_df,
            self.daily_data_map,
            current_time=time(9, 20)
        )
        # Both stocks should pass and be added to front_runners
        self.assertEqual(len(result_df), 2)
        # Check that the monitor was called for both
        self.assertEqual(mock_spurts_monitor.call_count, 2)
        mock_spurts_monitor.assert_any_call('BQ-PASS-EQ', 112, unittest.mock.ANY)
        mock_spurts_monitor.assert_any_call('PF-PASS-EQ', 212, unittest.mock.ANY)

    @patch('equity_backtesting_framework.initial_breakouts.intraday_equity_spurts_monitor')
    def test_pass_case_after_0925(self, mock_spurts_monitor):
        """Test the pass case after 09:25, evaluating only Pre-filtered stocks."""
        result_df = initial_breakouts(
            self.b_q_df,
            self.pre_filtered_df,
            self.pass_monitoring_df,
            self.daily_data_map,
            current_time=time(9, 30)
        )
        # Only the pre-filtered stock should be evaluated and passed
        self.assertEqual(len(result_df), 1)
        self.assertEqual(result_df['symbol'].iloc[0], 'PF-PASS-EQ')
        # Check that the monitor was called only once
        self.assertEqual(mock_spurts_monitor.call_count, 1)
        mock_spurts_monitor.assert_called_with('PF-PASS-EQ', 212, unittest.mock.ANY)

    @patch('equity_backtesting_framework.initial_breakouts.intraday_equity_spurts_monitor')
    def test_fail_long_wick(self, mock_spurts_monitor):
        """Test that stocks with long wicks are filtered out."""
        result_df = initial_breakouts(
            self.b_q_df,
            self.pre_filtered_df,
            self.fail_wick_monitoring_df,
            self.daily_data_map,
            current_time=time(9, 20)
        )
        # No stocks should pass
        self.assertTrue(result_df.empty)
        # The monitor should not have been called
        self.assertEqual(mock_spurts_monitor.call_count, 0)

    @patch('equity_backtesting_framework.initial_breakouts.intraday_equity_spurts_monitor')
    def test_fail_not_bullish(self, mock_spurts_monitor):
        """Test that non-bullish (close <= open) candles are filtered out."""
        fail_bullish_df = self.pass_monitoring_df.copy()
        fail_bullish_df['close'] = fail_bullish_df['open'] - 1 # Make it a red candle

        result_df = initial_breakouts(
            self.b_q_df,
            self.pre_filtered_df,
            fail_bullish_df,
            self.daily_data_map,
            current_time=time(9, 20)
        )
        self.assertTrue(result_df.empty)
        self.assertEqual(mock_spurts_monitor.call_count, 0)

if __name__ == '__main__':
    unittest.main()
