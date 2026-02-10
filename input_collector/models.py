from pydantic import BaseModel
from typing import Dict, Any

class FrameInput(BaseModel):
    scan_id: str
    camera_angle: str
    is_calibrated: bool
    data: Dict[str, Any]
