"""
ai_analysis.py - AI narrative layer for FinSight AI (Gemini).

CRITICAL DESIGN PRINCIPLE:
The AI does NOT calculate anything. All numbers come from our own code
(ratios, DCF, margin of safety). We pass those verified numbers to Gemini,
and it only writes the NARRATIVE (bull case / bear case) around them.
This prevents the AI from inventing financial data.

Built provider-agnostic in spirit: the get_ai_analysis function is the single
entry point, so another provider (OpenAI/Anthropic) could be swapped in later.
"""
import os
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# The free tier uses Flash-class models (Pro is paid-only as of 2026).
MODEL_NAME = "gemini-2.5-flash"


def _build_context(profile, ratios, dcf):
    """
    Assemble the verified numbers into a clean text summary that we hand
    to the AI as ground truth. The AI must reason ONLY from these.
    """
    name = profile.get("companyName", "the company") if profile else "the company"
    sector = profile.get("sector", "N/A") if profile else "N/A"
    price = profile.get("price", "N/A") if profile else "N/A"

    lines = [f"Company: {name}", f"Sector: {sector}", f"Current Price: ${price}"]

    # Latest ratios (first row = most recent year)
    if ratios:
        r = ratios[0]
        def pct(v):
            return f"{v*100:.1f}%" if isinstance(v, (int, float)) else "N/A"
        def num(v):
            return f"{v:.2f}" if isinstance(v, (int, float)) else "N/A"
        lines.append("Latest financial ratios:")
        lines.append(f"  Net Margin: {pct(r.get('Net Margin'))}")
        lines.append(f"  Gross Margin: {pct(r.get('Gross Margin'))}")
        lines.append(f"  ROE: {pct(r.get('ROE'))}")
        lines.append(f"  ROA: {pct(r.get('ROA'))}")
        lines.append(f"  Current Ratio: {num(r.get('Current Ratio'))}")
        lines.append(f"  Debt-to-Equity: {num(r.get('Debt-to-Equity'))}")
        lines.append(f"  P/E: {num(r.get('P/E'))}")

    # DCF outputs
    if dcf:
        iv = dcf.get("intrinsic_per_share")
        up = dcf.get("upside")
        lines.append("DCF valuation results:")
        lines.append(f"  Intrinsic Value/Share: ${iv:.2f}" if iv else "  Intrinsic Value: N/A")
        if up is not None:
            lines.append(f"  Upside/(Downside) vs price: {up*100:+.1f}%")

    return "\n".join(lines)


def get_ai_analysis(profile, ratios, dcf):
    """
    Ask Gemini to write a Bull Case and Bear Case grounded ONLY in the
    numbers we computed. Returns a dict:
        {"bull": "...", "bear": "...", "error": None}
    or an error message if the call fails.
    """
    if not GEMINI_API_KEY:
        return {"bull": None, "bear": None,
                "error": "GEMINI_API_KEY not found. Check your .env file."}

    context = _build_context(profile, ratios, dcf)

    prompt = f"""You are an equity research assistant. Below are VERIFIED financial
metrics that have already been calculated. Do NOT invent or change any numbers.
Use ONLY these figures to write your analysis.

{context}

Write two sections:

BULL CASE: 3-4 concise bullet points arguing why this could be a good investment,
referencing the specific metrics above (e.g. strong margins, ROE, undervaluation).

BEAR CASE: 3-4 concise bullet points arguing why this could be a poor or risky
investment, referencing the specific metrics above (e.g. high valuation, leverage,
thin margins, overvaluation per the DCF).

Rules:
- Base every point on the numbers provided. Do not fabricate data.
- Be balanced and objective, not promotional.
- Format each section as bullet points starting with "- ".
- Separate the two sections with the exact header lines "BULL CASE:" and "BEAR CASE:".
"""

    try:
        from google import genai

        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
        text = response.text if hasattr(response, "text") else str(response)

        # Split the response into bull and bear sections
        bull, bear = _split_sections(text)
        return {"bull": bull, "bear": bear, "error": None}

    except Exception as e:
        return {"bull": None, "bear": None, "error": f"AI call failed: {e}"}


def _split_sections(text):
    """Split the AI response into bull and bear parts by the header lines."""
    bull, bear = text, ""
    upper = text.upper()
    if "BEAR CASE" in upper:
        idx = upper.index("BEAR CASE")
        bull = text[:idx]
        bear = text[idx:]
    # Clean the headers out of the bodies
    bull = bull.replace("BULL CASE:", "").replace("Bull Case:", "").strip()
    bear = bear.replace("BEAR CASE:", "").replace("Bear Case:", "").strip()
    return bull, bear


if __name__ == "__main__":
    # Standalone test with real data
    from data_fetch import (get_company_profile, get_income_statement,
                            get_balance_sheet, get_cash_flow)
    from ratios import calculate_ratios
    from valuation import calculate_wacc, run_dcf

    t = "AAPL"
    p = get_company_profile(t)
    i = get_income_statement(t)
    b = get_balance_sheet(t)
    c = get_cash_flow(t)
    r = calculate_ratios(i, b, c, p)
    w = calculate_wacc(p, i, b)["WACC"]
    d = run_dcf(i, c, b, p, w)

    result = get_ai_analysis(p, r, d)
    if result["error"]:
        print("ERROR:", result["error"])
    else:
        print("=== BULL CASE ===")
        print(result["bull"])
        print("\n=== BEAR CASE ===")
        print(result["bear"])