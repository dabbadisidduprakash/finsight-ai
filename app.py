"""
app.py - Streamlit UI for FinSight AI.
Day 14: encoding-safe, plain ASCII throughout.
"""
import streamlit as st
import pandas as pd
from src.data_fetch import (
    get_company_profile,
    get_income_statement,
    get_balance_sheet,
    get_cash_flow,
)
from src.ratios import calculate_ratios
from src.valuation import (
    calculate_fcff,
    calculate_wacc,
    run_dcf,
    calculate_margin_of_safety,
    sensitivity_analysis,
    is_financial_sector,
)
from src.ai_analysis import (
    get_ai_analysis,
    get_investment_memo,
    get_executive_summary,
)
from src.recommendation import get_recommendation

st.set_page_config(
    page_title="FinSight AI",
    page_icon="chart_with_upwards_trend",
    layout="wide",
)

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
    """Returns True if the user has entered the correct password."""
    correct = _get_password()
    if not correct:
        return True  # no password set = open access (safety fallback)

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
        "US stock ticker",
        value="AAPL",
        label_visibility="collapsed",
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
            st.error(
                "Could not find data for '" + ticker + "'. "
                "Check the ticker (US-listed only), or the API key may have "
                "hit its daily limit."
            )
        else:
            st.session_state["profile"] = profile
            st.session_state["income"] = income
            st.session_state["balance"] = balance
            st.session_state["cashflow"] = cashflow
            st.session_state.pop("ai_result", None)
            st.session_state.pop("memo_result", None)
            st.session_state.pop("exec_summary", None)
            st.session_state.pop("dcf", None)

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
        st.markdown(
            "**Sector:** " + str(profile.get("sector", "N/A")) + "  \n"
            + "**Price:** " + price_txt.replace("$", "\\$")
            + " &nbsp;&nbsp; **Market Cap:** " + mcap_str.replace("$", "\\$")
        )

    st.divider()

    ratios = calculate_ratios(income, balance, cashflow, profile)

    is_financial = is_financial_sector(profile)

    if "dcf" not in st.session_state:
        default_wacc_data = calculate_wacc(profile, income, balance)
        if default_wacc_data:
            default_dcf = run_dcf(
                income, cashflow, balance, profile,
                default_wacc_data["WACC"],
                growth_rate=0.08, terminal_growth=0.025,
            )
            if default_dcf:
                st.session_state["dcf"] = default_dcf

    tabs = st.tabs(
        ["Dashboard", "Income Statement", "Balance Sheet",
         "Cash Flow", "Ratios", "Valuation", "AI Analysis",
         "Recommendation"]
    )
    (tab_dash, tab1, tab2, tab3, tab4, tab5, tab6, tab7) = tabs

    def show_statement(data, key_columns):
        if not data:
            st.warning("No data available for this statement.")
            return
        df = pd.DataFrame(data)
        if "calendarYear" in df.columns:
            years = df["calendarYear"].astype(str).tolist()
        elif "date" in df.columns:
            years = df["date"].astype(str).tolist()
        else:
            years = [str(i) for i in range(len(data))]
        table = {}
        for raw_key, friendly_name in key_columns.items():
            if raw_key in df.columns:
                table[friendly_name] = df[raw_key].tolist()
        display_df = pd.DataFrame(table, index=years).T

        def _fmt_row(row):
            # EPS shown with 2 decimals; everything else as whole numbers with commas
            if "EPS" in str(row.name):
                return [f"{v:,.2f}" if isinstance(v, (int, float)) else "-" for v in row]
            return [f"{v:,.0f}" if isinstance(v, (int, float)) else "-" for v in row]

        formatted = display_df.apply(_fmt_row, axis=1, result_type="expand")
        formatted.columns = display_df.columns
        st.dataframe(formatted, use_container_width=True)

    def build_trend_df(data, field, label):
        if not data:
            return None
        rows = []
        for item in data:
            year = str(item.get("calendarYear") or item.get("date", ""))[:4]
            val = item.get(field)
            if val is not None:
                rows.append({"Year": year, label: val})
        if not rows:
            return None
        df = pd.DataFrame(rows).iloc[::-1].reset_index(drop=True)
        return df.set_index("Year")

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

        st.divider()

        dcf = st.session_state.get("dcf")
        if is_financial:
            st.warning(
                "**DCF not applicable.** This is a financial-sector company "
                "(bank/insurer). Discounted cash flow does not work for financials "
                "because their business is lending and capital itself - FCFF is "
                "meaningless here. Analysts value these using P/E, Price-to-Book, "
                "or dividend-discount models instead. See the Ratios tab for P/E."
            )
        elif dcf and dcf.get("intrinsic_per_share") is not None:
            v1, v2, v3 = st.columns(3)
            v1.metric("Intrinsic Value", "$" + format(dcf["intrinsic_per_share"], ",.2f"))
            v2.metric("Market Price", "$" + format(dcf["market_price"], ",.2f"))
            up = dcf.get("upside")
            v3.metric("Upside/(Downside)",
                      format(up*100, "+.1f") + "%" if up is not None else "N/A")

            mos = calculate_margin_of_safety(
                dcf["intrinsic_per_share"], dcf["market_price"]
            )
            rec = get_recommendation(up, mos, ratios)
            banner = "**Recommendation: " + rec["recommendation"] + "** (Confidence: " + rec["confidence_label"] + ")"
            if rec["color"] == "success":
                st.success(banner)
            elif rec["color"] == "warning":
                st.warning(banner)
            elif rec["color"] == "error":
                st.error(banner)
            else:
                st.info(banner)

            if st.button("Generate Executive Summary"):
                with st.spinner("Gemini is summarizing..."):
                    es = get_executive_summary(profile, ratios, dcf, rec)
                st.session_state["exec_summary"] = es
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
        ch1, ch2 = st.columns(2)
        with ch1:
            rev_df = build_trend_df(income, "revenue", "Revenue")
            if rev_df is not None:
                st.markdown("**Revenue**")
                st.bar_chart(rev_df)
            ni_df = build_trend_df(income, "netIncome", "Net Income")
            if ni_df is not None:
                st.markdown("**Net Income**")
                st.bar_chart(ni_df)
        with ch2:
            fcff_rows = calculate_fcff(income, cashflow)
            if fcff_rows:
                fcff_df = pd.DataFrame([
                    {"Year": r["Year"][:4], "FCFF": r["FCFF"]}
                    for r in fcff_rows if r.get("FCFF") is not None
                ])
                if not fcff_df.empty:
                    fcff_df = fcff_df.iloc[::-1].set_index("Year")
                    st.markdown("**Free Cash Flow (FCFF)**")
                    st.bar_chart(fcff_df)
            ocf_df = build_trend_df(cashflow, "operatingCashFlow", "Operating CF")
            if ocf_df is not None:
                st.markdown("**Operating Cash Flow**")
                st.bar_chart(ocf_df)

    with tab1:
        st.markdown("**Income Statement** (last 5 years, USD)")
        show_statement(income, {
            "revenue": "Revenue", "grossProfit": "Gross Profit",
            "operatingIncome": "Operating Income", "netIncome": "Net Income",
            "eps": "EPS",
        })

    with tab2:
        st.markdown("**Balance Sheet** (last 5 years, USD)")
        show_statement(balance, {
            "totalAssets": "Total Assets", "totalLiabilities": "Total Liabilities",
            "totalEquity": "Total Equity",
            "cashAndCashEquivalents": "Cash & Equivalents", "totalDebt": "Total Debt",
        })

    with tab3:
        st.markdown("**Cash Flow Statement** (last 5 years, USD)")
        show_statement(cashflow, {
            "operatingCashFlow": "Operating Cash Flow",
            "capitalExpenditure": "Capital Expenditure",
            "freeCashFlow": "Free Cash Flow",
            "netCashProvidedByOperatingActivities": "Net Operating Cash",
        })

    with tab4:
        st.markdown("**Financial Ratios** (last 5 years)")
        if not ratios:
            st.warning("Could not calculate ratios.")
        else:
            pct_rows = ["Gross Margin", "Net Margin", "ROE", "ROA"]

            def fmt(val, row_name):
                if val is None:
                    return "-"
                if row_name in pct_rows:
                    return format(val*100, ".1f") + "%"
                return format(val, ".2f")

            years = [row["Year"] for row in ratios]
            ratio_names = [k for k in ratios[0].keys() if k != "Year"]
            text_table = {}
            for name in ratio_names:
                text_table[name] = [fmt(row.get(name), name) for row in ratios]
            st.dataframe(pd.DataFrame(text_table, index=years).T,
                        use_container_width=True)
            st.caption(
                "Current Ratio above 1 = can cover short-term bills. "
                "Higher margins/ROE = more profitable. "
                "Debt-to-Equity: higher = more leverage/risk."
            )

    with tab5:
        st.markdown("**FCFF - Free Cash Flow to the Firm** (last 5 years, USD)")
        st.caption("FCFF = Operating Cash Flow + Interest x (1 - Tax) - CapEx")
        fcff_rows = calculate_fcff(income, cashflow)
        if fcff_rows:
            display_rows = ["Operating Cash Flow", "Interest (after-tax)",
                            "CapEx", "FCFF"]
            years = [r["Year"] for r in fcff_rows]
            table = {}
            for name in display_rows:
                table[name] = [
                    format(r[name], ",.0f") if r.get(name) is not None else "-"
                    for r in fcff_rows
                ]
            st.dataframe(pd.DataFrame(table, index=years).T,
                        use_container_width=True)

        st.divider()
        st.markdown("**WACC - Weighted Average Cost of Capital**")
        col_a, col_b = st.columns(2)
        with col_a:
            rf = st.slider("Risk-Free Rate (10Y Treasury) %", 0.0, 8.0, 4.3, 0.1) / 100
        with col_b:
            erp = st.slider("Equity Risk Premium %", 3.0, 8.0, 5.0, 0.1) / 100
        wacc_data = calculate_wacc(profile, income, balance,
                                   risk_free_rate=rf, equity_risk_premium=erp)
        if wacc_data:
            m1, m2, m3 = st.columns(3)
            m1.metric("WACC", format(wacc_data["WACC"]*100, ".2f") + "%")
            m2.metric("Cost of Equity", format(wacc_data["Cost of Equity (Re)"]*100, ".2f") + "%")
            m3.metric("Cost of Debt", format(wacc_data["Cost of Debt (Rd)"]*100, ".2f") + "%")
            current_wacc = wacc_data["WACC"]
        else:
            st.warning("Could not calculate WACC.")
            current_wacc = None

        st.divider()
        st.markdown("### DCF Intrinsic Value")
        col_g, col_t = st.columns(2)
        with col_g:
            growth = st.slider("FCFF Growth Rate (next 5 yrs) %", 0.0, 20.0, 8.0, 0.5) / 100
        with col_t:
            term_growth = st.slider("Terminal Growth Rate %", 0.0, 5.0, 2.5, 0.1) / 100

        if current_wacc is None:
            st.warning("Need WACC to run the DCF.")
        else:
            dcf = run_dcf(income, cashflow, balance, profile, current_wacc,
                          growth_rate=growth, terminal_growth=term_growth)
            if not dcf or dcf.get("intrinsic_per_share") is None:
                st.warning("Could not complete DCF. Try lowering terminal growth.")
            else:
                intrinsic = dcf["intrinsic_per_share"]
                mprice = dcf["market_price"]
                upside = dcf["upside"]
                r1, r2, r3 = st.columns(3)
                r1.metric("Intrinsic Value / Share", "$" + format(intrinsic, ",.2f"))
                r2.metric("Current Market Price", "$" + format(mprice, ",.2f"))
                r3.metric("Upside / (Downside)",
                          format(upside*100, "+.1f") + "%" if upside is not None else "N/A")

                mos = calculate_margin_of_safety(intrinsic, mprice)
                st.markdown("**Margin of Safety**")
                required_mos = st.slider(
                    "Required Margin of Safety % (your risk buffer)", 0, 50, 25, 5,
                ) / 100
                if mos is not None:
                    mos_display = format(mos*100, "+.1f") + "%" if mos > -1 else "None (overvalued)"
                    ms1, ms2 = st.columns(2)
                    ms1.metric("Actual Margin of Safety", mos_display)
                    ms2.metric("Required (your setting)", format(required_mos*100, ".0f") + "%")
                    if mos >= required_mos:
                        st.success("Meets your margin of safety (" + format(mos*100, ".0f") + "%).")
                    elif mos > 0:
                        st.warning("Below required buffer (" + format(mos*100, ".0f") + "% vs " + format(required_mos*100, ".0f") + "%).")
                    else:
                        st.error("No margin of safety - trades above intrinsic value.")

                if upside is not None:
                    if upside > 0.15:
                        st.success("Potentially UNDERVALUED - about " + format(upside*100, ".0f") + "% above price.")
                    elif upside < -0.15:
                        st.error("Potentially OVERVALUED - about " + format(abs(upside)*100, ".0f") + "% below price.")
                    else:
                        st.info("Roughly FAIRLY VALUED.")

                st.markdown("**Valuation Breakdown**")
                breakdown = {
                    "Base FCFF (latest)": "$" + format(dcf["base_fcff"], ",.0f"),
                    "PV of 5-yr FCFF": "$" + format(dcf["pv_fcff_total"], ",.0f"),
                    "PV of Terminal Value": "$" + format(dcf["pv_terminal"], ",.0f"),
                    "Enterprise Value": "$" + format(dcf["enterprise_value"], ",.0f"),
                    "Equity Value": "$" + format(dcf["equity_value"], ",.0f"),
                    "Shares Outstanding": format(dcf["shares"], ",.0f") if dcf["shares"] else "N/A",
                }
                st.dataframe(
                    pd.DataFrame(list(breakdown.items()),
                                 columns=["Item", "Value"]).set_index("Item"),
                    use_container_width=True,
                )
                if dcf["enterprise_value"]:
                    tv_pct = dcf["pv_terminal"] / dcf["enterprise_value"] * 100
                    st.caption(format(tv_pct, ".0f") + "% of enterprise value is terminal value.")

                st.session_state["dcf"] = dcf

                st.divider()
                st.markdown("### Sensitivity Analysis")
                sens = sensitivity_analysis(income, cashflow, balance, profile,
                                            current_wacc, terminal_growth=term_growth)
                if sens:
                    wacc_list, growth_list, grid = sens
                    col_labels = ["g=" + format(g*100, ".0f") + "%" for g in growth_list]
                    row_labels = ["WACC=" + format(w*100, ".1f") + "%" for w in wacc_list]
                    cell_text = []
                    for row in grid:
                        cell_text.append([
                            "$" + format(v, ",.0f") if v is not None else "-" for v in row
                        ])
                    st.dataframe(
                        pd.DataFrame(cell_text, index=row_labels, columns=col_labels),
                        use_container_width=True,
                    )
                    st.caption("Current price: $" + format(mprice, ",.2f") + ". Value rises with growth, falls with WACC.")

    with tab6:
        st.markdown("### AI Investment Analysis")
        st.caption("AI narrative (Gemini) from calculated metrics only. Not advice.")
        dcf_for_ai = st.session_state.get("dcf")
        if dcf_for_ai is None:
            st.info("Valuation unavailable - try re-analyzing the company.")
        else:
            if st.button("Generate AI Bull & Bear Case"):
                with st.spinner("Gemini is analyzing..."):
                    result = get_ai_analysis(profile, ratios, dcf_for_ai)
                st.session_state["ai_result"] = result
            result = st.session_state.get("ai_result")
            if result:
                if result.get("error"):
                    st.error("AI analysis failed: " + str(result["error"]))
                else:
                    st.success("AI analysis generated (based on calculated metrics)")
                    c_bull, c_bear = st.columns(2)
                    with c_bull:
                        st.markdown("#### Bull Case")
                        st.markdown(result.get("bull") or "_No bull case._")
                    with c_bear:
                        st.markdown("#### Bear Case")
                        st.markdown(result.get("bear") or "_No bear case._")
                    st.caption("AI narrative for education. Not investment advice.")

    with tab7:
        st.markdown("### Investment Committee Recommendation")
        st.caption(
            "Transparent rule-based scoring (valuation + margin of safety + "
            "financial health), narrated by AI. The decision is deterministic."
        )
        dcf_for_rec = st.session_state.get("dcf")
        if dcf_for_rec is None:
            st.info("Valuation unavailable - try re-analyzing the company.")
        else:
            upside = dcf_for_rec.get("upside")
            intrinsic = dcf_for_rec.get("intrinsic_per_share")
            mprice = dcf_for_rec.get("market_price")
            mos = calculate_margin_of_safety(intrinsic, mprice)
            rec = get_recommendation(upside, mos, ratios)

            if rec["color"] == "success":
                st.success("## " + rec["recommendation"])
            elif rec["color"] == "warning":
                st.warning("## " + rec["recommendation"])
            elif rec["color"] == "error":
                st.error("## " + rec["recommendation"])
            else:
                st.info("## " + rec["recommendation"])

            cc1, cc2 = st.columns(2)
            cc1.metric("Confidence Level", rec["confidence_label"])
            cc2.metric("Composite Score", format(rec["total_score"], "+d"))

            st.markdown("**Score Components**")
            comp = rec["components"]
            st.dataframe(pd.DataFrame({
                "Dimension": ["Valuation", "Margin of Safety", "Financial Health"],
                "Score": [format(comp["valuation"], "+d"),
                          format(comp["margin_of_safety"], "+d"),
                          format(comp["financial_health"], "+d")],
            }).set_index("Dimension"), use_container_width=True)

            sw1, sw2 = st.columns(2)
            with sw1:
                st.markdown("**Financial Strengths**")
                if rec["strengths"]:
                    for s in rec["strengths"]:
                        st.markdown("- " + s)
                else:
                    st.markdown("_None identified._")
            with sw2:
                st.markdown("**Financial Weaknesses**")
                if rec["weaknesses"]:
                    for w in rec["weaknesses"]:
                        st.markdown("- " + w)
                else:
                    st.markdown("_None identified._")

            st.markdown("**Reasons For / Against**")
            ra1, ra2 = st.columns(2)
            with ra1:
                st.markdown("_Supporting:_")
                if rec["supporting"]:
                    for s in rec["supporting"]:
                        st.markdown("- " + s)
                else:
                    st.markdown("_None._")
            with ra2:
                st.markdown("_Concerns:_")
                concerns = rec["opposing"] + list(rec["weaknesses"])
                if concerns:
                    for c in concerns:
                        st.markdown("- " + c)
                else:
                    st.markdown("_None._")
            if rec.get("context_notes"):
                for note in rec["context_notes"]:
                    st.caption(note)

            st.divider()
            st.markdown("**AI Investment Memo**")
            if st.button("Generate Investment Memo"):
                with st.spinner("Gemini is writing the memo..."):
                    memo_result = get_investment_memo(profile, ratios, dcf_for_rec, rec)
                st.session_state["memo_result"] = memo_result
            memo_result = st.session_state.get("memo_result")
            if memo_result:
                if memo_result.get("error"):
                    st.error("Memo failed: " + str(memo_result["error"]))
                else:
                    st.markdown(memo_result["memo"])
                    st.caption("AI-written memo. Educational only - not investment advice.")

st.divider()
st.caption("FinSight AI - Built with Streamlit, Financial Modeling Prep and Google Gemini. For educational and demonstration purposes only - not investment advice.")