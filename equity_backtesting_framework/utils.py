"""
This module provides utility functions for the backtesting framework,
such as logging configuration.
"""

import logging
import sys
import os
from datetime import datetime
from . import config

def setup_logging(date_str: str):
    """
    Sets up a centralized logger that writes to both a file and the console.
    A new log file is created for each backtesting day.
    """
    log_folder = config.LOGGING_CONFIG.get('log_folder', 'logs/')
    os.makedirs(log_folder, exist_ok=True)

    log_filename = os.path.join(log_folder, f"backtest_{date_str}.log")

    # Configure the root logger
    # This setup is basic. For more complex scenarios, multiple named loggers could be used.
    logging.basicConfig(
        level=config.LOGGING_CONFIG.get('log_level', 'INFO'),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_filename, mode='w'), # 'w' to overwrite log for each run on the same day
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Get the root logger and log the initial message
    logger = logging.getLogger()
    logger.info(f"Logging setup complete. Log file: {log_filename}")

def get_logger(name: str):
    """Returns a named logger."""
    return logging.getLogger(name)
