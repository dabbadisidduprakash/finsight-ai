"""
capbudget.py - Capital Budgeting / Project Appraisal model.

Evaluates whether a specific project should be undertaken: computes CFAT
(cash flow after tax) per year, then NPV and IRR against the project's WACC
(hurdle rate). Standalone - all inputs are project-specific.

Validated against the reference Excel model (CFAT and IRR match exactly).
Uses the TECHNICALLY-CORRECT NPV convention (initial outflow at t=0), which
differs from Excel's built-in NPV() that discounts the first cash flow by one
period - a common modeling error.
"""


def _npv(rate, cashflows):
    """Correct NPV: cashflows[0] is at t=0 (initial outflow, undiscounted)."""
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cashflows))


def _npv_excel(rate, cashflows):
    """Excel-style NPV: first cash flow discounted by one period (for comparison)."""
    return sum(cf / (1 + rate) ** (t + 1) for t, cf in enumerate(cashflows))


def _irr(cashflows):
    """IRR via bisection. cashflows[0] at t=0."""
    lo, hi = -0.9, 10.0
    f_lo = _npv(lo, cashflows)
    for _ in range(300):
        mid = (lo + hi) / 2
        f_mid = _npv(mid, cashflows)
        if abs(f_mid) < 1e-7:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo = mid
            f_lo = f_mid
    return (lo + hi) / 2


def compute_wacc(beta, rf, rm, kd_pretax, tax_rate, equity, debt):
    """Project hurdle rate: CAPM cost of equity + after-tax cost of debt, weighted."""
    ke = rf + beta * (rm - rf)
    kd = kd_pretax * (1 - tax_rate)
    total = equity + debt
    we = equity / total if total else 0
    wd = debt / total if total else 0
    return {"ke": ke, "kd": kd, "we": we, "wd": wd, "wacc": ke * we + kd * wd}


def build_capital_budget(inp):
    """
    Build the full capital budgeting schedule from project inputs.
    Returns CFAT per year, depreciation schedule, WACC, NPV (correct + excel), IRR.
    """
    rev = inp["revenue"]
    n = len(rev)
    cogs_pct = inp["cogs_pct"]
    sga_pct = inp["sga_pct"]
    tax = inp["tax_rate"]
    dep_rate = inp["dep_rate"]
    ppe0 = inp["ppe_initial"]
    wc_pct = inp["wc_pct"]
    wc_initial = inp["wc_initial"]
    salvage_wc_pct = inp["salvage_wc_pct"]
    salvage_fa = inp["salvage_fa"]
    tax_shield_loss = inp["tax_shield_loss"]
    cannibalization = inp["cannibalization"]
    additions = inp["additions"]  # PP&E added at start of each year (index 0 = year 1)

    # Working capital: WC held in year t (1..n-1) = next year's revenue * wc_pct.
    # Final year: WC unwinds (recovered via salvage line, not a change line).
    wc = [wc_initial]
    for t in range(n):
        wc.append(rev[t + 1] * wc_pct if t + 1 < n else 0)

    # Depreciation schedule (WDV) including mid-project additions
    dep, opening_bv, closing_bv = [], [], []
    opening = ppe0
    for t in range(n):
        block = opening + additions[t]
        d = block * dep_rate
        close = block - d
        opening_bv.append(opening)
        dep.append(d)
        closing_bv.append(close)
        opening = close

    # Project P&L
    results = []
    for t in range(n):
        r = rev[t]
        c = r * cogs_pct
        gp = r - c
        sga = r * sga_pct
        ebitda = gp - sga
        d = dep[t]
        ebit = ebitda - d
        ebit_at = ebit * (1 - tax)
        results.append({"revenue": r, "cogs": c, "gross_profit": gp, "sga": sga,
                        "ebitda": ebitda, "depreciation": d, "ebit": ebit,
                        "ebit_after_tax": ebit_at})

    # CFAT
    cfat = [-(ppe0 + wc_initial)]  # t=0 initial outflow
    for t in range(n):
        ebit_at = results[t]["ebit_after_tax"]
        add_dep = results[t]["depreciation"]
        # Working capital change only for non-final years; final year recovers via salvage
        d_wc = (wc[t + 1] - wc[t]) if t < n - 1 else 0
        d_fa = additions[t]
        s_wc = wc[t] * salvage_wc_pct if t == n - 1 else 0
        s_fa = salvage_fa if t == n - 1 else 0
        t_shield = tax_shield_loss if t == n - 1 else 0
        cann = cannibalization
        cf = ebit_at + add_dep - d_wc - d_fa + s_wc + s_fa + t_shield - cann
        cfat.append(cf)
        results[t].update({"d_wc": d_wc, "d_fa": d_fa, "salvage_wc": s_wc,
                           "salvage_fa": s_fa, "tax_shield": t_shield,
                           "cannibalization": cann, "cfat": cf})

    w = compute_wacc(inp["beta"], inp["rf"], inp["rm"], inp["kd_pretax"],
                     inp["tax_rate"], inp["equity"], inp["debt"])
    hurdle = w["wacc"]

    return {
        "cfat": cfat, "results": results, "dep": dep,
        "opening_bv": opening_bv, "closing_bv": closing_bv, "wc": wc,
        "wacc": w, "hurdle": hurdle,
        "npv": _npv(hurdle, cfat),
        "npv_excel": _npv_excel(hurdle, cfat),
        "irr": _irr(cfat),
        "initial_outflow": ppe0 + wc_initial,
        "years": n,
    }

