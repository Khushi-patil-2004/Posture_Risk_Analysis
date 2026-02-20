# Frame Processor - Real-time Streaming Frame Processing (Procedural)
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select, insert, update
from database import sessions_table, raw_angles_table, angle_accumulation_table, get_connection
import config
import logger
import scoring_engine


def parse_iso_timestamp(iso_timestamp: str) -> float:
    """
    Convert ISO timestamp to Unix milliseconds
    
    Args:
        iso_timestamp: ISO 8601 formatted timestamp string
        
    Returns:
        Unix timestamp in milliseconds
    """
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        return dt.timestamp() * 1000
    except Exception as e:
        logger.log_error("Timestamp Parse Failed", {"error": str(e), "timestamp": iso_timestamp})
        return datetime.utcnow().timestamp() * 1000


def calculate_instant_fps(session_id: int, current_timestamp_ms: float) -> Optional[float]:
    """
    Calculate FPS from current frame and previous frame
    
    Args:
        session_id: Session ID
        current_timestamp_ms: Current frame timestamp in milliseconds
        
    Returns:
        Instant FPS for this frame, or None if this is the first frame
    """
    conn = None
    try:
        conn = get_connection()
        
        # Get the last frame's timestamp
        query = select(raw_angles_table.c.timestamp_ms).where(
            raw_angles_table.c.session_id == session_id
        ).order_by(raw_angles_table.c.timestamp_ms.desc()).limit(1)
        
        result = conn.execute(query).fetchone()
        
        if not result:
            # First frame, no FPS yet
            return None
        
        last_timestamp_ms = result[0]
        delta_ms = current_timestamp_ms - last_timestamp_ms
        
        if delta_ms <= 0:
            # Removed logging for performance
            return None
        
        # FPS = 1000 / delta_ms (converts ms to seconds)
        fps = 1000.0 / delta_ms
        
        # Removed logging for performance
        
        return fps
        
    except Exception as e:
        logger.log_error("FPS Calculation Failed", {
            "session_id": session_id,
            "error": str(e)
        })
        return None
    finally:
        if conn:
            conn.close()


