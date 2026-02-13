"""
This module implements the granular breakout analysis for the 09:15-09:20 window.
It scores equities based on microstructure, relative strength, and other factors.
"""

import pandas as pd
import numpy as np
from datetime import datetime, time
from .fyers_service import FyersService
from . import config

def _calculate_vwap(df):
    """Calculates VWAP for a given period."""
    q = df['volume'].values
    p = (df['high'] + df['low'] + df['close']) / 3
    return np.sum(p * q) / np.sum(q) if np.sum(q) != 0 else 0

def _print_summary_table():
    """Prints the breakout quality scoring table to the console."""
    table = """
| Criteria                                     | Condition                                                              | Score    |
|----------------------------------------------|------------------------------------------------------------------------|----------|
| ✅ Green Candle Count (3–5)                  | At least 3 of 5 1-min candles are green (Close > Open)                 | +1 to +3 |
| ✅ Strong Body Candle Present                | (Close - Open) ≥ 0.6 × (High - Low) for at least 1 candle              | +1       |
| ✅ Volume Confirmation                       | Cumulative Vol (09:15–09:20) > 2x avg 5-min vol (last 20 candles)      | +2       |
| ✅ Price > PDH                               | Close at 09:20 > Previous Day High                                     | +1       |
| ✅ Price > ORH + Sustained > VWAP/PDH        | Close > ORH AND price above VWAP/PDH for ≥ 3 of 5 candles              | +1       |
| ✅ Relative Strength > 0.3%                  | RS = Stock return - Index return > 0.3%                                | +1       |
| ✅ Trend Alignment with HTF                  | Price > EMA(20) on 15m AND EMA20 has positive slope                    | +1       |
| ❌ Trap/Exhaustion Filters                   | Rejection wicks, high volume reversals, or overextension               | Reject   |
"""
    print("\n--- Breakout Quality Scoring Table ---")
    print(table)

