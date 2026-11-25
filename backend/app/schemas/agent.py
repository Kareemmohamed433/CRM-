from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from backend.app.models.models import UserRole


class SalesAgentProfileBase(BaseModel):
    personality_prompt: Optional[str] = "مندوب مبيعات عقاري محترف، ودود ولبق، يتحدث باللهجة المصرية الطبيعية بإيجاز واحترافية."
    preferred_voice: Optional[str] = "ar-EG-SalmaNeural"
    speaking_rate: Optional[str] = "+20%"
    working_hours_start: Optional[str] = "09:00"
    working_hours_end: Optional[str] = "18:00"
    max_active_leads: Optional[int] = 50
    is_accepting_leads: Optional[bool] = True
    monthly_target_sales: Optional[float] = 10000000.0
    target_visits_per_month: Optional[int] = 20


class SalesAgentProfileUpdate(BaseModel):
    personality_prompt: Optional[str] = None
    preferred_voice: Optional[str] = None
    speaking_rate: Optional[str] = None
    working_hours_start: Optional[str] = None
    working_hours_end: Optional[str] = None
    max_active_leads: Optional[int] = None
    is_accepting_leads: Optional[bool] = None
    monthly_target_sales: Optional[float] = None
    target_visits_per_month: Optional[int] = None


class SalesAgentProfileOut(SalesAgentProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    company_id: int
    created_at: datetime


class AgentWithStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    email: str
    full_name: str
    phone: Optional[str] = None
    role: UserRole
    is_active: bool
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    profile: Optional[SalesAgentProfileOut] = None

    # Performance stats
    total_assigned_leads: int = 0
    active_leads: int = 0
    won_leads: int = 0
    conversion_rate: float = 0.0
    completed_visits: int = 0
    overdue_followups: int = 0


class BulkLeadTransferRequest(BaseModel):
    target_agent_id: int
    lead_ids: Optional[List[int]] = None  # None = transfer all active leads
    reason: str = Field(..., min_length=3, description="Business reason for transfer")
    notes: Optional[str] = ""