def derive_capbudget_defaults(income, balance, cashflow, years=7):
    """
    Derive capital-budgeting defaults from the loaded company's real data.
    Year-1 revenue anchors to the company's last actual revenue; other years
    project at the historical growth rate. Cost ratios come from actuals.
    Everything remains editable in the UI. NOTE: uses whole-company revenue as
    the anchor - a real project would be a fraction, but this is editable.
    """
    def _g(d, *keys):
        for k in keys:
            v = d.get(k)
            if isinstance(v, (int, float)):
                return v
        return 0

    inc0 = income[0] if income else {}
    bal0 = balance[0] if balance else {}
    cf0 = cashflow[0] if cashflow else {}

    revenue0 = _g(inc0, "revenue") or 100.0

    revs = [_g(i, "revenue") for i in income if _g(i, "revenue") > 0]
    growth = 0.06
    if len(revs) >= 2 and revs[1] > 0:
        growth = max(min((revs[0] - revs[1]) / revs[1], 0.30), -0.05)

    cogs_pct = 1 - (_g(inc0, "grossProfit") / revenue0) if revenue0 else 0.48
    sga_pct = _g(inc0, "sellingGeneralAndAdministrativeExpenses") / revenue0 if revenue0 else 0.08
    if sga_pct <= 0:
        sga_pct = _g(inc0, "operatingExpenses") / revenue0 * 0.5 if revenue0 else 0.08

    pretax = _g(inc0, "incomeBeforeTax")
    tax = _g(inc0, "incomeTaxExpense")
    tax_rate = (tax / pretax) if pretax > 0 else 0.25

    ppe = _g(bal0, "propertyPlantEquipmentNet")
    da = _g(inc0, "depreciationAndAmortization")
    dep_rate = (da / ppe) if ppe > 0 else 0.15

    # Build revenue line: year 1 = anchor, then grow
    revenue = []
    r = revenue0
    for i in range(years):
        if i == 0:
            revenue.append(revenue0)
        else:
            r = r * (1 + growth)
            revenue.append(r)

    debt = _g(bal0, "totalDebt")
    equity = _g(bal0, "totalStockholdersEquity", "totalEquity")
    # scale initial PP&E and WC off revenue for a sensible default
    ppe_initial = revenue0 * 0.15
    wc_initial = revenue0 * 0.05

    return {
        "revenue": revenue,
        "growth": round(growth, 4),
        "additions": [0.0] * years,
        "cogs_pct": round(max(min(cogs_pct, 0.9), 0.0), 4),
        "sga_pct": round(max(min(sga_pct, 0.4), 0.0), 4),
        "tax_rate": round(max(min(tax_rate, 0.4), 0.0), 4),
        "dep_rate": round(max(min(dep_rate, 0.5), 0.01), 4),
        "ppe_initial": round(ppe_initial, 0),
        "wc_pct": 0.25,
        "wc_initial": round(wc_initial, 0),
        "salvage_wc_pct": 0.8,
        "salvage_fa": round(ppe_initial * 0.4, 0),
        "tax_shield_loss": 0.0,
        "cannibalization": 0.0,
        "beta": 1.2,
        "rf": 0.043,
        "rm": 0.10,
        "kd_pretax": 0.06,
        "equity": equity if equity > 0 else 60.0,
        "debt": debt if debt > 0 else 30.0,
    }

def excel_defaults():
    """Reference-Excel inputs (produces the validated CFAT/IRR)."""
    return {
        "revenue": [60, 90, 120, 150, 180, 150, 120],
        "additions": [0, 0, 15, 0, 15, 0, 0],  # year 3 and year 5 additions
        "cogs_pct": 0.48,
        "sga_pct": 0.08,
        "tax_rate": 0.25,
        "dep_rate": 0.15,
        "ppe_initial": 75,
        "wc_pct": 0.25,
        "wc_initial": 15,
        "salvage_wc_pct": 0.8,
        "salvage_fa": 30,
        "tax_shield_loss": 15.91 * 0.25,
        "cannibalization": 5 * 0.75,
        "beta": 1.75,
        "rf": 0.0668,
        "rm": 0.16,
        "kd_pretax": 0.15,
        "equity": 60,
        "debt": 30,
    }


if __name__ == "__main__":
    out = build_capital_budget(excel_defaults())
    print("WACC (Hurdle):", round(out["hurdle"] * 100, 2), "%")
    print("CFAT:", [round(c, 2) for c in out["cfat"]])
    print("NPV (correct):", round(out["npv"], 2))
    print("NPV (Excel-style):", round(out["npv_excel"], 2))
    print("IRR:", round(out["irr"] * 100, 2), "%")