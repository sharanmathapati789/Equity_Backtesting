"""
This module identifies 'Stage_Breakouts' by processing 5-minute candles
after the initial market open. It uses a stateful manager to handle
retest confirmations and cool-off periods.
"""

import pandas as pd
from datetime import datetime, timedelta, time

from . import config
from .intraday_equity_spurts_monitor import intraday_equity_spurts_monitor

class StageBreakoutsManager:
    """
    Manages the logic for identifying and confirming Stage Breakouts.
    This class is stateful to handle retest confirmations and cool-off periods.
    """
    def __init__(self):
        self.stage_breakers_df = pd.DataFrame(columns=['symbol', 'stage_entry_point', 'candle_ts', 'source'])
        self.pending_confirmation = {}  # {symbol: {data}}
        self.cooled_off_stocks = {}  # {symbol: cool_off_end_time}

    def process_new_data(self, new_candles_df: pd.DataFrame):
        """
        Main method to be called with each new 5-minute data batch.

        :param new_candles_df: A DataFrame with the latest 5-minute candle for multiple stocks.
                               It MUST contain columns: symbol, open, high, low, close, volume,
                               pdh, avg20_volume, atr14. The index should be the candle timestamp.
        :return: A DataFrame of newly confirmed stage breakouts for this interval.
        """
        if new_candles_df.empty:
            return pd.DataFrame()

        newly_confirmed_breakers = []

        # --- 1. Process stocks pending retest confirmation from the PREVIOUS candle ---
        symbols_to_retest = list(self.pending_confirmation.keys())
        for symbol in symbols_to_retest:
            if symbol in new_candles_df['symbol'].values:
                latest_candle = new_candles_df[new_candles_df['symbol'] == symbol].iloc[0]
                pending_data = self.pending_confirmation[symbol]

                if latest_candle['close'] >= pending_data['pdh']:
                    # RETEST PASSED: Confirm the breakout
                    print(f"✅ Retest CONFIRMED for {symbol}.")
                    self._add_to_stage_breakers(pending_data)
                    newly_confirmed_breakers.append(pending_data)
                else:
                    # RETEST FAILED: Move to cool-off
                    print(f"❌ Retest FAILED for {symbol}. Closing price back below PDH.")
                    self._add_to_cool_off(symbol, latest_candle.name)

                del self.pending_confirmation[symbol]

        # --- 2. Process all new candles to find NEW breakouts ---
        for _, candle in new_candles_df.iterrows():
            symbol = candle['symbol']
            current_time = candle.name

            # Skip if symbol is in cool-off or pending confirmation
            if symbol in self.cooled_off_stocks and current_time < self.cooled_off_stocks[symbol]:
                continue
            if symbol in self.pending_confirmation:
                continue

            # --- Apply Time-based Filters ---
            cfg = config.STAGE_BREAKOUTS_CONFIG
            if not (time(9, 20) < current_time.time() <= time.fromisoformat(cfg['stage_monitoring_end_time'])):
                continue
            if current_time.time() >= time.fromisoformat(cfg['late_cutoff_time']):
                continue

            # --- Apply Breakout Rule and Filters ---
            breakout_rule = candle['open'] < candle['pdh'] and candle['close'] >= candle['pdh']
            if not breakout_rule:
                continue

            # Wick Filter
            candle_range = candle['high'] - candle['low']
            wick = candle['high'] - candle['close']
            wick_ok = candle_range == 0 or (wick / candle_range) <= cfg['wick_threshold']

            # Volume Filter
            volume_ok = candle['volume'] > cfg['vol_multiplier'] * candle['avg20_volume']

            # ATR Filter
            atr_ok = abs(candle['close'] - candle['open']) >= cfg['atr_body_threshold'] * candle['atr14']

            if wick_ok and volume_ok and atr_ok:
                breakout_data = {
                    'symbol': symbol,
                    'stage_entry_point': candle['high'],
                    'candle_ts': current_time,
                    'open': candle['open'], 'high': candle['high'], 'low': candle['low'], 'close': candle['close'],
                    'volume': candle['volume'], 'pdh': candle['pdh'], 'avg20_volume': candle['avg20_volume'],
                    'atr14': candle['atr14'], 'source': 'Stage_Breakouts'
                }

                if cfg['require_retest_confirmation']:
                    print(f"PENDING: {symbol} passed initial stage breakout filters. Awaiting retest confirmation.")
                    self.pending_confirmation[symbol] = breakout_data
                else:
                    # If retest is not required, confirm immediately
                    self._add_to_stage_breakers(breakout_data)
                    newly_confirmed_breakers.append(breakout_data)
            else:
                # Failed a filter, put it in cool-off
                self._add_to_cool_off(symbol, current_time)
                reasons = [f for f, ok in [('wick', wick_ok), ('volume', volume_ok), ('ATR', atr_ok)] if not ok]
                print(f"Log FAIL: {symbol} failed stage breakout filters ({', '.join(reasons)}). Adding to cool-off.")

        return pd.DataFrame(newly_confirmed_breakers)

    def _add_to_stage_breakers(self, data: dict):
        """Adds a confirmed breakout to the main DataFrame and triggers the monitor."""
        # De-duplication check
        existing = self.stage_breakers_df[self.stage_breakers_df['symbol'] == data['symbol']]
        if not existing.empty and data['stage_entry_point'] <= existing.iloc[0]['stage_entry_point']:
            print(f"Log: Ignoring duplicate breakout for {data['symbol']} with non-improving entry point.")
            return

        # Add or update entry
        self.stage_breakers_df = self.stage_breakers_df[self.stage_breakers_df['symbol'] != data['symbol']]
        new_breaker_df = pd.DataFrame([data])
        self.stage_breakers_df = pd.concat([self.stage_breakers_df, new_breaker_df], ignore_index=True)

        print(f"✅ CONFIRMED: {data['symbol']} added to Stage_breakers. Entry: {data['stage_entry_point']:.2f}")
        intraday_equity_spurts_monitor(data['symbol'], data['stage_entry_point'], data)

    def _add_to_cool_off(self, symbol: str, current_time: datetime):
        """Adds a symbol to the cool-off list."""
        cool_off_minutes = config.STAGE_BREAKOUTS_CONFIG['cool_off_minutes']
        self.cooled_off_stocks[symbol] = current_time + timedelta(minutes=cool_off_minutes)
        # Clean up old entries from cool-off list to prevent memory leak
        self.cooled_off_stocks = {s: t for s, t in self.cooled_off_stocks.items() if t > current_time}
