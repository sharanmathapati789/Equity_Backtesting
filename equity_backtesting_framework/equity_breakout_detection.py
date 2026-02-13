"""
This module implements the pre-filter stage for the Equity Breakout Detection process.
It screens a list of equities based on a set of technical criteria using daily data.
"""

import pandas as pd
from .fyers_service import FyersService
from . import config

def run_pre_filter_stage(fyers_service: FyersService) -> pd.DataFrame:
    """
    Runs the entire pre-filter stage for all equities defined in the config.

    This function orchestrates the process of:
    1. Loading the list of symbols from the specified CSV file.
    2. Fetching daily historical data for each symbol.
    3. Applying a series of technical filters (trend, price action, candle strength, etc.).
    4. Returning a DataFrame containing only the symbols that pass all filters.

    :param fyers_service: An initialized instance of the FyersService.
    :return: A pandas DataFrame named `Pre_filtered_data` with a single 'symbol' column.
    """
    try:
        symbols_df = pd.read_csv(config.GENERAL_CONFIG['Nifty_SmallCap_csv_path'])
        symbols = symbols_df['fyers_symbol'].tolist()
    except FileNotFoundError:
        print(f"Error: Symbol file not found at '{config.GENERAL_CONFIG['Nifty_SmallCap_csv_path']}'")
        return pd.DataFrame(columns=['symbol'])

    print(f"--- Starting Pre-Filter Stage for {len(symbols)} symbols ---")
    pre_filtered_symbols = []

    for symbol in symbols:
        # Fetch sufficient historical data for indicator calculation (e.g., 50 days).
        df = fyers_service.get_historical_data(symbol, resolution='D', days_lookback=50)

        if df is None or df.empty or len(df) < 20:
            # print(f"Could not get sufficient data for {symbol}. Skipping.")
            continue

        # --- Prepare Data ---
        # Calculate 15-period EMA
        df['ema15'] = df['close'].ewm(span=config.EQUITY_BREAKOUT_DETECTION_CONFIG['ema_period'], adjust=False).mean()

        # Ensure we have enough data for lookbacks (T-1 to T-6)
        if len(df) < 8:
            continue

        # Define reference days based on the end of the dataframe (latest data is T-1)
        yest = df.iloc[-1]   # Yesterday (T-1)
        day_2 = df.iloc[-2]  # 2 days ago (T-2)
        day_3 = df.iloc[-3]  # 3 days ago (T-3)

        # --- Apply Filters ---
        # 1. Price Filter: Previous day's close within range
        price_cond = config.EQUITY_BREAKOUT_DETECTION_CONFIG['price_min'] <= yest['close'] <= config.EQUITY_BREAKOUT_DETECTION_CONFIG['price_max']

        # 2. Trend Filters
        ema_slope_cond = yest['ema15'] > day_2['ema15']  # Upward EMA slope
        price_above_ema_cond = yest['low'] > yest['ema15']  # PDL > EMA(15)

        # 3. Price Action Filters
        higher_high_cond = yest['high'] > day_2['high']  # PDH > 2DH
        close_above_2dh_cond = yest['close'] > day_2['high']  # Previous Day Close > 2DH
        higher_low_cond = yest['low'] > day_2['low']  # PDL > 2DL

        # 4. Candle Strength Filters
        candle_range = yest['high'] - yest['low']
        marubozu_cond = False
        close_in_top_range_cond = False

        if candle_range > 0:
            # Marubozu-type candle
            wick_pct = config.EQUITY_BREAKOUT_DETECTION_CONFIG['candle_strength_wick_pct']
            upper_wick = yest['high'] - yest['close']
            lower_wick = yest['open'] - yest['low']
            marubozu_cond = (upper_wick < wick_pct * candle_range) and (lower_wick < wick_pct * candle_range)

            # Close in Top 20% of Range
            close_pct = config.EQUITY_BREAKOUT_DETECTION_CONFIG['close_top_pct_of_range']
            close_in_top_range_cond = ((yest['close'] - yest['low']) / candle_range) > close_pct

        # Bullish Engulfing
        engulfing_cond = (yest['open'] < day_2['close']) and (yest['close'] > day_2['open'])

        candle_strength_cond = engulfing_cond or marubozu_cond or close_in_top_range_cond

        # 5. Market Structure Filters
        # PDH > Max High of last 5 days (excluding yesterday)
        max_high_last_5_days = df.iloc[-6:-1]['high'].max()  # T-2, T-3, T-4, T-5, T-6
        swing_high_cond = yest['high'] > max_high_last_5_days

        # Last 3 days show Higher Highs & Higher Lows
        hh_hl_3_days_cond = (yest['high'] > day_2['high'] > day_3['high']) and \
                            (yest['low'] > day_2['low'] > day_3['low'])

        # --- Final Check ---
        all_conditions = {
            "Price": price_cond,
            "EMA Slope": ema_slope_cond,
            "Price > EMA": price_above_ema_cond,
            "Higher High": higher_high_cond,
            "Close > 2DH": close_above_2dh_cond,
            "Higher Low": higher_low_cond,
            "Candle Strength": candle_strength_cond,
            "Swing High": swing_high_cond,
            "HH/HL Structure": hh_hl_3_days_cond,
        }

        if all(all_conditions.values()):
            print(f"✅ PASSED: {symbol} met all pre-filter criteria.")
            pre_filtered_symbols.append(symbol)
        else:
            # Optional: Uncomment for detailed debugging to see which filter failed
            failed_filters = [key for key, value in all_conditions.items() if not value]
            if failed_filters:
                print(f"❌ FAILED: {symbol} (Reason: {', '.join(failed_filters)})")


    pre_filtered_df = pd.DataFrame(pre_filtered_symbols, columns=['symbol'])
    print(f"\n--- Pre-filtering complete. Found {len(pre_filtered_df)} potential breakout stocks. ---")
    return pre_filtered_df
