from fastapi import FastAPI
import uuid
from storage import FRAME_STORE
from log_parser import load_frames_from_raw_logs

DATA_FILE = "data/flutter_raw_logs.jsonl"
BASE_URL = "http://127.0.0.1:8001"

app = FastAPI(title="Input Collector API")

# TRACK CREATED SESSIONS
SESSION_REGISTRY = []

@app.get("/create-session")
def create_session():
    session_id = f"session_{uuid.uuid4().hex[:8]}"

    load_frames_from_raw_logs(session_id, DATA_FILE)

    SESSION_REGISTRY.append(session_id)

    return {
        "session_id": session_id,
        "input_api_url": f"{BASE_URL}/input/{session_id}"
    }
@app.get("/input/{session_id}")
def get_input(session_id: str):
    return {
        "session_id": session_id,
        "frames": FRAME_STORE.get(session_id, [])
    }
# ✅ THIS IS WHAT POSTURE_ENGINE NEEDS
@app.get("/sessions")
def list_sessions():
    return {
        "sessions": SESSION_REGISTRY
    }
# 🔍 DEBUG ENDPOINT
@app.get("/debug/{session_id}")
def debug_session(session_id: str):
    """Shows exact frames in storage for debugging"""
    frames = FRAME_STORE.get(session_id, [])
    
    # Count by view
    frame_views = {}
    for f in frames:
        view = f.get("camera_angle", "UNKNOWN")
        frame_views[view] = frame_views.get(view, 0) + 1
    
    # Count by metric in each view
    metrics_by_view = {}
    for f in frames:
        view = f.get("camera_angle")
        if view:
            data_keys = f.get("data", {}).keys()
            if view not in metrics_by_view:
                metrics_by_view[view] = {}
            for key in data_keys:
                metrics_by_view[view][key] = metrics_by_view[view].get(key, 0) + 1
    
    return {
        "session_id": session_id,
        "total_frames": len(frames),
        "frames_by_view": frame_views,
        "metrics_by_view": metrics_by_view,
        "sample_frame_0": frames[0] if frames else None,
        "sample_frame_3600": frames[3600] if len(frames) > 3600 else None,
        "sample_frame_last": frames[-1] if frames else None
    }