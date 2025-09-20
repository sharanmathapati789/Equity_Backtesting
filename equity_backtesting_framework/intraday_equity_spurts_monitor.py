"""
This module contains the SpurtMonitorManager, which is responsible for detecting
intraday price/volume surges around predefined entry points.
"""

import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta

from .fyers_service import FyersService
from . import config
from .order_manager import OrderManager

class SpurtMonitorManager:
    """
    A stateful manager to monitor equities for intraday spurts and trigger trades.
    """
    def __init__(self, fyers_service: FyersService, order_manager: OrderManager):
        self.fyers_service = fyers_service
        self.order_manager = order_manager
        self.monitored_stocks = {}  # {symbol: {entry_point, metadata, history_df}}
        self.spurts_df = pd.DataFrame()
        self.cooled_off_spurts = {}  # {symbol: cool_off_end_time}

        # Fetch and cache index data for relative strength calculations
        self.index_df_1min = self.fyers_service.get_historical_data(
            config.GENERAL_CONFIG['Index_Symbol'], '1', days_lookback=2
        )

    def add_stock_to_monitor(self, symbol: str, entry_point: float, metadata: dict):
        """Adds a stock to the monitoring list."""
        if symbol in self.monitored_stocks:
            print(f"Info: {symbol} is already being monitored.")
            return

        print(f"Adding {symbol} to Intraday Spurt Monitor. Entry point: {entry_point:.2f}")
        history_df = self.fyers_service.get_historical_data(symbol, '1', days_lookback=2)

        self.monitored_stocks[symbol] = {
            "entry_point": entry_point,
            "metadata": metadata,
            "history_df": history_df
        }

    def process_new_1min_data(self, new_1min_data_map: dict, current_time: datetime):
        """
        Main processing loop, called every minute with new 1-min candles.
        :param new_1min_data_map: A dict of {symbol: latest_1min_candle_series}
        """
        if not self.monitored_stocks:
            return

        for symbol, candle in new_1min_data_map.items():
            if symbol not in self.monitored_stocks:
                continue

            # Check cool-off period
            if symbol in self.cooled_off_spurts and current_time < self.cooled_off_spurts[symbol]:
                continue

            # Update history
            history = self.monitored_stocks[symbol]['history_df']
            history = pd.concat([history, pd.DataFrame([candle])])
            self.monitored_stocks[symbol]['history_df'] = history.tail(30) # Keep last 30 candles

            # Check for spurt
            is_spurt, score, context = self._check_for_spurt(symbol, current_time)

            if is_spurt:
                print(f"SPURT DETECTED for {symbol} with score {score:.0f}%")

                # Trigger Order Manager
                cfg = config.ORDER_MANAGER_CONFIG
                sl = candle['close'] * (1 - cfg['default_stop_loss_pct'] / 100)
                tgt = candle['close'] * (1 + cfg['default_target_pct'] / 100)
                self.order_manager.execute_buy_order(
                    symbol=symbol,
                    price=candle['close'],
                    stop_loss=sl,
                    target=tgt,
                    timestamp=current_time
                )

                # Add to outputs and cool-off list
                self._record_spurt(symbol, current_time, score, context)
                self._add_to_cool_off(symbol, current_time)

    def _check_for_spurt(self, symbol: str, current_time: datetime):
        """The core logic to analyze a stock for a spurt."""
        stock_data = self.monitored_stocks[symbol]
        history = stock_data['history_df']

        if len(history) < 20: return False, 0, {}

        latest = history.iloc[-1]
        past_20 = history.iloc[-20:-1]

        # --- Calculate indicators ---
        avg_move = (past_20['close'] - past_20['close'].shift(1)).abs().mean()
        avg_vol = past_20['volume'].mean()

        # --- Regime Awareness ---
        k, m = self._get_regime_multipliers(current_time.time())

        # --- Core Triggers ---
        price_surge = abs(latest['close'] - history.iloc[-2]['close']) > k * avg_move
        volume_spike = latest['volume'] > m * avg_vol

        # --- Context Filter ---
        entry_point = stock_data['entry_point']
        atr = history['high'].sub(history['low']).rolling(14).mean().iloc[-1]
        is_near_entry = abs(latest['close'] - entry_point) < (0.5 * atr)

        # --- Relative Strength ---
        rs_ok = self._check_relative_strength(history, current_time)

        # --- Scoring ---
        score = 0
        if price_surge: score += 50
        if volume_spike: score += 30
        if is_near_entry: score += 20

        if not rs_ok: score *= 0.5 # Penalize if not outperforming

        if score >= config.INTRADAY_SPURTS_MONITOR_CONFIG['weighted_score_threshold_pct']:
            context = {"price_surge": price_surge, "volume_spike": volume_spike, "near_entry": is_near_entry, "rs_ok": rs_ok}
            return True, score, context

        return False, score, {}

    def _get_regime_multipliers(self, current_time: time):
        cfg = config.INTRADAY_SPURTS_MONITOR_CONFIG
        if time(9, 15) <= current_time <= time(9, 45): # Opening Drive
            return cfg['price_momentum_surge_k'], cfg['volume_spike_m_large_cap']
        elif time(14, 30) <= current_time <= time(15, 30): # Closing Hour
            return cfg['price_momentum_surge_k'], cfg['volume_spike_m_mid_liquid']
        else: # Midday
            return cfg['price_momentum_surge_k'] * 1.4, cfg['volume_spike_m_large_cap'] * 1.2

    def _check_relative_strength(self, stock_history, current_time):
        """Checks if stock is outperforming index in last 15 mins."""
        if self.index_df_1min.empty: return True # Default to true if no index data

        end_time = current_time
        start_time = end_time - timedelta(minutes=15)

        stock_period = stock_history[(stock_history.index >= start_time) & (stock_history.index <= end_time)]
        index_period = self.index_df_1min[(self.index_df_1min.index >= start_time) & (self.index_df_1min.index <= end_time)]

        if len(stock_period) < 2 or len(index_period) < 2: return True

        stock_return = (stock_period.iloc[-1]['close'] / stock_period.iloc[0]['open']) - 1
        index_return = (index_period.iloc[-1]['close'] / index_period.iloc[0]['open']) - 1

        return stock_return > index_return

    def _record_spurt(self, symbol, timestamp, score, context):
        """Records a confirmed spurt to the spurts_df."""
        new_spurt = pd.DataFrame([{
            'Symbol': symbol,
            'TimeOfSpurt': timestamp,
            'SpurtScore%': score,
            'Context': str(context),
            'LifecycleStatus': 'Start'
        }])
        self.spurts_df = pd.concat([self.spurts_df, new_spurt], ignore_index=True)

    def _add_to_cool_off(self, symbol, current_time):
        """Adds a symbol to the cool-off list after a spurt."""
        cool_off_minutes = config.INTRADAY_SPURTS_MONITOR_CONFIG['cool_off_period_minutes']
        self.cooled_off_spurts[symbol] = current_time + timedelta(minutes=cool_off_minutes)

# --- Global Instance and Entry Point ---

# This manager will be instantiated once in the main application.
# For modularity, we define the entry point function that uses it.
# The main orchestrator will need to create the instance and pass it around,
# or we can use a global singleton pattern here. For simplicity in this context:
_manager_instance = None

def get_spurt_monitor_manager(fyers_service: FyersService):
    """Factory function to get a singleton instance of the manager."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = SpurtMonitorManager(fyers_service)
    return _manager_instance

def intraday_equity_spurts_monitor(symbol: str, entry_point: float, metadata: dict):
    """
    Entry point function to add a stock to the spurt monitor.
    This function is called from initial_breakouts and stage_breakouts.
    It assumes the manager instance has been created by the main app.
    """
    if _manager_instance is None:
        raise Exception("SpurtMonitorManager has not been initialized. Call get_spurt_monitor_manager() first.")
    _manager_instance.add_stock_to_monitor(symbol, entry_point, metadata)
