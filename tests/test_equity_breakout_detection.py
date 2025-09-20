import unittest
import pandas as pd
from datetime import datetime
from unittest.mock import MagicMock

# Import the function to be tested
from equity_backtesting_framework.equity_breakout_detection import run_pre_filter_stage
from equity_backtesting_framework import config

class TestEquityBreakoutDetection(unittest.TestCase):

    def setUp(self):
        """Set up a base DataFrame that passes all conditions by default."""
        # Generate 25 days of data to satisfy the len(df) < 20 check
        dates = pd.to_datetime([f'2023-01-{i+1:02d}' for i in range(25)])

        # Base data that is neutral
        base_data = {
            'open':  [100 + i*0.5 for i in range(25)],
            'high':  [102 + i*0.5 for i in range(25)],
            'low':   [99 + i*0.5 for i in range(25)],
            'close': [101 + i*0.5 for i in range(25)],
            'volume':[1000] * 25
        }
        self.df = pd.DataFrame(base_data, index=dates)

        # Now, carefully modify the last 8 rows to pass all conditions
        # This makes the logic clearer than crafting all 25 rows by hand

        # Make EMA low before the final ramp up
        self.df.loc[self.df.index[15:20], 'close'] = [110, 111, 112, 113, 114]

        # T-3, T-2, T-1 (indices -3, -2, -1)
        self.df.loc[self.df.index[-3], 'high'] = 131
        self.df.loc[self.df.index[-3], 'low'] = 124
        self.df.loc[self.df.index[-3], 'close'] = 130

        self.df.loc[self.df.index[-2], 'high'] = 136
        self.df.loc[self.df.index[-2], 'low'] = 129
        self.df.loc[self.df.index[-2], 'close'] = 135

        self.df.loc[self.df.index[-1], 'open'] = 135
        self.df.loc[self.df.index[-1], 'high'] = 140.5
        self.df.loc[self.df.index[-1], 'low'] = 135  # Ensures PDL > EMA
        self.df.loc[self.df.index[-1], 'close'] = 140 # Price is in range

        # Mock FyersService
        self.mock_fyers_service = MagicMock()

        config.GENERAL_CONFIG['Nifty_SmallCap_csv_path'] = './dummy_symbols.csv'
        config.EQUITY_BREAKOUT_DETECTION_CONFIG['price_min'] = 20
        config.EQUITY_BREAKOUT_DETECTION_CONFIG['price_max'] = 2000

    def test_pass_case(self):
        """Test a stock that should pass all pre-filter conditions."""
        pd.DataFrame({'fyers_symbol': ['PASS-EQ']}).to_csv('./dummy_symbols.csv', index=False)
        self.mock_fyers_service.get_historical_data.return_value = self.df
        result_df = run_pre_filter_stage(self.mock_fyers_service)
        self.assertEqual(len(result_df), 1, "The pass-case data did not result in a passed stock.")
        self.assertEqual(result_df['symbol'].iloc[0], 'PASS-EQ')

    def test_fail_price_too_low(self):
        """Test that a stock fails if its price is below the minimum."""
        pd.DataFrame({'fyers_symbol': ['FAIL-EQ']}).to_csv('./dummy_symbols.csv', index=False)
        fail_df = self.df.copy()
        fail_df.loc[fail_df.index[-1], 'close'] = 10
        self.mock_fyers_service.get_historical_data.return_value = fail_df
        result_df = run_pre_filter_stage(self.mock_fyers_service)
        self.assertTrue(result_df.empty)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
