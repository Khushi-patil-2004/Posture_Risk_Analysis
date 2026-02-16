import os
import json
import re
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")


def _extract_json(text: str):
    """
    Safely extract JSON object from LLM response.
    """
    if not text:
        return None

    # Remove code blocks if present
    text = text.strip()
    text = re.sub(r"```json|```", "", text, flags=re.IGNORECASE).strip()

    # Find first JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def generate_ai_recommendation(context: dict):
    """
    Groq-powered AI recommendation.
    Always safe. Never crashes. Falls back cleanly.
    """

    # Feature toggle
    if os.getenv("ENABLE_AI", "true").lower() != "true":
        return None

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("⚠️ GROQ_API_KEY not set, skipping AI recommendation")
        return None

    try:
        client = Groq(api_key=api_key)

        prompt = f"""
You are a posture health expert.

User Profile:
Age: {context['user']['age']}
Height: {context['user']['height_cm']} cm
Weight: {context['user']['weight_kg']} kg

Posture Results:
{json.dumps(context['posture_results'], indent=2)}

Posture Trends:
{json.dumps(context['trends'], indent=2)}

RULES:
- Respond ONLY with JSON
- No explanation
- No markdown
- No text outside JSON

JSON FORMAT:
{{
  "risk_level": "LOW | MODERATE | HIGH",
  "dominant_issue": "metric_name",
  "recommendation": {{
    "priority": "LOW | MEDIUM | HIGH",
    "message": "short personalized advice",
    "actions": ["action 1", "action 2", "action 3"]
  }}
}}
"""

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        raw = response.choices[0].message.content
        parsed = _extract_json(raw)

        if not parsed:
            print("⚠️ Groq returned non-JSON response")
            return None

        print("🤖 AI recommendation generated")
        return parsed

    except Exception as e:
        print("⚠️ Groq AI failed, using fallback:", e)
        return None
