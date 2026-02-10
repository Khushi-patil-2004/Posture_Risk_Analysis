from fastapi import FastAPI
import uuid
from storage import FRAME_STORE
from log_parser import load_frames_from_raw_logs

DATA_FILE = "data/flutter_raw_logs.jsonl"
BASE_URL = "http://127.0.0.1:8001"

app = FastAPI(title="Input Collector API")

# ✅ TRACK CREATED SESSIONS
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
