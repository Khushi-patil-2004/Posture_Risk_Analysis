# Unified Posture Analysis Server

**Team 2** - Consolidated Input Collector + Posture Engine + Recommendation Engine

## 🎯 Overview

This is a complete refactor of the posture analysis system, consolidating two separate servers into a single FastAPI application with PostgreSQL persistence, JWT authentication, dynamic FPS calculation, and AI-powered recommendations.

## 🏗️ Architecture

### Single Server Design
- **Port**: 8000 (unified from previous 8000 + 8001)
- **Database**: PostgreSQL (Neon)
- **Authentication**: JWT-based
- **AI**: Groq API (Llama 3.1)
- **Data Flow**: Team 1 Simulation → Scoring Engine → Recommendation Engine

### Key Components

1. **Authentication System** (`auth.py`)
   - JWT token generation and validation
   - User registration and login
   - Profile management

2. **Team 1 Simulator** (`team1_simulator.py`)
   - Real-time angle generation (10-20 FPS)
   - Random walk algorithm for realistic data
   - Dual camera angles (FRONT + SIDE)

3. **Scoring Engine** (`scoring_engine.py`)
   - Dynamic FPS calculation from timestamps
   - Approach 1 algorithm (time-based band mapping)
   - Multi-metric risk assessment

4. **Recommendation Engine** (`recommendation_engine.py`)
   - Groq AI integration
   - Trend analysis across sessions
   - Fallback rule-based recommendations

5. **Database Layer** (`database.py`)
   - SQLAlchemy Core (procedural, no ORM)
   - 5 tables: users, sessions, raw_angles, posture_results, recommendations

6. **Logging System** (`logger.py`)
   - Color-coded terminal output
   - Step-by-step lifecycle visibility
   - Structured data logging

## 📊 Database Schema

### Tables

**users** - User profiles
- id, username, password_hash, age, height_cm, weight_kg, created_at

**sessions** - Posture analysis sessions
- id, user_id, start_time, end_time, avg_fps, total_frames, status

**raw_angles** - Raw angle data from simulation
- id, session_id, camera_angle, neck_bend, shoulder_slope, torso_tilt, head_forward_index, confidence, is_calibrated, timestamp_ms

**posture_results** - Scoring results
- id, session_id, user_id, metric_name, risk_percent, status, time_good/warning/bad_min

**recommendations** - AI-generated recommendations
- id, session_id, user_id, recommendation_text, priority, dominant_issue, risk_level, actions_json

## 🚀 Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Edit `.env` file with your credentials:
- DATABASE_URL (PostgreSQL connection string)
- GROQ_API_KEY (Groq AI API key)
- JWT_SECRET_KEY (change for production)

### 3. Initialize Database

```bash
python setup.py
```

Follow prompts to:
- Install dependencies
- Create database tables
- Create test user (demo_user / test123)

### 4. Run Server

```bash
uvicorn main:app --reload --port 8000
```

### 5. Access API Documentation

Open browser: http://localhost:8000/docs

## 📡 API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login and get JWT token
- `GET /auth/profile` - Get user profile (requires JWT)
- `PUT /auth/profile` - Update profile (requires JWT)

### Session Management
- `POST /sessions/start` - Start new session (begins simulation)
- `POST /sessions/{id}/stop` - Stop session and run analysis
- `GET /sessions/{id}/status` - Get session status (FPS, frames, duration)

### Results & Recommendations
- `GET /results/{id}` - Get posture scoring results
- `GET /recommendations/{id}` - Get AI recommendation
- `GET /dashboard/{user_id}` - Get user dashboard with all sessions

### Quick Testing
- `POST /simulate/quick-session` - Run complete 30-sec session automatically

### Utility
- `GET /health` - Health check
- `GET /` - API information

## 🧪 Testing the System

### Complete Lifecycle Test

```bash
# 1. Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo_user","password":"test123"}'

# Save the token from response

# 2. Start session
curl -X POST http://localhost:8000/sessions/start \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"duration_seconds":30}'

# Save session_id from response

# 3. Wait 30 seconds...

# 4. Stop session (triggers scoring + AI)
curl -X POST http://localhost:8000/sessions/SESSION_ID/stop \
  -H "Authorization: Bearer YOUR_TOKEN"

# 5. Get results
curl http://localhost:8000/results/SESSION_ID \
  -H "Authorization: Bearer YOUR_TOKEN"

# 6. Get recommendation
curl http://localhost:8000/recommendations/SESSION_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Or Use Quick Session

```bash
curl -X POST http://localhost:8000/simulate/quick-session \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🎨 Terminal Output

