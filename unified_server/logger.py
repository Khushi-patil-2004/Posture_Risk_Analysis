# Structured Logging Module - Procedural Approach
import sys
from datetime import datetime
from typing import Any, Dict, Optional

# ANSI Color Codes for Terminal
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

# Step Prefixes with Emojis
STEP_PREFIXES = {
    "AUTH": "🔐",
    "TEAM1": "📊",
    "ENGINE": "⚙️",
    "AI": "🤖",
    "DB": "💾",
    "API": "🌐",
    "SYSTEM": "🔧",
    "ERROR": "❌",
    "SUCCESS": "✅",
    "WARNING": "⚠️"
}

# Next Step Suggestions
NEXT_STEPS = {
    "AUTH:LOGIN": "Call POST /sessions/start to begin angle streaming",
    "AUTH:REGISTER": "Call POST /auth/login to get JWT token",
    "TEAM1:START": "Frames being generated at target FPS, wait for session completion",
    "TEAM1:FRAME": "Continue monitoring, or call POST /sessions/{id}/stop to end",
    "ENGINE:FPS": "Session FPS calculated, proceeding to scoring",
    "ENGINE:SCORE": "Scoring complete, generating recommendations",
    "AI:GROQ": "Recommendation saved to database, fetch via GET /recommendations/{id}",
    "DB:INSERT": "Data persisted successfully",
    "API:REQUEST": "Processing request",
}


def get_timestamp() -> str:
    """Get formatted timestamp"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def log_step(step: str, action: str, data: Optional[Dict[str, Any]] = None, color: str = Colors.CYAN):
    """
    Log a step with structured format
    
    Args:
        step: Step category (AUTH, TEAM1, ENGINE, AI, DB, etc.)
        action: Description of the action
        data: Optional dictionary of data to display
        color: ANSI color code
    """
    prefix = STEP_PREFIXES.get(step, "🔹")
    timestamp = get_timestamp()
    
    print(f"{color}{Colors.BOLD}[{timestamp}] {prefix} [{step}]{Colors.RESET} {action}")
    
    if data:
        for key, value in data.items():
            # Truncate long values
            if isinstance(value, str) and len(value) > 100:
                value = value[:97] + "..."
            print(f"   {Colors.WHITE}├─ {key}: {value}{Colors.RESET}")
    
    # Suggest next step
    next_step_key = f"{step}:{action.split()[0].upper()}"
    if next_step_key in NEXT_STEPS:
        print(f"   {Colors.YELLOW}└─ >>> Next: {NEXT_STEPS[next_step_key]}{Colors.RESET}")
    print()  # Blank line for readability


def log_auth(action: str, data: Optional[Dict[str, Any]] = None):
    """Log authentication events"""
    log_step("AUTH", action, data, Colors.PURPLE)


def log_team1(action: str, data: Optional[Dict[str, Any]] = None):
    """Log Team 1 simulator events"""
    log_step("TEAM1", action, data, Colors.BLUE)


def log_engine(action: str, data: Optional[Dict[str, Any]] = None):
    """Log scoring engine events"""
    log_step("ENGINE", action, data, Colors.CYAN)


def log_ai(action: str, data: Optional[Dict[str, Any]] = None):
    """Log AI recommendation events"""
    log_step("AI", action, data, Colors.GREEN)


def log_db(action: str, data: Optional[Dict[str, Any]] = None):
    """Log database events"""
    log_step("DB", action, data, Colors.WHITE)


def log_api(action: str, data: Optional[Dict[str, Any]] = None):
    """Log API events"""
    log_step("API", action, data, Colors.CYAN)


def log_error(action: str, error: Exception, data: Optional[Dict[str, Any]] = None):
    """Log errors with traceback"""
    error_data = data or {}
    error_data["Error"] = str(error)
    error_data["Type"] = type(error).__name__
    log_step("ERROR", action, error_data, Colors.RED)


def log_success(action: str, data: Optional[Dict[str, Any]] = None):
    """Log success events"""
    log_step("SUCCESS", action, data, Colors.GREEN)


def log_warning(action: str, data: Optional[Dict[str, Any]] = None):
    """Log warnings"""
    log_step("WARNING", action, data, Colors.YELLOW)


def log_lifecycle(phase: str, details: str = ""):
    """
    Log major lifecycle events with clear visual separation
    
    Args:
        phase: Phase name (e.g., "STARTUP", "SESSION_START", "SESSION_END")
        details: Optional details
    """
    separator = "=" * 80
    print(f"\n{Colors.BOLD}{Colors.CYAN}{separator}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}>>> {phase} {details}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{separator}{Colors.RESET}\n")
