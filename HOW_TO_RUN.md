# How to Run the Equity Backtesting Framework: A Step-by-Step Guide

This guide will walk you through setting up and running the backtesting framework as if you've just downloaded the code.

### **Step 1: Install the Necessary Tools**

The script is written in Python and uses several common data science libraries. You need to install them first.

1.  Open your computer's terminal or command prompt.
2.  Navigate to the root folder where you have saved this project's code.
3.  Run the following command. This command reads the `requirements.txt` file and automatically downloads and installs all the required libraries.

    ```bash
    pip install -r requirements.txt
    ```

### **Step 2: Enter Your API Credentials**

The script needs to connect to the Fyers trading platform to get stock data. You need to provide it with your unique keys.

1.  In the project folder, find and open this file: `equity_backtesting_framework/config.py`.
2.  Look for the section named `FYERS_CONFIG`.
3.  You will see placeholders like `'YOUR_CLIENT_ID'`. Carefully replace these placeholders with your actual Fyers App keys. **Do not delete the quote marks.**

    ```python
    # Find this section in the file:
    FYERS_CONFIG = {
        'client_id': 'YOUR_CLIENT_ID',  # <-- Replace this value
        'secret_key': 'YOUR_SECRET_KEY', # <-- Replace this value
        'redirect_uri': 'YOUR_REDIRECT_URI', # <-- Replace this value
        # ... other settings
    }
    ```

### **Step 3: Authorize the Script (First-Time Only)**

The first time you run the script, you need to grant it permission to access your Fyers account.

1.  Go back to your terminal, making sure you are in the project's root folder.
2.  Run the main script using this exact command:

    ```bash
    python -m equity_backtesting_framework.main
    ```
3.  The script will start, see it has no authorization, and will print a special login URL in the terminal.
4.  **Copy this URL**, open your web browser (like Chrome or Firefox), and **paste the URL** into the address bar.
5.  Log in to Fyers using your normal username and password.
6.  After you log in, Fyers will redirect you to a new page. The URL of this new page is important. It will look something like `https://your-redirect-uri/?s=ok&code=200&auth_code=...`.
7.  Look for `auth_code=` in the new URL and **copy the long string of characters** that follows it.
8.  Go back to your terminal. The script will be waiting for you to **paste this `auth_code`** and press Enter.

Once you do this, the script will save your authorization in a file named `access_token.txt`. You will not have to do this login process again for subsequent runs.

### **Step 4: Run the Backtester**

After the one-time setup is complete, running the backtester is simple.

1.  Open your terminal and navigate to the project's root folder.
2.  Execute the following command:

    ```bash
    python -m equity_backtesting_framework.main
    ```

This command tells Python to run the `main.py` script located inside the `equity_backtesting_framework` folder. The script will then start the backtesting process, printing its progress to the screen and saving a detailed log in the `logs/` directory.
