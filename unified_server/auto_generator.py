"""
Automatic Frame Generator Module
Generates synthetic posture frames at 15 FPS with async database operations
"""
import asyncio
import time
import random
from datetime import datetime
from typing import Dict, Set
from sqlalchemy import select, update
import config
import database
import async_database
import logger
import frame_processor
import async_frame_processor
import scoring_engine
import recommendation_engine
from database import sessions_table, get_connection

# Track active generation tasks
active_generators: Dict[int, asyncio.Task] = {}
generation_stop_flags: Dict[int, bool] = {}


def generate_synthetic_angles(phase: str, is_calibrated: bool = True) -> Dict:
    """
    Generate realistic synthetic angle data based on phase
    
    Args:
        phase: "FRONT"/"front" or "SIDE"/"side" (case-insensitive)
        is_calibrated: Whether camera is calibrated
        
    Returns:
        Dict with angle data matching expected format
    """
    frame_data = {}
    
    # Normalize phase to uppercase for comparison
    phase_upper = phase.upper()
    
    if phase_upper == "FRONT":
        # Generate FRONT camera angles with some variation
        frame_data['front'] = {
            'neck_bend': {
                'value': random.uniform(15, 25),  # Slightly forward neck
                'confidence': random.uniform(0.85, 0.98)
            },
            'torso_tilt': {
                'value': random.uniform(-5, 10),  # Slight forward lean
                'confidence': random.uniform(0.85, 0.98)
            },
            'shoulder_slope': {
                'value': random.uniform(-3, 8),  # Slight shoulder asymmetry
                'confidence': random.uniform(0.85, 0.98)
            }
        }
    elif phase_upper == "SIDE":
        # Generate SIDE camera angles with some variation
        frame_data['side'] = {
            'neck_bend': {
                'value': random.uniform(20, 35),  # Forward head posture
                'confidence': random.uniform(0.85, 0.98)
            },
            'head_forward_index': {
                'value': random.uniform(5, 15),  # Head forward measurement
                'confidence': random.uniform(0.85, 0.98)
            }
        }
    
    return frame_data


async def auto_generate_frames(session_id: int, target_fps: float = 15.0):
    """
    Background task that generates frames at specified FPS
    
    Args:
        session_id: Session to generate frames for
        target_fps: Target frame rate (default 15 FPS)
    """
    try:
        logger.log_success("Auto-Generation Started", {
            "session_id": session_id,
            "fps": target_fps
        })
        
        frame_id = 1
        start_time = time.time()
        frame_interval = 1.0 / target_fps  # Time between frames in seconds
        
        # Initialize stop flag
        generation_stop_flags[session_id] = False
        
        # Cache session phase to avoid querying DB every frame
        cached_phase = "front"  # Start with default
        phase_check_interval = max(int(target_fps), 15)  # Check phase every N frames (at least every 15 frames)
        
        while not generation_stop_flags.get(session_id, False):
            frame_start_time = time.time()
            
            # Only check session status periodically to reduce DB overhead
            if frame_id == 1 or frame_id % phase_check_interval == 0:
                session_info = await async_database.async_get_session_info(session_id)
                
                if not session_info:
                    logger.log_error("Session Not Found", {"session_id": session_id})
                    break
                
                # Check if session is still active
                if session_info['status'] != "active":
                    logger.log_warning("Session No Longer Active", {
                        "session_id": session_id,
                        "status": session_info['status']
                    })
                    break
                
                cached_phase = session_info.get('current_phase', 'front')
            
            current_phase = cached_phase
            
            # Determine frame type based on current phase
            frame_type = current_phase.lower()
            is_calibrated = True
            
            # Generate synthetic angle data
            frame_data = generate_synthetic_angles(current_phase, is_calibrated)
            
            # Generate timestamp
            timestamp = datetime.utcnow().isoformat() + "Z"
            
            # Process the frame using ASYNC processor for high performance
            try:
                result = await async_frame_processor.process_frame_async(
                    session_id=session_id,
                    frame_id=frame_id,
                    timestamp=timestamp,
                    frame_type=frame_type,
                    is_calibrated=is_calibrated,
                    frame_data=frame_data
                )
                
                # Log every 10th frame to balance visibility and performance
                if frame_id % 10 == 0 or frame_id == 1:
                    logger.log_team1(f"🎬 Frame #{frame_id} Generated", {
                        "session_id": session_id,
                        "phase": current_phase,
                        "fps": f"{result.get('fps', 0):.2f}" if result.get('fps') else "calculating...",
                        "valid_metrics": result.get('valid_metrics', []),
                        "angles": {k: f"{v['value']:.1f}°" for k, v in frame_data.get(frame_type, {}).items()},
                        "frame_time_ms": f"{(time.time() - start_time) * 1000:.0f}",
                        "target_fps": target_fps,
                        "session_complete": result.get('session_complete', False)
                    })
                
                # Check if session completed (auto-scoring triggered)
                if result.get('session_complete'):
                    logger.log_success("Auto-Generation Complete", {
                        "session_id": session_id,
                        "total_frames": frame_id,
                        "reason": "Session duration reached (2 hours)"
                    })
                    break
                    
            except Exception as e:
                logger.log_error("Frame Generation Error", {
                    "session_id": session_id,
                    "frame_id": frame_id,
                    "error": str(e)
                })
                # Continue generating despite errors
            
            frame_id += 1
            
            # Calculate adaptive sleep to maintain target FPS
            frame_processing_time = time.time() - frame_start_time
            sleep_time = max(0, frame_interval - frame_processing_time)
            await asyncio.sleep(sleep_time)
        
        # Cleanup
        if session_id in generation_stop_flags:
            del generation_stop_flags[session_id]
        
        logger.log_success("Auto-Generation Stopped", {
            "session_id": session_id,
            "total_frames_generated": frame_id - 1
        })
        
    except asyncio.CancelledError:
        logger.log_warning("Auto-Generation Cancelled", {"session_id": session_id})
        if session_id in generation_stop_flags:
            del generation_stop_flags[session_id]
        raise
    except Exception as e:
        logger.log_error("Auto-Generation Failed", {
            "session_id": session_id,
            "error": str(e)
        })
        if session_id in generation_stop_flags:
            del generation_stop_flags[session_id]