The server provides rich, color-coded terminal logging:

- 🔐 **AUTH** - Authentication events (purple)
- 📊 **TEAM1** - Data generation (blue)
- ⚙️ **ENGINE** - Scoring calculations (cyan)
- 🤖 **AI** - Groq recommendations (green)
- 💾 **DB** - Database operations (white)
- ✅ **SUCCESS** - Successful operations (green)
- ⚠️ **WARNING** - Warnings (yellow)
- ❌ **ERROR** - Errors (red)

Each log shows:
- Timestamp
- Action description
- Structured data
- Next step suggestion

## 🔬 How It Works

### 1. Session Start
- User authenticates and starts session
- System creates session record in database
- Team 1 simulator begins generating angles at 10-20 FPS
- Frames stored in `raw_angles` table with high-precision timestamps

### 2. Data Generation (Team 1)
- Random walk algorithm generates realistic angle fluctuations
- Dual camera angles (FRONT + SIDE)
- Each frame: neck_bend, shoulder_slope, torso_tilt, head_forward_index
- Confidence scores: 0.85-0.99

### 3. Session Stop & Scoring
- Simulation stops
- **Dynamic FPS calculation**: `fps = 1000 / avg(timestamp_n - timestamp_n-1)`
- System fetches calibrated frames (confidence ≥ 0.8)
- **Approach 1 algorithm**:
  - Classify each angle into good/warning/bad
  - Aggregate time in each band
  - Calculate weighted score: `score = band_start + (time_percent × band_width)`
- Results saved to `posture_results` table

### 4. AI Recommendation
- Fetch user profile (age, height, weight)
- Compute trends from historical sessions
- Send to Groq API with context
- Parse JSON response
- Fallback to rule-based if AI fails
- Save to `recommendations` table

## 📈 Metrics & Thresholds

### FRONT View
- **Neck Bend**: Good <10°, Warning 10-20°, Bad ≥20°
- **Shoulder Slope**: Good <5°, Warning 5-10°, Bad ≥10°
- **Torso Tilt**: Good <10%, Warning 10-20%, Bad ≥20%

### SIDE View
- **Neck Bend**: Good <10°, Warning 10-20°, Bad ≥20°
- **Head Forward Index**: Good <0.15, Warning 0.15-0.25, Bad ≥0.25

### Risk Levels
- **Good Posture**: 0-30%
- **Moderate Risk**: 30-60%
- **High Risk**: 60-100%

## 🔐 Security Notes

- JWT tokens expire after 24 hours (configurable)
- Passwords hashed with SHA-256 (upgrade to bcrypt for production)
- All endpoints except register/login require authentication
- Users can only access their own data

## 🚧 Future Enhancements

- [ ] Async background jobs with Celery
- [ ] Redis caching for session data
- [ ] WebSocket for real-time updates
- [ ] Advanced trend analysis with charts
- [ ] Email notifications for high-risk sessions
- [ ] Export reports as PDF
- [ ] Mobile app integration

## 📝 Notes

- Default test user: `demo_user` / `test123` (age: 28, height: 170cm, weight: 65kg)
- Simulation runs at 15 FPS by default (configurable 10-20)
- All timestamps stored in UTC
- Database connection pooling enabled

## 🐛 Troubleshooting

**Database connection failed**
- Check `DATABASE_URL` in `.env`
- Ensure PostgreSQL server is accessible
- Verify SSL mode and channel binding

**Groq API errors**
- Check `GROQ_API_KEY` in `.env`
- Verify API quota/limits
- Set `ENABLE_AI=false` to use fallback recommendations

**Session not processing**
- Check terminal logs for errors
- Verify session status: `GET /sessions/{id}/status`
- Ensure sufficient frames generated (check `total_frames`)

## 📚 Documentation

Interactive API documentation available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 👥 Team

**Team 2** - Backend Engineering
- Posture Scoring Engine
- Recommendation System
- Database Architecture

---

**Version**: 2.0.0
**Last Updated**: February 2026
