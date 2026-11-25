from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from backend.app.models.models import FollowUpStatus, PriorityLevel


class FollowUpCreate(BaseModel):
    lead_id: Optional[int] = None
    assigned_user_id: Optional[int] = None
    follow_up_type: str = "Call"
    purpose: str
    due_date: datetime
    priority: PriorityLevel = PriorityLevel.MEDIUM
    notes: Optional[str] = ""


class FollowUpUpdate(BaseModel):
    follow_up_type: Optional[str] = None
    purpose: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[PriorityLevel] = None
    status: Optional[FollowUpStatus] = None
    notes: Optional[str] = None
    assigned_user_id: Optional[int] = None


class FollowUpComplete(BaseModel):
    completion_outcome: str
    notes: Optional[str] = ""
    schedule_next: bool = False
    next_purpose: Optional[str] = None
    next_due_date: Optional[datetime] = None


class FollowUpOut(BaseModel):
    id: int
    company_id: int
    lead_id: Optional[int] = None
    lead_name: Optional[str] = None
    lead_phone: Optional[str] = None
    assigned_user_id: int
    assigned_user_name: Optional[str] = None
    created_by_id: Optional[int] = None
    created_by_name: Optional[str] = None
    team_id: Optional[int] = None
    follow_up_type: str
    purpose: str
    due_date: datetime
    priority: PriorityLevel
    status: FollowUpStatus
    notes: str
    completion_outcome: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    is_overdue: bool = False
    is_due_today: bool = False

    class Config:
        from_attributes = True


class FollowUpStats(BaseModel):
    total: int
    overdue: int
    due_today: int
    upcoming: int
    completed: int


class FollowUpBriefing(BaseModel):
    greeting: str
    cairo_time: str
    overdue_count: int
    due_today_count: int
    earliest_task_time: Optional[str] = None
    attention_summary: str
    actionable_items: List[str] = []


class FollowUpPaginatedResponse(BaseModel):
    items: List[FollowUpOut]
    total: int
    page: int
    limit: int
