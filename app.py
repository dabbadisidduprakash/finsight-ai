"""
app.py - Streamlit UI for FinSight AI.
Day 6: FCFF + WACC + DCF intrinsic value in the Valuation tab.
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
from src.valuation import calculate_fcff, calculate_wacc, run_dcf

st.set_page_config(page_title="FinSight AI", page_icon="📊", layout="wide")

st.title("📊 FinSight AI")
st.caption("AI Investment Committee Assistant")
st.divider()

ticker = st.text_input(
    "Enter a US stock ticker (e.g. AAPL, MSFT, GOOGL):",
    value="AAPL",
).strip().upper()

if st.button("Analyze Company"):
    if not ticker:
        st.warning("Please enter a ticker symbol.")
    else:
        with st.spinner(f"Fetching data for {ticker}..."):
            profile = get_company_profile(ticker)
            income = get_income_statement(ticker)
            balance = get_balance_sheet(ticker)
            cashflow = get_cash_flow(ticker)

        if profile is None:
            st.error(
                f"Could not find data for '{ticker}'. "
                "Check the ticker, or your API key may have hit its daily limit."
            )
        else:
            st.session_state["profile"] = profile
            st.session_state["income"] = income
            st.session_state["balance"] = balance
            st.session_state["cashflow"] = cashflow

if "profile" in st.session_state:
    profile = st.session_state["profile"]

    col_logo, col_info = st.columns([1, 5])
    with col_logo:
        if profile.get("image"):
            st.image(profile["image"], width=80)
    with col_info:
        st.subheader(profile.get("companyName", "Unknown"))
        mcap = profile.get("marketCap")
        mcap_str = f"${mcap:,}" if isinstance(mcap, (int, float)) else "N/A"
        st.write(
            f"**Sector:** {profile.get('sector', 'N/A')}  |  "
            f"**Price:** ${profile.get('price', 'N/A')}  |  "
            f"**Market Cap:** {mcap_str}"
        )

    st.divider()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📈 Income Statement", "⚖️ Balance Sheet", "💵 Cash Flow",
         "📊 Ratios", "🧮 Valuation"]
    )

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
        st.dataframe(
            display_df.style.format("{:,.0f}", na_rep="—"),
            use_container_width=True,
        )

    with tab1:
        st.markdown("**Income Statement** (last 5 years, USD)")
        show_statement(
            st.session_state.get("income"),
            {
                "revenue": "Revenue",
                "grossProfit": "Gross Profit",
                "operatingIncome": "Operating Income",
                "netIncome": "Net Income",
                "eps": "EPS",
            },
        )

    with tab2:
        st.markdown("**Balance Sheet** (last 5 years, USD)")
        show_statement(
            st.session_state.get("balance"),
            {
                "totalAssets": "Total Assets",
                "totalLiabilities": "Total Liabilities",
                "totalEquity": "Total Equity",
                "cashAndCashEquivalents": "Cash & Equivalents",
                "totalDebt": "Total Debt",
            },
        )

    with tab3:
        st.markdown("**Cash Flow Statement** (last 5 years, USD)")
        show_statement(
            st.session_state.get("cashflow"),
            {
                "operatingCashFlow": "Operating Cash Flow",
                "capitalExpenditure": "Capital Expenditure",
                "freeCashFlow": "Free Cash Flow",
                "netCashProvidedByOperatingActivities": "Net Operating Cash",
            },
        )

    with tab4:
        st.markdown("**Financial Ratios** (last 5 years)")
        ratios = calculate_ratios(
            st.session_state.get("income"),
            st.session_state.get("balance"),
            st.session_state.get("cashflow"),
            profile,
        )
        if not ratios:
            st.warning("Could not calculate ratios (missing data).")
        else:
            pct_rows = ["Gross Margin", "Net Margin", "ROE", "ROA"]

            def fmt(val, row_name):
                if val is None:
                    return "—"
                if row_name in pct_rows:
                    return f"{val*100:.1f}%"
                return f"{val:.2f}"

            years = [row["Year"] for row in ratios]
            ratio_names = [k for k in ratios[0].keys() if k != "Year"]

            text_table = {}
            for name in ratio_names:
                text_table[name] = [fmt(row.get(name), name) for row in ratios]

            display_df = pd.DataFrame(text_table, index=years).T
            st.dataframe(display_df, use_container_width=True)

            st.caption(
                "Current Ratio >1 = can cover short-term bills. "
                "Higher margins/ROE = more profitable. "
                "Debt-to-Equity: higher = more leverage/risk. "
                "P/E shown for latest year only."
            )

    with tab5:
        # ---------- FCFF ----------
        st.markdown("**FCFF — Free Cash Flow to the Firm** (last 5 years, USD)")
        st.caption(
            "FCFF = Operating Cash Flow + Interest×(1−Tax) − CapEx. "
            "The cash the whole business generates for all investors."
        )
        fcff_rows = calculate_fcff(
            st.session_state.get("income"),
            st.session_state.get("cashflow"),
        )
        if fcff_rows:
            display_rows = ["Operating Cash Flow", "Interest (after-tax)",
                            "CapEx", "FCFF"]
            years = [r["Year"] for r in fcff_rows]
            table = {}
            for name in display_rows:
                table[name] = [
                    f"{r[name]:,.0f}" if r.get(name) is not None else "—"
                    for r in fcff_rows
                ]
            st.dataframe(pd.DataFrame(table, index=years).T,
                        use_container_width=True)

        st.divider()

        # ---------- WACC ----------
        st.markdown("**WACC — Weighted Average Cost of Capital** (discount rate)")
        col_a, col_b = st.columns(2)
        with col_a:
            rf = st.slider("Risk-Free Rate (10Y Treasury) %", 0.0, 8.0, 4.3, 0.1) / 100
        with col_b:
            erp = st.slider("Equity Risk Premium %", 3.0, 8.0, 5.0, 0.1) / 100

        wacc_data = calculate_wacc(
            profile,
            st.session_state.get("income"),
            st.session_state.get("balance"),
            risk_free_rate=rf,
            equity_risk_premium=erp,
        )

        if wacc_data:
            m1, m2, m3 = st.columns(3)
            m1.metric("WACC", f"{wacc_data['WACC']*100:.2f}%")
            m2.metric("Cost of Equity", f"{wacc_data['Cost of Equity (Re)']*100:.2f}%")
            m3.metric("Cost of Debt", f"{wacc_data['Cost of Debt (Rd)']*100:.2f}%")
            current_wacc = wacc_data["WACC"]
        else:
            st.warning("Could not calculate WACC.")
            current_wacc = None

        st.divider()

        # ---------- DCF ----------
        st.markdown("### 🎯 DCF Intrinsic Value")
        st.caption(
            "Project FCFF forward, add a terminal value, discount everything "
            "back by WACC, then convert to value per share. Adjust the growth "
            "assumptions below — the result is highly sensitive to them."
        )

        col_g, col_t = st.columns(2)
        with col_g:
            growth = st.slider(
                "FCFF Growth Rate (next 5 yrs) %", 0.0, 20.0, 8.0, 0.5
            ) / 100
        with col_t:
            term_growth = st.slider(
                "Terminal Growth Rate %", 0.0, 5.0, 2.5, 0.1
            ) / 100

        if current_wacc is None:
            st.warning("Need WACC to run the DCF.")
        else:
            dcf = run_dcf(
                st.session_state.get("income"),
                st.session_state.get("cashflow"),
                st.session_state.get("balance"),
                profile,
                current_wacc,
                growth_rate=growth,
                terminal_growth=term_growth,
            )

            if not dcf or dcf.get("intrinsic_per_share") is None:
                st.warning(
                    "Could not complete DCF. This can happen if WACC is below "
                    "the terminal growth rate — try lowering terminal growth."
                )
            else:
                intrinsic = dcf["intrinsic_per_share"]
                price = dcf["market_price"]
                upside = dcf["upside"]

                r1, r2, r3 = st.columns(3)
                r1.metric("Intrinsic Value / Share", f"${intrinsic:,.2f}")
                r2.metric("Current Market Price", f"${price:,.2f}")
                r3.metric(
                    "Upside / (Downside)",
                    f"{upside*100:+.1f}%" if upside is not None else "N/A",
                )

                # Verdict
                if upside is not None:
                    if upside > 0.15:
                        st.success(
                            f"📈 **Potentially UNDERVALUED** — the DCF suggests "
                            f"the stock is worth about {upside*100:.0f}% more "
                            f"than its current price (at these assumptions)."
                        )
                    elif upside < -0.15:
                        st.error(
                            f"📉 **Potentially OVERVALUED** — the DCF suggests "
                            f"the stock is worth about {abs(upside)*100:.0f}% "
                            f"less than its current price (at these assumptions)."
                        )
                    else:
                        st.info(
                            "➖ **Roughly FAIRLY VALUED** — intrinsic value is "
                            "close to the market price at these assumptions."
                        )

                # Breakdown
                st.markdown("**Valuation Breakdown**")
                breakdown = {
                    "Base FCFF (latest)": f"${dcf['base_fcff']:,.0f}",
                    "PV of 5-yr FCFF": f"${dcf['pv_fcff_total']:,.0f}",
                    "PV of Terminal Value": f"${dcf['pv_terminal']:,.0f}",
                    "Enterprise Value": f"${dcf['enterprise_value']:,.0f}",
                    "Equity Value": f"${dcf['equity_value']:,.0f}",
                    "Shares Outstanding": f"{dcf['shares']:,.0f}" if dcf['shares'] else "N/A",
                }
                st.dataframe(
                    pd.DataFrame(list(breakdown.items()),
                                 columns=["Item", "Value"]).set_index("Item"),
                    use_container_width=True,
                )

                # % of value from terminal (a real interview point)
                if dcf["enterprise_value"]:
                    tv_pct = dcf["pv_terminal"] / dcf["enterprise_value"] * 100
                    st.caption(
                        f"⚠️ {tv_pct:.0f}% of the enterprise value comes from the "
                        f"terminal value — typical for DCF, but it means the result "
                        f"leans heavily on the terminal growth assumption."
                    )

                st.session_state["dcf"] = dcf