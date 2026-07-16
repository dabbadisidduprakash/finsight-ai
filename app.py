"""
app.py - Streamlit UI for FinSight AI.
Day 2: company profile + 5-year financial statements in tabs.
"""
import streamlit as st
import pandas as pd
from src.data_fetch import (
    get_company_profile,
    get_income_statement,
    get_balance_sheet,
    get_cash_flow,
)

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

    tab1, tab2, tab3 = st.tabs(
        ["📈 Income Statement", "⚖️ Balance Sheet", "💵 Cash Flow"]
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