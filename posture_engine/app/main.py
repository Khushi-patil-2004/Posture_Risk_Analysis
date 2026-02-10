from fastapi import FastAPI, HTTPException
import requests
from app.scoring import process_session
INPUT_COLLECTOR_BASE = "http://127.0.0.1:8001"
app = FastAPI(title="Posture Scoring Engine")
RESULT_STORE = {}


# 🔁 AUTO PROCESS ALL SESSIONS
@app.on_event("startup")
def auto_process_all_sessions():
    try:
        print("🔄 Fetching available sessions from input_collector...")

        resp = requests.get(f"{INPUT_COLLECTOR_BASE}/sessions", timeout=5)
        session_ids = resp.json().get("sessions", [])

        if not session_ids:
            print("⚠️ No sessions found")
            return

        for session_id in session_ids:
            print(f"📊 Processing session: {session_id}")

            input_resp = requests.get(
                f"{INPUT_COLLECTOR_BASE}/input/{session_id}", timeout=5
            )

            frames = input_resp.json().get("frames", [])
            if not frames:
                print(f"⚠️ No frames for {session_id}")
                continue

            results = process_session(frames)
            RESULT_STORE[session_id] = results

            print(f"✅ Completed: {session_id}")
            print(f"🔗 Result API → http://127.0.0.1:8000/result/{session_id}")

    except Exception as e:
        print("❌ Startup error:", str(e))


# 🔓 FINAL RESULT API (SHARE THIS)
@app.get("/result/{session_id}")
def get_result(session_id: str):
    if session_id not in RESULT_STORE:
        raise HTTPException(status_code=404, detail="Result not ready")

    return {
        "session_id": session_id,
        "results": RESULT_STORE[session_id]
    }

