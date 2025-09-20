"""
This module provides a service class for interacting with the Fyers API.
It handles authentication, session management, and data fetching.
"""

import os
import webbrowser
from fyers_apiv3 import fyersModel
import pandas as pd
from datetime import datetime, timedelta

# It's better to import the whole config and access items from it.
from . import config

class FyersService:
    """
    A wrapper class for the Fyers API to handle authentication and data requests.
    """
    def __init__(self):
        """
        Initializes the FyersService, loading configuration and establishing a session.
        """
        self.client_id = config.FYERS_CONFIG['client_id']
        self.secret_key = config.FYERS_CONFIG['secret_key']
        self.redirect_uri = config.FYERS_CONFIG['redirect_uri']
        self.log_path = config.FYERS_CONFIG['log_path']
        self.access_token_path = config.FYERS_CONFIG['access_token_path']

        # Ensure the log directory exists
        os.makedirs(self.log_path, exist_ok=True)

        self.fyers = self._initialize_session()

    def _get_access_token_from_file(self):
        """Reads the access token from the local file."""
        if os.path.exists(self.access_token_path):
            with open(self.access_token_path, 'r') as f:
                return f.read().strip()
        return None

    def _save_access_token_to_file(self, token):
        """Saves the access token to a local file."""
        with open(self.access_token_path, 'w') as f:
            f.write(token)
        print(f"Access token saved to {self.access_token_path}")

    def _initialize_session(self):
        """
        Initializes the Fyers API session.
        It first tries to use a saved access token. If that fails or doesn't exist,
        it guides the user through the process of generating a new one.
        """
        access_token = self._get_access_token_from_file()

        if not access_token:
            print("Access token not found. Starting new session generation.")
            access_token = self.generate_new_access_token()

        fyers = fyersModel.FyersModel(
            client_id=self.client_id,
            token=access_token,
            log_path=self.log_path
        )

        # Verify token validity by fetching profile
        profile = fyers.get_profile()
        if profile.get('s') != 'ok':
            print("The saved access token is invalid or expired. Please generate a new one.")
            access_token = self.generate_new_access_token()
            fyers = fyersModel.FyersModel(
                client_id=self.client_id,
                token=access_token,
                log_path=self.log_path
            )

        print("Fyers API session initialized successfully.")
        return fyers

    def generate_new_access_token(self):
        """
        Guides the user through the interactive process of generating a new access token.
        """
        session = fyersModel.SessionModel(
            client_id=self.client_id,
            secret_key=self.secret_key,
            redirect_uri=self.redirect_uri,
            response_type='code',
            grant_type='authorization_code'
        )

        auth_url = session.generate_authcode()
        print("-" * 80)
        print("Fyers API needs authorization. This is a one-time process (or until token expires).")
        print(f"1. Please open the following URL in your browser:\n   {auth_url}")

        try:
            webbrowser.open(auth_url, new=1)
            print("   Your web browser should have opened for you to log in.")
        except Exception:
            print("   Could not automatically open browser. Please copy/paste the URL manually.")

        print("2. Log in with your Fyers credentials.")
        print("3. You will be redirected to a URL specified in your Fyers App settings.")
        print("4. From the redirected URL, copy the 'auth_code' value.")
        auth_code = input("5. Paste the auth_code here and press Enter: ")
        print("-" * 80)

        session.set_token(auth_code)
        response = session.generate_token()

        if response.get('s') == 'ok' and response.get('access_token'):
            access_token = response['access_token']
            self._save_access_token_to_file(access_token)
            print("New access token generated and saved successfully.")
            return access_token
        else:
            print(f"Error generating access token: {response.get('message', 'Unknown error')}")
            raise ConnectionAbortedError("Could not generate Fyers access token. Please check your credentials and auth_code.")

    def get_historical_data(self, symbol, resolution, days_lookback=365):
        """
        Fetches historical data for a given symbol for a specified lookback period.

        :param symbol: The symbol to fetch data for (e.g., 'NSE:SBIN-EQ').
        :param resolution: Data resolution ('D' for daily, '5' for 5-minute, etc.).
        :param days_lookback: The number of days of data to fetch from today.
        :return: A pandas DataFrame with OHLCV data, or an empty DataFrame on error.
        """
        date_to = datetime.now().strftime('%Y-%m-%d')
        date_from = (datetime.now() - timedelta(days=days_lookback)).strftime('%Y-%m-%d')

        data = {
            "symbol": symbol,
            "resolution": resolution,
            "date_format": "1",  # YYYY-MM-DD
            "range_from": date_from,
            "range_to": date_to,
            "cont_flag": "1"
        }

        try:
            response = self.fyers.history(data=data)
            if response.get('s') == 'ok' and 'candles' in response:
                candles = response['candles']
                df = pd.DataFrame(candles)
                df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
                df['datetime'] = pd.to_datetime(df['datetime'], unit='s')
                # Convert to IST and remove timezone info for simplicity in calculations
                df['datetime'] = df['datetime'].dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)
                df.set_index('datetime', inplace=True)
                print(f"Successfully fetched {len(df)} records for {symbol} with resolution {resolution}.")
                return df
            else:
                print(f"Error fetching data for {symbol}: {response.get('message', 'No candles in response')}")
                return pd.DataFrame()
        except Exception as e:
            print(f"An exception occurred while fetching data for {symbol}: {e}")
            return pd.DataFrame()
