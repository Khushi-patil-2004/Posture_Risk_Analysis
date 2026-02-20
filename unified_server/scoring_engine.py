# Scoring Engine - Angle-Time Maps with Distribution Analysis (Procedural)
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from sqlalchemy import select, insert, update, delete
from database import sessions_table, angle_accumulation_table, posture_results_table, get_connection
import config
import logger
import recommendation_engine


def posture_status(score: float) -> str:
    """
    Convert risk score to status text
    
    Args:
        score: Risk score (0-100)
        
    Returns:
        Status string
    """
    if score <= 30:
        return "Good posture"
    elif score <= 60:
        return "Moderate risk"
    return "High risk"


def build_angle_time_maps(session_id: int) -> Dict:
    """
    Query angle_accumulation table and build nested time maps
    
    Format: {camera_angle: {metric_name: {angle_int: time_seconds}}}
    Example: {"FRONT": {"neck_bend": {15: 120.5, 16: 98.2, 17: 45.1}}}
    
    Args:
        session_id: Session ID
        
    Returns:
        Nested dict of angle-time maps
    """
    try:
        conn = get_connection()
        
        query = select(angle_accumulation_table).where(
            angle_accumulation_table.c.session_id == session_id
        ).order_by(
            angle_accumulation_table.c.camera_angle,
            angle_accumulation_table.c.metric_name,
            angle_accumulation_table.c.angle_value
        )
        
        rows = conn.execute(query).fetchall()
        conn.close()
        
        # Build nested structure
        angle_maps = defaultdict(lambda: defaultdict(dict))
        
        for row in rows:
            camera_angle = row[2]  # camera_angle column
            metric_name = row[3]   # metric_name column
            angle_value = row[4]   # angle_value column
            total_time = row[5]    # total_time_seconds column
            
            angle_maps[camera_angle][metric_name][angle_value] = total_time
        
        # Convert to regular dict
        result = {
            camera: {
                metric: dict(angles)
                for metric, angles in metrics.items()
            }
            for camera, metrics in angle_maps.items()
        }
        
        logger.log_engine("Angle Maps Built", {
            "session_id": session_id,
            "cameras": list(result.keys()),
            "total_metrics": sum(len(metrics) for metrics in result.values())
        })
        
        return result
        
    except Exception as e:
        logger.log_error("Angle Map Build Failed", {
            "session_id": session_id,
            "error": str(e)
        })
        return {}


def analyze_angle_distribution(angle_time_map: Dict[int, float], 
                               metric_ranges: Dict[str, Tuple[float, float]]) -> Dict:
    """
    Analyze distribution of angles and compute risk metrics
    
    Args:
        angle_time_map: {angle_int: time_seconds}
        metric_ranges: good/warning/bad ranges from config
        
    Returns:
        Dict with distribution stats and risk score
    """
    if not angle_time_map:
        return {"risk_percent": 0, "status": "No data", "time_good_min": 0, 
                "time_warning_min": 0, "time_bad_min": 0}
    
    # Classify time in each band
    time_by_class = {"good": 0.0, "warning": 0.0, "bad": 0.0}
    total_time = 0.0
    
    for angle_int, time_sec in angle_time_map.items():
        total_time += time_sec
        
        # Classify this angle value
        angle_float = float(angle_int)
        classified = False
        
        for level, (low, high) in metric_ranges.items():
            if low <= angle_float <= high:
                time_by_class[level] += time_sec
                classified = True
                break
        
        if not classified:
            # Default to bad if outside all defined ranges
            time_by_class["bad"] += time_sec
    
    # Convert seconds to minutes
    time_good_min = time_by_class["good"] / 60.0
    time_warning_min = time_by_class["warning"] / 60.0
    time_bad_min = time_by_class["bad"] / 60.0
    total_time_min = total_time / 60.0
    
    # Calculate weighted risk score using Approach 1 algorithm
    if total_time_min == 0:
        risk_percent = 0
    else:
        final_score = 0.0
        for level, time_min in [("good", time_good_min), ("warning", time_warning_min), ("bad", time_bad_min)]:
            band_start, band_end = config.SCORE_BANDS[level]
            band_width = band_end - band_start
            time_percent = time_min / total_time_min
            score_inside_band = band_start + (time_percent * band_width)
            final_score += score_inside_band * time_min
        
        risk_percent = round(final_score / total_time_min)
    
    return {
        "risk_percent": risk_percent,
        "status": posture_status(risk_percent),
        "time_good_min": round(time_good_min, 2),
        "time_warning_min": round(time_warning_min, 2),
        "time_bad_min": round(time_bad_min, 2),
        "total_time_min": round(total_time_min, 2),
        "unique_angles": len(angle_time_map),
        "angle_range": [min(angle_time_map.keys()), max(angle_time_map.keys())] if angle_time_map else [0, 0]
    }


