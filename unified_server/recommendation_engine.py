# Recommendation Engine - Groq AI Integration (Procedural)
import json
from typing import Dict, List, Optional
from groq import Groq
from sqlalchemy import select, insert, delete
from database import recommendations_table, posture_results_table, users_table, get_connection
import config
import logger


def build_groq_prompt(user_profile: Dict, results: Dict, angle_maps: Optional[Dict] = None, trends: Optional[Dict] = None) -> str:
    """
    Build prompt for Groq AI with angle-time map data
    
    Args:
        user_profile: User age, height, weight
        results: Scoring results
        angle_maps: Angle-time distribution maps {camera: {metric: {angle: time}}}
        trends: Optional trend data
        
    Returns:
        Formatted prompt string
    """
    # Extract dominant issue
    metric_scores = {k: v["risk_percent"] for k, v in results.items() if k != "__OVERALL__"}
    if not metric_scores:
        dominant_metric = "general posture"
        dominant_score = 0
    else:
        dominant_metric = max(metric_scores, key=metric_scores.get)
        dominant_score = metric_scores[dominant_metric]
    
    # Build prompt
    prompt = f"""You are a posture health expert. Generate a personalized posture improvement recommendation.

USER PROFILE:
- Age: {user_profile.get('age', 'Unknown')} years
- Height: {user_profile.get('height_cm', 'Unknown')} cm
- Weight: {user_profile.get('weight_kg', 'Unknown')} kg

POSTURE ANALYSIS RESULTS:
- Dominant Issue: {dominant_metric} ({dominant_score}% risk)
- Overall Risk: {results.get('__OVERALL__', {}).get('average_risk_percent', 0)}%

DETAILED METRICS:
"""
    
    for metric_key, data in results.items():
        if metric_key == "__OVERALL__":
            continue
        prompt += f"- {data['metric']}: {data['risk_percent']}% risk ({data['status']})\n"
        if 'angle_range' in data:
            prompt += f"  Range: {data['angle_range'][0]}° to {data['angle_range'][1]}° ({data.get('unique_angles', 0)} unique values)\n"
    
    # Add angle distribution insights
    if angle_maps:
        prompt += "\nANGLE DISTRIBUTION DETAILS:\n"
        for camera, metrics in angle_maps.items():
            for metric_name, angle_time in metrics.items():
                # Find most common angles
                sorted_angles = sorted(angle_time.items(), key=lambda x: x[1], reverse=True)[:3]
                if sorted_angles:
                    prompt += f"- {camera} {metric_name}: Most common angles are "
                    prompt += ", ".join([f"{angle}° ({time:.1f}s)" for angle, time in sorted_angles])
                    prompt += "\n"
    
    if trends:
        prompt += "\nTRENDS:\n"
        for metric, trend_data in trends.items():
            prompt += f"- {metric}: {trend_data['direction']} (change: {trend_data['change']:+.1f}%)\n"
    
    prompt += """
Generate a response in the following JSON format:
{
    "priority": "HIGH" or "MEDIUM" or "LOW",
    "message": "Brief explanation of main issue with specific angle insights",
    "actions": ["action 1", "action 2", "action 3"]
}

Be specific, actionable, and personalized based on the user's profile, metrics, and angle distributions.
"""
    
    return prompt


def call_groq_api(prompt: str) -> Optional[Dict]:
    """
    Call Groq API for recommendation generation
    
    Args:
        prompt: Formatted prompt string
        
    Returns:
        Parsed JSON response or None if failed
    """
    if not config.ENABLE_AI:
        logger.log_warning("AI Disabled", {"reason": "ENABLE_AI=false in config"})
        return None
    
    try:
        client = Groq(api_key=config.GROQ_API_KEY)
        
        logger.log_ai("Calling Groq API", {
            "model": config.GROQ_MODEL,
            "prompt_length": len(prompt)
        })
        
        response = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a posture health expert providing personalized recommendations."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        content = response.choices[0].message.content
        
        # Try to extract JSON from response
        try:
            # Find JSON in response
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                parsed = json.loads(json_str)
                
                logger.log_ai("Groq API Success", {
                    "priority": parsed.get("priority"),
                    "actions_count": len(parsed.get("actions", []))
                })
                
                return parsed
            else:
                logger.log_warning("No JSON in Groq Response", {"content": content[:200]})
                return None
                
        except json.JSONDecodeError as e:
            logger.log_error("JSON Parse Failed", e, {"content": content[:200]})
            return None
        
    except Exception as e:
        logger.log_error("Groq API Failed", e)
        return None