def analyze_breakout_quality(pre_filtered_df: pd.DataFrame, fyers_service: FyersService, backtest_date: datetime) -> pd.DataFrame:
    """
    Analyzes stocks from the pre-filtered list for breakout quality in the 09:15-09:20 window.

    :param pre_filtered_df: DataFrame of symbols that passed the pre-filter stage.
    :param fyers_service: An initialized instance of the FyersService.
    :param backtest_date: The specific date for the backtest.
    :return: A DataFrame with symbols and their breakout quality scores.
    """
    if pre_filtered_df.empty:
        print("No pre-filtered stocks to analyze for breakout quality.")
        return pd.DataFrame()

    _print_summary_table()

    qualified_stocks = []

    # Fetch index data for relative strength calculation
    index_symbol = config.GENERAL_CONFIG['Index_Symbol']
    index_df_1min = fyers_service.get_historical_data(index_symbol, '1', days_lookback=2)

    if index_df_1min.empty:
        print(f"Could not fetch index data for {index_symbol}. Cannot perform relative strength analysis.")
        return pd.DataFrame()

    for symbol in pre_filtered_df['symbol']:
        print(f"\nAnalyzing {symbol} for 09:15-09:20 breakout...")

        # 1. Fetch all necessary data for the symbol
        df_1min = fyers_service.get_historical_data(symbol, '1', days_lookback=2)
        df_5min = fyers_service.get_historical_data(symbol, '5', days_lookback=5)
        df_15min = fyers_service.get_historical_data(symbol, '15', days_lookback=5)
        df_daily = fyers_service.get_historical_data(symbol, 'D', days_lookback=5)

        if any(df.empty for df in [df_1min, df_5min, df_15min, df_daily]):
            print(f"Could not fetch complete data for {symbol}. Skipping.")
            continue

        # 2. Isolate the 09:15-09:20 data window
        start_time = backtest_date.replace(hour=9, minute=15, second=0, microsecond=0)
        end_time = backtest_date.replace(hour=9, minute=20, second=0, microsecond=0)

        candles_0915_0920 = df_1min[(df_1min.index >= start_time) & (df_1min.index < end_time)]
        if len(candles_0915_0920) != 5:
            print(f"Did not find exactly 5 1-min candles for {symbol} between 09:15-09:20. Found {len(candles_0915_0920)}. Skipping.")
            continue

        score = 0

        # --- Step 1: Microstructure Analysis ---
        green_candles = candles_0915_0920[candles_0915_0920['close'] > candles_0915_0920['open']]
        is_strong_body = ((candles_0915_0920['close'] - candles_0915_0920['open']).abs() >=
                          config.BREAKOUT_LOGIC_CONFIG['strong_body_candle_pct'] * (candles_0915_0920['high'] - candles_0915_0920['low']))

        # Volume confirmation
        prev_day_5min_candles = df_5min[df_5min.index.date < backtest_date.date()].tail(20)
        avg_5min_vol = prev_day_5min_candles['volume'].mean()
        cumulative_vol = candles_0915_0920['volume'].sum()
        volume_confirmed = cumulative_vol > config.BREAKOUT_LOGIC_CONFIG['volume_spike_multiplier'] * avg_5min_vol

        if len(green_candles) >= 3: score += min(len(green_candles) - 2, 3)
        if is_strong_body.any(): score += 1
        if volume_confirmed: score += 2

        # --- Step 2: Relative Strength vs Index ---
        stock_open = candles_0915_0920.iloc[0]['open']
        stock_close = candles_0915_0920.iloc[-1]['close']
        stock_return = (stock_close / stock_open) - 1

        index_candles = index_df_1min[(index_df_1min.index >= start_time) & (index_df_1min.index < end_time)]
        if len(index_candles) == 5:
            index_open = index_candles.iloc[0]['open']
            index_close = index_candles.iloc[-1]['close']
            index_return = (index_close / index_open) - 1
            rs = stock_return - index_return
            if rs > config.BREAKOUT_LOGIC_CONFIG['relative_strength_threshold']:
                score += 1

        # --- Step 3: Sustained Price Positioning ---
        pdh = df_daily[df_daily.index.date < backtest_date.date()].iloc[-1]['high']
        orh = candles_0915_0920['high'].max()
        vwap = _calculate_vwap(candles_0915_0920)

        if stock_close > pdh: score += 1
        sustained_above = (candles_0915_0920['close'] > vwap).sum() >= 3 or (candles_0915_0920['close'] > pdh).sum() >= 3
        if stock_close > orh and sustained_above: score += 1

        # --- Step 4: Trend Alignment from Higher Timeframe ---
        htf_candles = df_15min[df_15min.index < start_time].tail(5)
        if len(htf_candles) > 1:
            htf_candles['ema20'] = htf_candles['close'].ewm(span=20, adjust=False).mean()
            last_htf_candle = htf_candles.iloc[-1]
            prev_htf_candle = htf_candles.iloc[-2]
            if last_htf_candle['close'] > last_htf_candle['ema20'] and last_htf_candle['ema20'] > prev_htf_candle['ema20']:
                score += 1

        # --- Step 6: Trap/Exhaustion Filter ---
        candle_0919 = candles_0915_0920.iloc[3] # 09:19 candle
        is_trap = False
        if candle_0919['volume'] == candles_0915_0920['volume'].max():
            upper_wick = candle_0919['high'] - candle_0919['close']
            candle_range = candle_0919['high'] - candle_0919['low']
            if candle_range > 0 and (upper_wick / candle_range) > config.BREAKOUT_LOGIC_CONFIG['exhaustion_wick_pct']:
                is_trap = True
                print(f"Filter: {symbol} rejected due to potential exhaustion wick on 09:19 candle.")

        total_move = (orh / stock_open) - 1
        if total_move > config.BREAKOUT_LOGIC_CONFIG['overextension_pct']:
            is_trap = True
            print(f"Filter: {symbol} rejected due to overextension > {config.BREAKOUT_LOGIC_CONFIG['overextension_pct']*100}%.")

        if is_trap:
            continue

        # --- Final Score Check ---
        if score >= config.BREAKOUT_LOGIC_CONFIG['breakout_quality_min_score']:
            print(f"✅ QUALIFIED: {symbol} passed with a score of {score}/10.")
            qualified_stocks.append({'symbol': symbol, 'breakout_score': score, 'timestamp': end_time})

    return pd.DataFrame(qualified_stocks)
