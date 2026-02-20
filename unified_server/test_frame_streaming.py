"""
Test Frame Streaming Client

Simulates Team 1 sending streaming frames to POST /frames/ingest

Usage:
    python test_frame_streaming.py --session-id 1 --duration 60 --fps 15
"""

import requests
import time
import random
import argparse
from datetime import datetime, timezone
import json

# API Configuration
BASE_URL = "http://localhost:8000"
USERNAME = "demo_user"
PASSWORD = "test123"

def login():
    """Authenticate and get JWT token"""
    print(f"\n🔐 Logging in as {USERNAME}...")
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    )
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        print(f"✅ Login successful! Token: {token[:20]}...")
        return token
    else:
        print(f"❌ Login failed: {response.status_code} - {response.text}")
        return None


def create_session(token):
    """Create a new session"""
    print(f"\n📝 Creating new session...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        f"{BASE_URL}/sessions/start",
        json={"duration_seconds": 7200},
        headers=headers
    )
    
    if response.status_code == 200:
        session_data = response.json()
        session_id = session_data["session_id"]
        print(f"✅ Session created! ID: {session_id}")
        print(f"   Current phase: {session_data['current_phase']}")
        print(f"   Expected end: {session_data['expected_end_time']}")
        return session_id
    else:
        print(f"❌ Session creation failed: {response.status_code} - {response.text}")
        return None


def generate_random_angle_data(camera_angle):
    """
    Generate random angle data for a frame
    
    Returns nested structure: {front: {...}} or {side: {...}}
    """
    # Generate calibration status (95% calibrated)
    is_calibrated = random.random() < 0.95
    
    if camera_angle == "front":
        return {
            "front": {
                "is_calibrated": is_calibrated,
                "neck_bend_degree": {
                    "value": random.uniform(10.0, 30.0),
                    "confidence": random.uniform(0.85, 0.99)
                },
                "shoulder_slope_degree": {
                    "value": random.uniform(-5.0, 15.0),
                    "confidence": random.uniform(0.85, 0.99)
                },
                "torso_tilt_degree": {
                    "value": random.uniform(-10.0, 20.0),
                    "confidence": random.uniform(0.85, 0.99)
                }
            }
        }
    else:  # side
        return {
            "side": {
                "is_calibrated": is_calibrated,
                "neck_bend_degree": {
                    "value": random.uniform(5.0, 25.0),
                    "confidence": random.uniform(0.85, 0.99)
                },
                "head_forward_index": {
                    "value": random.uniform(0.5, 3.0),
                    "confidence": random.uniform(0.85, 0.99)
                }
            }
        }


