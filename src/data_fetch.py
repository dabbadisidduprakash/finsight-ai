"""
data_fetch.py - yfinance backend, FMP-compatible output shape.

Returns the same structures the old FMP version did:
  - profile: a dict
  - statements: a list of yearly dicts, newest first
so ratios.py, valuation.py and app.py need no changes.
"""

import yfinance as yf
import pandas as pd


# ---- Row-name aliases -------------------------------------------------
# yfinance row labels vary by company and sector, so each FMP key maps to
# a list of possible yfinance row names, tried in order.

INCOME_MAP = {
    "revenue": ["Total Revenue", "Operating Revenue"],
    "costOfRevenue": ["Cost Of Revenue", "Cost Of Goods Sold"],
    "grossProfit": ["Gross Profit"],
    "researchAndDevelopmentExpenses": ["Research And Development"],
    "sellingGeneralAndAdministrativeExpenses": ["Selling General And Administration", "Selling General And Administrative"],
    "otherExpenses": ["Other Operating Expenses"],
    "operatingExpenses": ["Operating Expense", "Total Expenses"],
    "interestIncome": ["Interest Income", "Interest Income Non Operating"],
    "operatingIncome": ["Operating Income", "EBIT", "Total Operating Income As Reported"],
    "netIncome": ["Net Income", "Net Income Common Stockholders",
                  "Net Income From Continuing Operation Net Minority Interest"],
    "eps": ["Diluted EPS", "Basic EPS"],
    "interestExpense": ["Interest Expense", "Interest Expense Non Operating"],
    "incomeBeforeTax": ["Pretax Income", "Income Before Tax"],
    "incomeTaxExpense": ["Tax Provision", "Income Tax Expense"],
    "ebitda": ["EBITDA", "Normalized EBITDA"],
    "epsDiluted": ["Diluted EPS"],
    "weightedAverageShsOutDil": ["Diluted Average Shares"],
    "weightedAverageShsOut": ["Basic Average Shares"],
    "ebit": ["EBIT", "Operating Income"],
}

BALANCE_MAP = {
    "totalAssets": ["Total Assets"],
    "totalNonCurrentAssets": ["Total Non Current Assets"],
    "totalNonCurrentLiabilities": ["Total Non Current Liabilities Net Minority Interest"],
    "totalLiabilitiesAndTotalEquity": ["Total Assets"],
    "totalLiabilities": ["Total Liabilities Net Minority Interest", "Total Liabilities"],
    "totalStockholdersEquity": ["Stockholders Equity", "Total Equity Gross Minority Interest", "Common Stock Equity"],
    "totalEquity": ["Stockholders Equity", "Total Equity Gross Minority Interest",
                    "Common Stock Equity"],
    "totalDebt": ["Total Debt", "Net Debt"],
    "totalCurrentAssets": ["Current Assets", "Total Current Assets"],
    "totalCurrentLiabilities": ["Current Liabilities", "Total Current Liabilities"],
    "cashAndCashEquivalents": ["Cash And Cash Equivalents",
                               "Cash Cash Equivalents And Short Term Investments"],
    "cashAndShortTermInvestments": ["Cash Cash Equivalents And Short Term Investments",
                                    "Cash And Cash Equivalents"],
    "inventory": ["Inventory"],
    "longTermDebt": ["Long Term Debt"],
    "shortTermInvestments": ["Other Short Term Investments"],
    "netReceivables": ["Accounts Receivable", "Receivables"],
    "otherCurrentAssets": ["Other Current Assets"],
    "propertyPlantEquipmentNet": ["Net PPE"],
    "goodwill": ["Goodwill"],
    "intangibleAssets": ["Other Intangible Assets", "Goodwill And Other Intangible Assets"],
    "longTermInvestments": ["Investments And Advances", "Long Term Equity Investment"],
    "otherNonCurrentAssets": ["Other Non Current Assets"],
    "accountPayables": ["Accounts Payable", "Payables"],
    "accruedExpenses": ["Current Accrued Expenses"],
    "shortTermDebt": ["Current Debt", "Current Debt And Capital Lease Obligation"],
    "deferredRevenue": ["Current Deferred Revenue"],
    "otherCurrentLiabilities": ["Other Current Liabilities"],
    "deferredTaxLiabilitiesNonCurrent": ["Non Current Deferred Taxes Liabilities"],
    "otherNonCurrentLiabilities": ["Other Non Current Liabilities"],
    "commonStock": ["Common Stock"],
    "retainedEarnings": ["Retained Earnings"],
    "additionalPaidInCapital": ["Additional Paid In Capital"],
    "treasuryStock": ["Treasury Stock"],
    "accumulatedOtherComprehensiveIncomeLoss": ["Gains Losses Not Affecting Retained Earnings"],
}

