"""
This module provides a service class for interacting with the Fyers API.
It handles authentication, session management, and data fetching.
The authentication logic is based on the user's proven SimpleAuth class.
"""

import os
import json
import time
import logging
import webbrowser
from fyers_apiv3 import fyersModel
import pandas as pd
from datetime import datetime, timedelta

from . import config

class FyersService:
    """
    A wrapper class for the Fyers API.
    Authentication logic is adapted from the user's provided SimpleAuth class.
    """
    def __init__(self):
        self.client_id = config.FYERS_CONFIG['client_id']
        self.secret_key = config.FYERS_CONFIG['secret_key']
        # IMPORTANT: This redirect_uri must match the one in the user's Fyers App settings.
        self.redirect_uri = "https://trade.fyers.in/api-login/redirect-uri/index.html"
        self.log_path = config.FYERS_CONFIG['log_path']
        self.token_file = config.FYERS_CONFIG['access_token_path']

        os.makedirs(self.log_path, exist_ok=True)

        access_token = self._authenticate()
        if not access_token:
            raise ConnectionError("Fyers authentication failed. Could not retrieve access token.")

        self.fyers = fyersModel.FyersModel(
            client_id=self.client_id,
            token=access_token,
            log_path=self.log_path
        )
        print("Fyers API session initialized successfully.")

    def _load_token(self):
        """Load saved access token from JSON if valid."""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                token = data.get('access_token')
                expiry = data.get('expiry', 0)
                # Check if token expires in the next 10 minutes (600 seconds)
                if token and time.time() + 600 < expiry:
                    logging.info("Using saved and valid access token.")
                    return token
                else:
                    logging.info("Saved token has expired or is nearing expiry.")
            return None
        except Exception as e:
            logging.warning(f"Could not load token: {e}")
            return None

    def _save_token(self, token, expiry_seconds=86400):
        """Save access token to JSON file."""
        try:
            data = {
                'access_token': token,
                'expiry': int(time.time() + expiry_seconds),
                'created': int(time.time())
            }
            with open(self.token_file, 'w') as f:
                json.dump(data, f, indent=2)
            logging.info(f"Access token saved successfully to {self.token_file}")
        except Exception as e:
            logging.error(f"Failed to save token: {e}")

    def _validate_token(self, token):
        """Validate access token with Fyers API."""
        try:
            client = fyersModel.FyersModel(client_id=self.client_id, token=token, log_path=self.log_path)
            profile = client.get_profile()
            if profile.get('code') == 200:
                logging.info("Token validation successful.")
                return True
            else:
                logging.warning(f"Token validation failed: {profile.get('message', 'Unknown error')}")
                return False
        except Exception as e:
            logging.warning(f"Token validation error: {e}")
            return False

    def _authenticate(self):
        """Main authentication flow, adapted from user's SimpleAuth."""
        saved_token = self._load_token()
        if saved_token and self._validate_token(saved_token):
            return saved_token

        print("\nFYERS API AUTHENTICATION REQUIRED")
        print("=" * 50)

        try:
            session = fyersModel.SessionModel(
                client_id=self.client_id,
                secret_key=self.secret_key,
                redirect_uri=self.redirect_uri,
                response_type='code',
                grant_type='authorization_code'
            )

            auth_url = session.generate_authcode()
            print(f"1. Opening browser to: {auth_url}")
            webbrowser.open(auth_url)
            print("2. Complete login process in browser.")
            print("3. Copy authorization code from the final redirected URL.")
            print("-" * 50)

            auth_code = input("Enter authorization code: ").strip()
            if not auth_code:
                print("No authorization code provided.")
                return None

            session.set_token(auth_code)
            response = session.generate_token()

            # Using the user's success condition check
            if response and response.get('code') == 200:
                access_token = response['access_token']
                self._save_token(access_token)
                print("Authentication successful!")
                return access_token
            else:
                print(f"Authentication failed: {response.get('message', 'Unknown error')}")
                return None

        except Exception as e:
            logging.error(f"Authentication error: {e}", exc_info=True)
            return None

    def get_historical_data(self, symbol, resolution, days_lookback=365):
        """Fetches historical data (unchanged from previous version)."""
        date_to = datetime.now().strftime('%Y-%m-%d')
        date_from = (datetime.now() - timedelta(days=days_lookback)).strftime('%Y-%m-%d')

        data = {
            "symbol": symbol,
            "resolution": resolution,
            "date_format": "1",
            "range_from": date_from,
            "range_to": date_to,
            "cont_flag": "1"
        }

        try:
            response = self.fyers.history(data=data)
            if response.get('s') == 'ok' and 'candles' in response:
                df = pd.DataFrame(response['candles'])
                df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
                df['datetime'] = pd.to_datetime(df['datetime'], unit='s')
                df['datetime'] = df['datetime'].dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)
                df.set_index('datetime', inplace=True)
                return df
            else:
                logging.warning(f"Error fetching data for {symbol}: {response.get('message', 'No candles')}")
                return pd.DataFrame()
        except Exception as e:
            logging.error(f"Exception fetching data for {symbol}: {e}")
            return pd.DataFrame()
