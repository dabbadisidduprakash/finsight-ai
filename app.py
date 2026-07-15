"""
app.py - Streamlit UI for FinSight AI. Day 1.
"""
import streamlit as st
from src.data_fetch import get_company_profile

st.set_page_config(page_title="FinSight AI", page_icon="📊", layout="centered")

st.title("📊 FinSight AI")
st.caption("AI Investment Committee Assistant — Day 1")
st.divider()

st.subheader("Company Search")
ticker = st.text_input(
    "Enter a US stock ticker (e.g. AAPL, MSFT, GOOGL):",
    value="AAPL",
).strip().upper()

if st.button("Fetch Company"):
    if not ticker:
        st.warning("Please enter a ticker symbol.")
    else:
        with st.spinner(f"Fetching {ticker}..."):
            profile = get_company_profile(ticker)

        if profile is None:
            st.error(
                f"Could not find data for '{ticker}'. "
                "Check the ticker, or your API key may have hit its daily limit."
            )
        else:
            st.success(f"Loaded: {profile.get('companyName', 'Unknown')}")
            if profile.get("image"):
                st.image(profile["image"], width=80)
            col1, col2, col3 = st.columns(3)
            col1.metric("Price", f"${profile.get('price', 'N/A')}")
            col2.metric("Sector", profile.get("sector", "N/A"))
            col3.metric("Country", profile.get("country", "N/A"))
            st.markdown("**About:**")
            st.write(profile.get("description", "No description available."))