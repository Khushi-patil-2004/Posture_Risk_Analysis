# Manual Scoring Endpoint Guide

## Overview
The manual scoring endpoint allows you to trigger scoring and recommendation generation for any session **without waiting for the full 2-hour duration**. This is useful for testing and development.

## Endpoint

```
POST /sessions/{session_id}/score-now
```

**Authentication**: Bearer token required

## What It Does

1. ✅ Verifies the session exists
2. ✅ Scores all accumulated angle data (even if < 2 hours)
3. ✅ Generates AI-powered recommendations
4. ✅ Updates session status to "completed"
5. ✅ Stores results in database

## Usage Examples

### PowerShell
```powershell
# Get token
$token = (Invoke-RestMethod -Uri "http://localhost:8000/auth/login" -Method POST -Body (@{username="demo_user"; password="test123"} | ConvertTo-Json) -ContentType "application/json").token

# Create headers
$headers = @{Authorization="Bearer $token"}

# Trigger scoring
$response = Invoke-RestMethod -Uri "http://localhost:8000/sessions/2/score-now" -Method POST -Headers $headers

# View response
$response | ConvertTo-Json
```

### Python
```python
import requests

# Login
login_response = requests.post(
    "http://localhost:8000/auth/login",
    json={"username": "demo_user", "password": "test123"}
)
token = login_response.json()["token"]
headers = {"Authorization": f"Bearer {token}"}

# Trigger scoring
score_response = requests.post(
    "http://localhost:8000/sessions/2/score-now",
    headers=headers
)

print(score_response.json())
```

### cURL
```bash
# Login and get token
TOKEN=$(curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"demo_user","password":"test123"}' \
  | jq -r '.token')

# Trigger scoring
curl -X POST "http://localhost:8000/sessions/2/score-now" \
  -H "Authorization: Bearer $TOKEN"
```

## Response Format

### Success (200 OK)
```json
{
  "success": true,
  "session_id": 2,
  "metrics_scored": 3,
  "message": "Scoring and recommendations generated successfully"
}
```

### Errors

**Session Not Found (404)**
```json
{
  "detail": "Session not found"
}
```

**No Angle Data (400)**
```json
{
  "detail": "Scoring failed - no angle data accumulated for this session"
}
```

**Server Error (500)**
```json
{
  "detail": "Scoring failed: [error message]"
}
```

## After Scoring

Once scoring completes, you can retrieve:

### 1. Results
```
GET /results/{session_id}
```

Example response:
```json
{
  "session_id": 2,
  "total_metrics": 9,
  "results": [
    {
      "metric_name": "FRONT_neck_bend",
      "risk_percent": 70,
      "status": "High risk",
      "time_good_min": 0.0,
      "time_warning_min": 2.24,
      "time_bad_min": 0.0
    }
  ]
}
```

### 2. Recommendations
```
GET /recommendations/{session_id}
```

Example response:
```json
{
  "session_id": 2,
  "recommendation_text": "Your dominant issue is FRONT_neck_bend...",
  "priority": "HIGH",
  "dominant_issue": "FRONT_neck_bend",
  "risk_level": "HIGH",
  "actions": [
    "Perform exercises to strengthen your neck...",
    "Maintain good posture while sitting...",
    "Engage in activities that promote good posture awareness..."
  ]
}
```

## Testing Workflow

Complete testing workflow:

```powershell
# 1. Start server (Terminal 1)
cd unified_server
uvicorn main:app --reload --port 8000

# 2. Run simulator (Terminal 2) - Optional: create test data
python team1_service.py --auto --fps 15

# 3. After a few seconds, stop simulator (Ctrl+C)

# 4. Trigger manual scoring
python test_manual_scoring.py

# Or use PowerShell directly:
$token = (Invoke-RestMethod -Uri "http://localhost:8000/auth/login" -Method POST -Body (@{username="demo_user"; password="test123"} | ConvertTo-Json) -ContentType "application/json").token
$headers = @{Authorization="Bearer $token"}

# Check session status
Invoke-RestMethod -Uri "http://localhost:8000/sessions/2/status" -Headers $headers | ConvertTo-Json

# Trigger scoring
Invoke-RestMethod -Uri "http://localhost:8000/sessions/2/score-now" -Method POST -Headers $headers | ConvertTo-Json

# Get results
Invoke-RestMethod -Uri "http://localhost:8000/results/2" -Headers $headers | ConvertTo-Json

# Get recommendations
Invoke-RestMethod -Uri "http://localhost:8000/recommendations/2" -Headers $headers | ConvertTo-Json
```

## Notes

- ⚠️ Can be called multiple times (will recalculate scores)
- ⚠️ Session must have at least some accumulated angle data
- ⚠️ Session status changes to "completed" after scoring
- ✅ Useful for development/testing without waiting 2 hours
- ✅ Works with any amount of accumulated data
