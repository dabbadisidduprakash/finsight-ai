"""
app.py - FinSight AI. Fully-structured financial statements.
"""
import streamlit as st
import pandas as pd
from src.data_fetch import (
    get_company_profile, get_income_statement,
    get_balance_sheet, get_cash_flow,
)
from src.ratios import calculate_ratios
from src.valuation import (
    calculate_fcff, calculate_wacc, run_dcf,
    calculate_margin_of_safety, sensitivity_analysis, is_financial_sector,
)
from src.ai_analysis import (
    get_ai_analysis, get_investment_memo, get_executive_summary,
)
from src.recommendation import get_recommendation

st.set_page_config(page_title="FinSight AI", page_icon="chart_with_upwards_trend", layout="wide")


# ---------- Password gate ----------
def _get_password():
    try:
        if "APP_PASSWORD" in st.secrets:
            return st.secrets["APP_PASSWORD"]
    except Exception:
        pass
    import os
    return os.getenv("APP_PASSWORD")


def check_password():
    correct = _get_password()
    if not correct:
        return True
    if st.session_state.get("password_ok"):
        return True
    st.title("FinSight AI")
    st.caption("AI Investment Committee Assistant")
    pw = st.text_input("Enter access password", type="password")
    if st.button("Enter"):
        if pw == correct:
            st.session_state["password_ok"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()


check_password()
# ---------- End password gate ----------

st.title("FinSight AI")
st.caption("AI Investment Committee Assistant - DCF Valuation, Ratio Analysis, Grounded AI Insight")
st.divider()

c_input, c_btn = st.columns([4, 1])
with c_input:
    ticker = st.text_input(
        "US stock ticker", value="AAPL", label_visibility="collapsed",
        placeholder="Enter a US stock ticker (e.g. AAPL, MSFT, GOOGL)",
    ).replace(" ", "").upper()
with c_btn:
    analyze = st.button("Analyze", use_container_width=True)

if analyze:
    if not ticker:
        st.warning("Please enter a ticker symbol.")
    else:
        with st.spinner("Fetching data for " + ticker + "..."):
            profile = get_company_profile(ticker)
            income = get_income_statement(ticker)
            balance = get_balance_sheet(ticker)
            cashflow = get_cash_flow(ticker)
        if profile is None:
            st.error("Could not find data for '" + ticker + "'. Check the ticker (US-listed only), or the API key may have hit its daily limit.")
        else:
            st.session_state["profile"] = profile
            st.session_state["income"] = income
            st.session_state["balance"] = balance
            st.session_state["cashflow"] = cashflow
            for k in ["ai_result", "memo_result", "exec_summary", "dcf"]:
                st.session_state.pop(k, None)

if "profile" in st.session_state:
    profile = st.session_state["profile"]
    income = st.session_state.get("income")
    balance = st.session_state.get("balance")
    cashflow = st.session_state.get("cashflow")

    col_logo, col_info = st.columns([1, 6])
    with col_logo:
        if profile.get("image"):
            st.image(profile["image"], width=72)
    with col_info:
        st.subheader(profile.get("companyName", "Unknown"))
        mcap = profile.get("marketCap")
        mcap_str = "$" + format(mcap, ",.0f") if isinstance(mcap, (int, float)) else "N/A"
        price_val = profile.get("price")
        price_txt = "$" + format(price_val, ",.2f") if isinstance(price_val, (int, float)) else "N/A"
        st.markdown("**Sector:** " + str(profile.get("sector", "N/A")) + "  \n"
                    + "**Price:** " + price_txt.replace("$", "\\$")
                    + " &nbsp;&nbsp; **Market Cap:** " + mcap_str.replace("$", "\\$"))

    st.divider()
    ratios = calculate_ratios(income, balance, cashflow, profile)
    is_financial = is_financial_sector(profile)

    if "dcf" not in st.session_state and not is_financial:
        dw = calculate_wacc(profile, income, balance)
        if dw:
            dd = run_dcf(income, cashflow, balance, profile, dw["WACC"],
                         growth_rate=0.08, terminal_growth=0.025)
            if dd:
                st.session_state["dcf"] = dd

    tabs = st.tabs(["Dashboard", "Income Statement", "Balance Sheet",
                    "Cash Flow", "Ratios", "Valuation", "AI Analysis", "Recommendation"])
    (tab_dash, tab1, tab2, tab3, tab4, tab5, tab6, tab7) = tabs

    def _year_labels(data):
        labels = []
        for i, item in enumerate(data):
            y = item.get("fiscalYear") or item.get("calendarYear") or item.get("date", i)
            labels.append(str(y)[:4] if item.get("date") else str(y))
        return labels

    def show_structured(data, layout):
        """
        layout: list of ('header'|'line'|'subtotal', label, field_or_None)
        Structure shown via text markers (no styler, to avoid duplicate-label issues).
        """
        if not data:
            st.warning("No data available for this statement.")
            return
        years = _year_labels(data)
        display_rows = []
        index_labels = []
        seen = {}
        for kind, label, field in layout:
            # Make labels unique (styler-safe) by suffixing duplicates invisibly
            base = label
            if kind == "header":
                disp = "  " + label.upper()
            elif kind == "subtotal":
                disp = label
            else:
                disp = "   " + label  # indent line items
            # ensure uniqueness
            if disp in seen:
                seen[disp] += 1
                disp = disp + " " * seen[disp]
            else:
                seen[disp] = 0
            index_labels.append(disp)

            if kind == "header":
                display_rows.append(["" for _ in data])
            else:
                vals = []
                for item in data:
                    v = item.get(field) if field else None
                    vals.append(format(v, ",.0f") if isinstance(v, (int, float)) else "-")
                display_rows.append(vals)

        df = pd.DataFrame(display_rows, index=index_labels, columns=years)
        st.dataframe(df, use_container_width=True, height=(len(index_labels) + 1) * 35 + 3)

    # ================= DASHBOARD =================
    with tab_dash:
        st.markdown("## Company Dashboard")
        d1, d2, d3, d4 = st.columns(4)
        price = profile.get("price")
        d1.metric("Price", "$" + format(price, ",.2f") if isinstance(price, (int, float)) else "N/A")
        pe = ratios[0].get("P/E") if ratios else None
        d2.metric("P/E", format(pe, ".1f") if isinstance(pe, (int, float)) else "N/A")
        nm = ratios[0].get("Net Margin") if ratios else None
        d3.metric("Net Margin", format(nm*100, ".1f") + "%" if isinstance(nm, (int, float)) else "N/A")
        roe = ratios[0].get("ROE") if ratios else None
        d4.metric("ROE", format(roe*100, ".0f") + "%" if isinstance(roe, (int, float)) else "N/A")

        if isinstance(roe, (int, float)) and roe > 0.50:
            st.caption("Note: ROE above 50% often reflects a small equity base (commonly from share buybacks) rather than profitability alone - read it alongside net margin and ROA.")

        st.divider()
        dcf = st.session_state.get("dcf")
        if is_financial:
            st.warning("DCF not applicable - this is a financial-sector company (bank/insurer). DCF does not work for financials; analysts use P/E, Price-to-Book, or dividend-discount models. See the Ratios tab.")
        elif dcf and dcf.get("intrinsic_per_share") is not None:
            v1, v2, v3 = st.columns(3)
            v1.metric("Intrinsic Value", "$" + format(dcf["intrinsic_per_share"], ",.2f"))
            v2.metric("Market Price", "$" + format(dcf["market_price"], ",.2f"))
            up = dcf.get("upside")
            v3.metric("Upside/(Downside)", format(up*100, "+.1f") + "%" if up is not None else "N/A")
            mos = calculate_margin_of_safety(dcf["intrinsic_per_share"], dcf["market_price"])
            rec = get_recommendation(up, mos, ratios)
            banner = "**Recommendation: " + rec["recommendation"] + "** (Confidence: " + rec["confidence_label"] + ")"
            {"success": st.success, "warning": st.warning, "error": st.error, "info": st.info}[rec["color"]](banner)
            if st.button("Generate Executive Summary"):
                with st.spinner("Gemini is summarizing..."):
                    st.session_state["exec_summary"] = get_executive_summary(profile, ratios, dcf, rec)
            es = st.session_state.get("exec_summary")
            if es:
                if es.get("error"):
                    st.error(es["error"])
                else:
                    st.markdown("**Executive Summary**")
                    st.info(es["summary"])
        else:
            st.info("Valuation unavailable - try re-analyzing the company.")

        st.divider()
        st.markdown("### 5-Year Trends")

        def _trend(data, field, label):
            if not data:
                return None
            rows = [{"Year": str(it.get("fiscalYear") or it.get("date", ""))[:4], label: it.get(field)}
                    for it in data if it.get(field) is not None]
            if not rows:
                return None
            return pd.DataFrame(rows).iloc[::-1].set_index("Year")

        ch1, ch2 = st.columns(2)
        with ch1:
            r = _trend(income, "revenue", "Revenue")
            if r is not None:
                st.markdown("**Revenue**"); st.bar_chart(r)
            n = _trend(income, "netIncome", "Net Income")
            if n is not None:
                st.markdown("**Net Income**"); st.bar_chart(n)
        with ch2:
            fr = calculate_fcff(income, cashflow)
            if fr:
                fd = pd.DataFrame([{"Year": x["Year"][:4], "FCFF": x["FCFF"]} for x in fr if x.get("FCFF") is not None])
                if not fd.empty:
                    st.markdown("**Free Cash Flow (FCFF)**"); st.bar_chart(fd.iloc[::-1].set_index("Year"))
            o = _trend(cashflow, "operatingCashFlow", "Operating CF")
            if o is not None:
                st.markdown("**Operating Cash Flow**"); st.bar_chart(o)

    # ================= INCOME STATEMENT =================
    with tab1:
        st.markdown("**Income Statement** (last 5 years, USD)")
        show_structured(income, [
            ("header", "REVENUE", None),
            ("line", "Revenue", "revenue"),
            ("line", "Cost of Revenue", "costOfRevenue"),
            ("subtotal", "Gross Profit", "grossProfit"),
            ("header", "OPERATING EXPENSES", None),
            ("line", "Research & Development", "researchAndDevelopmentExpenses"),
            ("line", "Selling, General & Admin", "sellingGeneralAndAdministrativeExpenses"),
            ("line", "Other Operating Expenses", "otherExpenses"),
            ("line", "Total Operating Expenses", "operatingExpenses"),
            ("subtotal", "Operating Income", "operatingIncome"),
            ("header", "NON-OPERATING", None),
            ("line", "Interest Income", "interestIncome"),
            ("line", "Interest Expense", "interestExpense"),
            ("line", "Other Income / (Expense), net", "totalOtherIncomeExpensesNet"),
            ("subtotal", "Income Before Tax", "incomeBeforeTax"),
            ("header", "BOTTOM LINE", None),
            ("line", "Income Tax Expense", "incomeTaxExpense"),
            ("subtotal", "Net Income", "netIncome"),
            ("header", "PER SHARE & MEMO", None),
            ("line", "EPS (Basic)", "eps"),
            ("line", "EPS (Diluted)", "epsDiluted"),
            ("line", "Weighted Avg Shares (Diluted)", "weightedAverageShsOutDil"),
            ("line", "EBITDA", "ebitda"),
            ("line", "EBIT", "ebit"),
        ])
        st.caption("Grouped with subtotals. EPS in dollars; all other figures in USD.")

    # ================= BALANCE SHEET =================
    with tab2:
        st.markdown("**Balance Sheet** (last 5 years, USD)")
        show_structured(balance, [
            ("header", "CURRENT ASSETS", None),
            ("line", "Cash & Cash Equivalents", "cashAndCashEquivalents"),
            ("line", "Short-Term Investments", "shortTermInvestments"),
            ("line", "Net Receivables", "netReceivables"),
            ("line", "Inventory", "inventory"),
            ("line", "Other Current Assets", "otherCurrentAssets"),
            ("subtotal", "Total Current Assets", "totalCurrentAssets"),
            ("header", "NON-CURRENT ASSETS", None),
            ("line", "Property, Plant & Equipment (Net)", "propertyPlantEquipmentNet"),
            ("line", "Goodwill", "goodwill"),
            ("line", "Intangible Assets", "intangibleAssets"),
            ("line", "Long-Term Investments", "longTermInvestments"),
            ("line", "Other Non-Current Assets", "otherNonCurrentAssets"),
            ("subtotal", "Total Non-Current Assets", "totalNonCurrentAssets"),
            ("subtotal", "TOTAL ASSETS", "totalAssets"),
            ("header", "CURRENT LIABILITIES", None),
            ("line", "Accounts Payable", "accountPayables"),
            ("line", "Accrued Expenses", "accruedExpenses"),
            ("line", "Short-Term Debt", "shortTermDebt"),
            ("line", "Deferred Revenue", "deferredRevenue"),
            ("line", "Other Current Liabilities", "otherCurrentLiabilities"),
            ("subtotal", "Total Current Liabilities", "totalCurrentLiabilities"),
            ("header", "NON-CURRENT LIABILITIES", None),
            ("line", "Long-Term Debt", "longTermDebt"),
            ("line", "Deferred Tax Liabilities", "deferredTaxLiabilitiesNonCurrent"),
            ("line", "Other Non-Current Liabilities", "otherNonCurrentLiabilities"),
            ("subtotal", "Total Non-Current Liabilities", "totalNonCurrentLiabilities"),
            ("subtotal", "TOTAL LIABILITIES", "totalLiabilities"),
            ("header", "SHAREHOLDERS' EQUITY", None),
            ("line", "Common Stock", "commonStock"),
            ("line", "Retained Earnings", "retainedEarnings"),
            ("line", "Additional Paid-In Capital", "additionalPaidInCapital"),
            ("line", "Treasury Stock", "treasuryStock"),
            ("line", "Accumulated Other Comp. Income", "accumulatedOtherComprehensiveIncomeLoss"),
            ("subtotal", "Total Stockholders' Equity", "totalStockholdersEquity"),
            ("subtotal", "TOTAL LIABILITIES & EQUITY", "totalLiabilitiesAndTotalEquity"),
        ])

    # ================= CASH FLOW =================
    with tab3:
        st.markdown("**Cash Flow Statement** (last 5 years, USD)")
        show_structured(cashflow, [
            ("header", "OPERATING ACTIVITIES", None),
            ("line", "Net Income", "netIncome"),
            ("line", "Depreciation & Amortization", "depreciationAndAmortization"),
            ("line", "Stock-Based Compensation", "stockBasedCompensation"),
            ("line", "Deferred Income Tax", "deferredIncomeTax"),
            ("line", "Change in Working Capital", "changeInWorkingCapital"),
            ("line", "Other Non-Cash Items", "otherNonCashItems"),
            ("subtotal", "Cash from Operations", "netCashProvidedByOperatingActivities"),
            ("header", "INVESTING ACTIVITIES", None),
            ("line", "Capital Expenditure", "investmentsInPropertyPlantAndEquipment"),
            ("line", "Acquisitions (Net)", "acquisitionsNet"),
            ("line", "Purchases of Investments", "purchasesOfInvestments"),
            ("line", "Sales/Maturities of Investments", "salesMaturitiesOfInvestments"),
            ("line", "Other Investing Activities", "otherInvestingActivities"),
            ("subtotal", "Cash from Investing", "netCashProvidedByInvestingActivities"),
            ("header", "FINANCING ACTIVITIES", None),
            ("line", "Net Debt Issuance", "netDebtIssuance"),
            ("line", "Common Stock Issuance", "commonStockIssuance"),
            ("line", "Common Stock Repurchased", "commonStockRepurchased"),
            ("line", "Dividends Paid", "netDividendsPaid"),
            ("line", "Other Financing Activities", "otherFinancingActivities"),
            ("subtotal", "Cash from Financing", "netCashProvidedByFinancingActivities"),
            ("header", "NET CHANGE", None),
            ("line", "Effect of Forex on Cash", "effectOfForexChangesOnCash"),
            ("subtotal", "Net Change in Cash", "netChangeInCash"),
            ("line", "Cash at Beginning of Period", "cashAtBeginningOfPeriod"),
            ("subtotal", "Cash at End of Period", "cashAtEndOfPeriod"),
            ("header", "MEMO", None),
            ("line", "Free Cash Flow", "freeCashFlow"),
            ("line", "Capital Expenditure", "capitalExpenditure"),
        ])

    # ================= RATIOS =================
    with tab4:
        st.markdown("**Financial Ratios** (last 5 years)")
        if not ratios:
            st.warning("Could not calculate ratios.")
        else:
            pct_rows = ["Gross Margin", "Net Margin", "ROE", "ROA"]

            def fmt(val, rn):
                if val is None:
                    return "-"
                if rn in pct_rows:
                    return format(val*100, ".1f") + "%"
                return format(val, ".2f")

            yrs = [row["Year"] for row in ratios]
            names = [k for k in ratios[0].keys() if k != "Year"]
            tt = {name: [fmt(row.get(name), name) for row in ratios] for name in names}
            st.dataframe(pd.DataFrame(tt, index=yrs).T, use_container_width=True)
            st.caption("Current Ratio above 1 = can cover short-term bills. Higher margins/ROE = more profitable. Debt-to-Equity: higher = more leverage/risk.")
            lr = ratios[0].get("ROE") if ratios else None
            if isinstance(lr, (int, float)) and lr > 0.50:
                st.info("Note on ROE: An unusually high ROE (over 50%) often reflects a very small equity base - frequently caused by large share buybacks that reduce shareholder equity - rather than extraordinary profitability alone. Read it alongside net margin and ROA.")

    # ================= VALUATION =================
    with tab5:
        st.markdown("**FCFF - Free Cash Flow to the Firm** (last 5 years, USD)")
        st.caption("FCFF = Operating Cash Flow + Interest x (1 - Tax) - CapEx")
        fr = calculate_fcff(income, cashflow)
        if fr:
            dr = ["Operating Cash Flow", "Interest (after-tax)", "CapEx", "FCFF"]
            yrs = [r["Year"] for r in fr]
            tb = {name: [format(r[name], ",.0f") if r.get(name) is not None else "-" for r in fr] for name in dr}
            st.dataframe(pd.DataFrame(tb, index=yrs).T, use_container_width=True)

        st.divider()
        st.markdown("**WACC - Weighted Average Cost of Capital**")
        ca, cb = st.columns(2)
        with ca:
            rf = st.slider("Risk-Free Rate (10Y Treasury) %", 0.0, 8.0, 4.3, 0.1) / 100
        with cb:
            erp = st.slider("Equity Risk Premium %", 3.0, 8.0, 5.0, 0.1) / 100
        wd = calculate_wacc(profile, income, balance, risk_free_rate=rf, equity_risk_premium=erp)
        if wd:
            m1, m2, m3 = st.columns(3)
            m1.metric("WACC", format(wd["WACC"]*100, ".2f") + "%")
            m2.metric("Cost of Equity", format(wd["Cost of Equity (Re)"]*100, ".2f") + "%")
            m3.metric("Cost of Debt", format(wd["Cost of Debt (Rd)"]*100, ".2f") + "%")
            cw = wd["WACC"]
        else:
            st.warning("Could not calculate WACC.")
            cw = None

        st.divider()
        st.markdown("### DCF Intrinsic Value")
        cg, ct = st.columns(2)
        with cg:
            growth = st.slider("FCFF Growth Rate (next 5 yrs) %", 0.0, 20.0, 8.0, 0.5) / 100
        with ct:
            tg = st.slider("Terminal Growth Rate %", 0.0, 5.0, 2.5, 0.1) / 100
        if cw is None:
            st.warning("Need WACC to run the DCF.")
        else:
            dcf = run_dcf(income, cashflow, balance, profile, cw, growth_rate=growth, terminal_growth=tg)
            if not dcf or dcf.get("intrinsic_per_share") is None:
                st.warning("Could not complete DCF. Try lowering terminal growth.")
            else:
                iv, mp, up = dcf["intrinsic_per_share"], dcf["market_price"], dcf["upside"]
                r1, r2, r3 = st.columns(3)
                r1.metric("Intrinsic Value / Share", "$" + format(iv, ",.2f"))
                r2.metric("Current Market Price", "$" + format(mp, ",.2f"))
                r3.metric("Upside / (Downside)", format(up*100, "+.1f") + "%" if up is not None else "N/A")
                mos = calculate_margin_of_safety(iv, mp)
                st.markdown("**Margin of Safety**")
                rm = st.slider("Required Margin of Safety % (your risk buffer)", 0, 50, 25, 5) / 100
                if mos is not None:
                    md = format(mos*100, "+.1f") + "%" if mos > -1 else "None (overvalued)"
                    x1, x2 = st.columns(2)
                    x1.metric("Actual Margin of Safety", md)
                    x2.metric("Required (your setting)", format(rm*100, ".0f") + "%")
                    if mos >= rm:
                        st.success("Meets your margin of safety (" + format(mos*100, ".0f") + "%).")
                    elif mos > 0:
                        st.warning("Below required buffer (" + format(mos*100, ".0f") + "% vs " + format(rm*100, ".0f") + "%).")
                    else:
                        st.error("No margin of safety - trades above intrinsic value.")
                if up is not None:
                    if up > 0.15:
                        st.success("Potentially UNDERVALUED - about " + format(up*100, ".0f") + "% above price.")
                    elif up < -0.15:
                        st.error("Potentially OVERVALUED - about " + format(abs(up)*100, ".0f") + "% below price.")
                    else:
                        st.info("Roughly FAIRLY VALUED.")
                st.markdown("**Valuation Breakdown**")
                bd = {
                    "Base FCFF (latest)": "$" + format(dcf["base_fcff"], ",.0f"),
                    "PV of 5-yr FCFF": "$" + format(dcf["pv_fcff_total"], ",.0f"),
                    "PV of Terminal Value": "$" + format(dcf["pv_terminal"], ",.0f"),
                    "Enterprise Value": "$" + format(dcf["enterprise_value"], ",.0f"),
                    "Equity Value": "$" + format(dcf["equity_value"], ",.0f"),
                    "Shares Outstanding": format(dcf["shares"], ",.0f") if dcf["shares"] else "N/A",
                }
                st.dataframe(pd.DataFrame(list(bd.items()), columns=["Item", "Value"]).set_index("Item"), use_container_width=True)
                if dcf["enterprise_value"]:
                    st.caption(format(dcf["pv_terminal"]/dcf["enterprise_value"]*100, ".0f") + "% of enterprise value is terminal value.")
                st.session_state["dcf"] = dcf
                st.divider()
                st.markdown("### Sensitivity Analysis")
                sens = sensitivity_analysis(income, cashflow, balance, profile, cw, terminal_growth=tg)
                if sens:
                    wl, gl, grid = sens
                    cl = ["g=" + format(g*100, ".0f") + "%" for g in gl]
                    rl = ["WACC=" + format(w*100, ".1f") + "%" for w in wl]
                    ct2 = [["$" + format(v, ",.0f") if v is not None else "-" for v in row] for row in grid]
                    st.dataframe(pd.DataFrame(ct2, index=rl, columns=cl), use_container_width=True)
                    st.caption("Current price: $" + format(mp, ",.2f") + ". Value rises with growth, falls with WACC.")

    # ================= AI ANALYSIS =================
    with tab6:
        st.markdown("### AI Investment Analysis")
        st.caption("AI narrative (Gemini) from calculated metrics only. Not advice.")
        da = st.session_state.get("dcf")
        if da is None:
            st.info("Valuation unavailable - try re-analyzing the company.")
        else:
            if st.button("Generate AI Bull & Bear Case"):
                with st.spinner("Gemini is analyzing..."):
                    st.session_state["ai_result"] = get_ai_analysis(profile, ratios, da)
            res = st.session_state.get("ai_result")
            if res:
                if res.get("error"):
                    st.error("AI analysis failed: " + str(res["error"]))
                else:
                    st.success("AI analysis generated (based on calculated metrics)")
                    cb1, cb2 = st.columns(2)
                    with cb1:
                        st.markdown("#### Bull Case"); st.markdown(res.get("bull") or "_No bull case._")
                    with cb2:
                        st.markdown("#### Bear Case"); st.markdown(res.get("bear") or "_No bear case._")
                    st.caption("AI narrative for education. Not investment advice.")

    # ================= RECOMMENDATION =================
    with tab7:
        st.markdown("### Investment Committee Recommendation")
        st.caption("Transparent rule-based scoring (valuation + margin of safety + financial health), narrated by AI. The decision is deterministic.")
        dr2 = st.session_state.get("dcf")
        if dr2 is None:
            st.info("Valuation unavailable - try re-analyzing the company.")
        else:
            up = dr2.get("upside")
            mos = calculate_margin_of_safety(dr2.get("intrinsic_per_share"), dr2.get("market_price"))
            rec = get_recommendation(up, mos, ratios)
            {"success": st.success, "warning": st.warning, "error": st.error, "info": st.info}[rec["color"]]("## " + rec["recommendation"])
            c1, c2 = st.columns(2)
            c1.metric("Confidence Level", rec["confidence_label"])
            c2.metric("Composite Score", format(rec["total_score"], "+d"))
            st.markdown("**Score Components**")
            comp = rec["components"]
            st.dataframe(pd.DataFrame({
                "Dimension": ["Valuation", "Margin of Safety", "Financial Health"],
                "Score": [format(comp["valuation"], "+d"), format(comp["margin_of_safety"], "+d"), format(comp["financial_health"], "+d")],
            }).set_index("Dimension"), use_container_width=True)
            s1, s2 = st.columns(2)
            with s1:
                st.markdown("**Financial Strengths**")
                for s in (rec["strengths"] or ["_None identified._"]):
                    st.markdown("- " + s)
            with s2:
                st.markdown("**Financial Weaknesses**")
                for w in (rec["weaknesses"] or ["_None identified._"]):
                    st.markdown("- " + w)
            st.markdown("**Reasons For / Against**")
            a1, a2 = st.columns(2)
            with a1:
                st.markdown("_Supporting:_")
                for s in (rec["supporting"] or ["_None._"]):
                    st.markdown("- " + s)
            with a2:
                st.markdown("_Concerns:_")
                cc = rec["opposing"] + list(rec["weaknesses"])
                for c in (cc or ["_None._"]):
                    st.markdown("- " + c)
            if rec.get("context_notes"):
                for note in rec["context_notes"]:
                    st.caption(note)
            st.divider()
            st.markdown("**AI Investment Memo**")
            if st.button("Generate Investment Memo"):
                with st.spinner("Gemini is writing the memo..."):
                    st.session_state["memo_result"] = get_investment_memo(profile, ratios, dr2, rec)
            mr = st.session_state.get("memo_result")
            if mr:
                if mr.get("error"):
                    st.error("Memo failed: " + str(mr["error"]))
                else:
                    st.markdown(mr["memo"])
                    st.caption("AI-written memo. Educational only - not investment advice.")

st.divider()
st.caption("FinSight AI - Built with Streamlit, Financial Modeling Prep and Google Gemini. For educational and demonstration purposes only - not investment advice.")