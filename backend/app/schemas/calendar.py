from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class UnifiedCalendarEvent(BaseModel):
    id: str  # "appt-{id}" or "task-{id}"
    original_id: int
    source_type: str  # "APPOINTMENT" or "TASK"
    event_type: str  # "Task", "Phone Call", "Office Meeting", "Property Visit", "Client Meeting"
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    lead_id: Optional[int] = None
    lead_name: Optional[str] = None
    lead_phone: Optional[str] = None
    assigned_user_id: int
    assigned_user_name: str
    location: Optional[str] = None
    priority: Optional[str] = None
    status: str
    has_conflict: bool = False
    conflict_notes: Optional[str] = None
    color: str

    model_config = ConfigDict(from_attributes=True)


class CalendarDailyBriefing(BaseModel):
    cairo_greeting: str
    selected_date: str
    total_events: int
    appointments_count: int
    tasks_count: int
    overdue_count: int
    due_today_count: int
    earliest_event_time: Optional[str] = None
    conflicts_count: int
    summary_text: str
    attention_items: List[str] = []

