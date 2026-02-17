# All tunable posture thresholds
# app/config.py
FPS = 1
CONFIDENCE_THRESHOLD = 0.8
SESSION_CONFIG = {
    "FRONT": {
        "duration_min": 60,
        "metrics": {
            "neck_bend_degree": {
                "ranges": {
                    "good": (0, 10),        # <10
                    "warning": (10, 20),    # 10–20
                    "bad": (20, 180)        # >=20
                }
            },
            "shoulder_slope_degree": {
                "ranges": {
                    "good": (0, 5),         # <5
                    "warning": (5, 10),     # 5–10
                    "bad": (10, 180)        # >=10
                }
            },
            "torso_tilt_percent": {        # changed to percent (as per image)
                "ranges": {
                    "good": (0, 10),        # <10%
                    "warning": (10, 20),    # 10–20%
                    "bad": (20, 100)        # >=20%
                }
            }
        }
    },

    "SIDE": {
        "duration_min": 60,
        "metrics": {
            "neck_bend_degree": {
                "ranges": {
                    "good": (0, 10),
                    "warning": (10, 20),
                    "bad": (20, 180)
                }
            },
            "head_forward_index": {   # ratio (relative to shoulder width)
                "ranges": {
                    "good": (0.0, 0.15),     # <0.15
                    "warning": (0.15, 0.25), # 0.15–0.25
                    "bad": (0.25, 1.0)       # >=0.25
                }
            }
        }
    }
}

SCORE_BANDS = {
    "good": (0, 30),
    "warning": (30, 70),
    "bad": (70, 100)
}

