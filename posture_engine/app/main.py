from fastapi import FastAPI, HTTPException
import requests
from app.scoring import process_session
from app.recommendation.builder import build_recommendation

INPUT_COLLECTOR_BASE = "http://127.0.0.1:8001"

app = FastAPI(title="Posture Scoring Engine")

# Stores final outputs
RESULT_STORE = {}

# Stores past session results for trend analysis
SESSION_HISTORY = {}


def process_single_session(session_id: str, user_profile: dict):
    """
    Shared logic to process one session
    """

    input_resp = requests.get(
        f"{INPUT_COLLECTOR_BASE}/input/{session_id}", timeout=5
    )
    frames = input_resp.json().get("frames", [])

    if not frames:
        raise ValueError("No frames found")

    #  DEBUG: Log what we got from input_collector
    print(f"\n INPUT COLLECTOR DEBUG:")
    print(f"Session: {session_id}")
    print(f"Frames received: {len(frames)}")
    
    frame_views = {}
    for f in frames:
        view = f.get("camera_angle", "UNKNOWN")
        frame_views[view] = frame_views.get(view, 0) + 1
    print(f"Frames by view: {frame_views}")
    
    if frames:
        print(f"First frame sample: {frames[0]}")

    # 1️ Core scoring (UNCHANGED)
    scoring_results = process_session(frames)

    # 2️ Save for trend analysis
    SESSION_HISTORY.setdefault(session_id, [])
    SESSION_HISTORY[session_id].append(scoring_results)

    # 3️ Recommendation (trend + AI + fallback)
    recommendation = build_recommendation(
        results=scoring_results,
        session_id=session_id,
        user_profile=user_profile,
        session_history=SESSION_HISTORY[session_id]
    )

    # 4️ Store final output
    RESULT_STORE[session_id] = {
        "session_id": session_id,
        "results": scoring_results,
        "recommendation": recommendation
    }


@app.on_event("startup")
def auto_process_all_sessions():
    print("Fetching available sessions from input_collector...")

    try:
        resp = requests.get(f"{INPUT_COLLECTOR_BASE}/sessions", timeout=5)
        session_ids = resp.json().get("sessions", [])
    except Exception as e:
        print(" Cannot reach input_collector:", e)
        return

    if not session_ids:
        print(" No sessions found")
        return

    # Default user profile (can be replaced by DB later)
    default_user_profile = {
        "age": 28,
        "height_cm": 170,
        "weight_kg": 65
    }

    for session_id in session_ids:
        print(f" Processing session: {session_id}")

        try:
            process_single_session(session_id, default_user_profile)

            print(f" Completed: {session_id}")
            print(f"Result API → http://127.0.0.1:8000/result/{session_id}")

        except Exception as e:
            print(f"Session {session_id} failed:", e)


# OPTIONAL: MANUAL REPROCESS (VERY USEFUL)
@app.post("/process/{session_id}")
def reprocess_session(session_id: str, user_profile: dict):
    try:
        process_single_session(session_id, user_profile)
        return {"message": "Session processed", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


#  FINAL RESULT API (SHARE THIS)
@app.get("/result/{session_id}")
def get_result(session_id: str):
    if session_id not in RESULT_STORE:
        raise HTTPException(status_code=404, detail="Result not ready")

    return RESULT_STORE[session_id]
# DEBUG ENDPOINT - Shows raw scoring results
@app.get("/debug/{session_id}")
def debug_result(session_id: str):
    if session_id not in RESULT_STORE:
        return {"error": "Session not processed yet"}
    
    result = RESULT_STORE[session_id]
    metrics_in_results = list(result.get("results", {}).keys())
    
    return {
        "session_id": session_id,
        "total_metrics_scored": len(metrics_in_results),
        "metrics_list": metrics_in_results,
        "raw_scores": result.get("results", {}),
        "history": SESSION_HISTORY.get(session_id, [])
    }