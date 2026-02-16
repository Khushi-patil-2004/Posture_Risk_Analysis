from app.recommendation.rules import METRIC_RULES
from app.recommendation.ai_engine import generate_ai_recommendation
from app.recommendation.ai_personalizer import build_personalization_context
from app.recommendation.config import RISK_THRESHOLDS, TREND_THRESHOLD
from app.recommendation.explainer import generate_explanation


def _compute_trends(session_history):
    trends = {}

    for session in session_history:
        for metric, data in session.items():
            trends.setdefault(metric, []).append(
                data.get("posture_risk_percent", 0)
            )

    trend_result = {}
    for metric, values in trends.items():
        if len(values) < 2:
            continue

        delta = values[-1] - values[0]
        direction = (
            "WORSENING" if delta > TREND_THRESHOLD else
            "IMPROVING" if delta < -TREND_THRESHOLD else
            "STABLE"
        )

        trend_result[metric] = {
            "direction": direction,
            "change": delta,
            "latest": values[-1]
        }

    return trend_result


def build_recommendation(
    results: dict,
    session_id: str,
    user_profile: dict,
    session_history: list
):
    # 1️⃣ Identify dominant issue
    dominant_metric = max(
        results.items(),
        key=lambda x: x[1].get("posture_risk_percent", 0)
    )[0]

    dominant_risk = results[dominant_metric]["posture_risk_percent"]

    if dominant_risk >= RISK_THRESHOLDS["HIGH"]:
        risk_level = "HIGH"
        priority = "HIGH"
    elif dominant_risk >= RISK_THRESHOLDS["MODERATE"]:
        risk_level = "MODERATE"
        priority = "MEDIUM"
    else:
        risk_level = "LOW"
        priority = "LOW"

    # 2️⃣ Compute trends
    trends = _compute_trends(session_history)

    # 3️⃣ Try AI personalization
    context = build_personalization_context(
        user_profile=user_profile,
        trends=trends,
        results=results
    )

    ai_output = generate_ai_recommendation(context)

    if ai_output:
        return {
            "session_id": session_id,
            **ai_output
        }

    # 4️⃣ Fallback (still intelligent)
    base_actions = METRIC_RULES.get(
        dominant_metric, {}
    ).get("base_actions", [])

    if dominant_metric in trends and trends[dominant_metric]["direction"] == "WORSENING":
        base_actions.append("Increase posture breaks frequency")
    # 5️⃣ Explanation (WHY this posture is risky)
    explanation_input = {
        "session_id": session_id,
        "risk": {
            "metric": dominant_metric,
            "risk_level": risk_level,
            "risk_percent": dominant_risk
        }
    }

    explanation = generate_explanation(explanation_input)

    return {
        "session_id": session_id,
        "risk_level": risk_level,
        "dominant_issue": dominant_metric,
        "recommendation": {
            "priority": priority,
            "message": f"Posture issue detected: {METRIC_RULES.get(dominant_metric, {}).get('label', dominant_metric)}.",
            "actions": base_actions
        }
    }

