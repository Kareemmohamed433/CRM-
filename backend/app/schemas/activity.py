from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from backend.app.models.models import ActivityType


class ActivityCreate(BaseModel):
    lead_id: int
    property_id: Optional[int] = None
    activity_type: ActivityType = ActivityType.CALL
    summary: str
    outcome: Optional[str] = ""
    objection: Optional[str] = ""
    sentiment: Optional[str] = "Neutral"
    next_action: Optional[str] = ""
    next_followup_date: Optional[datetime] = None


class VisitOutcomeCreate(BaseModel):
    lead_id: int
    property_id: Optional[int] = None
    visited_at: Optional[datetime] = None
    outcome: str  # e.g., "Completed - Interested", "Completed - Rejected Unit", "No Show"
    objection: Optional[str] = ""  # "Price too high", "Down payment", "Location", "Layout"
    customer_stated_budget: Optional[float] = None
    feedback_notes: str
    suggest_alternatives: bool = True
    next_followup_date: Optional[datetime] = None


class ActivityOut(BaseModel):
    id: int
    company_id: int
    lead_id: int
    lead_name: Optional[str] = None
    property_id: Optional[int] = None
    property_unit: Optional[str] = None
    user_id: int
    user_name: Optional[str] = None
    activity_type: ActivityType
    summary: str
    outcome: Optional[str] = ""
    objection: Optional[str] = ""
    sentiment: Optional[str] = "Neutral"
    next_action: Optional[str] = ""
    next_followup_date: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