def start_auto_generation(session_id: int, fps: float = 15.0) -> Dict:
    """
    Start automatic frame generation for a session
    
    Args:
        session_id: Session ID to generate frames for
        fps: Target frame rate (default 1 FPS)
        
    Returns:
        Dict with success status and message
    """
    # Check if already generating for this session
    if session_id in active_generators and not active_generators[session_id].done():
        return {
            "success": False,
            "message": f"Auto-generation already running for session {session_id}",
            "status": "already_running"
        }
    
    # Create and store the background task
    task = asyncio.create_task(auto_generate_frames(session_id, fps))
    active_generators[session_id] = task
    
    return {
        "success": True,
        "message": f"Auto-generation started at {fps} FPS",
        "session_id": session_id,
        "fps": fps,
        "status": "started"
    }


def stop_auto_generation(session_id: int) -> Dict:
    """
    Stop automatic frame generation for a session
    
    Args:
        session_id: Session ID to stop generation for
        
    Returns:
        Dict with success status and message
    """
    # Check if generation is running
    if session_id not in active_generators or active_generators[session_id].done():
        return {
            "success": False,
            "message": f"No active generation found for session {session_id}",
            "status": "not_running"
        }
    
    # Set stop flag
    generation_stop_flags[session_id] = True
    
    # Cancel the task
    active_generators[session_id].cancel()
    
    return {
        "success": True,
        "message": f"Auto-generation stopped for session {session_id}",
        "session_id": session_id,
        "status": "stopped"
    }


def get_generation_status(session_id: int) -> Dict:
    """
    Get status of auto-generation for a session
    
    Args:
        session_id: Session ID to check
        
    Returns:
        Dict with generation status
    """
    is_running = (
        session_id in active_generators 
        and not active_generators[session_id].done()
    )
    
    return {
        "session_id": session_id,
        "is_generating": is_running,
        "status": "running" if is_running else "stopped"
    }


def cleanup_completed_tasks():
    """
    Remove completed tasks from active_generators
    """
    completed = [sid for sid, task in active_generators.items() if task.done()]
    for sid in completed:
        del active_generators[sid]
