"""
search.py - resolve a company NAME or US TICKER to US-listed equity candidates,
using Financial Modeling Prep (FMP) Stable API.

Returns a list of dicts: {"symbol", "name", "exchange"} - best match first.
"""

import os
import requests
import streamlit as st

BASE = "https://financialmodelingprep.com/stable"

# Fix for names where search picks wrong share class
PREFERRED_TICKER = {
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "facebook": "META",
}


def _api_key():
    try:
        return st.secrets["FMP_API_KEY"]
    except Exception:
        return os.environ.get("FMP_API_KEY", "")


def _search_api(endpoint, query):
    """Call one FMP search endpoint, return list of dicts."""
    try:
        r = requests.get(
            f"{BASE}/{endpoint}",
            params={"query": query, "apikey": _api_key()},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"FMP {endpoint} error: {e}")
        return []


def _profile_fallback(query):
    """Try the query as a direct ticker via profile endpoint."""
    try:
        r = requests.get(
            f"{BASE}/profile",
            params={"symbol": query.upper(), "apikey": _api_key()},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and len(data) > 0 and data[0].get("symbol"):
            info = data[0]
            return [{"symbol": info["symbol"], "name": info.get("companyName", info["symbol"]), "exchange": info.get("exchangeShortName", "")}]
    except Exception:
        pass
    return []


def search_us_companies(query, limit=8):
    """Return up to `limit` US-listed equities matching a name or ticker."""
    query = (query or "").strip()
    if not query:
        return []

    # Check preferred ticker override
    mapped = PREFERRED_TICKER.get(query.lower())
    if mapped:
        result = _profile_fallback(mapped)
        if result:
            return result

    # Try symbol search
    results = _search_api("search-symbol", query)

    # Also try name search
    results += _search_api("search-name", query)

    rows, seen = [], set()
    for item in results:
        sym = (item.get("symbol") or "").upper()
        if not sym or sym in seen:
            continue
        if "." in sym:
            continue
        exch = (item.get("exchangeShortName") or item.get("exchange") or "").upper()
        if exch and exch not in ("NASDAQ", "NYSE", "AMEX", "NEW YORK STOCK EXCHANGE"):
            continue
        name = item.get("name") or sym
        seen.add(sym)
        rows.append({"symbol": sym, "name": name, "exchange": exch})
        if len(rows) >= limit:
            break

    # If search returned nothing, try query as a direct ticker
    if not rows:
        rows = _profile_fallback(query)

    up = query.upper()
    rows.sort(key=lambda r: (r["symbol"] != up,))
    return rows
