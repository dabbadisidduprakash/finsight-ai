"""
recommendation.py - rule-based investment recommendation scoring.
Deterministic logic (not AI). Scores valuation, margin of safety, and
financial health into a recommendation with a confidence level.
"""


def _score_valuation(upside):
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
    if not ratios:
        return 0, ["No ratio data."], [], []

    r = ratios[0]
    points = 0
    reasons, strengths, weaknesses = [], [], []

    nm = r.get("Net Margin")
    if isinstance(nm, (int, float)):
        if nm > 0.15:
            points += 1
            strengths.append(f"Strong net margin ({nm*100:.0f}%)")
        elif nm < 0.05:
            points -= 1
            weaknesses.append(f"Thin net margin ({nm*100:.0f}%)")

    roe = r.get("ROE")
    if isinstance(roe, (int, float)):
        if roe > 0.20:
            points += 1
            strengths.append(f"High ROE ({roe*100:.0f}%)")
        elif roe < 0.05:
            points -= 1
            weaknesses.append(f"Low ROE ({roe*100:.0f}%)")

    de = r.get("Debt-to-Equity")
    if isinstance(de, (int, float)):
        if de > 2.0:
            points -= 1
            weaknesses.append(f"High leverage (D/E {de:.1f})")
        elif de < 0.5:
            points += 1
            strengths.append(f"Low leverage (D/E {de:.1f})")

    cr = r.get("Current Ratio")
    if isinstance(cr, (int, float)):
        if cr < 1.0:
            weaknesses.append(f"Current ratio below 1 ({cr:.2f})")
        elif cr > 1.5:
            strengths.append(f"Healthy liquidity (current ratio {cr:.2f})")

    reasons.append(f"Financial health score: {points:+d}")
    return points, reasons, strengths, weaknesses


def get_recommendation(upside, mos, ratios):
    val_pts, val_reason = _score_valuation(upside)
    mos_pts, mos_reason = _score_margin_of_safety(mos)
    fin_pts, fin_reasons, strengths, weaknesses = _score_financial_health(ratios)

    total = val_pts + mos_pts + fin_pts

    if total >= 4:
        rec, color = "BUY", "success"
    elif total >= 1:
        rec, color = "ACCUMULATE / HOLD", "info"
    elif total >= -1:
        rec, color = "HOLD", "info"
    elif total >= -3:
        rec, color = "REDUCE", "warning"
    else:
        rec, color = "AVOID / SELL", "error"

    confidence = min(abs(total) / 6.0, 1.0)
    if confidence > 0.66:
        conf_label = "High"
    elif confidence > 0.33:
        conf_label = "Moderate"
    else:
        conf_label = "Low"

    supporting = []
    opposing = []
    context_notes = []
    for pts, reason in [(val_pts, val_reason), (mos_pts, mos_reason)]:
        if pts > 0:
            supporting.append(reason)
        elif pts < 0:
            opposing.append(reason)
        else:
            context_notes.append(reason)

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
        "context_notes": context_notes,
        "components": {
            "valuation": val_pts,
            "margin_of_safety": mos_pts,
            "financial_health": fin_pts,
        },
    }


if __name__ == "__main__":
    fake_ratios = [{
        "Net Margin": 0.269, "ROE": 1.519, "ROA": 0.312,
        "Debt-to-Equity": 1.52, "Current Ratio": 0.89, "P/E": 44.56,
    }]
    rec = get_recommendation(upside=-0.647, mos=-1.0, ratios=fake_ratios)
    print("Recommendation:", rec["recommendation"])
    print("Confidence:", rec["confidence_label"])
    print("Score:", rec["total_score"])
    print("Supporting:", rec["supporting"])
    print("Concerns:", rec["opposing"] + rec["weaknesses"])