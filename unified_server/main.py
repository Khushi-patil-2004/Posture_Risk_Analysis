# Main FastAPI Application - Unified Posture Analysis Server
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from sqlalchemy import select, update, insert
import asyncio

# Import our modules
import config
import database
import async_database
import logger
import auth
import frame_processor
import scoring_engine
import recommendation_engine
import auto_generator
from database import sessions_table, get_connection

# Initialize FastAPI
app = FastAPI(
    title="Unified Posture Analysis API",
    description="Team 2 - Consolidated Input Collector + Posture Engine + Recommendations",
    version="2.0.0"
)

# Security scheme for Swagger UI
security = HTTPBearer()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class RegisterRequest(BaseModel):
    username: str
    password: str
    age: Optional[int] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class UpdateProfileRequest(BaseModel):
    age: Optional[int] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None


class StartSessionRequest(BaseModel):
    duration_seconds: int = 3600  # Default 1 hour


class ProcessSessionRequest(BaseModel):
    user_profile: Optional[dict] = None


# Frame Ingestion Models
class AngleWithConfidence(BaseModel):
    value: float
    confidence: float


class FrontData(BaseModel):
    is_calibrated: bool
    neck_bend_degree: Optional[AngleWithConfidence] = None
    torso_tilt_degree: Optional[AngleWithConfidence] = None
    shoulder_slope_degree: Optional[AngleWithConfidence] = None


class SideData(BaseModel):
    is_calibrated: bool
    neck_bend_degree: Optional[AngleWithConfidence] = None
    head_forward_index: Optional[AngleWithConfidence] = None


class IngestFrameRequest(BaseModel):
    session_id: int
    fps: Optional[float] = 15.0  # Target FPS for auto-generation (default 15 FPS)


# ============================================================================
# DEPENDENCY INJECTION - JWT Auth
# ============================================================================

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    """
    Extract user_id from JWT token in Authorization header
    
    Raises HTTPException if token is missing or invalid
    """
    token = credentials.credentials
    
    user_id = auth.extract_user_id(token)
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return user_id


# ============================================================================
# STARTUP/SHUTDOWN EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup"""
    logger.log_lifecycle("STARTUP", "Initializing Unified Posture Analysis Server")
    
    # Initialize async database pool for high-performance operations
    try:
        await async_database.init_async_pool()
        logger.log_success("Async DB Pool Initialized", {"driver": "asyncpg"})
    except Exception as e:
        logger.log_error("Async DB Pool Failed", {"error": str(e)})
    
    # Test database connection
    db_ok = database.test_connection()
    
    # Initialize database tables
    init_ok = database.init_database()
    
    # Create test user if doesn't exist
    try:
        auth.create_test_user()
    except:
        pass  # User might already exist
    
    # Test Groq API
    if config.ENABLE_AI:
        logger.log_ai("Groq AI Enabled", {"model": config.GROQ_MODEL})
    else:
        logger.log_warning("Groq AI Disabled", {"ENABLE_AI": "false"})
    
    if db_ok and init_ok:
        logger.log_success("Server Ready", {
            "database": "Connected",
            "async_pool": "Ready",
            "groq_ai": "Enabled" if config.ENABLE_AI else "Disabled",
            "simulation_fps": config.SIMULATION_FPS
        })
    else:
        logger.log_error("Startup Failed", Exception("Database initialization issue"))


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.log_lifecycle("SHUTDOWN", "Stopping all services")
    
    # Flush any remaining accumulation data to database
    try:
        logger.log_info("Flushing Accumulation Buffer", {})
        await async_database.flush_accumulation_buffer(force=True)
        logger.log_success("Buffer Flushed", {})
    except Exception as e:
        logger.log_error("Buffer Flush Failed", {"error": str(e)})
    
    # Close async database pool
    try:
        await async_database.close_async_pool()
        logger.log_success("Async DB Pool Closed", {})
    except Exception as e:
        logger.log_error("Pool Close Failed", {"error": str(e)})


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """
    Health check endpoint
    
    Tests database and API connectivity
    """
    db_ok = database.test_connection()
    
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "groq_ai": "enabled" if config.ENABLE_AI else "disabled",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# AUTHENTICATION ROUTES (Team 3 Simulation)
# ============================================================================

