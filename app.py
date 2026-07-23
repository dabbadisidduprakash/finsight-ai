"""
app.py - FinSight AI. Full app: structured statements, forecasting, capital budgeting.
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
from src.forecasting import derive_assumptions, build_projection
from src.capbudget import build_capital_budget, excel_defaults, derive_capbudget_defaults

st.set_page_config(page_title="FinSight AI", page_icon="chart_with_upwards_trend", layout="wide")


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
            dd = run_dcf(income, cashflow, balance, profile, dw["WACC"], growth_rate=0.08, terminal_growth=0.025)
            if dd:
                st.session_state["dcf"] = dd

    tabs = st.tabs(["Dashboard", "Income Statement", "Balance Sheet",
                    "Cash Flow", "Ratios", "Valuation",
                    "Forecasting", "Capital Budgeting",
                    "AI Analysis", "Recommendation"])
    (tab_dash, tab1, tab2, tab3, tab4, tab5, tab8, tab9, tab6, tab7) = tabs

    def _year_labels(data):
        labels = []
        for i, item in enumerate(data):
            y = item.get("fiscalYear") or item.get("calendarYear") or item.get("date", i)
            labels.append(str(y)[:4] if item.get("date") else str(y))
        return labels

    def show_structured(data, layout):
        if not data:
            st.warning("No data available for this statement.")
            return
        years = _year_labels(data)
        display_rows, index_labels, seen = [], [], {}
        for kind, label, field in layout:
            if kind == "header":
                disp = "  " + label.upper()
            elif kind == "subtotal":
                disp = label
            else:
                disp = "   " + label
            if disp in seen:
                seen[disp] += 1
                disp = disp + " " * seen[disp]
            else:
                seen[disp] = 0
            index_labels.append(disp)
            if kind == "header":
                display_rows.append(["" for _ in data])
            else:
                display_rows.append([format(item.get(field), ",.2f" if field in ("eps", "epsDiluted") else ",.0f") if isinstance(item.get(field) if field else None, (int, float)) else "-" for item in data])
        df = pd.DataFrame(display_rows, index=index_labels, columns=years)
        st.dataframe(df, use_container_width=True, height=(len(index_labels) + 1) * 35 + 3)

    # ===== DASHBOARD =====
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
            rows = [{"Year": str(it.get("fiscalYear") or it.get("date", ""))[:4], label: it.get(field)} for it in data if it.get(field) is not None]
            if not rows:
                return None
            return pd.DataFrame(rows).iloc[::-1].set_index("Year")

        ch1, ch2 = st.columns(2)
        with ch1:
            r = _trend(income, "revenue", "Revenue")
            if r is not None:
                st.markdown("**Revenue**"); st.bar_chart(r)
            nn = _trend(income, "netIncome", "Net Income")
            if nn is not None:
                st.markdown("**Net Income**"); st.bar_chart(nn)
        with ch2:
            fr = calculate_fcff(income, cashflow)
            if fr:
                fd = pd.DataFrame([{"Year": x["Year"][:4], "FCFF": x["FCFF"]} for x in fr if x.get("FCFF") is not None])
                if not fd.empty:
                    st.markdown("**Free Cash Flow (FCFF)**"); st.bar_chart(fd.iloc[::-1].set_index("Year"))
            o = _trend(cashflow, "operatingCashFlow", "Operating CF")
            if o is not None:
                st.markdown("**Operating Cash Flow**"); st.bar_chart(o)

    # ===== INCOME STATEMENT =====
    with tab1:
        st.markdown("**Income Statement** (last " + str(len(income)) + " years, USD)")
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

    # ===== BALANCE SHEET =====
    with tab2:
        st.markdown("**Balance Sheet** (last " + str(len(balance)) + " years, USD)")
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

    # ===== CASH FLOW =====
    with tab3:
        st.markdown("**Cash Flow Statement** (last " + str(len(cashflow)) + " years, USD)")
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

    # ===== RATIOS =====
    with tab4:
        st.markdown("**Financial Ratios** (last " + str(len(ratios)) + " years)")
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
                st.info("Note on ROE: An unusually high ROE (over 50%) often reflects a very small equity base - frequently caused by large share buybacks - rather than extraordinary profitability alone. Read it alongside net margin and ROA.")

    # ===== VALUATION =====
    with tab5:
        st.markdown("**FCFF - Free Cash Flow to the Firm** (last " + str(len(income)) + " years, USD)")
        st.caption("FCFF = Operating Cash Flow + Interest x (1 - Tax) - CapEx")
        fr = calculate_fcff(income, cashflow)
        if fr:
            dr = ["Operating Cash Flow", "Interest (after-tax)", "CapEx", "FCFF"]
            yrs = [r["Year"] for r in fr]
            tb = {name: [format(r[name], ",.0f") if r.get(name) is not None else "-" for r in fr] for name in dr}
            st.dataframe(pd.DataFrame(tb, index=yrs).T, use_container_width=True)
        st.divider()
        st.markdown("**WACC - Weighted Average Cost of Capital**")
        vca, vcb = st.columns(2)
        with vca:
            rf = st.slider("Risk-Free Rate (10Y Treasury) %", 0.0, 8.0, 4.3, 0.1, key="val_rf") / 100
        with vcb:
            erp = st.slider("Equity Risk Premium %", 3.0, 8.0, 5.0, 0.1, key="val_erp") / 100
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
        vcg, vct = st.columns(2)
        with vcg:
            growth = st.slider("FCFF Growth Rate (next 5 yrs) %", 0.0, 20.0, 8.0, 0.5, key="val_growth") / 100
        with vct:
            tg = st.slider("Terminal Growth Rate %", 0.0, 5.0, 2.5, 0.1, key="val_tg") / 100
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
                rm = st.slider("Required Margin of Safety % (your risk buffer)", 0, 50, 25, 5, key="val_mos") / 100
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

    # ===== AI ANALYSIS =====
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

    # ===== RECOMMENDATION =====
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

    # ===== FORECASTING =====
    with tab8:
        st.markdown("### 5-Year Financial Projection")
        st.caption("An integrated 3-statement model projecting Income Statement, Balance Sheet, and Cash Flow forward 5 years. Assumptions pre-filled from actual historicals - adjust to your own view. The balance sheet balances by construction (see Balance Check at the bottom).")
        if not income or not balance or not cashflow:
            st.warning("Load a company first (financial data required).")
        elif is_financial:
            st.warning("Forecasting is disabled for financial-sector companies - the standard operating-model structure does not fit banks/insurers.")
        else:
            defaults = derive_assumptions(income, balance, cashflow)
            st.markdown("**Assumptions** (defaults from historicals - adjust as needed)")
            fa, fb, fc = st.columns(3)
            with fa:
                f_growth = st.slider("Revenue Growth % / yr", -10.0, 40.0, float(defaults["growth"]*100), 0.5, key="fc_growth") / 100
                f_gm = st.slider("Gross Margin %", 0.0, 90.0, float(defaults["gross_margin"]*100), 0.5, key="fc_gm") / 100
                f_opex = st.slider("Operating Expenses % of Revenue", 0.0, 60.0, float(defaults["opex_pct"]*100), 0.5, key="fc_opex") / 100
                f_tax = st.slider("Tax Rate %", 0.0, 40.0, float(defaults["tax_rate"]*100), 0.5, key="fc_tax") / 100
            with fb:
                f_capex = st.slider("CapEx % of Revenue", 0.0, 20.0, float(defaults["capex_pct"]*100), 0.5, key="fc_capex") / 100
                f_da = st.slider("Depreciation % of PP&E", 0.0, 50.0, float(defaults["da_rate"]*100), 0.5, key="fc_da") / 100
                f_int = st.slider("Interest Rate on Debt %", 0.0, 15.0, float(defaults["int_rate"]*100), 0.1, key="fc_int") / 100
                f_pay = st.slider("Dividend Payout %", 0.0, 100.0, float(defaults["payout"]*100), 1.0, key="fc_pay") / 100
            with fc:
                f_ar = st.slider("Receivable Days", 0.0, 180.0, float(defaults["ar_days"]), 1.0, key="fc_ar")
                f_inv = st.slider("Inventory Days", 0.0, 180.0, float(defaults["inv_days"]), 1.0, key="fc_inv")
                f_ap = st.slider("Payable Days", 0.0, 240.0, float(defaults["ap_days"]), 1.0, key="fc_ap")
            assumptions = {
                "revenue0": defaults["revenue0"], "growth": f_growth, "gross_margin": f_gm,
                "opex_pct": f_opex, "da_rate": f_da, "capex_pct": f_capex, "tax_rate": f_tax,
                "ar_days": f_ar, "inv_days": f_inv, "ap_days": f_ap, "int_rate": f_int, "payout": f_pay,
            }
            proj = build_projection(income, balance, cashflow, assumptions)
            yrs = proj["years"]

            def _pt(statement):
                return pd.DataFrame({label: [format(v, ",.0f") if isinstance(v, (int, float)) else "-" for v in vals] for label, vals in statement.items()}, index=yrs).T

            st.markdown("#### Projected Income Statement")
            st.dataframe(_pt(proj["income"]), use_container_width=True)
            st.markdown("#### Projected Balance Sheet")
            st.dataframe(_pt(proj["balance"]), use_container_width=True)
            st.markdown("#### Projected Cash Flow Statement")
            st.dataframe(_pt(proj["cashflow"]), use_container_width=True)
            st.markdown("#### Supporting Schedules (PP&E & Debt)")
            st.dataframe(_pt(proj["schedules"]), use_container_width=True)
            st.markdown("#### Balance Check")
            checks = proj["balance_check"]
            bc_df = pd.DataFrame({"Assets - (Liab + Equity)": [format(c, ",.2f") for c in checks]}, index=yrs).T
            st.dataframe(bc_df, use_container_width=True)
            if all(abs(c) < 1 for c in checks):
                st.success("Balanced: Assets = Liabilities + Equity in every year.")
            else:
                st.error("Imbalance detected - check assumptions.")
            st.caption("Non-operating lines (goodwill, intangibles, deferred taxes) held flat at last actual value - standard convention when no driver exists. Cash is the balancing item.")

    # ===== CAPITAL BUDGETING =====
    with tab9:
        st.markdown("### Capital Budgeting - Project Appraisal (NPV / IRR)")
        st.caption("Evaluate whether a specific project is worth undertaking. The model computes CFAT, NPV, and IRR against the project's hurdle rate (WACC).")
        if income and balance and cashflow:
            d = derive_capbudget_defaults(income, balance, cashflow)
            st.info("Defaults derived from " + str(profile.get("companyName", "the loaded company")) + "'s actual latest financials. A project is a slice of the business - adjust the scale to your specific project.")
        else:
            d = excel_defaults()
            st.info("Defaults from a worked example (no company loaded).")
        n_years = len(d["revenue"])

        st.markdown("**Project Revenue** (Year 1 anchored to last actual revenue; growth fills the rest; each year editable)")
        cg1, cg2 = st.columns([1, 3])
        with cg1:
            proj_growth = st.slider("Revenue Growth % / yr", -10.0, 40.0, float(d.get("growth", 0.06)*100), 0.5, key="cb_growth") / 100
        r0 = d["revenue"][0]
        rev_defaults = [r0 if i == 0 else r0 * (1 + proj_growth) ** i for i in range(n_years)]
        rev_cols = st.columns(n_years)
        revenue = []
        for i in range(n_years):
            with rev_cols[i]:
                revenue.append(st.number_input("Yr " + str(i + 1), value=float(round(rev_defaults[i], 0)), step=max(round(r0*0.01, 0), 1.0), key="cb_rev_" + str(i)))

        st.markdown("**PP&E Additions by Year** (mid-project capex; 0 if none)")
        add_cols = st.columns(n_years)
        additions = []
        for i in range(n_years):
            with add_cols[i]:
                additions.append(st.number_input("Yr " + str(i + 1), value=float(d["additions"][i]), step=max(round(r0*0.01, 0), 1.0), key="cb_add_" + str(i)))

        st.markdown("**Cost & Operating Assumptions**")
        ca, cb, cc = st.columns(3)
        with ca:
            cogs_pct = st.slider("COGS % of Revenue", 0.0, 90.0, d["cogs_pct"]*100, 0.5, key="cb_cogs") / 100
            sga_pct = st.slider("SG&A % of Revenue", 0.0, 40.0, d["sga_pct"]*100, 0.5, key="cb_sga") / 100
            tax_rate = st.slider("Tax Rate %", 0.0, 40.0, d["tax_rate"]*100, 0.5, key="cb_tax") / 100
        with cb:
            dep_rate = st.slider("Depreciation Rate % (WDV)", 0.0, 40.0, d["dep_rate"]*100, 0.5, key="cb_dep") / 100
            ppe_initial = st.number_input("Initial PP&E Outflow", value=float(d["ppe_initial"]), step=max(round(r0*0.01, 0), 1.0), key="cb_ppe")
            wc_initial = st.number_input("Initial Working Capital", value=float(d["wc_initial"]), step=max(round(r0*0.01, 0), 1.0), key="cb_wci")
        with cc:
            wc_pct = st.slider("Working Capital % of Next-Yr Revenue", 0.0, 50.0, d["wc_pct"]*100, 1.0, key="cb_wcpct") / 100
            cannibalization = st.number_input("Annual Cannibalization Cost", value=float(d["cannibalization"]), step=0.25, key="cb_cann")

        st.markdown("**Terminal Values (final year)**")
        ta, tb, tcc = st.columns(3)
        with ta:
            salvage_wc_pct = st.slider("Salvage of Working Capital %", 0.0, 100.0, d["salvage_wc_pct"]*100, 5.0, key="cb_swc") / 100
        with tb:
            salvage_fa = st.number_input("Salvage of Fixed Assets", value=float(d["salvage_fa"]), step=max(round(r0*0.01, 0), 1.0), key="cb_sfa")
        with tcc:
            tax_shield_loss = st.number_input("Tax Shield on Loss (final yr)", value=float(d["tax_shield_loss"]), step=0.5, key="cb_tsl")

        st.markdown("**Hurdle Rate (Project WACC via CAPM)**")
        wa, wb, wc2 = st.columns(3)
        with wa:
            beta = st.number_input("Project Beta", value=float(d["beta"]), step=0.05, key="cb_beta")
            cb_rf = st.slider("Risk-Free Rate %", 0.0, 15.0, d["rf"]*100, 0.1, key="cb_rf") / 100
        with wb:
            rm = st.slider("Market Return %", 0.0, 30.0, d["rm"]*100, 0.5, key="cb_rm") / 100
            kd_pretax = st.slider("Pre-Tax Cost of Debt %", 0.0, 25.0, d["kd_pretax"]*100, 0.5, key="cb_kd") / 100
        with wc2:
            equity = st.number_input("Equity in Project", value=float(d["equity"]), step=max(round(r0*0.01, 0), 1.0), key="cb_eq")
            debt = st.number_input("Debt in Project", value=float(d["debt"]), step=max(round(r0*0.01, 0), 1.0), key="cb_debt")

        inp = {
            "revenue": revenue, "additions": additions, "cogs_pct": cogs_pct, "sga_pct": sga_pct,
            "tax_rate": tax_rate, "dep_rate": dep_rate, "ppe_initial": ppe_initial, "wc_pct": wc_pct,
            "wc_initial": wc_initial, "salvage_wc_pct": salvage_wc_pct, "salvage_fa": salvage_fa,
            "tax_shield_loss": tax_shield_loss, "cannibalization": cannibalization, "beta": beta,
            "rf": cb_rf, "rm": rm, "kd_pretax": kd_pretax, "equity": equity, "debt": debt,
        }
        out = build_capital_budget(inp)
        st.divider()
        st.markdown("#### Results")
        rc1, rc2, rc3 = st.columns(3)
        rc1.metric("NPV", format(out["npv"], ",.2f"))
        rc2.metric("IRR", format(out["irr"]*100, ".2f") + "%")
        rc3.metric("Hurdle Rate (WACC)", format(out["hurdle"]*100, ".2f") + "%")
        if out["npv"] > 0 and out["irr"] > out["hurdle"]:
            st.success("ACCEPT the project - positive NPV and IRR exceeds the hurdle rate. It creates value.")
        elif out["npv"] > 0:
            st.info("NPV is positive but review IRR vs. hurdle rate.")
        else:
            st.error("REJECT the project - negative NPV. It destroys value at this hurdle rate.")
        st.caption("NPV uses the correct convention (initial outflow at t=0). Excel's built-in NPV() discounts the first cash flow by one period; by that method this project shows " + format(out["npv_excel"], ",.2f") + ". The correct figure is " + format(out["npv"], ",.2f") + ".")
        st.markdown("**Hurdle Rate Breakdown**")
        w = out["wacc"]
        st.dataframe(pd.DataFrame({
            "Component": ["Cost of Equity (CAPM)", "After-Tax Cost of Debt", "Equity Weight", "Debt Weight", "WACC (Hurdle)"],
            "Value": [format(w["ke"]*100, ".2f") + "%", format(w["kd"]*100, ".2f") + "%", format(w["we"], ".3f"), format(w["wd"], ".3f"), format(out["hurdle"]*100, ".2f") + "%"],
        }).set_index("Component"), use_container_width=True)
        st.markdown("**Cash Flow After Tax (CFAT) by Year**")
        cfat_labels = ["Year " + str(i) for i in range(len(out["cfat"]))]
        cfat_labels[0] = "Year 0 (Initial)"
        st.dataframe(pd.DataFrame({"CFAT": [format(c, ",.2f") for c in out["cfat"]]}, index=cfat_labels).T, use_container_width=True)
        st.markdown("**Project P&L & CFAT Detail**")
        dy = ["Year " + str(i + 1) for i in range(n_years)]
        drows = {
            "Revenue": [r["revenue"] for r in out["results"]],
            "COGS": [-r["cogs"] for r in out["results"]],
            "Gross Profit": [r["gross_profit"] for r in out["results"]],
            "SG&A": [-r["sga"] for r in out["results"]],
            "EBITDA": [r["ebitda"] for r in out["results"]],
            "Depreciation": [-r["depreciation"] for r in out["results"]],
            "EBIT": [r["ebit"] for r in out["results"]],
            "EBIT x (1-tax)": [r["ebit_after_tax"] for r in out["results"]],
            "Add: Depreciation": [r["depreciation"] for r in out["results"]],
            "Less: Chg in WC": [-r["d_wc"] for r in out["results"]],
            "Less: Fixed Asset Add": [-r["d_fa"] for r in out["results"]],
            "Add: Salvage WC": [r["salvage_wc"] for r in out["results"]],
            "Add: Salvage FA": [r["salvage_fa"] for r in out["results"]],
            "Add: Tax Shield": [r["tax_shield"] for r in out["results"]],
            "Less: Cannibalization": [-r["cannibalization"] for r in out["results"]],
            "CFAT": [r["cfat"] for r in out["results"]],
        }
        dfmt = {k: [format(v, ",.2f") if isinstance(v, (int, float)) else "-" for v in vals] for k, vals in drows.items()}
        st.dataframe(pd.DataFrame(dfmt, index=dy).T, use_container_width=True)
        st.markdown("**Depreciation Schedule (WDV)**")
        deprows = {"Opening Block": out["opening_bv"], "Depreciation": [-x for x in out["dep"]], "Closing Book Value": out["closing_bv"]}
        depfmt = {k: [format(v, ",.2f") for v in vals] for k, vals in deprows.items()}
        st.dataframe(pd.DataFrame(depfmt, index=dy).T, use_container_width=True)

st.divider()
st.caption("FinSight AI - Built with Streamlit, Financial Modeling Prep and Google Gemini. For educational and demonstration purposes only - not investment advice.")