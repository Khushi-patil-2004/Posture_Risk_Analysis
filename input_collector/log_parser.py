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
