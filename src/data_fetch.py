"""
data_fetch.py - Financial Modeling Prep (FMP) Stable API backend.

Returns the same structures:
  - profile: a dict
  - statements: a list of yearly dicts, newest first
so ratios.py, valuation.py and app.py need no changes.
"""

import os
import requests
import streamlit as st


def _api_key():
    try:
        return st.secrets["FMP_API_KEY"]
    except Exception:
        return os.environ.get("FMP_API_KEY", "")

BASE = "https://financialmodelingprep.com/stable"


def _get(endpoint, **params):
    params["apikey"] = _api_key()
    url = f"{BASE}/{endpoint}"
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and "Error Message" in data:
            print(f"FMP error: {data['Error Message']}")
            return None
        return data
    except Exception as e:
        print(f"ERROR fetching {endpoint}: {e}")
        return None


def get_company_profile(ticker):
    data = _get("profile", symbol=ticker)
    if not data or not isinstance(data, list) or len(data) == 0:
        return None
    info = data[0]
    if not info.get("symbol"):
        return None
    mcap = info.get("mktCap")
    price = info.get("price")
    raw_beta = info.get("beta")
    return {
        "symbol": info.get("symbol"),
        "companyName": info.get("companyName"),
        "price": price,
        "beta": raw_beta,
        "betaReported": raw_beta is not None,
        "marketCap": mcap,
        "mktCap": mcap,
        "sharesOutstanding": info.get("sharesOutstanding") or (
            int(mcap / price) if mcap and price else None
        ),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "currency": info.get("currency"),
        "exchange": info.get("exchangeShortName") or info.get("exchange"),
        "description": info.get("description"),
        "ceo": info.get("ceo"),
        "website": info.get("website"),
        "country": info.get("country"),
        "fullTimeEmployees": info.get("fullTimeEmployees"),
    }


def _statement(endpoint, ticker, limit=5):
    data = _get(endpoint, symbol=ticker, limit=limit)
    if not data or not isinstance(data, list) or len(data) == 0:
        return None
    return data


def get_income_statement(ticker, limit=5):
    return _statement("income-statement", ticker, limit)


def get_balance_sheet(ticker, limit=5):
    return _statement("balance-sheet-statement", ticker, limit)


def get_cash_flow(ticker, limit=5):
    return _statement("cash-flow-statement", ticker, limit)
