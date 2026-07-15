"""
data_fetch.py - talks to the FMP API. Separation of concerns.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("FMP_API_KEY")
BASE_URL = "https://financialmodelingprep.com/stable"

def get_company_profile(ticker):
    if not API_KEY:
        print("ERROR: FMP_API_KEY not found. Check your .env file.")
        return None
    url = f"{BASE_URL}/profile?symbol={ticker}&apikey={API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data:
            return None
        return data[0]
    except requests.exceptions.RequestException as e:
        print(f"ERROR fetching {ticker}: {e}")
        return None

if __name__ == "__main__":
    profile = get_company_profile("AAPL")
    if profile:
        print("Company:", profile.get("companyName"))
        print("Price:  ", profile.get("price"))
        print("Sector: ", profile.get("sector"))
    else:
        print("Failed to fetch profile.")
