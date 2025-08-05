from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.schedule_event import ScheduleEventType


class ScheduleEventResponse(BaseModel):
    id: int
    job_id: str
    job_name: str
    event_type: ScheduleEventType
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScheduleEventStats(BaseModel):
    total_events: int
    success_count: int
    error_count: int
    missed_count: int
    success_rate: float
