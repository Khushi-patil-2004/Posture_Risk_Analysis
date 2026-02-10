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
                    "good": (0, 10),                                                                              
                    "warning": (11, 30),
                    "bad": (31, 180)
                }
            },
            "shoulder_slope_degree": {
                "ranges": {
                    "good": (0, 5),
                    "warning": (6, 15),
                    "bad": (16, 180)
                }
            },
            "torso_tilt_degree": {
                "ranges": {
                    "good": (0, 5),
                    "warning": (6, 15),
                    "bad": (16, 180)
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
                    "warning": (11, 25),
                    "bad": (26, 180)
                }
            },
            "head_forward_index": {   # percentage
                "ranges": {
                    "good": (0, 2),
                    "warning": (3, 5),
                    "bad": (6, 100)
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

