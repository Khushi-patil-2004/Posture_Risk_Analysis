import os
from openai import OpenAI


def generate_ai_recommendation(context: dict):
    """
    Optional AI-powered personalization.
    If OPENAI_API_KEY is missing or API fails,
    returns None and system falls back safely.
    """

    api_key = os.getenv("OPENAI_API_KEY")

    # 🔒 If key not present → disable AI silently
    if not api_key:
        print("⚠️ OPENAI_API_KEY not set, skipping AI recommendation")
        return None

    try:
        client = OpenAI(api_key=api_key)

        prompt = f"""
You are a posture health expert.

User profile:
Age: {context['user']['age']}
Height: {context['user']['height_cm']} cm
Weight: {context['user']['weight_kg']} kg

Posture results:
{context['posture_results']}

Posture trends:
{context['trends']}

TASK:
Return STRICT JSON:
{{
  "risk_level": "...",
  "dominant_issue": "...",
  "message": "...",
  "actions": ["...", "..."]
}}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )

        return eval(response.choices[0].message.content)

    except Exception as e:
        print("⚠️ AI failed, using fallback:", e)
        return None
