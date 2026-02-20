"""
Team 1 Auto-Simulator Service

Simulates Team 1's continuous streaming API
- Auto-switches from front to side after 1 hour
- Variable FPS (10-20 with jitter)
- Realistic angle variations using random walk
- Runs until 2 hours complete or session ends

Usage:
    python team1_service.py --session-id 1
    python team1_service.py --auto  (creates session automatically)
"""

import requests
import time
import random
import argparse
import sys
from datetime import datetime, timezone
from typing import Dict, Tuple

# API Configuration
BASE_URL = "http://localhost:8000"
USERNAME = "demo_user"
PASSWORD = "test123"

# Posture angle ranges (realistic values)
ANGLE_RANGES = {
    "front": {
        "neck_bend": (10.0, 30.0),          # Forward neck bend
        "torso_tilt": (-5.0, 15.0),         # Torso lean
        "shoulder_slope": (-10.0, 10.0)     # Shoulder imbalance
    },
    "side": {
        "neck_bend": (5.0, 25.0),           # Neck tilt from side
        "head_forward": (0.5, 3.0)          # Head forward distance ratio
    }
}

# Random walk configuration
ANGLE_CHANGE_MAX = 2.0  # Max degrees change per frame
CALIBRATION_THRESHOLD = 0.95  # 95% frames are calibrated


class AngleTracker:
    """Tracks current angle values with random walk"""
    
    def __init__(self, camera_type: str):
        self.camera_type = camera_type
        self.ranges = ANGLE_RANGES[camera_type]
        
        # Initialize at mid-point of each range
        self.current = {}
        for metric, (min_val, max_val) in self.ranges.items():
            self.current[metric] = (min_val + max_val) / 2
    
    def next_values(self) -> Dict[str, float]:
        """Generate next set of angles using random walk"""
        new_values = {}
        
        for metric, (min_val, max_val) in self.ranges.items():
            # Random walk: current ± random delta
            delta = random.uniform(-ANGLE_CHANGE_MAX, ANGLE_CHANGE_MAX)
            new_value = self.current[metric] + delta
            
            # Clamp to realistic range
            new_value = max(min_val, min(max_val, new_value))
            
            self.current[metric] = new_value
            new_values[metric] = new_value
        
        return new_values


