# Async Frame Processor - High-Performance Frame Processing
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import config
import logger
import async_database


def parse_iso_timestamp(iso_timestamp: str) -> float:
    """Convert ISO timestamp to Unix milliseconds"""
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        return dt.timestamp() * 1000
    except Exception as e:
        logger.log_error("Timestamp Parse Failed", {"error": str(e), "timestamp": iso_timestamp})
        return datetime.utcnow().timestamp() * 1000


async def calculate_instant_fps_async(session_id: int, current_timestamp_ms: float) -> Optional[float]:
    """
    Async calculate FPS from current frame and previous frame
    
    Args:
        session_id: Session ID
        current_timestamp_ms: Current frame timestamp in milliseconds
        
    Returns:
        Instant FPS for this frame, or None if this is the first frame
    """
    try:
        last_timestamp_ms = await async_database.async_get_last_timestamp(session_id)
        
        if last_timestamp_ms is None:
            return None  # First frame
        
        delta_ms = current_timestamp_ms - last_timestamp_ms
        
        if delta_ms <= 0:
            return None
        
        fps = 1000.0 / delta_ms
        return fps
        
    except Exception as e:
        logger.log_error("FPS Calculation Failed", {
            "session_id": session_id,
            "error": str(e)
        })
        return None


def extract_angle_data(frame_type: str, frame_data: dict) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Extract angle values and confidence from nested front/side structure"""
    angle_data = {}
    confidence_data = {}
    
    frame_obj = frame_data.get(frame_type, {})
    
    for metric_name, metric_obj in frame_obj.items():
        if isinstance(metric_obj, dict) and 'value' in metric_obj and 'confidence' in metric_obj:
            angle_data[metric_name] = metric_obj['value']
            confidence_data[metric_name] = metric_obj['confidence']
    
    return angle_data, confidence_data


def validate_frame(is_calibrated: bool, confidence_data: Dict[str, float]) -> List[str]:
    """
    Validate frame and return list of valid metrics
    
    Args:
        is_calibrated: Camera calibration status
        confidence_data: Dict of metric -> confidence value
        
    Returns:
        List of valid metric names
    """
    if not is_calibrated:
        return []  # Skip uncalibrated frames
    
    valid_metrics = []
    for metric_name, confidence in confidence_data.items():
        if confidence >= config.CONFIDENCE_THRESHOLD:
            valid_metrics.append(metric_name)
    
    return valid_metrics


async def accumulate_angle_time_async(session_id: int, camera_angle: str,
                                      angle_data: Dict[str, float], fps: float,
                                      valid_metrics: List[str], frame_id: int):
    """
    Accumulate time for each angle using in-memory buffer (ultra-fast, non-blocking)
    
    Args:
        session_id: Session ID
        camera_angle: FRONT or SIDE
        angle_data: Dict of metric -> angle value
        fps: FPS for this frame
        valid_metrics: List of valid metrics
        frame_id: Current frame ID (for flush decision)
    """
    if fps is None or fps <= 0:
        fps = 15.0  # Default
    
    frame_time_seconds = 1.0 / fps
    
    # Add to in-memory buffer (instant, non-blocking)
    for metric_name in valid_metrics:
        if metric_name not in angle_data:
            continue
        
        angle_value_raw = angle_data[metric_name]
        angle_value = round(angle_value_raw, config.ANGLE_ROUNDING_PRECISION)
        angle_value_int = int(angle_value)
        
        await async_database.buffer_accumulation(
            session_id, camera_angle, metric_name, 
            angle_value_int, frame_time_seconds
        )
    
    # Flush to database every N frames
    if frame_id % async_database.FLUSH_THRESHOLD == 0:
        asyncio.create_task(async_database.flush_accumulation_buffer())


async def process_frame_async(session_id: int, frame_id: int, timestamp: str,
                              frame_type: str, is_calibrated: bool,
                              frame_data: dict) -> Dict:
    """
    High-performance async frame processing
    
    Args:
        session_id: Session ID
        frame_id: Frame sequence number
        timestamp: ISO timestamp string
        frame_type: "front" or "side"
        is_calibrated: Calibration status
        frame_data: Nested front/side angle data
        
    Returns:
        Dict with processing results
    """
    # Step 1: Parse timestamp (sync)
    timestamp_ms = parse_iso_timestamp(timestamp)
    
    # Step 2: Start async operations concurrently
    fps_task = calculate_instant_fps_async(session_id, timestamp_ms)
    
    # Step 3: Extract and validate (sync, fast)
    angle_data, confidence_data = extract_angle_data(frame_type, frame_data)
    valid_metrics = validate_frame(is_calibrated, confidence_data)
    
    # Step 4: Wait for FPS calculation
    fps = await fps_task
    
    # Step 5: Insert frame (async, non-blocking - fire and forget)
    camera_angle = frame_type.upper()
    asyncio.create_task(async_database.async_insert_frame(
        session_id, frame_id, camera_angle,
        angle_data, confidence_data, is_calibrated,
        fps, timestamp, timestamp_ms
    ))
    
    # Step 6: Accumulate angles (in-memory, instant)
    fps_for_accumulation = fps if fps and fps > 0 else 15.0
    await accumulate_angle_time_async(
        session_id, camera_angle, angle_data, 
        fps_for_accumulation, valid_metrics, frame_id
    )
    
    # Step 7: Update session stats every 5 frames (reduce overhead)
    if frame_id % 5 == 0:
        asyncio.create_task(async_database.async_update_session_stats(session_id, fps))
    
    # Step 8: Check completion every 100 frames
    is_complete = False
    completion_msg = None
    if frame_id % 100 == 0:
        is_complete, completion_msg = await async_database.async_check_session_completion(session_id)
    
    return {
        "success": True,
        "frame_id": frame_id,
        "fps": round(fps, 2) if fps else None,
        "valid_metrics": valid_metrics,
        "session_complete": is_complete,
        "message": completion_msg
    }