def send_frame(token, session_id, frame_count, camera_angle):
    """Send a single frame to the API"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # Generate frame data
    angle_data = generate_random_angle_data(camera_angle)
    
    frame_payload = {
        "session_id": session_id,
        "frame_id": frame_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": camera_angle,
        **angle_data  # Unpack front or side data (includes is_calibrated now)
    }
    
    response = requests.post(
        f"{BASE_URL}/frames/ingest",
        json=frame_payload,
        headers=headers
    )
    
    return response


def stream_frames(token, session_id, duration_seconds, target_fps, phase_duration=None):
    """
    Stream frames to the API
    
    Args:
        token: JWT authentication token
        session_id: Session ID
        duration_seconds: Total duration to stream
        target_fps: Target frames per second
        phase_duration: Duration per phase (None = use full duration for one phase)
    """
    print(f"\n🎬 Starting frame streaming...")
    print(f"   Session ID: {session_id}")
    print(f"   Duration: {duration_seconds}s")
    print(f"   Target FPS: {target_fps}")
    
    frame_count = 0
    start_time = time.time()
    phase_start_time = start_time
    current_phase = "front"
    
    # Calculate target frame interval with jitter
    base_interval = 1.0 / target_fps
    
    while True:
        elapsed = time.time() - start_time
        
        # Check if duration is complete
        if elapsed >= duration_seconds:
            print(f"\n✅ Streaming complete! Total frames sent: {frame_count}")
            break
        
        # Handle phase transitions (if phase_duration is set)
        if phase_duration:
            phase_elapsed = time.time() - phase_start_time
            if phase_elapsed >= phase_duration:
                # Switch phase
                if current_phase == "front":
                    current_phase = "side"
                    phase_start_time = time.time()
                    print(f"\n🔄 Switching to SIDE phase")
        
        # Send frame
        frame_count += 1
        response = send_frame(token, session_id, frame_count, current_phase)
        
        if response.status_code == 200:
            result = response.json()
            if frame_count % 10 == 0:  # Print every 10th frame
                print(f"   Frame {frame_count:4d} | {current_phase.upper():5s} | "
                      f"FPS: {result.get('current_fps', 0):5.1f} | "
                      f"Valid: {result.get('valid_metrics_count', 0)} | "
                      f"Accumulated: {result.get('total_accumulated_time', 0):6.1f}s")
        elif response.status_code == 400:
            error = response.json()
            if "session complete" in error.get("detail", "").lower():
                print(f"\n🎉 Session auto-completed! Scoring triggered.")
                break
            else:
                print(f"\n⚠️  Frame {frame_count} rejected: {error.get('detail')}")
        else:
            print(f"\n❌ Frame {frame_count} failed: {response.status_code} - {response.text}")
        
        # Variable FPS: Add jitter (±20%)
        jitter = random.uniform(0.8, 1.2)
        interval = base_interval * jitter
        time.sleep(interval)
    
    return frame_count


def get_session_status(token, session_id):
    """Get current session status"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/sessions/{session_id}/status",
        headers=headers
    )
    
    if response.status_code == 200:
        status = response.json()
        print(f"\n📊 Session Status:")
        print(f"   Status: {status['status']}")
        print(f"   Current phase: {status.get('current_phase', 'N/A')}")
        print(f"   Total frames: {status['total_frames']}")
        print(f"   Accumulated time: {status.get('accumulated_time_sec', 0):.1f}s")
        print(f"   Progress: {status.get('progress_percent', 0):.1f}%")
        print(f"   Average FPS: {status.get('avg_fps', 0):.2f}")
        return status
    else:
        print(f"❌ Status fetch failed: {response.status_code}")
        return None


def get_results(token, session_id):
    """Get scoring results if available"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/results/{session_id}",
        headers=headers
    )
    
    if response.status_code == 200:
        results = response.json()
        print(f"\n📈 Scoring Results:")
        for metric, data in results.get("results", {}).items():
            if metric != "__OVERALL__":
                print(f"   {metric}: {data.get('risk_percent', 0):.1f}% risk ({data.get('status', 'N/A')})")
        
        overall = results.get("results", {}).get("__OVERALL__")
        if overall:
            print(f"\n   Overall Average: {overall.get('average_risk_percent', 0):.1f}%")
        
        return results
    elif response.status_code == 404:
        print(f"\n⚠️  No results yet (scoring not triggered)")
        return None
    else:
        print(f"❌ Results fetch failed: {response.status_code}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Test frame streaming client")
    parser.add_argument("--session-id", type=int, help="Use existing session ID")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds (default: 60)")
    parser.add_argument("--fps", type=int, default=15, help="Target FPS (default: 15)")
    parser.add_argument("--two-phase", action="store_true", help="Enable two-phase mode (front + side)")
    parser.add_argument("--check-status", action="store_true", help="Only check session status")
    parser.add_argument("--get-results", action="store_true", help="Only get results")
    
    args = parser.parse_args()
    
    # Login
    token = login()
    if not token:
        return
    
    # Use existing session or create new
    if args.session_id:
        session_id = args.session_id
        print(f"\n📎 Using existing session ID: {session_id}")
    else:
        session_id = create_session(token)
        if not session_id:
            return
    
    # Check status only
    if args.check_status:
        get_session_status(token, session_id)
        return
    
    # Get results only
    if args.get_results:
        get_results(token, session_id)
        return
    
    # Calculate phase duration if two-phase mode
    phase_duration = args.duration / 2 if args.two_phase else None
    
    # Stream frames
    frame_count = stream_frames(
        token=token,
        session_id=session_id,
        duration_seconds=args.duration,
        target_fps=args.fps,
        phase_duration=phase_duration
    )
    
    # Show final status
    print("\n" + "="*80)
    get_session_status(token, session_id)
    
    # Try to get results
    get_results(token, session_id)
    
    print("\n" + "="*80)
    print("✅ Test complete!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
