"""
This module identifies 'Front_runners' based on the initial market move
at 09:20 and continues to monitor for opportunities from the pre-filtered
list after 09:25.
"""

import pandas as pd
from datetime import time

from . import config
# The 'intraday_equity_spurts_monitor' module will be created in a later step.
# We include the import here and a placeholder function to fulfill the dependency.
from .intraday_equity_spurts_monitor import intraday_equity_spurts_monitor

def initial_breakouts(
    breakout_quality_df: pd.DataFrame,
    pre_filtered_df: pd.DataFrame,
    data_monitoring_df: pd.DataFrame,
    daily_data_map: dict,
    current_time: time
) -> pd.DataFrame:
    """
    Identifies Front_runners by analyzing the 09:15-09:20 candle.

    :param breakout_quality_df: DataFrame of stocks with high breakout scores.
    :param pre_filtered_df: DataFrame of stocks from the pre-filter stage.
    :param data_monitoring_df: DataFrame with live 5-minute candle data for the day.
    :param daily_data_map: A dictionary mapping symbols to their daily historical data (for PDH).
    :param current_time: The current time to determine the logic path (09:20 or >=09:25).
    :return: A DataFrame of front-runners that have passed the initial checks.
    """
    front_runners_list = []

    # 1. Determine which symbols to evaluate based on the time
    if current_time == time(9, 20):
        symbols_to_eval = pd.concat([
            breakout_quality_df['symbol'],
            pre_filtered_df['symbol']
        ]).unique()
        print(f"\n--- Running initial_breakouts at 09:20 for {len(symbols_to_eval)} symbols ---")
    elif current_time >= time(9, 25):
        symbols_to_eval = pre_filtered_df['symbol'].unique()
        print(f"\n--- Running initial_breakouts at {current_time} for {len(symbols_to_eval)} pre-filtered symbols ---")
    else:
        return pd.DataFrame() # Return empty if not the right time

    # 2. Process each symbol
    for symbol in symbols_to_eval:
        # The data_monitoring_df is expected to be keyed by symbol and timestamp
        if 'symbol' not in data_monitoring_df.columns:
            print("Error: 'symbol' column not found in data_monitoring_df.")
            continue

        symbol_candles = data_monitoring_df[data_monitoring_df['symbol'] == symbol]

        # We are interested in the first 5-minute candle of the day (09:15-09:20)
        if symbol_candles.empty:
            # print(f"Log: No 09:15 candle data for {symbol} in data_monitoring_df. Skipping.")
            continue

        # Assuming the dataframe is sorted and the first entry is the 09:15 candle
        candle_0915 = symbol_candles.iloc[0]

        daily_df = daily_data_map.get(symbol)
        if daily_df is None or len(daily_df) < 2:
            print(f"Log: Missing daily data to calculate PDH for {symbol}. Skipping.")
            continue
        pdh = daily_df.iloc[-2]['high']

        # --- Apply Filters ---
        is_bullish = candle_0915['close'] > candle_0915['open']

        candle_range = candle_0915['high'] - candle_0915['low']
        has_small_wick = True
        if candle_range > 0:
            wick = candle_0915['high'] - candle_0915['close']
            wick_threshold = config.INITIAL_BREAKOUTS_CONFIG['wick_threshold']
            if wick > wick_threshold * candle_range:
                has_small_wick = False

        # --- Final Check ---
        if is_bullish and has_small_wick:
            initial_entry_point = candle_0915['high']
            open_above_pdh = candle_0915['open'] > pdh

            front_runner_row = {
                'symbol': symbol,
                'initial_entry_point': initial_entry_point,
                'open_above_pdh': open_above_pdh,
                'timestamp': candle_0915.name,
                'source': 'Initial_Breakouts'
            }
            front_runners_list.append(front_runner_row)

            print(f"Log PASS: {symbol} added to Front_runners. Entry: {initial_entry_point:.2f}")

            # As per requirement, trigger the next stage of monitoring for each accepted symbol
            intraday_equity_spurts_monitor(symbol, initial_entry_point, front_runner_row)
        else:
            reasons = []
            if not is_bullish: reasons.append('not_bullish')
            if not has_small_wick: reasons.append('long_wick')
            # print(f"Log FAIL: {symbol} ({', '.join(reasons)})")

    front_runners_df = pd.DataFrame(front_runners_list)
    return front_runners_df
