"""
Main orchestrator for the Equity Backtesting Framework.

This script manages the entire backtesting workflow, including:
- Looping through backtesting days.
- Initializing services and managers.
- Orchestrating the execution of different analysis modules at the correct times.
- Simulating the passage of time during a trading day.
- Generating final reports.
"""

import pandas as pd
from datetime import datetime, timedelta, time
import time as system_time
import logging

# --- Module Imports ---
from . import config
from .utils import setup_logging
from .fyers_service import FyersService
from .equity_breakout_detection import run_pre_filter_stage
from .breakout_logic import analyze_breakout_quality
from .initial_breakouts import initial_breakouts
from .stage_breakouts import StageBreakoutsManager
# Renamed to avoid confusion with the manager class
from .intraday_equity_spurts_monitor import SpurtMonitorManager as SpurtMonitorManager_Class, get_spurt_monitor_manager
from .order_manager import OrderManager

def run_backtest_for_day(backtest_date: datetime, fyers_service: FyersService):
    """
    Encapsulates the entire backtesting logic for a single trading day.
    """
    date_str = backtest_date.strftime('%Y-%m-%d')
    setup_logging(date_str)
    logging.info(f"========== Starting Backtest for {date_str} ==========")

    # 1. Initialize all managers and services for the day
    order_manager = OrderManager()
    stage_breakouts_manager = StageBreakoutsManager()
    # The SpurtMonitorManager needs the fyers_service and order_manager instances
    spurt_monitor_manager = SpurtMonitorManager_Class(fyers_service, order_manager)


    # 2. Pre-Market Analysis (run before 09:15)
    logging.info("--- Running Pre-Market Analysis ---")
    pre_filtered_df = run_pre_filter_stage(fyers_service)
    if pre_filtered_df.empty:
        logging.warning("No stocks passed the pre-filter stage. Ending backtest for the day.")
        return

    # 3. Pre-fetch all data for the day to simulate a live environment efficiently
    logging.info("--- Pre-fetching all data for the day ---")
    symbols_to_track = pre_filtered_df['symbol'].tolist()
    daily_data_map = {s: fyers_service.get_historical_data(s, 'D', 30) for s in symbols_to_track}
    data_1min_map = {s: fyers_service.get_historical_data(s, '1', 2) for s in symbols_to_track}
    data_5min_map = {s: fyers_service.get_historical_data(s, '5', 2) for s in symbols_to_track}

    # 4. 09:15-09:20 Analysis
    logging.info("--- Analyzing 09:15-09:20 Breakout Quality ---")
    breakout_quality_df = analyze_breakout_quality(pre_filtered_df, fyers_service, backtest_date)
    logging.info(f"Found {len(breakout_quality_df)} stocks with high breakout quality scores.")

    # 5. Simulate the trading day from 09:15 to 15:30
    logging.info("--- Starting Intraday Simulation ---")
    current_time = backtest_date.replace(hour=9, minute=15, second=0, microsecond=0)
    end_time = backtest_date.replace(hour=15, minute=30, second=0, microsecond=0)

    while current_time <= end_time:
        loop_start_time = system_time.time()
        current_time_str = current_time.strftime('%H:%M')

        # --- Time-based Triggers ---

        # At 09:20, run the first initial_breakouts check
        if current_time.time() == time(9, 20):
            logging.info(f"[{current_time_str}] Running initial breakouts check (09:20)")
            # Create the 5-min candle from 1-min data
            df_0915_5min = pd.concat([df.loc[current_time-timedelta(minutes=5):current_time] for df in data_1min_map.values()]).groupby('symbol').agg(
                {'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}
            )
            initial_breakouts(breakout_quality_df, pre_filtered_df, df_0915_5min.reset_index(), daily_data_map, current_time.time())

        # On 5-minute intervals (e.g., 09:25, 09:30...)
        if current_time.minute % 5 == 0 and current_time.time() > time(9, 20):
            logging.info(f"[{current_time_str}] Running 5-minute interval checks...")

            # Get the latest 5-min candle for all tracked symbols
            latest_5min_candles_list = []
            for symbol in symbols_to_track:
                if symbol in data_5min_map and not data_5min_map[symbol].empty:
                    candle = data_5min_map[symbol][data_5min_map[symbol].index == current_time]
                    if not candle.empty:
                        # Enrich candle with required data for stage_breakouts
                        enriched_candle = candle.iloc[0].copy()
                        enriched_candle['symbol'] = symbol
                        # These would be pre-calculated in a more advanced system
                        enriched_candle['pdh'] = daily_data_map[symbol].iloc[-2]['high']
                        enriched_candle['avg20_volume'] = daily_data_map[symbol].iloc[-21:-1]['volume'].mean()
                        enriched_candle['atr14'] = daily_data_map[symbol]['high'].sub(daily_data_map[symbol]['low']).rolling(14).mean().iloc[-1]
                        latest_5min_candles_list.append(enriched_candle)

            if latest_5min_candles_list:
                latest_5min_df = pd.DataFrame(latest_5min_candles_list)

                # Run stage breakouts
                stage_breakouts_manager.process_new_data(latest_5min_df.set_index('candle_ts'))

                # Run initial breakouts check again
                initial_breakouts(breakout_quality_df, pre_filtered_df, latest_5min_df, daily_data_map, current_time.time())

        # --- Per-Minute Processes ---

        # Get latest 1-min data for all monitored stocks
        latest_1min_data_map = {}
        for symbol in list(spurt_monitor_manager.monitored_stocks.keys()):
            if symbol in data_1min_map and not data_1min_map[symbol].empty:
                candle = data_1min_map[symbol][data_1min_map[symbol].index == current_time]
                if not candle.empty:
                    latest_1min_data_map[symbol] = candle.iloc[0]

        # Process spurts and open positions
        if latest_1min_data_map:
            spurt_monitor_manager.process_new_1min_data(latest_1min_data_map, current_time)
            order_manager.process_new_data(latest_1min_data_map)

        # Advance time
        current_time += timedelta(minutes=1)
        # Optional: sleep to simulate real-time passage
        # system_time.sleep(max(0, 0.1 - (system_time.time() - loop_start_time)))

    # 6. End of Day Wrap-up
    logging.info("--- Trading session finished. Wrapping up. ---")
    eod_prices = {s: df.iloc[-1]['close'] for s, df in data_1min_map.items() if not df.empty}
    order_manager.close_all_positions_eod(eod_prices)
    order_manager.generate_daily_report()

    logging.info(f"========== Backtest for {date_str} Finished ==========\n")


if __name__ == '__main__':
    try:
        # NOTE: FyersService requires interactive login for the first time to get an access token.
        # Ensure your credentials are set in config.py and you have a valid access_token.txt
        # or are ready to log in via the browser when prompted.
        fyers_service = FyersService()

        num_days = config.GENERAL_CONFIG.get('Backtesting_days', 1)

        for i in range(num_days):
            # Backtest from T-1, T-2, ...
            # This needs to be adjusted to only consider trading days.
            # For simplicity, we'll just go back calendar days.
            backtest_day = datetime.now() - timedelta(days=i + 1)

            # A proper implementation would use a trading calendar to skip weekends/holidays.
            if backtest_day.weekday() >= 5: # Skip weekends
                continue

            run_backtest_for_day(backtest_day, fyers_service)

    except Exception as e:
        logging.error(f"An unexpected error occurred in the main orchestrator: {e}", exc_info=True)
