# app/recommendation/explainer.py

import requests
import json
import re
from datetime import datetime


def generate_explanation(rec_input: dict) -> dict:
    session_id = rec_input["session_id"]
    risk = rec_input["risk"]

    metric_key = risk["metric"]
    risk_percent = risk["risk_percent"]
    risk_status = risk["risk_level"]

    prompt = f"""
You MUST respond ONLY with valid JSON.
Do NOT add explanation text.
Do NOT add markdown.

Metric: {metric_key}
Risk Percentage: {risk_percent}%
Risk Level: {risk_status}

Respond EXACTLY in this format:

{{
  "message": "short explanation why this posture is risky",
  "actions": ["action1", "action2", "action3"],
  "priority": "LOW or MODERATE or HIGH"
}}
"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "qwen2:0.5b",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2}
            },
            timeout=60
        )

        raw = response.json().get("response", "")
        parsed = _extract_json(raw)

        if not parsed:
            return _fallback()

        return {
            **parsed,
            "generated_at": datetime.now().isoformat()
        }

    except Exception:
        return _fallback()


def _extract_json(text: str):
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return None
    except Exception:
        return None


def _fallback():
    return {
        "message": "This posture increases strain on neck and upper spine over time.",
        "actions": [
            "Maintain neutral head alignment",
            "Adjust screen height",
            "Take posture breaks regularly"
        ],
        "priority": "MODERATE",
        "generated_at": datetime.now().isoformat()
    }