@app.post("/auth/register")
async def register(request: RegisterRequest):
    """
    Register a new user
    
    Team 3 simulation - User management
    """
    logger.log_api("POST /auth/register", {"username": request.username})
    
    success, message, user_id = auth.register_user(
        username=request.username,
        password=request.password,
        age=request.age,
        height_cm=request.height_cm,
        weight_kg=request.weight_kg
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {
        "success": True,
        "message": message,
        "user_id": user_id
    }


@app.post("/auth/login")
async def login(request: LoginRequest):
    """
    Authenticate user and get JWT token
    
    Team 3 simulation - Authentication
    """
    logger.log_api("POST /auth/login", {"username": request.username})
    
    success, message, token, user_data = auth.login_user(
        username=request.username,
        password=request.password
    )
    
    if not success:
        raise HTTPException(status_code=401, detail=message)
    
    return {
        "success": True,
        "message": message,
        "token": token,
        "user": user_data
    }


@app.get("/auth/profile", dependencies=[Depends(security)])
async def get_profile(user_id: int = Depends(get_current_user)):
    """
    Get current user profile
    
    Requires JWT token in Authorization header
    """
    logger.log_api("GET /auth/profile", {"user_id": user_id})
    
    profile = auth.get_user_profile(user_id)
    
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    
    return profile


@app.put("/auth/profile", dependencies=[Depends(security)])
async def update_profile(
    request: UpdateProfileRequest,
    user_id: int = Depends(get_current_user)
):
    """
    Update user profile
    
    Requires JWT token
    """
    logger.log_api("PUT /auth/profile", {"user_id": user_id})
    
    success, message = auth.update_user_profile(
        user_id=user_id,
        age=request.age,
        height_cm=request.height_cm,
        weight_kg=request.weight_kg
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}


# ============================================================================
# FRAME INGESTION ROUTES (Team 1 → Team 2)
# ============================================================================

@app.post("/frames/ingest", dependencies=[Depends(security)])
async def ingest_frame(
    request: IngestFrameRequest,
    user_id: int = Depends(get_current_user)
):
    """
    Start automatic frame generation for a session
    
    Generates synthetic posture frames at specified FPS (default 1 FPS).
    Frames are automatically generated and stored in the database.
    Auto-switches between FRONT and SIDE phases.
    Auto-scores after 2 hours of accumulated time.
    
    To stop generation, use POST /frames/stop-generation
    """
    logger.log_api("POST /frames/ingest", {"session_id": request.session_id})
    
    conn = None
    try:
        # Verify session belongs to user
        conn = get_connection()
        query = select(sessions_table).where(
            (sessions_table.c.id == request.session_id) &
            (sessions_table.c.user_id == user_id)
        )
        session = conn.execute(query).fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found or unauthorized")
        
        # Convert to dict for named access
        session_dict = dict(session._mapping)
        
        # Check if session is still active
        if session_dict['status'] != "active":
            raise HTTPException(status_code=400, detail=f"Session status is '{session_dict['status']}', cannot start generation")
        
        conn.close()
        
        # Start auto-generation
        result = auto_generator.start_auto_generation(
            session_id=request.session_id,
            fps=request.fps
        )
        
        if not result['success']:
            return {
                "success": False,
                "message": result['message'],
                "status": result['status']
            }
        
        return {
            "success": True,
            "session_id": request.session_id,
            "fps": request.fps,
            "message": f"Auto-generation started at {request.fps} FPS. Frames will be generated automatically.",
            "status": "generating",
            "info": {
                "duration": "2 hours (7200 seconds)",
                "auto_phase_switch": "FRONT (1 hour) → SIDE (1 hour)",
                "auto_scoring": "Triggered after 2 hours",
                "stop_endpoint": "POST /frames/stop-generation"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("Auto-Generation Start Failed", {
            "session_id": request.session_id,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.post("/frames/stop-generation", dependencies=[Depends(security)])
async def stop_frame_generation(
    session_id: int,
    user_id: int = Depends(get_current_user)
):
    """
    Stop automatic frame generation for a session
    
    Use this endpoint to manually stop frame generation before 2 hours.
    """
    logger.log_api("POST /frames/stop-generation", {"session_id": session_id})
    
    conn = None
    try:
        # Verify session belongs to user
        conn = get_connection()
        query = select(sessions_table).where(
            (sessions_table.c.id == session_id) &
            (sessions_table.c.user_id == user_id)
        )
        session = conn.execute(query).fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found or unauthorized")
        
        conn.close()
        
        # Stop auto-generation
        result = auto_generator.stop_auto_generation(session_id)
        
        return {
            "success": result['success'],
            "session_id": session_id,
            "message": result['message'],
            "status": result['status']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("Stop Generation Failed", {
            "session_id": session_id,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get("/frames/generation-status/{session_id}", dependencies=[Depends(security)])
async def get_frame_generation_status(
    session_id: int,
    user_id: int = Depends(get_current_user)
):
    """
    Get status of automatic frame generation for a session
    """
    logger.log_api("GET /frames/generation-status", {"session_id": session_id})
    
    conn = None
    try:
        # Verify session belongs to user
        conn = get_connection()
        query = select(sessions_table).where(
            (sessions_table.c.id == session_id) &
            (sessions_table.c.user_id == user_id)
        )
        session = conn.execute(query).fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found or unauthorized")
        
        conn.close()
        
        # Get generation status
        status = auto_generator.get_generation_status(session_id)
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("Status Check Failed", {
            "session_id": session_id,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


# ============================================================================
# SESSION MANAGEMENT ROUTES
# ============================================================================

@app.post("/sessions/start", dependencies=[Depends(security)])
async def start_session(
    request: StartSessionRequest,
    user_id: int = Depends(get_current_user)
):
    """
    Start a new 2-hour posture analysis session
    
    Creates session with front phase initialization
    Team 1 will stream frames to POST /frames/ingest
    """
    logger.log_api("POST /sessions/start", {
        "user_id": user_id,
        "duration_sec": request.duration_seconds
    })
    
    conn = None
    try:
        from datetime import timedelta
        
        # Create session in database with phase tracking
        conn = get_connection()
        start_time = datetime.utcnow()
        
        insert_query = insert(sessions_table).values(
            user_id=user_id,
            start_time=start_time,
            status="active",
            current_phase="front",  # Start with front phase
            phase_start_time=start_time,
            expected_end_time=start_time + timedelta(seconds=config.SESSION_DURATION_SECONDS)
        )
        result = conn.execute(insert_query)
        conn.commit()
        session_id = result.inserted_primary_key[0]
        
        logger.log_db("Session Created", {
            "session_id": session_id,
            "user_id": user_id,
            "initial_phase": "front"
        })
        
        return {
            "success": True,
            "session_id": session_id,
            "status": "active",
            "current_phase": "front",
            "start_time": start_time.isoformat(),
            "expected_end_time": (start_time + timedelta(seconds=config.SESSION_DURATION_SECONDS)).isoformat(),
            "instructions": "Team 1 should now stream frames to POST /frames/ingest with this session_id"
        }
        
    except Exception as e:
        logger.log_error("Session Start Failed", e, {"user_id": user_id})
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

# ============================================================================
# NOTE: POST /sessions/{session_id}/stop is REMOVED
# Session completion is now auto-triggered by frame_processor when 2 hours elapsed
# Scoring and recommendation generation happen automatically
# ============================================================================


@app.get("/sessions/{session_id}/status", dependencies=[Depends(security)])
async def get_session_status(
    session_id: int,
    user_id: int = Depends(get_current_user)
):
    """
    Get current session status
    
    Shows current phase, FPS, frame count, duration, accumulated time
    """
    logger.log_api("GET /sessions/{session_id}/status", {"session_id": session_id})
    
    conn = None
    try:
        conn = get_connection()
        
        # Get session info
        query = select(sessions_table).where(sessions_table.c.id == session_id)
        result = conn.execute(query).first()
        
        if not result:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = dict(result._mapping)
        
        # Get frame count
        from sqlalchemy import func
        count_query = select(func.count()).select_from(database.raw_angles_table).where(
            database.raw_angles_table.c.session_id == session_id
        )
        frame_count = conn.execute(count_query).scalar()
        
        # Get total accumulated time from angle_accumulation
        accumulated_query = select(func.sum(database.angle_accumulation_table.c.total_time_seconds)).where(
            database.angle_accumulation_table.c.session_id == session_id
        )
        total_accumulated_time = conn.execute(accumulated_query).scalar() or 0
        
        # Calculate duration
        if session["end_time"]:
            duration = (session["end_time"] - session["start_time"]).total_seconds()
        else:
            duration = (datetime.utcnow() - session["start_time"]).total_seconds()
        
        return {
            "session_id": session_id,
            "status": session["status"],
            "current_phase": session.get("current_phase"),
            "duration_sec": round(duration, 1),
            "total_frames": frame_count,
            "accumulated_time_sec": round(total_accumulated_time, 1),
            "progress_percent": round((total_accumulated_time / config.SESSION_DURATION_SECONDS) * 100, 1),
            "avg_fps": round(session["avg_fps"], 2) if session["avg_fps"] else None,
            "start_time": session["start_time"].isoformat() if session["start_time"] else None,
            "end_time": session["end_time"].isoformat() if session["end_time"] else None,
            "expected_end_time": session["expected_end_time"].isoformat() if session.get("expected_end_time") else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("Status Fetch Failed", e, {"session_id": session_id})
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.post("/sessions/{session_id}/score-now", dependencies=[Depends(security)])
async def trigger_manual_scoring(
    session_id: int,
    user_id: int = Depends(get_current_user)
):
    """
    Manually trigger scoring and recommendation generation for a session
    
    Useful for testing without waiting for the full 2-hour duration.
    Can be called at any time to score based on currently accumulated data.
    """
    logger.log_api("POST /sessions/{session_id}/score-now", {"session_id": session_id})
    
    conn = None
    try:
        conn = get_connection()
        
        # Verify session exists
        query = select(sessions_table).where(sessions_table.c.id == session_id)
        result = conn.execute(query).first()
        
        if not result:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Trigger scoring (this also generates recommendations internally)
        logger.log_engine(f"Manual Scoring Triggered", {"session_id": session_id})
        scoring_result = scoring_engine.score_session(session_id)
        
        if not scoring_result:
            raise HTTPException(
                status_code=400,detail="Scoring failed - no angle data accumulated for this session"
            )
        
        return {
            "success": True,
            "session_id": session_id,
            "metrics_scored": len(scoring_result) - 1,  # Exclude __OVERALL__ from count
            "message": "Scoring and recommendations generated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("Manual Scoring Failed", e, {"session_id": session_id})
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")
    finally:
        if conn:
            conn.close()


# ============================================================================
# RESULTS & RECOMMENDATIONS ROUTES
# ============================================================================

@app.get("/results/{session_id}", dependencies=[Depends(security)])
async def get_results(
    session_id: int,
    user_id: int = Depends(get_current_user)
):
    """
    Get posture scoring results for a session
    
    Returns all metrics with risk percentages
    """
    logger.log_api("GET /results/{session_id}", {"session_id": session_id})
    
    results = scoring_engine.get_session_results(session_id)
    
    if not results:
        raise HTTPException(status_code=404, detail="No results found for this session")
    
    return {
        "session_id": session_id,
        "total_metrics": len(results),
        "results": results
    }


@app.get("/recommendations/{session_id}", dependencies=[Depends(security)])
async def get_recommendation(
    session_id: int,
    user_id: int = Depends(get_current_user)
):
    """
    Get AI-generated recommendation for a session
    
    Returns personalized actions and priority
    """
    logger.log_api("GET /recommendations/{session_id}", {"session_id": session_id})
    
    recommendation = recommendation_engine.get_session_recommendation(session_id)
    
    if not recommendation:
        raise HTTPException(status_code=404, detail="No recommendation found for this session")
    
    return recommendation


@app.get("/dashboard/{user_id_param}", dependencies=[Depends(security)])
async def get_dashboard(
    user_id_param: int,
    user_id: int = Depends(get_current_user)
):
    """
    Get user dashboard with all sessions and trends
    
    Overview of posture health over time
    """
    # Ensure user can only access their own dashboard
    if user_id != user_id_param:
        raise HTTPException(status_code=403, detail="Access denied")
    
    logger.log_api("GET /dashboard", {"user_id": user_id})
    
    conn = None
    try:
        conn = get_connection()
        
        # Get all sessions
        query = select(sessions_table).where(
            sessions_table.c.user_id == user_id
        ).order_by(sessions_table.c.start_time.desc())
        
        sessions = conn.execute(query).fetchall()
        
        session_list = []
        for session in sessions:
            s = dict(session._mapping)
            session_list.append({
                "session_id": s["id"],
                "status": s["status"],
                "start_time": s["start_time"].isoformat() if s["start_time"] else None,
                "avg_fps": round(s["avg_fps"], 2) if s["avg_fps"] else None,
                "total_frames": s["total_frames"]
            })
        
        return {
            "user_id": user_id,
            "total_sessions": len(session_list),
            "sessions": session_list
        }
        
    except Exception as e:
        logger.log_error("Dashboard Fetch Failed", e, {"user_id": user_id})
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


# ============================================================================
# QUICK SIMULATION ROUTE
# ============================================================================

# ============================================================================
# NOTE: POST /simulate/quick-session is REMOVED
# Testing should now use actual frame ingestion via POST /frames/ingest
# ============================================================================


# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/")
async def root():
    """API information"""
    return {
        "name": "Unified Posture Analysis API",
        "version": "3.0.0",
        "team": "Team 2",
        "architecture": "Real-time streaming frame ingestion with angle-time accumulation",
        "endpoints": {
            "auth": ["/auth/register", "/auth/login", "/auth/profile"],
            "sessions": ["/sessions/start", "/sessions/{id}/status"],
            "frames": ["/frames/ingest"],
            "results": ["/results/{id}", "/recommendations/{id}", "/dashboard/{user_id}"],
            "health": ["/health"]
        },
        "documentation": "/docs",
        "notes": [
            "POST /sessions/{id}/stop removed - completion auto-triggered after 2 hours",
            "POST /simulate/quick-session removed - use real frame streaming"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
