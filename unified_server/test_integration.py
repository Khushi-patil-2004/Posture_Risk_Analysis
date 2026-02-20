"""
Quick Test Script for Unified Posture Analysis Server

This script tests the complete lifecycle:
1. Register/Login
2. Start Session
3. Wait for simulation
4. Stop session (triggers scoring + AI)
5. Fetch results and recommendations
"""

import requests
import time
import json

BASE_URL = "http://localhost:8000"

def print_section(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


def test_health():
    """Test health check"""
    print_section("1. HEALTH CHECK")
    
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    
    return response.status_code == 200


def test_login():
    """Test login with demo user"""
    print_section("2. LOGIN")
    
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={
            "username": "demo_user",
            "password": "test123"
        }
    )
    
    print(f"Status: {response.status_code}")
    data = response.json()
    print(json.dumps(data, indent=2))
    
    if response.status_code == 200:
        token = data.get("token")
        user_id = data.get("user", {}).get("id")
        print(f"\n✅ Token obtained: {token[:50]}...")
        return token, user_id
    else:
        print("\n❌ Login failed!")
        return None, None


def test_start_session(token):
    """Start a new session"""
    print_section("3. START SESSION")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        f"{BASE_URL}/sessions/start",
        headers=headers,
        json={"duration_seconds": 30}
    )
    
    print(f"Status: {response.status_code}")
    data = response.json()
    print(json.dumps(data, indent=2))
    
    if response.status_code == 200:
        session_id = data.get("session_id")
        print(f"\n✅ Session started: {session_id}")
        return session_id
    else:
        print("\n❌ Session start failed!")
        return None


def test_session_status(token, session_id):
    """Check session status"""
    print_section("4. SESSION STATUS")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/sessions/{session_id}/status",
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))


def test_stop_session(token, session_id):
    """Stop session and trigger analysis"""
    print_section("5. STOP SESSION & ANALYZE")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        f"{BASE_URL}/sessions/{session_id}/stop",
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    
    return response.status_code == 200


def test_get_results(token, session_id):
    """Get scoring results"""
    print_section("6. GET RESULTS")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/results/{session_id}",
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    data = response.json()
    
    if response.status_code == 200:
        print(f"\nTotal Metrics: {data.get('total_metrics')}")
        print("\nMetrics:")
        for result in data.get('results', []):
            print(f"  - {result.get('metric_name')}: {result.get('risk_percent')}% ({result.get('status')})")
    else:
        print(json.dumps(data, indent=2))


def test_get_recommendation(token, session_id):
    """Get AI recommendation"""
    print_section("7. GET RECOMMENDATION")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/recommendations/{session_id}",
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    data = response.json()
    
    if response.status_code == 200:
        print(f"\nPriority: {data.get('priority')}")
        print(f"Risk Level: {data.get('risk_level')}")
        print(f"Dominant Issue: {data.get('dominant_issue')}")
        print(f"\nRecommendation: {data.get('recommendation_text')}")
        print(f"\nActions:")
        for action in data.get('actions', []):
            print(f"  - {action}")
    else:
        print(json.dumps(data, indent=2))


def main():
    """Run complete test"""
    print("\n" + "🔬"*40)
    print("UNIFIED POSTURE ANALYSIS SERVER - INTEGRATION TEST")
    print("🔬"*40)
    
    # Test 1: Health Check
    if not test_health():
        print("\n❌ Server not healthy! Exiting.")
        return
    
    # Test 2: Login
    token, user_id = test_login()
    if not token:
        print("\n❌ Cannot proceed without token. Make sure demo_user exists.")
        print("Run: python setup.py")
        return
    
    # Test 3: Start Session
    session_id = test_start_session(token)
    if not session_id:
        return
    
    # Test 4: Monitor Status
    print("\n⏳ Waiting 5 seconds to see initial frames...")
    time.sleep(5)
    test_session_status(token, session_id)
    
    # Test 5: Wait for simulation to complete
    print("\n⏳ Waiting 27 more seconds for simulation to complete...")
    print("   (Watch the server terminal for real-time logs!)")
    time.sleep(27)
    
    # Test 6: Stop and Analyze
    if not test_stop_session(token, session_id):
        print("\n❌ Stop session failed!")
        return
    
    # Give some time for processing
    print("\n⏳ Waiting 3 seconds for analysis to complete...")
    time.sleep(3)
    
    # Test 7: Get Results
    test_get_results(token, session_id)
    
    # Test 8: Get Recommendation
    test_get_recommendation(token, session_id)
    
    # Final Summary
    print("\n" + "="*80)
    print("  ✅ INTEGRATION TEST COMPLETE")
    print("="*80)
    print(f"\nSession ID: {session_id}")
    print(f"User ID: {user_id}")
    print("\nCheck server terminal for detailed logs!")
    print(f"\nDashboard: GET {BASE_URL}/dashboard/{user_id}")
    print(f"API Docs: {BASE_URL}/docs")
    print()


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to server!")
        print("Make sure server is running: uvicorn main:app --reload --port 8000")
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
