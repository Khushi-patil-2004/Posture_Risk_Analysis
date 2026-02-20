# Async Database Module - High-Performance Async Operations with asyncpg
import asyncpg
import json
import config
from typing import Dict, List, Optional
import asyncio

# Global connection pool
_pool: Optional[asyncpg.Pool] = None
_pool_lock = asyncio.Lock()

# In-memory accumulation buffer for batching
_accumulation_buffer: Dict[str, Dict] = {}  # key: "session_id:camera:metric:angle" -> value: time_seconds
_buffer_lock = asyncio.Lock()
FLUSH_THRESHOLD = 30  # Flush every N frames

# In-memory timestamp cache for FPS calculation (avoid DB queries)
_last_timestamp_cache: Dict[int, float] = {}  # session_id -> last_timestamp_ms
_timestamp_lock = asyncio.Lock()

# In-memory session stats cache (avoid DB queries)
_session_stats_cache: Dict[int, Dict] = {}  # session_id -> {total_frames, avg_fps}
_stats_lock = asyncio.Lock()
STATS_FLUSH_THRESHOLD = 50  # Flush stats to DB every N frames


async def init_async_pool():
    """Initialize async connection pool"""
    global _pool
    
    if _pool is not None:
        return _pool
    
    async with _pool_lock:
        if _pool is not None:  # Double-check after acquiring lock
            return _pool
        
        database_url = config.DATABASE_URL
        # asyncpg expects postgresql:// format (not postgresql+psycopg)
        if database_url.startswith("postgresql+psycopg://"):
            database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        
        _pool = await asyncpg.create_pool(
            database_url,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        return _pool


async def get_async_pool() -> asyncpg.Pool:
    """Get or create async connection pool"""
    global _pool
    if _pool is None:
        await init_async_pool()
    return _pool


async def async_insert_frame(session_id: int, frame_id: int, camera_angle: str,
                             angle_data: Dict[str, float], confidence_data: Dict[str, float],
                             is_calibrated: bool, fps: Optional[float], 
                             timestamp: str, timestamp_ms: float) -> bool:
    """
    Async insert frame into raw_angles table
    
    Args:
        session_id: Session ID
        frame_id: Frame sequence number
        camera_angle: FRONT or SIDE
        angle_data: Dict of metric -> angle value
        confidence_data: Dict of metric -> confidence
        is_calibrated: Calibration status
        fps: Calculated FPS
        timestamp: ISO timestamp string
        timestamp_ms: Unix timestamp in milliseconds
        
    Returns:
        True if successful
    """
    try:
        pool = await get_async_pool()
        
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO raw_angles (
                    session_id, frame_id, camera_angle, angle_data, 
                    confidence_data, is_calibrated, fps_at_frame, timestamp_iso, timestamp_ms
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, session_id, frame_id, camera_angle, json.dumps(angle_data), 
                json.dumps(confidence_data), is_calibrated, fps, timestamp, timestamp_ms)
        
        # Update timestamp cache (for next FPS calculation)
        async with _timestamp_lock:
            _last_timestamp_cache[session_id] = timestamp_ms
        
        return True
    except Exception as e:
        print(f"Async insert frame error: {e}")
        return False


async def async_get_last_timestamp(session_id: int) -> Optional[float]:
    """Get last frame timestamp for FPS calculation (from cache, ultra-fast)"""
    try:
        async with _timestamp_lock:
            return _last_timestamp_cache.get(session_id, None)
    except Exception as e:
        print(f"Async get last timestamp error: {e}")
        return None


async def buffer_accumulation(session_id: int, camera_angle: str, metric_name: str,
                              angle_value: int, time_seconds: float):
    """
    Add accumulation data to in-memory buffer (non-blocking)
    
    Args:
        session_id: Session ID
        camera_angle: FRONT or SIDE
        metric_name: Metric name (neck_bend, etc.)
        angle_value: Rounded angle value
        time_seconds: Time to add
    """
    async with _buffer_lock:
        key = f"{session_id}:{camera_angle}:{metric_name}:{angle_value}"
        
        if key in _accumulation_buffer:
            _accumulation_buffer[key]['total_time'] += time_seconds
        else:
            _accumulation_buffer[key] = {
                'session_id': session_id,
                'camera_angle': camera_angle,
                'metric_name': metric_name,
                'angle_value': angle_value,
                'total_time': time_seconds
            }


async def flush_accumulation_buffer(force: bool = False):
    """
    Flush accumulation buffer to database
    
    Args:
        force: Force flush regardless of threshold
    """
    async with _buffer_lock:
        buffer_size = len(_accumulation_buffer)
        
        if buffer_size == 0:
            return
        
        if not force and buffer_size < FLUSH_THRESHOLD:
            return  # Wait for more data
        
        # Copy buffer and clear it
        items_to_flush = list(_accumulation_buffer.values())
        _accumulation_buffer.clear()
    
    # Flush to database (outside lock for better concurrency)
    try:
        pool = await get_async_pool()
        
        async with pool.acquire() as conn:
            # Use batch insert with ON CONFLICT
            for item in items_to_flush:
                await conn.execute("""
                    INSERT INTO angle_accumulation 
                        (session_id, camera_angle, metric_name, angle_value, total_time_seconds)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (session_id, camera_angle, metric_name, angle_value)
                    DO UPDATE SET total_time_seconds = angle_accumulation.total_time_seconds + EXCLUDED.total_time_seconds
                """, item['session_id'], item['camera_angle'], item['metric_name'],
                    item['angle_value'], item['total_time'])
        
        print(f"✅ Flushed {len(items_to_flush)} accumulation records to database")
    except Exception as e:
        print(f"❌ Flush accumulation error: {e}")
        # Re-add failed items back to buffer
        async with _buffer_lock:
            for item in items_to_flush:
                key = f"{item['session_id']}:{item['camera_angle']}:{item['metric_name']}:{item['angle_value']}"
                if key in _accumulation_buffer:
                    _accumulation_buffer[key]['total_time'] += item['total_time']
                else:
                    _accumulation_buffer[key] = item


async def async_update_session_stats(session_id: int, current_fps: Optional[float]) -> bool:
    """
    Async update session statistics (in-memory, ultra-fast)
    
    Args:
        session_id: Session ID
        current_fps: Current frame FPS
        
    Returns:
        True if successful
    """
    try:
        async with _stats_lock:
            # Initialize if not exists
            if session_id not in _session_stats_cache:
                _session_stats_cache[session_id] = {
                    'total_frames': 0,
                    'avg_fps': 0.0,
                    'fps_sum': 0.0
                }
            
            stats = _session_stats_cache[session_id]
            stats['total_frames'] += 1
            
            # Update rolling average FPS
            if current_fps and current_fps > 0:
                stats['fps_sum'] += current_fps
                stats['avg_fps'] = stats['fps_sum'] / stats['total_frames']
            
            # Flush to database every N frames
            if stats['total_frames'] % STATS_FLUSH_THRESHOLD == 0:
                asyncio.create_task(_flush_session_stats_to_db(session_id))
        
        return True
    except Exception as e:
        print(f"Async update session stats error: {e}")
        return False


async def _flush_session_stats_to_db(session_id: int):
    """Flush session stats from cache to database"""
    try:
        async with _stats_lock:
            if session_id not in _session_stats_cache:
                return
            stats = _session_stats_cache[session_id].copy()
        
        pool = await get_async_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE sessions 
                SET total_frames = $1, avg_fps = $2 
                WHERE id = $3
            """, stats['total_frames'], stats['avg_fps'], session_id)
    except Exception as e:
        print(f"Flush session stats error: {e}")


async def async_check_session_completion(session_id: int) -> tuple[bool, Optional[str]]:
    """
    Check if session has accumulated 2 hours worth of data
    
    Returns:
        Tuple of (is_complete, message)
    """
    try:
        pool = await get_async_pool()
        
        async with pool.acquire() as conn:
            total_accumulated = await conn.fetchval("""
                SELECT SUM(total_time_seconds) 
                FROM angle_accumulation 
                WHERE session_id = $1
            """, session_id)
        
        total_accumulated = total_accumulated or 0
        
        if total_accumulated >= config.SESSION_DURATION_SECONDS:
            return True, f"Session complete: {total_accumulated:.1f}s accumulated"
        
        return False, None
    except Exception as e:
        print(f"Async check session completion error: {e}")
        return False, None


async def async_get_session_info(session_id: int) -> Optional[Dict]:
    """
    Get session info (status, phase) without blocking
    
    Returns:
        Dict with session info or None if not found
    """
    try:
        pool = await get_async_pool()
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT status, current_phase FROM sessions WHERE id = $1
            """, session_id)
        
        if not row:
            return None
        
        return {
            'status': row['status'],
            'current_phase': row['current_phase']
        }
    except Exception as e:
        print(f"Async get session info error: {e}")
        return None


async def close_async_pool():
    """Close async connection pool"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
