 # Core scoring logic
from collections import defaultdict
from app.config import SESSION_CONFIG, CONFIDENCE_THRESHOLD, SCORE_BANDS
from app.utils import classify_value

FPS = 1  # as per document (1 frame = 1 second)

def posture_status(score: float) -> str:
    if score <= 30:
        return "Good posture"
    elif score <= 60:
        return "Moderate risk"
    return "High risk"


def compute_weighted_score(class_time, valid_time, session_duration):
    """
    Implements STEP 2 → STEP 5 from the document
    """
    final_score = 0.0

    for level, time_min in class_time.items():
        band_start, band_end = SCORE_BANDS[level]
        band_width = band_end - band_start

        # STEP 2: time → session percentage
        time_percent = time_min / session_duration

        # STEP 4: score inside band
        score_inside_band = band_start + (time_percent * band_width)

        # STEP 5: weighted aggregation
        final_score += score_inside_band * time_min

    return final_score / valid_time if valid_time > 0 else 0.0


def process_session(frames):
    """
    STEP 1:
    Aggregate time by counting frames (FPS-based).
    Each valid frame contributes exactly 1 second.
    """

    # DEBUG: Log frame statistics
    print(f"\n=== SCORING DEBUG ===")
    print(f"Total frames received: {len(frames)}")
    
    frame_views = {}
    for f in frames:
        view = f.get("camera_angle", "UNKNOWN")
        frame_views[view] = frame_views.get(view, 0) + 1
    print(f"Frames by view: {frame_views}")

    # (view, metric) → GOOD/WARNING/BAD time (minutes)
    class_time_map = defaultdict(
        lambda: {"good": 0.0, "warning": 0.0, "bad": 0.0}
    )

    # (view, metric) → total valid time (minutes)
    valid_time_map = defaultdict(float)

    # -------- STEP 1: Range-wise time aggregation --------
    for frame in frames:
        view = frame["camera_angle"]
        if view not in SESSION_CONFIG:
            print(f" View '{view}' not in SESSION_CONFIG")
            continue

        for metric, cfg in SESSION_CONFIG[view]["metrics"].items():
            value = frame["data"].get(metric)
            confidence = frame["data"].get(metric.replace("_degree", "_confidence"), 0)

            if value is None:
                print(f" {view}_{metric}: Missing value")
                continue
            
            if confidence < CONFIDENCE_THRESHOLD:
                print(f" {view}_{metric}: Low confidence {confidence} < {CONFIDENCE_THRESHOLD}")
                continue

            posture_class = classify_value(value, cfg["ranges"])
            print(f" {view}_{metric}: value={value:.2f}, confidence={confidence:.2f} → {posture_class}")

            # FPS = 1 → 1 frame = 1 second = 1/60 minute
            time_min = 1 / 60

            class_time_map[(view, metric)][posture_class] += time_min
            valid_time_map[(view, metric)] += time_min

    results = {}

    
    for (view, metric), class_time in class_time_map.items():
        valid_time = valid_time_map[(view, metric)]
        session_duration = SESSION_CONFIG[view]["duration_min"]

        if valid_time == 0:
            continue

        final_score = compute_weighted_score(
            class_time,
            valid_time,
            session_duration
        )

        results[f"{view}_{metric}"] = {
            "metric": metric.replace("_degree", "").replace("_", " "),
            "posture_risk_percent": round(final_score),
            "status": posture_status(final_score)
        }

    # -------- CALCULATE OVERALL SESSION SCORE --------
    if results:
        # Method 1: Average score across all metrics
        all_scores = [m["posture_risk_percent"] for m in results.values()]
        average_score = sum(all_scores) / len(all_scores)
        
        # Method 2: Worst metric (maximum risk)
        worst_metric_key = max(results.keys(), key=lambda k: results[k]["posture_risk_percent"])
        worst_metric_data = results[worst_metric_key]
        worst_score = worst_metric_data["posture_risk_percent"]
        worst_metric_name = worst_metric_data["metric"]
        
        # Find metrics contributing to moderate/high risk
        risk_factors = [
            (metric_key, data["metric"], data["posture_risk_percent"]) 
            for metric_key, data in results.items()
            if data["posture_risk_percent"] > 30  # Moderate or higher
        ]
        risk_factors.sort(key=lambda x: x[2], reverse=True)  # Sort by score descending
        
        # Add overall summary
        results["__OVERALL__"] = {
            "metric": "overall session posture",
            "average_risk_percent": round(average_score),
            "worst_metric": worst_metric_name,
            "worst_metric_risk_percent": worst_score,
            "overall_status": posture_status(average_score),
            "worst_metric_status": posture_status(worst_score),
            "reason": f"Mainly due to {worst_metric_name} ({worst_score}% risk)",
            "contributing_risk_factors": [
                {"metric": name, "risk_percent": score} 
                for _, name, score in risk_factors
            ],
            "total_metrics_evaluated": len(results)
        }

    return results
