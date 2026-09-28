"""
search.py - resolve a company NAME or US TICKER to US-listed equity candidates,
using Financial Modeling Prep (FMP) Stable API.

Returns a list of dicts: {"symbol", "name", "exchange"} - best match first.
"""

import os
import requests
import streamlit as st

BASE = "https://financialmodelingprep.com/stable"


def _api_key():
    try:
        return st.secrets["FMP_API_KEY"]
    except Exception:
        return os.environ.get("FMP_API_KEY", "")


def search_us_companies(query, limit=8):
    query = (query or "").strip()
    if not query:
        return []

    results = []

    # Try symbol search first
    try:
        r = requests.get(
            f"{BASE}/search-symbol",
            params={
                "query": query,
                "apikey": _api_key(),
            },
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            results.extend(data)
    except Exception as e:
        print(f"FMP symbol search error: {e}")

    # Also try name search
    try:
        r = requests.get(
            f"{BASE}/search-name",
            params={
                "query": query,
                "apikey": _api_key(),
            },
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            results.extend(data)
    except Exception as e:
        print(f"FMP name search error: {e}")

    rows, seen = [], set()
    for item in results:
        sym = (item.get("symbol") or "").upper()
        if not sym or sym in seen:
            continue
        if "." in sym:
            continue
        exch = (item.get("exchangeShortName") or item.get("exchange") or "").upper()
        if exch not in ("NASDAQ", "NYSE", "AMEX", ""):
            continue
        name = item.get("name") or sym
        seen.add(sym)
        rows.append({"symbol": sym, "name": name, "exchange": exch})
        if len(rows) >= limit:
            break

    up = query.upper()
    rows.sort(key=lambda r: (r["symbol"] != up,))
    return rows
