"""
forecasting.py - Integrated 3-statement projection model (senior-analyst grade).

Projects Income Statement, Balance Sheet, and Cash Flow 5 years forward from
the company's real latest-year data. BALANCES by construction every year
(Assets = Liabilities + Equity), using cash as the plug and a Year-0 equity
reconciling item.

Standard linkages (required by accounting):
  Net income -> retained earnings & top of cash flow
  Depreciation -> IS expense & added back in cash flow
  PP&E rolls forward: prior + capex - depreciation
  Retained earnings roll forward: prior + net income - dividends
  Ending cash (CF) -> cash line (BS)

Operating/financing lines are projected from drivers; non-operating lines
(goodwill, intangibles, deferred taxes, etc.) are held flat - the standard
convention when no driver exists.
"""


def _g(d, *keys):
    for k in keys:
        v = d.get(k)
        if isinstance(v, (int, float)):
            return v
    return 0


def derive_assumptions(income, balance, cashflow):
    """Derive default assumptions from the latest historicals (all adjustable)."""
    inc0 = income[0] if income else {}
    bal0 = balance[0] if balance else {}
    cf0 = cashflow[0] if cashflow else {}

    revenue = _g(inc0, "revenue") or 1

    growth = 0.06
    revs = [_g(i, "revenue") for i in income if _g(i, "revenue") > 0]
    if len(revs) >= 2:
        gr = []
        for i in range(len(revs) - 1):
            newer, older = revs[i], revs[i + 1]
            if older > 0:
                gr.append((newer - older) / older)
        if gr:
            growth = max(min(sum(gr) / len(gr), 0.30), -0.05)

    gross_margin = _g(inc0, "grossProfit") / revenue
    opex = _g(inc0, "operatingExpenses") / revenue
    da = _g(inc0, "depreciationAndAmortization")
    ppe = _g(bal0, "propertyPlantEquipmentNet")
    da_rate = (da / ppe) if ppe > 0 else 0.15
    capex = abs(_g(cf0, "capitalExpenditure", "investmentsInPropertyPlantAndEquipment"))
    capex_pct = capex / revenue if revenue else 0.03

    pretax = _g(inc0, "incomeBeforeTax")
    tax = _g(inc0, "incomeTaxExpense")
    tax_rate = (tax / pretax) if pretax > 0 else 0.21

    ar = _g(bal0, "netReceivables", "accountsReceivables")
    inv = _g(bal0, "inventory")
    ap = _g(bal0, "accountPayables", "totalPayables")
    cogs = revenue - _g(inc0, "grossProfit")
    ar_days = (ar / revenue * 365) if revenue else 40
    inv_days = (inv / cogs * 365) if cogs > 0 else 20
    ap_days = (ap / cogs * 365) if cogs > 0 else 40

    debt = _g(bal0, "totalDebt")
    int_exp = _g(inc0, "interestExpense")
    int_rate = (int_exp / debt) if debt > 0 else 0.04

    div = abs(_g(cf0, "netDividendsPaid", "commonDividendsPaid"))
    ni = _g(inc0, "netIncome")
    payout = max(min((div / ni) if ni > 0 else 0.0, 1.0), 0.0)

    return {
        "revenue0": revenue,
        "growth": round(growth, 4),
        "gross_margin": round(gross_margin, 4),
        "opex_pct": round(opex, 4),
        "da_rate": round(da_rate, 4),
        "capex_pct": round(capex_pct, 4),
        "tax_rate": round(tax_rate, 4),
        "ar_days": round(ar_days, 1),
        "inv_days": round(inv_days, 1),
        "ap_days": round(ap_days, 1),
        "int_rate": round(int_rate, 4),
        "payout": round(payout, 4),
    }


