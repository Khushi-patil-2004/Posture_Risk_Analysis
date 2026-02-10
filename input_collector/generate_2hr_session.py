import json
import time
import random

OUTPUT_FILE = "flutter_raw_logs.jsonl"
START_TIMESTAMP = int(time.time() * 1000)

def write_frame(frame):
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write("📊 STR_JSON: " + json.dumps(frame) + "\n")


def generate_front_frames():
    for i in range(3600):
        if i < 2100:      # GOOD
            neck = random.uniform(0, 8)
            shoulder = random.uniform(0, 4)
            torso = random.uniform(0, 4)
        elif i < 3000:    # WARNING
            neck = random.uniform(10, 18)
            shoulder = random.uniform(6, 12)
            torso = random.uniform(6, 12)
        else:             # BAD
            neck = random.uniform(25, 45)
            shoulder = random.uniform(18, 30)
            torso = random.uniform(18, 30)

        frame = {
            "scan_id": f"frame_front_{i}",
            "camera_angle": "FRONT",
            "is_calibrated": False,
            "data": {
                "neck_bend_degree": round(neck, 2),
                "neck_confidence": 1.0,
                "shoulder_slope_degree": round(shoulder, 2),
                "shoulder_confidence": 0.99,
                "torso_tilt_degree": round(torso, 2),
                "torso_confidence": 0.99
            }
        }

        write_frame(frame)


def generate_side_frames():
    for i in range(3600):
        if i < 1800:      # GOOD
            hfi = random.uniform(0, 0.9)
        elif i < 2800:    # WARNING
            hfi = random.uniform(1.2, 2.8)
        else:             # BAD
            hfi = random.uniform(4, 7)

        frame = {
            "scan_id": f"frame_side_{i}",
            "camera_angle": "SIDE",
            "is_calibrated": False,
            "data": {
                "head_forward_index": round(hfi, 2),
                "head_forward_index_confidence": 0.99
            }
        }

        write_frame(frame)


# ---------- RUN ----------
open(OUTPUT_FILE, "w").close()  # clear file
generate_front_frames()
generate_side_frames()

print("✅ 2-hour session generated:", OUTPUT_FILE)
