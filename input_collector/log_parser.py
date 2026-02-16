import json
from storage import FRAME_STORE
PREFIX = "📊 STR_JSON:"
def load_frames_from_raw_logs(session_id: str, file_path: str):
    FRAME_STORE[session_id] = []

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith(PREFIX):
                continue

            json_part = line.replace(PREFIX, "").strip()
            try:
                FRAME_STORE[session_id].append(json.loads(json_part))
            except json.JSONDecodeError:
                continue
    
    # 🔍 DEBUG: Log what was loaded
    print(f"\n📊 LOG PARSER DEBUG:")
    print(f"Session: {session_id}")
    print(f"Total frames loaded: {len(FRAME_STORE[session_id])}")
    
    frame_views = {}
    for frame in FRAME_STORE[session_id]:
        view = frame.get("camera_angle", "UNKNOWN")
        frame_views[view] = frame_views.get(view, 0) + 1
    print(f"Frames by view: {frame_views}")
    
    if FRAME_STORE[session_id]:
        print(f"First frame sample: {FRAME_STORE[session_id][0]}")
        print(f"Last frame sample: {FRAME_STORE[session_id][-1]}")