def build_projection(income, balance, cashflow, assumptions, years=5):
    """Build the integrated 5-year projection. Returns dict of statements."""
    a = assumptions
    bal0 = balance[0] if balance else {}

    cash0 = _g(bal0, "cashAndCashEquivalents")
    st_inv0 = _g(bal0, "shortTermInvestments")
    ppe0 = _g(bal0, "propertyPlantEquipmentNet")
    debt0 = _g(bal0, "totalDebt")
    re0 = _g(bal0, "retainedEarnings")

    goodwill = _g(bal0, "goodwill")
    intangibles = _g(bal0, "intangibleAssets")
    lt_inv = _g(bal0, "longTermInvestments")
    other_nca = _g(bal0, "otherNonCurrentAssets")
    other_ca = _g(bal0, "otherCurrentAssets")
    deferred_tax = _g(bal0, "deferredTaxLiabilitiesNonCurrent")
    other_ncl = _g(bal0, "otherNonCurrentLiabilities")
    other_cl = _g(bal0, "otherCurrentLiabilities")
    accrued = _g(bal0, "accruedExpenses")

    # Year-0 reconciling plug so the model balances from Year 1
    _y0_assets = (cash0 + st_inv0 + _g(bal0, "netReceivables", "accountsReceivables")
                  + _g(bal0, "inventory") + other_ca + ppe0 + goodwill + intangibles
                  + lt_inv + other_nca)
    _y0_liab = (_g(bal0, "accountPayables", "totalPayables") + accrued + other_cl
                + debt0 + deferred_tax + other_ncl)
    other_equity = _y0_assets - _y0_liab - re0

    rev_prev = a["revenue0"]
    ppe_prev = ppe0
    re_prev = re0
    debt_level = debt0
    ar_prev = _g(bal0, "netReceivables", "accountsReceivables")
    inv_prev = _g(bal0, "inventory")
    ap_prev = _g(bal0, "accountPayables", "totalPayables")
    cash_prev = cash0

    IS = {k: [] for k in ["Revenue", "COGS", "Gross Profit", "Operating Expenses",
                          "EBITDA", "Depreciation & Amortization", "EBIT",
                          "Interest Expense", "Pre-Tax Income", "Tax", "Net Income",
                          "Dividends", "Retained Earnings Added"]}
    BS = {k: [] for k in ["Cash & Equivalents", "Short-Term Investments",
                          "Accounts Receivable", "Inventory", "Other Current Assets",
                          "Total Current Assets", "Net PP&E", "Goodwill",
                          "Intangible Assets", "Long-Term Investments",
                          "Other Non-Current Assets", "Total Non-Current Assets",
                          "TOTAL ASSETS", "Accounts Payable", "Accrued Expenses",
                          "Other Current Liabilities", "Total Current Liabilities",
                          "Long-Term Debt", "Deferred Tax Liabilities",
                          "Other Non-Current Liabilities", "Total Non-Current Liabilities",
                          "TOTAL LIABILITIES", "Common Equity (reconciling)",
                          "Retained Earnings", "TOTAL EQUITY", "TOTAL LIAB. & EQUITY"]}
    CF = {k: [] for k in ["Net Income", "Depreciation & Amortization",
                          "Change in Working Capital", "Cash from Operations",
                          "Capital Expenditure", "Cash from Investing",
                          "Change in Debt", "Dividends Paid", "Cash from Financing",
                          "Net Change in Cash", "Beginning Cash", "Ending Cash"]}
    SCH = {k: [] for k in ["PP&E: Beginning", "PP&E: + CapEx", "PP&E: - Depreciation",
                          "PP&E: Ending", "Debt: Beginning", "Debt: Ending",
                          "Interest on Debt"]}
    balance_check = []

    for y in range(1, years + 1):
        rev = rev_prev * (1 + a["growth"])
        cogs = rev * (1 - a["gross_margin"])
        gross = rev - cogs
        opex = rev * a["opex_pct"]
        ebitda = gross - opex
        dep = ppe_prev * a["da_rate"]
        ebit = ebitda - dep
        interest = debt_level * a["int_rate"]
        pretax = ebit - interest
        tax = max(pretax, 0) * a["tax_rate"]
        ni = pretax - tax
        div = max(ni, 0) * a["payout"]
        re_add = ni - div

        IS["Revenue"].append(rev)
        IS["COGS"].append(-cogs)
        IS["Gross Profit"].append(gross)
        IS["Operating Expenses"].append(-opex)
        IS["EBITDA"].append(ebitda)
        IS["Depreciation & Amortization"].append(-dep)
        IS["EBIT"].append(ebit)
        IS["Interest Expense"].append(-interest)
        IS["Pre-Tax Income"].append(pretax)
        IS["Tax"].append(-tax)
        IS["Net Income"].append(ni)
        IS["Dividends"].append(-div)
        IS["Retained Earnings Added"].append(re_add)

        ar = rev / 365 * a["ar_days"]
        inv = cogs / 365 * a["inv_days"]
        ap = cogs / 365 * a["ap_days"]
        change_wc = -((ar - ar_prev) + (inv - inv_prev)) + (ap - ap_prev)

        capex = rev * a["capex_pct"]
        ppe_end = ppe_prev + capex - dep

        cfo = ni + dep + change_wc
        cfi = -capex
        d_debt = 0
        cff = d_debt - div
        net_change = cfo + cfi + cff
        cash_end = cash_prev + net_change

        CF["Net Income"].append(ni)
        CF["Depreciation & Amortization"].append(dep)
        CF["Change in Working Capital"].append(change_wc)
        CF["Cash from Operations"].append(cfo)
        CF["Capital Expenditure"].append(-capex)
        CF["Cash from Investing"].append(cfi)
        CF["Change in Debt"].append(d_debt)
        CF["Dividends Paid"].append(-div)
        CF["Cash from Financing"].append(cff)
        CF["Net Change in Cash"].append(net_change)
        CF["Beginning Cash"].append(cash_prev)
        CF["Ending Cash"].append(cash_end)

        SCH["PP&E: Beginning"].append(ppe_prev)
        SCH["PP&E: + CapEx"].append(capex)
        SCH["PP&E: - Depreciation"].append(-dep)
        SCH["PP&E: Ending"].append(ppe_end)
        SCH["Debt: Beginning"].append(debt_level)
        SCH["Debt: Ending"].append(debt_level + d_debt)
        SCH["Interest on Debt"].append(interest)

        re_end = re_prev + re_add
        tca = cash_end + st_inv0 + ar + inv + other_ca
        tnca = ppe_end + goodwill + intangibles + lt_inv + other_nca
        ta = tca + tnca
        tcl = ap + accrued + other_cl
        tncl = debt_level + deferred_tax + other_ncl
        tl = tcl + tncl
        te = other_equity + re_end
        tle = tl + te

        BS["Cash & Equivalents"].append(cash_end)
        BS["Short-Term Investments"].append(st_inv0)
        BS["Accounts Receivable"].append(ar)
        BS["Inventory"].append(inv)
        BS["Other Current Assets"].append(other_ca)
        BS["Total Current Assets"].append(tca)
        BS["Net PP&E"].append(ppe_end)
        BS["Goodwill"].append(goodwill)
        BS["Intangible Assets"].append(intangibles)
        BS["Long-Term Investments"].append(lt_inv)
        BS["Other Non-Current Assets"].append(other_nca)
        BS["Total Non-Current Assets"].append(tnca)
        BS["TOTAL ASSETS"].append(ta)
        BS["Accounts Payable"].append(ap)
        BS["Accrued Expenses"].append(accrued)
        BS["Other Current Liabilities"].append(other_cl)
        BS["Total Current Liabilities"].append(tcl)
        BS["Long-Term Debt"].append(debt_level)
        BS["Deferred Tax Liabilities"].append(deferred_tax)
        BS["Other Non-Current Liabilities"].append(other_ncl)
        BS["Total Non-Current Liabilities"].append(tncl)
        BS["TOTAL LIABILITIES"].append(tl)
        BS["Common Equity (reconciling)"].append(other_equity)
        BS["Retained Earnings"].append(re_end)
        BS["TOTAL EQUITY"].append(te)
        BS["TOTAL LIAB. & EQUITY"].append(tle)

        balance_check.append(ta - tle)

        rev_prev = rev
        ppe_prev = ppe_end
        re_prev = re_end
        ar_prev, inv_prev, ap_prev = ar, inv, ap
        cash_prev = cash_end

    return {
        "years": ["Year " + str(i) for i in range(1, years + 1)],
        "income": IS,
        "balance": BS,
        "cashflow": CF,
        "schedules": SCH,
        "balance_check": balance_check,
    }