def get_fallback_recommendation(results: Dict, dominant_metric: str) -> Dict:
    """
    Generate rule-based fallback recommendation
    
    Args:
        results: Scoring results
        dominant_metric: Worst performing metric
        
    Returns:
        Recommendation dict
    """
    dominant_score = results.get(dominant_metric, {}).get("risk_percent", 0)
    
    if dominant_score >= config.RISK_THRESHOLDS["HIGH"]:
        priority = "HIGH"
    elif dominant_score >= config.RISK_THRESHOLDS["MODERATE"]:
        priority = "MEDIUM"
    else:
        priority = "LOW"
    
    # Get base actions from rules
    rule = config.METRIC_RULES.get(dominant_metric, {})
    base_actions = rule.get("base_actions", [
        "Maintain neutral posture",
        "Take regular breaks",
        "Adjust workspace ergonomics"
    ])
    
    message = f"Posture issue detected: {rule.get('label', dominant_metric)}. Risk level: {dominant_score}%"
    
    logger.log_warning("Using Fallback Recommendation", {
        "dominant_metric": dominant_metric,
        "priority": priority
    })
    
    return {
        "priority": priority,
        "message": message,
        "actions": base_actions.copy()  # Make a copy to avoid mutation
    }


def compute_trends(session_id: int) -> Dict:
    """
    Compute trends from historical session results
    
    Args:
        session_id: Current session ID
        
    Returns:
        Trends dict
    """
    try:
        conn = get_connection()
        
        # Get user_id from current session
        from database import sessions_table
        session_query = select(sessions_table.c.user_id).where(sessions_table.c.id == session_id)
        session_result = conn.execute(session_query).first()
        
        if not session_result:
            conn.close()
            return {}
        
        user_id = session_result[0]
        
        # Get all completed sessions for this user
        sessions_query = select(sessions_table.c.id).where(
            (sessions_table.c.user_id == user_id) &
            (sessions_table.c.status == "completed")
        ).order_by(sessions_table.c.start_time.desc()).limit(5)
        
        session_ids = [row[0] for row in conn.execute(sessions_query)]
        conn.close()
        
        if len(session_ids) < 2:
            return {}  # Need at least 2 sessions for trend
        
        # Import here to avoid circular dependency
        from scoring_engine import get_session_results
        
        # Get results for these sessions
        trends = {}
        
        for sid in session_ids:
            results = get_session_results(sid)
            for result in results:
                metric_name = result["metric_name"]
                risk = result["risk_percent"]
                
                if metric_name not in trends:
                    trends[metric_name] = []
                trends[metric_name].append(risk)
        
        # Calculate trend direction
        trend_result = {}
        for metric, values in trends.items():
            if len(values) < 2:
                continue
            
            delta = values[0] - values[-1]  # Latest - oldest
            
            if delta > config.TREND_THRESHOLD:
                direction = "WORSENING"
            elif delta < -config.TREND_THRESHOLD:
                direction = "IMPROVING"
            else:
                direction = "STABLE"
            
            trend_result[metric] = {
                "direction": direction,
                "change": delta,
                "latest": values[0]
            }
        
        return trend_result
        
    except Exception as e:
        logger.log_error("Trend Calculation Failed", e, {"session_id": session_id})
        return {}