def extract_angle_data(frame_type: str, frame_data: dict) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    Extract angle values and confidence from nested front/side structure
    
    Args:
        frame_type: "front" or "side"
        frame_data: Nested frame data from Team 1
        
    Returns:
        Tuple of (angle_data dict, confidence_data dict)
    """
    angle_data = {}
    confidence_data = {}
    
    # Get the nested object based on frame type
    frame_obj = frame_data.get(frame_type, {})
    
    # Extract all angle measurements
    for metric_name, metric_obj in frame_obj.items():
        if isinstance(metric_obj, dict) and 'value' in metric_obj and 'confidence' in metric_obj:
            # Extract nested structure: {value: 15.2, confidence: 0.95}
            angle_data[metric_name] = float(metric_obj['value'])
            confidence_data[metric_name] = float(metric_obj['confidence'])
    
    # Removed logging for performance (logging every frame is slow)
    
    return angle_data, confidence_data


def validate_frame(is_calibrated: bool, confidence_data: Dict[str, float], 
                   threshold: float = None) -> List[str]:
    """
    Validate frame and return list of valid metric names
    
    Args:
        is_calibrated: Frame calibration status
        confidence_data: Dict of metric_name -> confidence
        threshold: Minimum confidence threshold (default from config)
        
    Returns:
        List of valid metric names that pass calibration and confidence checks
    """
    if threshold is None:
        threshold = config.MIN_CONFIDENCE_PER_ANGLE
    
    valid_metrics = []
    
    # For now, all frames are calibrated per spec
    if not is_calibrated:
        logger.log_warning("Uncalibrated Frame", {"is_calibrated": False})
        return []
    
    # Check each metric's confidence
    for metric_name, confidence in confidence_data.items():
        if confidence >= threshold:
            valid_metrics.append(metric_name)
        else:
            logger.log_warning("Low Confidence", {
                "metric": metric_name,
                "confidence": f"{confidence:.2f}",
                "threshold": threshold
            })
    
    return valid_metrics


def insert_frame_to_db(session_id: int, frame_id: int, camera_angle: str, 
                       angle_data: Dict[str, float], confidence_data: Dict[str, float],
                       is_calibrated: bool, fps: Optional[float], 
                       timestamp_iso: str, timestamp_ms: float) -> bool:
    """
    Insert frame data into raw_angles table
    
    Args:
        session_id: Session ID
        frame_id: Frame sequence number
        camera_angle: FRONT or SIDE
        angle_data: Dict of metric -> angle value
        confidence_data: Dict of metric -> confidence
        is_calibrated: Calibration status
        fps: Calculated FPS for this frame
        timestamp_iso: Original ISO timestamp
        timestamp_ms: Unix timestamp in milliseconds
        
    Returns:
        True if successful, False otherwise
    """
    conn = None
    try:
        conn = get_connection()
        
        insert_query = insert(raw_angles_table).values(
            session_id=session_id,
            frame_id=frame_id,
            camera_angle=camera_angle,
            angle_data=angle_data,
            confidence_data=confidence_data,
            is_calibrated=is_calibrated,
            fps_at_frame=fps,
            timestamp_iso=timestamp_iso,
            timestamp_ms=timestamp_ms
        )
        
        conn.execute(insert_query)
        conn.commit()
        
        # Removed logging for performance - only log every 100th frame
        if frame_id % 100 == 0:
            logger.log_db("Frame Stored", {
                "session_id": session_id,
                "frame_id": frame_id,
                "camera_angle": camera_angle,
                "fps": f"{fps:.2f}" if fps else "N/A",
                "metrics": len(angle_data)
            })
        
        return True
        
    except Exception as e:
        logger.log_error("Frame Insert Failed", {
            "session_id": session_id,
            "frame_id": frame_id,
            "error": str(e)
        })
        return False
    finally:
        if conn:
            conn.close()


def accumulate_angle_time(session_id: int, camera_angle: str, 
                          angle_data: Dict[str, float], fps: float,
                          valid_metrics: List[str]) -> bool:
    """
    Accumulate time for each unique angle value using efficient batch upsert
    
    Args:
        session_id: Session ID
        camera_angle: FRONT or SIDE
        angle_data: Dict of metric -> angle value
        fps: FPS for this frame (defaults to 15 if not calculated)
        valid_metrics: List of metrics that passed validation
        
    Returns:
        True if successful, False otherwise
    """
    if fps is None or fps <= 0:
        # Use default FPS for first frame
        fps = 15.0
    
    conn = None
    try:
        conn = get_connection()
        frame_time_seconds = 1.0 / fps
        
        # Build all upsert values for batch execution
        values_list = []
        for metric_name in valid_metrics:
            if metric_name not in angle_data:
                continue
            
            # Round angle to integer per config
            angle_value_raw = angle_data[metric_name]
            angle_value = round(angle_value_raw, config.ANGLE_ROUNDING_PRECISION)
            angle_value_int = int(angle_value)
            
            values_list.append({
                'session_id': session_id,
                'camera_angle': camera_angle,
                'metric_name': metric_name,
                'angle_value': angle_value_int,
                'total_time_seconds': frame_time_seconds
            })
        
        if not values_list:
            return True  # No valid metrics to accumulate
        
        # Use PostgreSQL INSERT ... ON CONFLICT for efficient batch upsert
        # This is much faster than UPDATE + INSERT fallback
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        
        for values in values_list:
            stmt = pg_insert(angle_accumulation_table).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=['session_id', 'camera_angle', 'metric_name', 'angle_value'],
                set_={'total_time_seconds': angle_accumulation_table.c.total_time_seconds + values['total_time_seconds']}
            )
            conn.execute(stmt)
        
        conn.commit()
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.log_error("Accumulation Failed", {
            "session_id": session_id,
            "error": str(e)
        })
        return False
    finally:
        if conn:
            conn.close()


def update_session_stats(session_id: int, current_fps: Optional[float]) -> bool:
    """
    Update session statistics (frame count, average FPS)
    
    Args:
        session_id: Session ID
        current_fps: FPS of current frame
        
    Returns:
        True if successful
    """
    conn = None
    try:
        conn = get_connection()
        
        # Get current session data
        query = select(sessions_table).where(sessions_table.c.id == session_id)
        session = conn.execute(query).fetchone()
        
        if not session:
            return False
        
        # Update frame count
        new_frame_count = session[8] + 1  # total_frames is column index 8
        
        # Calculate running average FPS
        if current_fps and session[7]:  # avg_fps is column index 7
            current_avg = session[7]
            new_avg_fps = ((current_avg * (new_frame_count - 1)) + current_fps) / new_frame_count
        elif current_fps:
            new_avg_fps = current_fps
        else:
            new_avg_fps = session[7]
        
        # Update session
        update_query = update(sessions_table).where(
            sessions_table.c.id == session_id
        ).values(
            total_frames=new_frame_count,
            avg_fps=new_avg_fps
        )
        
        conn.execute(update_query)
        conn.commit()
        
        return True
        
    except Exception as e:
        logger.log_error("Session Stats Update Failed", {
            "session_id": session_id,
            "error": str(e)
        })
        return False
    finally:
        if conn:
            conn.close()


def check_session_completion(session_id: int) -> Tuple[bool, Optional[str]]:
    """
    Check if session has completed 2 hours and trigger scoring
    
    Args:
        session_id: Session ID
        
    Returns:
        Tuple of (is_complete, message)
    """
    conn = None
    try:
        conn = get_connection()
        
        # Sum total accumulated time across all angles
        from sqlalchemy import func as sql_func
        query = select(sql_func.sum(angle_accumulation_table.c.total_time_seconds)).where(
            angle_accumulation_table.c.session_id == session_id
        )
        
        result = conn.execute(query).fetchone()
        
        total_time = result[0] if result and result[0] else 0
        
        if total_time >= config.SESSION_DURATION_SECONDS:
            logger.log_lifecycle("SESSION COMPLETE", f"Session {session_id} reached 2 hours")
            
            # Trigger scoring
            logger.log_engine("Auto-Triggering Scoring", {"session_id": session_id})
            scoring_result = scoring_engine.score_session(session_id)
            
            if scoring_result:
                return True, f"Session completed after {total_time:.0f} seconds"
            else:
                return True, "Session complete but scoring failed"
        
        progress_pct = (total_time / config.SESSION_DURATION_SECONDS) * 100
        return False, f"Progress: {progress_pct:.1f}% ({total_time:.0f}s / {config.SESSION_DURATION_SECONDS}s)"
        
    except Exception as e:
        logger.log_error("Completion Check Failed", {
            "session_id": session_id,
            "error": str(e)
        })
        return False, f"Error: {str(e)}"
    finally:
        if conn:
            conn.close()


def process_incoming_frame(session_id: int, frame_id: int, timestamp: str,
                           frame_type: str, is_calibrated: bool,
                           frame_data: dict) -> Dict:
    """
    Main function to process a single incoming frame from Team 1
    
    Args:
        session_id: Session ID
        frame_id: Frame sequence number
        timestamp: ISO timestamp string
        frame_type: "front" or "side"
        is_calibrated: Calibration status
        frame_data: Nested front/side angle data
        
    Returns:
        Dict with processing results and session status
    """
    logger.log_team1("Frame Received", {
        "session_id": session_id,
        "frame_id": frame_id,
        "type": frame_type
    })
    
    # Step 1: Parse timestamp
    timestamp_ms = parse_iso_timestamp(timestamp)
    
    # Step 2: Calculate FPS from timestamp delta
    fps = calculate_instant_fps(session_id, timestamp_ms)
    
    # Step 3: Extract angle data from nested structure
    angle_data, confidence_data = extract_angle_data(frame_type, frame_data)
    
    # Step 4: Validate frame (check calibration and per-angle confidence)
    valid_metrics = validate_frame(is_calibrated, confidence_data)
    
    # Step 5: Insert frame into raw_angles table
    camera_angle = frame_type.upper()
    insert_success = insert_frame_to_db(
        session_id, frame_id, camera_angle,
        angle_data, confidence_data, is_calibrated,
        fps, timestamp, timestamp_ms
    )
    
    if not insert_success:
        return {"success": False, "error": "Failed to store frame"}
    
    # Step 6: Accumulate time per angle value (ONLY every 10th frame to reduce DB overhead)
    # This batches accumulation while still tracking data
    if frame_id % 10 == 0:
        fps_for_accumulation = fps if fps and fps > 0 else 15.0  # Default to 15 FPS if not calculated
        accumulate_angle_time(session_id, camera_angle, angle_data, fps_for_accumulation, valid_metrics)
    
    # Step 7: Update session statistics (ONLY every 10th frame)
    if frame_id % 10 == 0:
        update_session_stats(session_id, fps)
    
    # Step 8: Check if session is complete (2 hours) - only check periodically
    is_complete = False
    completion_msg = None
    if frame_id % 100 == 0:  # Check every 100 frames
        is_complete, completion_msg = check_session_completion(session_id)
