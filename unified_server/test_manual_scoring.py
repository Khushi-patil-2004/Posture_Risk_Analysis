"""
Test script for manual scoring endpoint
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_manual_scoring():
    print("🧪 Testing Manual Scoring Endpoint\n")
    
    # Step 1: Login
    print("1️⃣ Logging in...")
    login_response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": "demo_user", "password": "test123"}
    )
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.text}")
        return
    
    token = login_response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"✅ Logged in successfully\n")
    
    # Step 2: Check if session 2 exists
    print("2️⃣ Checking session 2 status...")
    status_response = requests.get(
        f"{BASE_URL}/sessions/2/status",
        headers=headers
    )
    
    if status_response.status_code == 404:
        print("❌ Session 2 not found. Please create a session first.")
        return
    
    status_data = status_response.json()
    print(f"✅ Session 2 found:")
    print(f"   - Status: {status_data['status']}")
    print(f"   - Total Frames: {status_data['total_frames']}")
    print(f"   - Accumulated Time: {status_data['accumulated_time_sec']} seconds")
    print(f"   - Progress: {status_data['progress_percent']}%\n")
    
    # Step 3: Trigger manual scoring
    print("3️⃣ Triggering manual scoring...")
    score_response = requests.post(
        f"{BASE_URL}/sessions/2/score-now",
        headers=headers
    )
    
    if score_response.status_code != 200:
        print(f"❌ Scoring failed: {score_response.text}")
        return
    
    score_data = score_response.json()
    print(f"✅ Scoring completed:")
    print(f"   - Success: {score_data['success']}")
    print(f"   - Metrics Scored: {score_data['metrics_scored']}")
    print(f"   - Message: {score_data['message']}\n")
    
    # Step 4: Get results
    print("4️⃣ Fetching results...")
    results_response = requests.get(
        f"{BASE_URL}/results/2",
        headers=headers
    )
    
    if results_response.status_code != 200:
        print(f"❌ Results fetch failed: {results_response.text}")
        return
    
    results_data = results_response.json()
    print(f"✅ Results retrieved:")
    print(f"   - Total Metrics: {results_data['total_metrics']}")
    print(f"   - Sample Metrics:")
    for i, metric in enumerate(results_data['results'][:3]):
        print(f"      {i+1}. {metric['metric_name']}: {metric['risk_percentage']:.1f}%")
    print()
    
    # Step 5: Get recommendations
    print("5️⃣ Fetching recommendations...")
    rec_response = requests.get(
        f"{BASE_URL}/recommendations/2",
        headers=headers
    )
    
    if rec_response.status_code != 200:
        print(f"❌ Recommendations fetch failed: {rec_response.text}")
        return
    
    rec_data = rec_response.json()
    print(f"✅ Recommendations retrieved:")
    print(f"   - Total: {rec_data['total_items']}")
    print(f"   - Sample:")
    for i, item in enumerate(rec_data['items'][:2]):
        print(f"      {i+1}. [{item['phase']}] {item['recommendation'][:80]}...")
    
    print("\n🎉 All tests passed!")

if __name__ == "__main__":
    try:
        test_manual_scoring()
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure it's running on port 8000")
    except Exception as e:
        print(f"❌ Error: {e}")