def generate_recommendation(session_id: int, user_id: int, scoring_results: Dict, angle_maps: Optional[Dict] = None) -> Dict:
    """
    Main recommendation generation function
    
    Integrates scoring results + user profile + trends + Groq AI
    
    Args:
        session_id: Session ID
        user_id: User ID
        scoring_results: Scoring results from score_session()
        angle_maps: Optional angle-time distribution maps
        
    Returns:
        Complete recommendation dict
    """
    try:
        logger.log_ai("Recommendation Started", {"session_id": session_id})
        
        # Use provided scoring_results instead of fetching
        results = scoring_results
        
        if not results:
            logger.log_warning("No Results to Recommend", {"session_id": session_id})
            return {}
        
        # Delete old recommendations to prevent duplicates (if re-generating)
        conn = get_connection()
        delete_query = delete(recommendations_table).where(
            recommendations_table.c.session_id == session_id
        )
        delete_result = conn.execute(delete_query)
        conn.commit()
        conn.close()
        
        if delete_result.rowcount > 0:
            logger.log_warning("Deleted Old Recommendations", {
                "session_id": session_id,
                "rows_deleted": delete_result.rowcount,
                "reason": "Re-generating recommendations"
            })
        
        # Step 1: Fetch user profile
        from auth import get_user_profile
        user_profile = get_user_profile(user_id)
        
        if not user_profile:
            user_profile = {"age": 28, "height_cm": 170, "weight_kg": 65}
        
        # Step 2: Compute trends
        trends = compute_trends(session_id)
        
        # Step 3: Identify dominant issue
        metric_scores = {k: v["risk_percent"] for k, v in results.items() if k != "__OVERALL__"}
        dominant_metric = max(metric_scores, key=metric_scores.get) if metric_scores else "general"
        dominant_score = metric_scores.get(dominant_metric, 0)
        
        # Determine risk level
        if dominant_score >= config.RISK_THRESHOLDS["HIGH"]:
            risk_level = "HIGH"
        elif dominant_score >= config.RISK_THRESHOLDS["MODERATE"]:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"
        
        # Step 4: Try Groq AI with angle map data
        ai_output = None
        if config.ENABLE_AI:
            prompt = build_groq_prompt(user_profile, results, angle_maps, trends)
            ai_output = call_groq_api(prompt)
        
        # Step 5: Use AI or fallback
        if ai_output:
            recommendation_data = ai_output
        else:
            recommendation_data = get_fallback_recommendation(results, dominant_metric)
        
        # Step 6: Build final recommendation
        final_recommendation = {
            "session_id": session_id,
            "user_id": user_id,
            "risk_level": risk_level,
            "dominant_issue": dominant_metric,
            "recommendation": recommendation_data
        }
        
        # Step 7: Save to database
        conn = get_connection()
        insert_query = insert(recommendations_table).values(
            session_id=session_id,
            user_id=user_id,
            recommendation_text=recommendation_data.get("message", ""),
            priority=recommendation_data.get("priority", "MEDIUM"),
            dominant_issue=dominant_metric,
            risk_level=risk_level,
            actions_json=json.dumps(recommendation_data.get("actions", []))
        )
        conn.execute(insert_query)
        conn.commit()
        conn.close()
        
        logger.log_success("Recommendation Saved", {
            "session_id": session_id,
            "priority": recommendation_data.get("priority"),
            "risk_level": risk_level
        })
        
        return final_recommendation
        
    except Exception as e:
        logger.log_error("Recommendation Generation Failed", e, {
            "session_id": session_id,
            "user_id": user_id
        })
        return {}


def get_session_recommendation(session_id: int) -> Optional[Dict]:
    """
    Fetch recommendation from database
    
    Args:
        session_id: Session ID
        
    Returns:
        Recommendation dict or None
    """
    try:
        conn = get_connection()
        
        query = select(recommendations_table).where(
            recommendations_table.c.session_id == session_id
        ).order_by(recommendations_table.c.created_at.desc())
        
        result = conn.execute(query).first()
        conn.close()
        
        if not result:
            return None
        
        rec_dict = dict(result._mapping)
        
        # Parse actions JSON
        try:
            actions = json.loads(rec_dict.get("actions_json", "[]"))
        except:
            actions = []
        
        return {
            "session_id": rec_dict["session_id"],
            "recommendation_text": rec_dict["recommendation_text"],
            "priority": rec_dict["priority"],
            "dominant_issue": rec_dict["dominant_issue"],
            "risk_level": rec_dict["risk_level"],
            "actions": actions,
            "created_at": rec_dict["created_at"].isoformat() if rec_dict.get("created_at") else None
        }
        
    except Exception as e:
        logger.log_error("Recommendation Fetch Failed", e, {"session_id": session_id})
        return None
