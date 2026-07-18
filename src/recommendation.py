"""
recommendation.py - rule-based investment recommendation scoring.

This is DETERMINISTIC logic (not AI). It scores a company across three
dimensions — valuation, margin of safety, and financial health — and
produces a recommendation with a confidence level. Every point is
transparent and defensible: you can explain exactly why the score is
what it is. The AI memo (elsewhere) narrates this; it does NOT decide it.
"""


def _score_valuation(upside):
    """
    Score based on DCF upside/(downside).
    Returns (points, reason). More upside = higher score.
    """
    if upside is None:
        return 0, "Valuation inconclusive (no DCF result)."
    if upside > 0.30:
        return 2, f"Strongly undervalued: DCF shows {upside*100:.0f}% upside."
    if upside > 0.10:
        return 1, f"Modestly undervalued: {upside*100:.0f}% upside."
    if upside > -0.10:
        return 0, "Roughly fairly valued vs. DCF."
    if upside > -0.30:
        return -1, f"Modestly overvalued: {upside*100:.0f}% downside."
    return -2, f"Strongly overvalued: DCF shows {upside*100:.0f}% downside."


def _score_margin_of_safety(mos):
    """Score based on margin of safety buffer."""
    if mos is None:
        return 0, "Margin of safety not available."
    if mos > 0.25:
        return 2, f"Large margin of safety ({mos*100:.0f}%): well protected."
    if mos > 0.10:
        return 1, f"Some margin of safety ({mos*100:.0f}%)."
    if mos > 0:
        return 0, f"Thin margin of safety ({mos*100:.0f}%)."
    return -1, "No margin of safety: trades above intrinsic value."


def _score_financial_health(ratios):
    """
    Score based on the latest year's profitability, leverage, liquidity.
    Returns (points, list_of_reasons, strengths, weaknesses).
    """
    if not ratios:
        return 0, ["No ratio data."], [], []

    r = ratios[0]  # latest year
    points = 0
    reasons, strengths, weaknesses = [], [], []

    # Profitability — net margin
    nm = r.get("Net Margin")
    if isinstance(nm, (int, float)):
        if nm > 0.15:
            points += 1
            strengths.append(f"Strong net margin ({nm*100:.0f}%)")
        elif nm < 0.05:
            points -= 1
            weaknesses.append(f"Thin net margin ({nm*100:.0f}%)")

    # Returns — ROE
    roe = r.get("ROE")
    if isinstance(roe, (int, float)):
        if roe > 0.20:
            points += 1
            strengths.append(f"High ROE ({roe*100:.0f}%)")
        elif roe < 0.05:
            points -= 1
            weaknesses.append(f"Low ROE ({roe*100:.0f}%)")

    # Leverage — debt-to-equity
    de = r.get("Debt-to-Equity")
    if isinstance(de, (int, float)):
        if de > 2.0:
            points -= 1
            weaknesses.append(f"High leverage (D/E {de:.1f})")
        elif de < 0.5:
            points += 1
            strengths.append(f"Low leverage (D/E {de:.1f})")

    # Liquidity — current ratio
    cr = r.get("Current Ratio")
    if isinstance(cr, (int, float)):
        if cr < 1.0:
            weaknesses.append(f"Current ratio below 1 ({cr:.2f})")
        elif cr > 1.5:
            strengths.append(f"Healthy liquidity (current ratio {cr:.2f})")

    reasons.append(f"Financial health score: {points:+d}")
    return points, reasons, strengths, weaknesses


def get_recommendation(upside, mos, ratios):
    """
    Combine all scores into a final recommendation + confidence.
    Returns a dict with recommendation, confidence, total_score,
    and the supporting detail lists.
    """
    val_pts, val_reason = _score_valuation(upside)
    mos_pts, mos_reason = _score_margin_of_safety(mos)
    fin_pts, fin_reasons, strengths, weaknesses = _score_financial_health(ratios)

    total = val_pts + mos_pts + fin_pts

    # Map total score to a recommendation
    # Range roughly -5 to +6
    if total >= 4:
        rec = "BUY"
        color = "success"
    elif total >= 1:
        rec = "ACCUMULATE / HOLD"
        color = "info"
    elif total >= -1:
        rec = "HOLD"
        color = "info"
    elif total >= -3:
        rec = "REDUCE"
        color = "warning"
    else:
        rec = "AVOID / SELL"
        color = "error"

    # Confidence = how far from neutral, scaled
    confidence = min(abs(total) / 6.0, 1.0)
    if confidence > 0.66:
        conf_label = "High"
    elif confidence > 0.33:
        conf_label = "Moderate"
    else:
        conf_label = "Low"

    supporting = []
    opposing = []
    for pts, reason in [(val_pts, val_reason), (mos_pts, mos_reason)]:
        if pts > 0:
            supporting.append(reason)
        elif pts < 0:
            opposing.append(reason)
        else:
            supporting.append(reason)  # neutral notes go with context

    return {
        "recommendation": rec,
        "color": color,
        "total_score": total,
        "confidence": confidence,
        "confidence_label": conf_label,
        "valuation_reason": val_reason,
        "mos_reason": mos_reason,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "supporting": supporting,
        "opposing": opposing,
        "components": {
            "valuation": val_pts,
            "margin_of_safety": mos_pts,
            "financial_health": fin_pts,
        },
    }


if __name__ == "__main__":
    # Test with sample numbers
    fake_ratios = [{
        "Net Margin": 0.269, "ROE": 1.519, "ROA": 0.312,
        "Debt-to-Equity": 1.52, "Current Ratio": 0.89, "P/E": 44.56,
    }]
    rec = get_recommendation(upside=-0.647, mos=-1.0, ratios=fake_ratios)
    print("Recommendation:", rec["recommendation"])
    print("Confidence:", rec["confidence_label"], f"({rec['confidence']*100:.0f}%)")
    print("Total score:", rec["total_score"])
    print("Strengths:", rec["strengths"])
    print("Weaknesses:", rec["weaknesses"])