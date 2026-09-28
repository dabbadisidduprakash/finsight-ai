"""
search.py - resolve a company NAME or a US TICKER to US-listed equity candidates,
using Financial Modeling Prep (FMP).

Returns a list of dicts: {"symbol", "name", "exchange"} - best match first.
"""

import os
import requests
import streamlit as st

BASE = "https://financialmodelingprep.com/api/v3"


def _api_key():
    try:
        return st.secrets["FMP_API_KEY"]
    except Exception:
        return os.environ.get("FMP_API_KEY", "")


def search_us_companies(query, limit=8):
    query = (query or "").strip()
    if not query:
        return []

    try:
        r = requests.get(
            f"{BASE}/search",
            params={
                "query": query,
                "limit": limit * 3,
                "exchange": "NASDAQ,NYSE,AMEX",
                "apikey": _api_key(),
            },
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"FMP search error: {e}")
        return []

    if not isinstance(data, list):
        return []

    rows, seen = [], set()
    for item in data:
        sym = (item.get("symbol") or "").upper()
        if not sym or sym in seen:
            continue
        if "." in sym:
            continue
        name = item.get("name") or sym
        exch = item.get("exchangeShortName") or item.get("exchange") or ""
        seen.add(sym)
        rows.append({"symbol": sym, "name": name, "exchange": exch})
        if len(rows) >= limit:
            break

    up = query.upper()
    rows.sort(key=lambda r: (r["symbol"] != up,))
    return rows
