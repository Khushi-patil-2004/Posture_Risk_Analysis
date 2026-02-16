# ai_personalizer.py
def build_personalization_context(user_profile, trends, results):
    return {
        "user": {
            "age": user_profile["age"],
            "height_cm": user_profile["height_cm"],
            "weight_kg": user_profile["weight_kg"]
        },
        "posture_results": results,
        "trends": trends
    }