def score_session(session_id: int) -> Dict:
    """
    Main scoring function - processes angle-time maps and calculates risk scores
    
    Args:
        session_id: Session ID
        
    Returns:
        Dict with scoring results
    """
    try:
        logger.log_engine("Scoring Started", {"session_id": session_id})
        
        # Get session data to find user_id
        conn = get_connection()
        query = select(sessions_table).where(sessions_table.c.id == session_id)
        session = conn.execute(query).fetchone()
        conn.close()
        
        if not session:
            logger.log_error("Session Not Found", {"session_id": session_id})
            return {}
        
        user_id = session[1]  # user_id is column index 1
        
        # Delete old results to prevent duplicates (if re-scoring)
        conn = get_connection()
        delete_query = delete(posture_results_table).where(
            posture_results_table.c.session_id == session_id
        )
        delete_result = conn.execute(delete_query)
        conn.commit()
        conn.close()
        
        if delete_result.rowcount > 0:
            logger.log_warning("Deleted Old Results", {
                "session_id": session_id,
                "rows_deleted": delete_result.rowcount,
                "reason": "Re-scoring session"
            })
        
        # Step 1: Build angle-time maps from accumulation table
        angle_maps = build_angle_time_maps(session_id)
        
        if not angle_maps:
            logger.log_warning("No Angle Data", {"session_id": session_id})
            return {}
        
        # Step 2: Analyze each metric's distribution and calculate risk
        results = {}
        
        for camera_angle, metrics in angle_maps.items():
            view_key = camera_angle.upper()
            
            if view_key not in config.SESSION_CONFIG:
                continue
            
            for metric_name, angle_time_map in metrics.items():
                # Get metric configuration
                metric_config = config.SESSION_CONFIG[view_key]["metrics"].get(metric_name)
                
                if not metric_config:
                    logger.log_warning("Unknown Metric", {
                        "metric": metric_name,
                        "view": view_key
                    })
                    continue
                
                # Analyze distribution
                analysis = analyze_angle_distribution(
                    angle_time_map,
                    metric_config["ranges"]
                )
                
                metric_key = f"{view_key}_{metric_name}"
                results[metric_key] = {
                    "metric": metric_name.replace("_", " "),
                    **analysis
                }
                
                # Insert into database
                conn = get_connection()
                insert_query = insert(posture_results_table).values(
                    session_id=session_id,
                    user_id=user_id,
                    metric_name=metric_key,
                    risk_percent=analysis["risk_percent"],
                    status=analysis["status"],
                    time_good_min=analysis["time_good_min"],
                    time_warning_min=analysis["time_warning_min"],
                    time_bad_min=analysis["time_bad_min"]
                )
                conn.execute(insert_query)
                conn.commit()
                conn.close()
                
                logger.log_engine(f"Metric Scored: {metric_key}", {
                    "risk_percent": analysis["risk_percent"],
                    "status": analysis["status"],
                    "unique_angles": analysis["unique_angles"],
                    "angle_range": analysis["angle_range"]
                })
        
        # Step 3: Calculate overall session metrics
        if results:
            all_scores = [m["risk_percent"] for m in results.values()]
            average_score = sum(all_scores) / len(all_scores)
            
            worst_metric_key = max(results.keys(), key=lambda k: results[k]["risk_percent"])
            worst_metric_data = results[worst_metric_key]
            
            results["__OVERALL__"] = {
                "metric": "overall session posture",
                "average_risk_percent": round(average_score),
                "worst_metric": worst_metric_key,
                "worst_metric_risk_percent": worst_metric_data["risk_percent"],
                "overall_status": posture_status(average_score),
                "total_metrics_evaluated": len(results) - 1
            }
            
            # Update session status to completed
            conn = get_connection()
            update_query = update(sessions_table).where(
                sessions_table.c.id == session_id
            ).values(
                status="completed",
                current_phase="completed"
            )
            conn.execute(update_query)
            conn.commit()
            conn.close()
            
            logger.log_success("Scoring Complete", {
                "session_id": session_id,
                "avg_risk": f"{average_score:.0f}%",
                "worst_metric": worst_metric_key,
                "total_metrics": len(results) - 1
            })
            
            # Step 4: Trigger recommendation generation
            try:
                logger.log_engine("Triggering Recommendation", {"session_id": session_id})
                recommendation_engine.generate_recommendation(
                    session_id=session_id,
                    user_id=user_id,
                    scoring_results=results,
                    angle_maps=angle_maps  # Pass raw angle-time maps to AI
                )
            except Exception as rec_err:
                logger.log_error("Recommendation Failed", {
                    "session_id": session_id,
                    "error": str(rec_err)
                })
        
        return results
        
    except Exception as e:
        logger.log_error("Scoring Failed", {
            "session_id": session_id,
            "error": str(e)
        })
        return {}


def get_session_results(session_id: int) -> List[Dict]:
    """
    Fetch scoring results from database
    
    Args:
        session_id: Session ID
        
    Returns:
        List of result dicts
    """
    try:
        conn = get_connection()
        
        query = select(posture_results_table).where(
            posture_results_table.c.session_id == session_id
        )
        
        results = conn.execute(query).fetchall()
        conn.close()
        
        return [dict(row._mapping) for row in results]
        
    except Exception as e:
        logger.log_error("Results Fetch Failed", {
            "session_id": session_id,
            "error": str(e)
        })
        return []
