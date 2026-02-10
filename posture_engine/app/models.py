from pydantic import BaseModel
from typing import Dict, Any, List

class FrameInput(BaseModel):
    scan_id: str
    camera_angle: str
    is_calibrated: bool
    data: Dict[str, Any]


class SessionStartResponse(BaseModel):
    session_id: str
    start_time_ist: str

class SessionInput(BaseModel):
    session_id: str
    frames: List[FrameInput]

class PostureOutput(BaseModel):
    session_id: str
    results: Dict[str, Any]
