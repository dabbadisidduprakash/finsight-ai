"""
search.py - resolve a company NAME or a US TICKER to US-listed equity candidates,
using Yahoo Finance. No API key required. Primary path uses yfinance's own
Search (which reuses Yahoo's authenticated session and avoids blocking);
a direct curl_cffi call is the fallback.

Returns a list of dicts: {"symbol", "name", "exchange"} - newest/best match first.
"""
import requests as _requests

_session = _requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})
# Yahoo exchange codes that correspond to US listings.
US_EXCHANGES = {
    "NMS", "NGM", "NCM",   # Nasdaq  (Global Select / Global Market / Capital Market)
    "NYQ", "NYS",          # NYSE
    "ASE",                 # NYSE American
    "PCX", "BTS", "BATS",  # NYSE Arca / Cboe BZX
    "OQB", "OQX", "PNK",   # OTCQB / OTCQX / Pink (kept so smaller US names still resolve)
}


def _is_us_symbol(sym):
    # US tickers carry no dot-suffix. Non-US Yahoo tickers do: RY.TO, BP.L, SAP.DE, 7203.T
    return bool(sym) and "." not in sym


def _row(q):
    sym = (q.get("symbol") or "").upper()
    name = (q.get("shortname") or q.get("longname")
            or q.get("shortName") or q.get("longName") or sym)
    exch = q.get("exchange") or q.get("exchDisp") or ""
    return {"symbol": sym, "name": name, "exchange": exch}


def _raw_quotes(query, want):
    # 1) yfinance's built-in search (preferred - handles Yahoo's crumb/session)
    try:
        import yfinance as yf
        if hasattr(yf, "Search"):
            qs = yf.Search(query, max_results=want, session=_session).quotes
            if qs:
                return qs
    except Exception:
        pass
    # 2) direct Yahoo search endpoint via curl_cffi (browser impersonation)
    try:
        from curl_cffi import requests as creq
        r = creq.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": query, "quotesCount": want, "newsCount": 0, "listsCount": 0},
            impersonate="chrome", timeout=10,
        )
        return (r.json() or {}).get("quotes", []) or []
    except Exception:
        return []


def search_us_companies(query, limit=8):
    """Return up to `limit` US-listed equities matching a name or ticker."""
    query = (query or "").strip()
    if not query:
        return []

    rows, seen = [], set()
    for q in _raw_quotes(query, limit * 3):
        if (q.get("quoteType") or "").upper() != "EQUITY":
            continue
        row = _row(q)
        if not row["symbol"] or row["symbol"] in seen:
            continue
        if not _is_us_symbol(row["symbol"]):
            continue
        # if Yahoo gave an exchange code, require it to be US; otherwise trust the no-dot rule
        if row["exchange"] and row["exchange"] not in US_EXCHANGES:
            continue
        seen.add(row["symbol"])
        rows.append(row)
        if len(rows) >= limit:
            break

    # Put an exact ticker match first (so typing "AAPL" behaves like a ticker).
    up = query.upper()
    rows.sort(key=lambda r: (r["symbol"] != up,))
    return rows
