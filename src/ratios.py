"""
ratios.py - calculates financial ratios from statement data.
No API calls here; this only DERIVES numbers from data already fetched.
Separation of concerns: fetching lives in data_fetch.py, math lives here.
"""


def safe_divide(numerator, denominator):
    """
    Divide two numbers safely. Returns None if we can't (missing data,
    or division by zero). This stops the app crashing on bad data.
    """
    try:
        if numerator is None or denominator is None:
            return None
        if denominator == 0:
            return None
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return None


def calculate_ratios(income, balance, cashflow, profile):
    """
    Build a list of yearly ratio dictionaries from the statement lists.
    Each statement is a list of years (newest first), matched by index.
    Returns a list like:
        [{"year": "2025", "Current Ratio": 1.2, "Net Margin": 0.25, ...}, ...]
    """
    if not income or not balance:
        return None

    # Use however many years all statements share
    num_years = min(len(income), len(balance))

    results = []
    for i in range(num_years):
        inc = income[i]
        bal = balance[i]

        # Year label (fall back gracefully if a field is missing)
        year = (
            str(inc.get("calendarYear"))
            if inc.get("calendarYear")
            else str(inc.get("date", i))
        )

        revenue = inc.get("revenue")
        gross_profit = inc.get("grossProfit")
        net_income = inc.get("netIncome")
        eps = inc.get("eps")

        total_assets = bal.get("totalAssets")
        total_equity = bal.get("totalEquity")
        total_debt = bal.get("totalDebt")
        current_assets = bal.get("totalCurrentAssets")
        current_liabilities = bal.get("totalCurrentLiabilities")

        # Price is a single current value (from profile), not per-year.
        # We only apply it to the most recent year (i == 0) for P/E.
        price = profile.get("price") if profile else None

        row = {
            "Year": year,
            "Current Ratio": safe_divide(current_assets, current_liabilities),
            "Gross Margin": safe_divide(gross_profit, revenue),
            "Net Margin": safe_divide(net_income, revenue),
            "Debt-to-Equity": safe_divide(total_debt, total_equity),
            "ROE": safe_divide(net_income, total_equity),
            "ROA": safe_divide(net_income, total_assets),
            "P/E": safe_divide(price, eps) if i == 0 else None,
        }
        results.append(row)

    return results


if __name__ == "__main__":
    # Test using real data from our fetchers
    from data_fetch import (
        get_company_profile,
        get_income_statement,
        get_balance_sheet,
        get_cash_flow,
    )

    ticker = "AAPL"
    prof = get_company_profile(ticker)
    inc = get_income_statement(ticker)
    bal = get_balance_sheet(ticker)
    cf = get_cash_flow(ticker)

    ratios = calculate_ratios(inc, bal, cf, prof)
    if ratios:
        print(f"Calculated ratios for {ticker}, {len(ratios)} years:\n")
        for row in ratios:
            print(f"Year {row['Year']}:")
            print(f"  Current Ratio: {row['Current Ratio']}")
            print(f"  Net Margin:    {row['Net Margin']}")
            print(f"  ROE:           {row['ROE']}")
            print(f"  Debt-to-Equity:{row['Debt-to-Equity']}")
            print(f"  P/E:           {row['P/E']}")
            print()
    else:
        print("FAILED to calculate ratios.")