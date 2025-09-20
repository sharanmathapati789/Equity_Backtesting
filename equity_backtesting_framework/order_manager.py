"""
This module contains the OrderManager class, which simulates trade
execution and position management for the backtesting framework.
"""

import pandas as pd
from datetime import datetime

class OrderManager:
    """
    Manages the lifecycle of trades: execution, tracking, and closing.
    """
    def __init__(self):
        self.open_positions = []
        self.closed_trades = []
        self._trade_id_counter = 0

    def _get_next_trade_id(self):
        """Generates a unique ID for each trade."""
        self._trade_id_counter += 1
        return self._trade_id_counter

    def execute_buy_order(self, symbol: str, price: float, stop_loss: float, target: float, timestamp: datetime):
        """
        Simulates the execution of a BUY order and adds it to open positions.
        """
        # Prevent opening a new position if one already exists for the symbol
        if any(p['symbol'] == symbol for p in self.open_positions):
            print(f"Info: Position for {symbol} is already open. Ignoring new BUY signal.")
            return

        trade_id = self._get_next_trade_id()
        position = {
            'trade_id': trade_id,
            'symbol': symbol,
            'entry_price': price,
            'stop_loss': stop_loss,
            'target': target,
            'entry_timestamp': timestamp,
            'status': 'OPEN'
        }
        self.open_positions.append(position)
        print(f"--- Trade Executed [ID: {trade_id}] ---")
        print(f"  Symbol: {symbol}, Entry: {price:.2f}, SL: {stop_loss:.2f}, Tgt: {target:.2f}")

    def process_new_data(self, new_data_map: dict):
        """
        Processes a new data candle for each symbol to check for SL/TP hits.
        :param new_data_map: A dict of {symbol: latest_candle_series}
        """
        if not self.open_positions:
            return

        # Iterate over a copy as we might modify the list
        for position in self.open_positions[:]:
            symbol = position['symbol']
            if symbol in new_data_map:
                candle = new_data_map[symbol]
                exit_price = None
                exit_reason = None

                # 1. Check if target was hit
                if candle['high'] >= position['target']:
                    exit_price = position['target']
                    exit_reason = 'TARGET_HIT'

                # 2. Check if stop-loss was hit
                elif candle['low'] <= position['stop_loss']:
                    exit_price = position['stop_loss']
                    exit_reason = 'STOPLOSS_HIT'

                if exit_price is not None:
                    self._close_position(position, exit_price, candle.name, exit_reason)

    def _close_position(self, position: dict, exit_price: float, exit_timestamp: datetime, reason: str):
        """Moves a position from open to closed and records the P&L."""
        pnl = exit_price - position['entry_price']
        pnl_pct = (pnl / position['entry_price']) * 100

        closed_trade = {
            **position,
            'exit_price': exit_price,
            'exit_timestamp': exit_timestamp,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'status': 'CLOSED',
            'exit_reason': reason
        }
        self.closed_trades.append(closed_trade)
        self.open_positions.remove(position)

        print(f"--- Trade Closed [ID: {position['trade_id']}] ---")
        print(f"  Symbol: {position['symbol']}, Reason: {reason}, P&L: {pnl:.2f} ({pnl_pct:.2f}%)")

    def close_all_positions_eod(self, eod_prices_map: dict):
        """Closes all remaining open positions at the end of the day."""
        print("\n--- Closing all open positions at EOD ---")
        for position in self.open_positions[:]:
            symbol = position['symbol']
            if symbol in eod_prices_map:
                exit_price = eod_prices_map[symbol]
                self._close_position(position, exit_price, datetime.now(), 'EOD_CLOSE')
            else:
                # If no closing price is available, close at entry price for neutral P&L
                self._close_position(position, position['entry_price'], datetime.now(), 'EOD_CLOSE_NO_DATA')

    def generate_daily_report(self) -> pd.DataFrame:
        """Generates a summary DataFrame of all closed trades for the day."""
        if not self.closed_trades:
            return pd.DataFrame()

        report_df = pd.DataFrame(self.closed_trades)

        # Reorder columns for clarity
        cols = ['trade_id', 'symbol', 'status', 'exit_reason', 'entry_timestamp', 'exit_timestamp',
                'entry_price', 'exit_price', 'stop_loss', 'target', 'pnl', 'pnl_pct']
        report_df = report_df[cols]

        print("\n" + "="*80)
        print(" " * 30 + "DAILY TRADING REPORT")
        print("="*80)
        print(report_df.to_string())

        # --- Summary Metrics ---
        total_pnl = report_df['pnl'].sum()
        total_trades = len(report_df)
        winning_trades = len(report_df[report_df['pnl'] > 0])
        losing_trades = total_trades - winning_trades
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0

        print("\n--- Summary ---")
        print(f"Total Trades: {total_trades}")
        print(f"Win Rate: {win_rate:.2f}%")
        print(f"Total P&L: {total_pnl:.2f}")
        print("="*80)

        return report_df
