"""
Centralized configuration file for the Equity Backtesting Framework.
"""

# General Configuration
GENERAL_CONFIG = {
    'Backtesting_days': 10,
    # Note: The user specified path was "/Users/Scripts/Equity/EQ_ST_EMA/Fyers/Nifty_SmallCap.csv".
    # Using a relative path for portability. The file loading logic should handle this.
    'Nifty_SmallCap_csv_path': 'Nifty_SmallCap.csv',
    'Index_Symbol': 'NSE:NIFTY50-INDEX',
}

# Fyers API Configuration
# IMPORTANT: Replace placeholders with your actual Fyers API credentials.
FYERS_CONFIG = {
    'client_id': 'YOUR_CLIENT_ID',
    'secret_key': 'YOUR_SECRET_KEY',
    'redirect_uri': 'http://localhost:3000/auth', # Example redirect URI
    'log_path': 'logs/fyers_api_logs/',
    'access_token_path': './fyers_access_token.json' # Path to store the generated access token
}

# Logging Configuration
LOGGING_CONFIG = {
    'log_folder': 'logs/',
    'log_level': 'INFO', # Level for file logs
    'console_log_level': 'INFO', # Level for console output
}

# Equity Breakout Detection (Pre-Filter) Configuration
EQUITY_BREAKOUT_DETECTION_CONFIG = {
    'price_min': 23.0,
    'price_max': 2300.0,
    'ema_period': 15,
    'candle_strength_wick_pct': 0.10, # 10%
    'close_top_pct_of_range': 0.80, # Close in top 20% of the candle's range
    'swing_high_period': 5, # Max high of last 5 days
}

# Monitoring Process Configuration
MONITORING_PROCESS_CONFIG = {
    'market_open_time': '09:15',
    'market_close_time': '15:15',
    'data_fetch_interval_minutes': 5,
    'historical_data_folder': 'Historical_Data',
}

# Breakout Logic (09:15-09:20 Window) Configuration
BREAKOUT_LOGIC_CONFIG = {
    'start_time': '09:15',
    'end_time': '09:20',
    'min_green_candles': 3,
    'strong_body_candle_pct': 0.60,
    'strong_candle_rejection_wick_pct': 0.30,
    'volume_spike_multiplier': 2.0,
    'avg_volume_period_candles': 20,
    'relative_strength_threshold': 0.003, # 0.3%
    'higher_tf_ema_period': 20,
    'breakout_quality_min_score': 7,
    'exhaustion_wick_pct': 0.50,
    'overextension_pct': 0.015, # 1.5%
}

# Initial Breakouts (Front Runners) Configuration
INITIAL_BREAKOUTS_CONFIG = {
    'wick_threshold': 0.30,
    'one_time_run_time': '09:20',
    'switch_to_pre_filtered_time': '09:25',
    'volume_multiplier_threshold': 1.2,
}

# Stage Breakouts Configuration
STAGE_BREAKOUTS_CONFIG = {
    'wick_threshold': 0.50,
    'vol_multiplier': 1.8,
    'atr_body_threshold': 0.3,
    'monitoring_end_time': '13:00',
    'late_cutoff_time': '14:30',
    'require_retest_confirmation': True,
    'cool_off_minutes': 30,
}

# Intraday Equity Spurts Monitor Configuration
INTRADAY_SPURTS_MONITOR_CONFIG = {
    'rolling_buffer_candles': 20,
    'price_momentum_surge_k': 2.5,
    'volume_spike_m_mid_liquid': 2.0,
    'volume_spike_m_large_cap': 3.0,
    'order_imbalance_threshold': 0.40,
    'weighted_score_threshold_pct': 70.0,
    'cool_off_period_minutes': 5,
}

# Order Manager Configuration
ORDER_MANAGER_CONFIG = {
    'default_stop_loss_pct': 1.0, # 1%
    'default_target_pct': 2.0, # 2%
}
