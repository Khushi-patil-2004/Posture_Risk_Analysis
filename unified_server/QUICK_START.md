# Quick Start Guide: Continuous Frame Streaming

## Architecture Changes

### 1. **Separate Calibration Flags**
Each camera (front/side) now has its own `is_calibrated` flag:

**Old Schema:**
```json
{
  "session_id": 1,
  "frame_id": 100,
  "type": "front",
  "is_calibrated": true,  // Global flag
  "front": {
    "neck_bend_degree": {"value": 15.5, "confidence": 0.92}
  }
}
```

**New Schema:**
```json
{
  "session_id": 1,
  "frame_id": 100,
  "type": "front",
  "front": {
    "is_calibrated": true,  // Per-camera flag
    "neck_bend_degree": {"value": 15.5, "confidence": 0.92},
    "torso_tilt_degree": {"value": 8.2, "confidence": 0.88},
    "shoulder_slope_degree": {"value": -2.1, "confidence": 0.95}
  }
}
```

### 2. **Continuous Data Flow**
- **No manual phase switching**: Team 1 simulator auto-switches from front to side after 1 hour
- **No stop endpoint**: Session automatically completes after 2 hours
- **Realistic angle variations**: Uses random walk algorithm for smooth transitions

---

## Usage

### Option 1: Fully Automated (Recommended)

**Start the server:**
```bash
cd unified_server
uvicorn main:app --reload --port 8000
```

**In a separate terminal, run Team 1 simulator:**
```bash
python team1_service.py --auto --fps 15
```

This will:
1. ✅ Auto-login as `demo_user`
2. ✅ Create a new 2-hour session
3. ✅ Stream FRONT camera for 1 hour
4. ✅ Auto-switch to SIDE camera for 1 hour
5. ✅ Auto-trigger scoring & recommendations
6. ✅ Stop when session completes

---

### Option 2: Use Existing Session

If you already created a session:
```bash
python team1_service.py --session-id 1 --fps 15
```

---

### Option 3: Manual Testing (For Debugging)

Use the updated test client:
```bash
# 60-second test with auto phase switching (30s front + 30s side)
python test_frame_streaming.py --duration 60 --fps 15 --two-phase

# Single phase test
python test_frame_streaming.py --duration 30 --fps 20

# Check session status
python test_frame_streaming.py --session-id 1 --check-status

# Get results after completion
python test_frame_streaming.py --session-id 1 --get-results
```

---

## What to Expect

### Console Output (team1_service.py)

```
🔐 Logging in as demo_user...
✅ Login successful!

📝 Creating new 2-hour session...
✅ Session created! ID: 1
   Phase: front
   Expected end: 2026-02-19T13:48:30.123Z

================================================================================
🎬 STARTING CONTINUOUS STREAM
================================================================================
Session ID: 1
Target FPS: 15
Duration: 2 hours (1hr front + 1hr side)
================================================================================

Frame    10 | FRONT | FPS:  14.8 | Accumulated:    0.7s | Progress:   0.0%
Frame    20 | FRONT | FPS:  15.2 | Accumulated:    1.3s | Progress:   0.0%
Frame    30 | FRONT | FPS:  14.9 | Accumulated:    2.0s | Progress:   0.0%
...

[After 1 hour - automatic switch]

================================================================================
🔄 PHASE TRANSITION: FRONT → SIDE
================================================================================
Front phase duration: 3600.5s (53972 frames)
Switching to side camera view...
================================================================================

Frame 53980 | SIDE  | FPS:  15.1 | Accumulated: 3601.2s | Progress:  50.0%
Frame 53990 | SIDE  | FPS:  14.8 | Accumulated: 3601.9s | Progress:  50.0%
...

[After 2 hours - automatic completion]

================================================================================
🎉 SESSION COMPLETED!
================================================================================
Total frames sent: 107945
Total duration: 7200.1s
Detail: Session status is 'completed', cannot accept frames
================================================================================
```

---

## API Endpoints

### Check Session Status
```bash
curl -X GET "http://localhost:8000/sessions/1/status" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response:**
```json
{
  "session_id": 1,
  "status": "active",
  "current_phase": "side",
  "duration_sec": 4521.3,
  "total_frames": 67890,
  "accumulated_time_sec": 4500.2,
  "progress_percent": 62.5,
  "avg_fps": 15.1
}
```

### Get Scoring Results
```bash
curl -X GET "http://localhost:8000/results/1" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response:**
```json
{
  "results": {
    "neck_bend": {
      "risk_percent": 65.2,
      "status": "MODERATE",
      "distribution": {...}
    },
    "__OVERALL__": {
      "average_risk_percent": 52.3
    }
  }
}
```

---

## Monitoring

### Real-Time Status Updates

The simulator prints status every 10 frames and a summary every 30 seconds:

```
--- Status Update ---
Elapsed: 1830s | Sent: 27452 | Failed: 3 | Avg FPS: 15.0
Current phase: front (phase elapsed: 1830s)
---------------------
```

### Server Logs

Watch the server terminal for ingestion logs:
```
[16:52:15.234] 🌐 [API] POST /frames/ingest
   ├─ session_id: 1
   ├─ frame_id: 12345
   ├─ type: front
```

---

## Files Modified

1. **main.py**: Updated `IngestFrameRequest`, `FrontData`, `SideData` with separate calibration
2. **team1_service.py**: New standalone simulator with auto phase switching
3. **test_frame_streaming.py**: Updated to match new schema
4. **.env**: Added Team 1 configuration
5. **frame_processor.py**: Already compatible (extracts calibration from nested structure)

---

## Troubleshooting

### Error: "Session status is 'completed', cannot accept frames"
✅ **Expected behavior** - session auto-completed after 2 hours. Check results endpoint.

### Error: "Invalid or expired token"
Run `python team1_service.py --auto` to get a fresh session with new token.

### Frames being rejected: "Confidence too low"
Adjust `MIN_CONFIDENCE_PER_ANGLE` in `config.py` (default: 0.8).

### Phase not switching
Check the console output - phase switch happens exactly at 3600 seconds of elapsed time.

---

## Performance Notes

- **Target FPS**: 15 (configurable via `--fps` flag)
- **Actual FPS**: Varies 12-18 due to ±20% jitter for realism
- **Total Frames**: ~54,000 per hour = ~108,000 total
- **Database Size**: ~50-100 MB per 2-hour session (JSONB storage)
- **Memory Usage**: ~200-300 MB for server process

---

**Ready to test!** 🚀
