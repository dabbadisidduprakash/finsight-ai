"""
data_fetch.py - talks to the Financial Modeling Prep (FMP) API.
Handles authentication for both local (.env) and deployed (Streamlit Secrets) environments.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()


def _get_key(name):
    """
    Read a secret from Streamlit's secrets (when deployed) OR the local
    .env file (when running locally). Tries Streamlit first, falls back
    to environment. This lets the same code work both places.
    """
    try:
        import streamlit as st
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name)


BASE_URL = "https://financialmodelingprep.com/stable"


def _get(endpoint, ticker, limit=5):
    """
    Internal helper. All statement calls share the same shape, so we write
    the request logic ONCE and reuse it. DRY: Don't Repeat Yourself.
    """
    api_key = _get_key("FMP_API_KEY")
    if not api_key:
        print("ERROR: FMP_API_KEY not found. Check your .env file or Streamlit Secrets.")
        return None
    
    clean_ticker = str(ticker).strip().upper()
    url = f"{BASE_URL}/{endpoint}?symbol={clean_ticker}&limit={limit}&apikey={api_key}"
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        if not data:
            return None
        return data
    except requests.exceptions.RequestException as e:
        print(f"ERROR fetching {endpoint} for {clean_ticker}: {e}")
        return None


def get_company_profile(ticker):
    """Fetch the company profile for a ticker (e.g. 'AAPL', 'IBM', 'EPAM'). Returns dict or None."""
    data = _get("profile", ticker, limit=1)
    if not data:
        return None
    return data[0]


def get_income_statement(ticker, limit=5):
    """Fetch the last `limit` years of income statements. Returns a list or None."""
    return _get("income-statement", ticker, limit)


def get_balance_sheet(ticker, limit=5):
    """Fetch the last `limit` years of balance sheets. Returns a list or None."""
    return _get("balance-sheet-statement", ticker, limit)


def get_cash_flow(ticker, limit=5):
    """Fetch the last `limit` years of cash flow statements. Returns a list or None."""
    return _get("cash-flow-statement", ticker, limit)


if __name__ == "__main__":
    test_ticker = "IBM"
    print(f"--- TESTING TICKER: {test_ticker} ---")
    
    print("--- PROFILE ---")
    p = get_company_profile(test_ticker)
    print(p.get("companyName") if p else "FAILED")

    print("--- INCOME STATEMENT ---")
    inc = get_income_statement(test_ticker)
    if inc:
        print(f"Got {len(inc)} years. Latest revenue:", inc[0].get("revenue"))
    else:
        print("FAILED")

    print("--- BALANCE SHEET ---")
    bs = get_balance_sheet(test_ticker)
    if bs:
        print(f"Got {len(bs)} years. Latest total assets:", bs[0].get("totalAssets"))
    else:
        print("FAILED")

    print("--- CASH FLOW ---")
    cf = get_cash_flow(test_ticker)
    if cf:
        print(f"Got {len(cf)} years. Latest operating cash flow:", cf[0].get("operatingCashFlow"))
    else:
        print("FAILED")