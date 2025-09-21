# How to Run the Equity Backtesting Framework

This guide provides two methods for setting up and running the backtesting script.

---

### **Method 1: First-Time Setup (If you do NOT have an access token)**

Follow this method if you are setting up from scratch and need the script to help you get a token.

#### **Step 1.1: Configure Your Fyers App**
The most reliable setup for a local script is to use a `localhost` redirect URI.

1.  **Log in to your Fyers Developer Account** and go to your App's settings.
2.  Set the **"Redirect URI"** field to exactly: `http://localhost:3000/`
3.  Save the changes.

#### **Step 1.2: Configure the Script**
1.  Open the file: `equity_backtesting_framework/config.py`.
2.  Enter your `client_id` and `secret_key`.
3.  Set the `redirect_uri` to the same localhost value: `'redirect_uri': 'http://localhost:3000/'`.

#### **Step 1.3: Run the Interactive Login**
1.  Run the script from your terminal: `python -m equity_backtesting_framework.main`
2.  Follow the prompts to log in via your browser and paste the `auth_code` from the final URL back into the terminal. (Your browser will show a "site not reached" error, which is normal).

---

### **Method 2: If You Already Have an Access Token**

**Use this method if your other scripts are already working.** This is a much simpler, non-interactive way to run the framework.

#### **Step 2.1: Get Your Access Token**
1.  Run your **other, working script** to generate a Fyers `access_token`.
2.  This token is the very long string that starts with `eyJ...` (it is a JWT).
3.  Copy this entire access token string.

#### **Step 2.2: Create the `access_token.txt` File**
1.  In the root folder of **this** project, create a new text file named `access_token.txt`.
2.  Open the file and **paste the access token** you copied from your other script.
3.  Save and close the file.

#### **Step 2.3: Configure the Script**
1.  Open `equity_backtesting_framework/config.py`.
2.  Fill in your `client_id` and `secret_key`.
3.  **The `redirect_uri` value does not matter for this method**, as the login flow will be skipped entirely. You can leave it as is.

#### **Step 2.4: Run the Backtester**
That's it! Now you can run the backtester directly. The script will read the token from the file and will not prompt you to log in.

```bash
# From the root directory of the project, run the following command:
python -m equity_backtesting_framework.main
```

The script will start immediately. If it ever fails due to an expired token, simply repeat Step 2.1 and 2.2 to update the `access_token.txt` file with a fresh one.