CASHFLOW_MAP = {
    "operatingCashFlow": ["Operating Cash Flow",
                          "Cash Flow From Continuing Operating Activities"],
    "netCashProvidedByOperatingActivities": ["Operating Cash Flow",
                          "Cash Flow From Continuing Operating Activities"],
    "capitalExpenditure": ["Capital Expenditure", "Purchase Of PPE"],
    "freeCashFlow": ["Free Cash Flow"],
    "netCashProvidedByInvestingActivities": ["Investing Cash Flow", "Cash Flow From Continuing Investing Activities"],
    "netCashProvidedByFinancingActivities": ["Financing Cash Flow", "Cash Flow From Continuing Financing Activities"],
    "netChangeInCash": ["Changes In Cash"],
    "cashAtEndOfPeriod": ["End Cash Position"],
    "netIncome": ["Net Income From Continuing Operations", "Net Income"],
    "stockBasedCompensation": ["Stock Based Compensation"],
    "deferredIncomeTax": ["Deferred Income Tax"],
    "changeInWorkingCapital": ["Change In Working Capital"],
    "otherNonCashItems": ["Other Non Cash Items"],
    "investmentsInPropertyPlantAndEquipment": ["Net PPE Purchase And Sale", "Capital Expenditure"],
    "acquisitionsNet": ["Net Business Purchase And Sale"],
    "purchasesOfInvestments": ["Purchase Of Investment"],
    "salesMaturitiesOfInvestments": ["Sale Of Investment"],
    "otherInvestingActivities": ["Net Other Investing Changes"],
    "netDebtIssuance": ["Net Issuance Payments Of Debt"],
    "commonStockIssuance": ["Common Stock Issuance", "Net Common Stock Issuance", "Issuance Of Capital Stock"],
    "commonStockRepurchased": ["Repurchase Of Capital Stock"],
    "netDividendsPaid": ["Cash Dividends Paid", "Common Stock Dividend Paid"],
    "otherFinancingActivities": ["Net Other Financing Charges"],
    "effectOfForexChangesOnCash": ["Effect Of Exchange Rate Changes"],
    "cashAtBeginningOfPeriod": ["Beginning Cash Position"],
    "depreciationAndAmortization": ["Depreciation And Amortization",
                                    "Depreciation Amortization Depletion"],
}


def _row(df, aliases):
    """Return a df row matching any alias (case-insensitive), else None."""
    if df is None or df.empty:
        return None
    lookup = {str(i).strip().lower(): i for i in df.index}
    for a in aliases:
        hit = lookup.get(a.strip().lower())
        if hit is not None:
            return df.loc[hit]
    return None


def _to_records(df, field_map, limit=5):
    """Convert a yfinance statement DataFrame into FMP-style yearly dicts."""
    if df is None or df.empty:
        return None

    df = df.dropna(axis=1, thresh=max(3, int(len(df.index)*0.3)))
    cols = list(df.columns)[:limit]
    records = []

    for col in cols:
        rec = {}
        year = getattr(col, "year", None) or str(col)[:4]
        rec["fiscalYear"] = str(year)
        rec["calendarYear"] = str(year)
        rec["date"] = str(col)[:10]

        for fmp_key, aliases in field_map.items():
            series = _row(df, aliases)
            val = None
            if series is not None:
                try:
                    raw = series.loc[col] if col in series.index else None
                    if raw is not None and not pd.isna(raw):
                        val = float(raw)
                except Exception:
                    val = None
            rec[fmp_key] = val

        records.append(rec)

    return records if records else None


def _ticker(symbol):
    return yf.Ticker(str(symbol).strip().upper())


def get_company_profile(ticker):
    """Return an FMP-shaped profile dict, or None."""
    try:
        info = _ticker(ticker).info
    except Exception as e:
        print(f"ERROR fetching profile for {ticker}: {e}")
        return None

    if not info or not info.get("symbol"):
        return None

    mcap = info.get("marketCap")
    price = (info.get("currentPrice")
             or info.get("regularMarketPrice")
             or info.get("previousClose"))

    raw_beta = info.get("beta")

    return {
        "symbol": info.get("symbol"),
        "companyName": info.get("longName") or info.get("shortName"),
        "price": price,
        "beta": raw_beta,
        "betaReported": raw_beta is not None,
        "marketCap": mcap,
        "mktCap": mcap,
        "sharesOutstanding": info.get("sharesOutstanding"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "currency": info.get("currency"),
        "exchange": info.get("exchange"),
        "description": info.get("longBusinessSummary"),
        "ceo": info.get("companyOfficers", [{}])[0].get("name")
               if info.get("companyOfficers") else None,
        "website": info.get("website"),
        "country": info.get("country"),
        "fullTimeEmployees": info.get("fullTimeEmployees"),
    }


def get_income_statement(ticker, limit=5):
    try:
        return _to_records(_ticker(ticker).income_stmt, INCOME_MAP, limit)
    except Exception as e:
        print(f"ERROR fetching income statement for {ticker}: {e}")
        return None


def get_balance_sheet(ticker, limit=5):
    try:
        return _to_records(_ticker(ticker).balance_sheet, BALANCE_MAP, limit)
    except Exception as e:
        print(f"ERROR fetching balance sheet for {ticker}: {e}")
        return None


def get_cash_flow(ticker, limit=5):
    try:
        return _to_records(_ticker(ticker).cashflow, CASHFLOW_MAP, limit)
    except Exception as e:
        print(f"ERROR fetching cash flow for {ticker}: {e}")
        return None


if __name__ == "__main__":
    for t in ["AAPL", "IBM", "CTSH", "EPAM", "ACN"]:
        print(f"\n===== {t} =====")
        p = get_company_profile(t)
        print("Profile:", p.get("companyName") if p else "FAILED")
        if p:
            print("  Price:", p.get("price"), "| Beta:", p.get("beta"),
                  "| MktCap:", p.get("marketCap"))

        inc = get_income_statement(t)
        print("Income:", f"{len(inc)} yrs, revenue={inc[0]['revenue']}"
              if inc else "FAILED")

        bal = get_balance_sheet(t)
        print("Balance:", f"{len(bal)} yrs, assets={bal[0]['totalAssets']}"
              if bal else "FAILED")

        cf = get_cash_flow(t)
        print("CashFlow:", f"{len(cf)} yrs, ocf={cf[0]['operatingCashFlow']}"
              if cf else "FAILED")