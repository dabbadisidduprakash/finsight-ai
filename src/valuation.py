"""
valuation.py - valuation calculations for FinSight AI.
Day 4: historical FCFF (Free Cash Flow to the Firm).
No API calls; derives from statement data already fetched.
"""


def safe_get(d, *keys):
    """Try several possible field names, return the first that exists and isn't None."""
    for k in keys:
        if d and d.get(k) is not None:
            return d.get(k)
    return None


def calculate_fcff(income, cashflow, limit=5):
    """
    Compute FCFF for each year.
    FCFF = Operating Cash Flow + Interest*(1 - TaxRate) - CapEx

    income, cashflow: lists of yearly statements (newest first), matched by index.
    Returns a list of dicts: [{"Year", "Operating Cash Flow", "Interest (after-tax)",
                               "CapEx", "FCFF"}, ...] or None.
    """
    if not income or not cashflow:
        return None

    num_years = min(len(income), len(cashflow), limit)
    results = []

    for i in range(num_years):
        inc = income[i]
        cf = cashflow[i]

        year = str(safe_get(inc, "calendarYear", "date") or i)

        # Operating cash flow (field name varies across FMP responses)
        ocf = safe_get(
            cf,
            "operatingCashFlow",
            "netCashProvidedByOperatingActivities",
        )

        # CapEx is usually reported as a negative number in cash flow statements
        capex = safe_get(cf, "capitalExpenditure")

        # Interest expense and the pieces we need to estimate the tax rate
        interest = safe_get(inc, "interestExpense")
        pretax_income = safe_get(inc, "incomeBeforeTax", "pretaxIncome")
        tax = safe_get(inc, "incomeTaxExpense")

        # Estimate effective tax rate = tax / pretax income (guard against bad data)
        if pretax_income and pretax_income != 0 and tax is not None:
            tax_rate = tax / pretax_income
            # Clamp to a sane range; weird data can produce nonsense rates
            if tax_rate < 0:
                tax_rate = 0.0
            if tax_rate > 0.5:
                tax_rate = 0.21  # fall back to a typical US corporate rate
        else:
            tax_rate = 0.21  # sensible default if we can't compute it

        # After-tax interest add-back (0 if no interest reported)
        interest_after_tax = interest * (1 - tax_rate) if interest else 0

        # FCFF. capex is negative in the data, so ADDING it subtracts the spend.
        # We normalize: use -abs(capex) to be safe regardless of its sign.
        if ocf is None:
            fcff = None
            capex_norm = None
        else:
            capex_norm = -abs(capex) if capex is not None else 0
            fcff = ocf + interest_after_tax + capex_norm

        results.append({
            "Year": year,
            "Operating Cash Flow": ocf,
            "Interest (after-tax)": interest_after_tax,
            "CapEx": capex_norm,
            "FCFF": fcff,
            "Tax Rate Used": tax_rate,
        })

    return results


if __name__ == "__main__":
    from data_fetch import get_income_statement, get_cash_flow

    ticker = "AAPL"
    inc = get_income_statement(ticker)
    cf = get_cash_flow(ticker)

    rows = calculate_fcff(inc, cf)
    if rows:
        print(f"FCFF for {ticker}, {len(rows)} years:\n")
        for r in rows:
            print(f"Year {r['Year']}:")
            print(f"  Operating Cash Flow: {r['Operating Cash Flow']}")
            print(f"  Interest (after-tax):{r['Interest (after-tax)']}")
            print(f"  CapEx:               {r['CapEx']}")
            print(f"  Tax Rate Used:       {r['Tax Rate Used']:.2%}")
            print(f"  FCFF:                {r['FCFF']}")
            print()
    else:
        print("FAILED to calculate FCFF.")