def login() -> str:
    """Authenticate and get JWT token"""
    print(f"\n🔐 Logging in as {USERNAME}...")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": USERNAME, "password": PASSWORD},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            # API returns 'token' not 'access_token'
            token = data.get("token") or data.get("access_token")
            if token:
                print(f"✅ Login successful!")
                return token
            else:
                print(f"❌ Login failed: Response missing token")
                print(f"    Response: {data}")
                sys.exit(1)
        else:
            print(f"❌ Login failed: {response.status_code}")
            print(f"    Response: {response.text[:200]}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Login error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def create_session(token: str) -> int:
    """Create a new 2-hour session"""
    print(f"\n📝 Creating new 2-hour session...")
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.post(
            f"{BASE_URL}/sessions/start",
            json={"duration_seconds": 7200},
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            session_data = response.json()
            session_id = session_data["session_id"]
            print(f"✅ Session created! ID: {session_id}")
            print(f"   Phase: {session_data['current_phase']}")
            print(f"   Expected end: {session_data['expected_end_time']}")
            return session_id
        else:
            print(f"❌ Session creation failed: {response.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Session creation error: {e}")
        sys.exit(1)


def generate_frame_payload(
    session_id: int,
    frame_count: int,
    camera_type: str,
    angle_tracker: AngleTracker,
    is_calibrated: bool = True
) -> dict:
    """Generate realistic frame payload"""
    
    angles = angle_tracker.next_values()
    
    # Generate high confidence values (0.85-0.99)
    confidence_base = random.uniform(0.85, 0.99)
    
    payload = {
        "session_id": session_id,
        "frame_id": frame_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": camera_type
    }
    
    if camera_type == "front":
        payload["front"] = {
            "is_calibrated": is_calibrated,
            "neck_bend_degree": {
                "value": round(angles["neck_bend"], 2),
                "confidence": round(confidence_base + random.uniform(-0.05, 0.05), 3)
            },
            "torso_tilt_degree": {
                "value": round(angles["torso_tilt"], 2),
                "confidence": round(confidence_base + random.uniform(-0.05, 0.05), 3)
            },
            "shoulder_slope_degree": {
                "value": round(angles["shoulder_slope"], 2),
                "confidence": round(confidence_base + random.uniform(-0.05, 0.05), 3)
            }
        }
    else:  # side
        payload["side"] = {
            "is_calibrated": is_calibrated,
            "neck_bend_degree": {
                "value": round(angles["neck_bend"], 2),
                "confidence": round(confidence_base + random.uniform(-0.05, 0.05), 3)
            },
            "head_forward_index": {
                "value": round(angles["head_forward"], 3),
                "confidence": round(confidence_base + random.uniform(-0.05, 0.05), 3)
            }
        }
    
    return payload


def send_frame(token: str, payload: dict) -> Tuple[bool, dict]:
    """Send frame to Team 2 API"""
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.post(
            f"{BASE_URL}/frames/ingest",
            json=payload,
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            return True, response.json()
        elif response.status_code == 400:
            error = response.json()
            # Check if session completed
            if "session complete" in error.get("detail", "").lower() or \
               "cannot accept frames" in error.get("detail", "").lower():
                return False, {"completed": True, "detail": error.get("detail")}
            return False, error
        else:
            return False, {"error": response.status_code, "detail": response.text[:100]}
            
    except requests.exceptions.Timeout:
        return False, {"error": "timeout"}
    except Exception as e:
        return False, {"error": str(e)}


def run_continuous_stream(token: str, session_id: int, target_fps: int = 15):
    """
    Run continuous frame streaming with auto phase switching
    
    - First hour: front camera
    - Second hour: side camera
    - Auto-switches without manual intervention
    """
    print(f"\n{'='*80}")
    print(f"🎬 STARTING CONTINUOUS STREAM")
    print(f"{'='*80}")
    print(f"Session ID: {session_id}")
    print(f"Target FPS: {target_fps}")
    print(f"Duration: 2 hours (1hr front + 1hr side)")
    print(f"{'='*80}\n")
    
    # Initialize angle trackers for both cameras
    front_tracker = AngleTracker("front")
    side_tracker = AngleTracker("side")
    
    frame_count = 0
    start_time = time.time()
    phase_start_time = start_time
    current_phase = "front"
    current_tracker = front_tracker
    
    # Phase duration: 1 hour = 3600 seconds
    PHASE_DURATION = 3600
    
    # Calculate base frame interval
    base_interval = 1.0 / target_fps
    
    # Statistics
    total_sent = 0
    total_failed = 0
    last_status_time = start_time
    
    try:
        while True:
            loop_start = time.time()
            
            # Check if phase should switch
            phase_elapsed = time.time() - phase_start_time
            if phase_elapsed >= PHASE_DURATION and current_phase == "front":
                # Switch to side phase
                print(f"\n{'='*80}")
                print(f"🔄 PHASE TRANSITION: FRONT → SIDE")
                print(f"{'='*80}")
                print(f"Front phase duration: {phase_elapsed:.1f}s ({total_sent} frames)")
                print(f"Switching to side camera view...")
                print(f"{'='*80}\n")
                
                current_phase = "side"
                current_tracker = side_tracker
                phase_start_time = time.time()
            
            # Generate calibration status (95% calibrated)
            is_calibrated = random.random() < CALIBRATION_THRESHOLD
            
            # Generate and send frame
            frame_count += 1
            payload = generate_frame_payload(
                session_id=session_id,
                frame_count=frame_count,
                camera_type=current_phase,
                angle_tracker=current_tracker,
                is_calibrated=is_calibrated
            )
            
            success, result = send_frame(token, payload)
            
            if success:
                total_sent += 1
                
                # Print status every 10th frame
                if frame_count % 10 == 0:
                    fps = result.get('fps', 0)
                    accumulated = result.get('total_accumulated_time', 0)
                    progress = (accumulated / 7200) * 100 if accumulated else 0
                    
                    print(f"Frame {frame_count:5d} | "
                          f"{current_phase.upper():5s} | "
                          f"FPS: {fps:5.1f} | "
                          f"Accumulated: {accumulated:7.1f}s | "
                          f"Progress: {progress:5.1f}%")
            else:
                total_failed += 1
                
                # Check if session completed
                if result.get('completed'):
                    print(f"\n{'='*80}")
                    print(f"🎉 SESSION COMPLETED!")
                    print(f"{'='*80}")
                    print(f"Total frames sent: {total_sent}")
                    print(f"Total duration: {time.time() - start_time:.1f}s")
                    print(f"Detail: {result.get('detail')}")
                    print(f"{'='*80}\n")
                    break
                else:
                    # Log error - show first 10 errors for debugging
                    if total_failed <= 10:
                        print(f"❌ Frame {frame_count} FAILED: {result}")
                        if total_failed == 10:
                            print(f"... (suppressing further error messages) ...")
            
            # Print periodic summary
            if time.time() - last_status_time >= 30:  # Every 30 seconds
                elapsed = time.time() - start_time
                actual_fps = total_sent / elapsed if elapsed > 0 else 0
                print(f"\n--- Status Update ---")
                print(f"Elapsed: {elapsed:.0f}s | Sent: {total_sent} | Failed: {total_failed} | Avg FPS: {actual_fps:.1f}")
                print(f"Current phase: {current_phase} (phase elapsed: {phase_elapsed:.0f}s)")
                print(f"---------------------\n")
                last_status_time = time.time()
            
            # Variable FPS: Add jitter (±20%)
            jitter = random.uniform(0.8, 1.2)
            interval = base_interval * jitter
            
            # Sleep for remaining time to maintain FPS
            loop_duration = time.time() - loop_start
            sleep_time = max(0, interval - loop_duration)
            
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    except KeyboardInterrupt:
        print(f"\n\n⚠️  Stream interrupted by user")
        print(f"Total frames sent: {total_sent}")
        print(f"Total duration: {time.time() - start_time:.1f}s")
    except Exception as e:
        print(f"\n\n❌ Stream error: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{'='*80}")
    print(f"Stream ended")
    print(f"{'='*80}\n")
    
    return total_sent


def main():
    parser = argparse.ArgumentParser(description="Team 1 Auto-Simulator Service")
    parser.add_argument("--session-id", type=int, help="Use existing session ID")
    parser.add_argument("--auto", action="store_true", help="Auto-create session")
    parser.add_argument("--fps", type=int, default=15, help="Target FPS (default: 15)")
    
    args = parser.parse_args()
    
    # Login
    token = login()
    
    # Get session ID
    if args.session_id:
        session_id = args.session_id
        print(f"\n📎 Using existing session ID: {session_id}")
    elif args.auto:
        session_id = create_session(token)
    else:
        print("\n❌ Error: Must specify --session-id or --auto")
        print("Usage:")
        print("  python team1_service.py --auto")
        print("  python team1_service.py --session-id 1")
        sys.exit(1)
    
    # Run continuous stream
    total_frames = run_continuous_stream(token, session_id, args.fps)
    
    print(f"\n✅ Service completed!")
    print(f"Total frames sent: {total_frames}\n")


if __name__ == "__main__":
    main()
