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

def calculate_cost_of_equity(beta, risk_free_rate=0.043, equity_risk_premium=0.05):
    """
    CAPM: Re = RiskFree + Beta * EquityRiskPremium
    Returns cost of equity as a decimal (e.g. 0.095 = 9.5%).
    """
    if beta is None:
        beta = 1.0  # default to market beta if missing
    return risk_free_rate + beta * equity_risk_premium


def calculate_wacc(profile, income, balance,
                   risk_free_rate=0.043, equity_risk_premium=0.05):
    """
    WACC = (E/V * Re) + (D/V * Rd * (1 - Tax))

    Uses market cap (E), total debt (D), beta (for Re via CAPM),
    interest/debt (for Rd), and effective tax rate.
    Returns a dict of all components, or None if key data is missing.
    """
    if not profile or not balance:
        return None

    # Equity value = market cap
    E = profile.get("marketCap")
    beta = profile.get("beta")

    # Debt value = total debt (latest year)
    bal = balance[0] if balance else {}
    D = safe_get(bal, "totalDebt")
    if D is None:
        D = 0

    if E is None or E == 0:
        return None

    V = E + D
    weight_equity = E / V
    weight_debt = D / V

    # Cost of equity via CAPM
    Re = calculate_cost_of_equity(beta, risk_free_rate, equity_risk_premium)

    # Cost of debt = interest expense / total debt (latest year)
    inc = income[0] if income else {}
    interest = safe_get(inc, "interestExpense")
    if D and D != 0 and interest:
        Rd = abs(interest) / D
    else:
        Rd = 0.0

    # Effective tax rate (same approach as FCFF)
    pretax = safe_get(inc, "incomeBeforeTax", "pretaxIncome")
    tax = safe_get(inc, "incomeTaxExpense")
    if pretax and pretax != 0 and tax is not None:
        tax_rate = tax / pretax
        if tax_rate < 0 or tax_rate > 0.5:
            tax_rate = 0.21
    else:
        tax_rate = 0.21

    wacc = (weight_equity * Re) + (weight_debt * Rd * (1 - tax_rate))

    return {
        "WACC": wacc,
        "Cost of Equity (Re)": Re,
        "Cost of Debt (Rd)": Rd,
        "Weight Equity (E/V)": weight_equity,
        "Weight Debt (D/V)": weight_debt,
        "Beta": beta if beta is not None else 1.0,
        "Tax Rate": tax_rate,
        "Market Cap (E)": E,
        "Total Debt (D)": D,
    }

def run_dcf(income, cashflow, balance, profile, wacc,
            growth_rate=0.08, terminal_growth=0.025, years=5):
    """
    Full DCF valuation.
      1. Project FCFF forward `years` at growth_rate
      2. Terminal value via Gordon Growth
      3. Discount everything by WACC to present value
      4. Enterprise Value -> Equity Value -> per share

    Returns a dict with all steps, or None if inputs are missing.
    """
    # Need a starting FCFF and a valid WACC above terminal growth
    fcff_rows = calculate_fcff(income, cashflow)
    if not fcff_rows or fcff_rows[0].get("FCFF") is None:
        return None
    if wacc is None or wacc <= terminal_growth:
        # WACC must exceed terminal growth or the math breaks (negative/huge TV)
        return None

    base_fcff = fcff_rows[0]["FCFF"]

    # 1. Project FCFF forward
    projected = []
    fcff = base_fcff
    for yr in range(1, years + 1):
        fcff = fcff * (1 + growth_rate)
        projected.append({"year": yr, "fcff": fcff})

    # 2. Terminal value (at final projected year)
    final_fcff = projected[-1]["fcff"]
    terminal_value = final_fcff * (1 + terminal_growth) / (wacc - terminal_growth)

    # 3. Discount projected FCFF and terminal value to present
    pv_fcff_total = 0
    for p in projected:
        pv = p["fcff"] / ((1 + wacc) ** p["year"])
        p["pv"] = pv
        pv_fcff_total += pv

    pv_terminal = terminal_value / ((1 + wacc) ** years)

    enterprise_value = pv_fcff_total + pv_terminal

    # 4. Enterprise -> Equity -> per share
    bal = balance[0] if balance else {}
    total_debt = safe_get(bal, "totalDebt") or 0
    cash = safe_get(bal, "cashAndCashEquivalents",
                    "cashAndShortTermInvestments") or 0

    equity_value = enterprise_value - total_debt + cash

    shares = safe_get(profile, "sharesOutstanding")
    if shares is None or shares == 0:
        # Fall back: derive shares from market cap / price
        mcap = profile.get("marketCap")
        price = profile.get("price")
        if mcap and price and price != 0:
            shares = mcap / price
        else:
            shares = None

    intrinsic_per_share = equity_value / shares if shares else None
    market_price = profile.get("price")

    upside = None
    if intrinsic_per_share and market_price and market_price != 0:
        upside = (intrinsic_per_share - market_price) / market_price

    return {
        "base_fcff": base_fcff,
        "projected": projected,
        "terminal_value": terminal_value,
        "pv_terminal": pv_terminal,
        "pv_fcff_total": pv_fcff_total,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "shares": shares,
        "intrinsic_per_share": intrinsic_per_share,
        "market_price": market_price,
        "upside": upside,
        "assumptions": {
            "wacc": wacc,
            "growth_rate": growth_rate,
            "terminal_growth": terminal_growth,
            "years": years,
        },
    }

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