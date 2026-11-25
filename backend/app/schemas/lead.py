from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, EmailStr
from backend.app.models.models import PipelineStage, PriorityLevel


class LeadCreate(BaseModel):
    full_name: str
    phone: str
    email: Optional[EmailStr] = None
    preferred_contact_method: str = "WhatsApp"
    source: str = "Meta Ads"
    team_id: Optional[int] = None
    assigned_agent_id: Optional[int] = None
    pipeline_stage: PipelineStage = PipelineStage.NEW
    
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    preferred_project_id: Optional[int] = None
    preferred_location: str = ""
    property_type: str = "Apartment"
    preferred_area_range: str = ""
    bedrooms: int = 0
    down_payment_budget: float = 0.0
    purchase_timeline: str = "Immediate (1 month)"
    
    notes: Optional[str] = ""
    tags: Optional[str] = ""
    do_not_contact: bool = False
    priority: PriorityLevel = PriorityLevel.MEDIUM


class LeadUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    preferred_contact_method: Optional[str] = None
    source: Optional[str] = None
    team_id: Optional[int] = None
    assigned_agent_id: Optional[int] = None
    status: Optional[str] = None
    pipeline_stage: Optional[PipelineStage] = None
    
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    preferred_project_id: Optional[int] = None
    preferred_location: Optional[str] = None
    property_type: Optional[str] = None
    preferred_area_range: Optional[str] = None
    bedrooms: Optional[int] = None
    down_payment_budget: Optional[float] = None
    purchase_timeline: Optional[str] = None
    
    notes: Optional[str] = None
    tags: Optional[str] = None
    do_not_contact: Optional[bool] = None
    priority: Optional[PriorityLevel] = None


class LeadStageUpdate(BaseModel):
    pipeline_stage: PipelineStage
    notes: Optional[str] = ""


class LeadOut(BaseModel):
    id: int
    company_id: int
    full_name: str
    phone: str
    email: Optional[str] = None
    preferred_contact_method: str
    source: str
    team_id: Optional[int] = None
    assigned_agent_id: Optional[int] = None
    assigned_agent_name: Optional[str] = None
    status: str
    pipeline_stage: PipelineStage
    
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    preferred_project_id: Optional[int] = None
    preferred_project_name: Optional[str] = None
    preferred_location: str
    property_type: str
    preferred_area_range: str
    bedrooms: int
    down_payment_budget: float
    purchase_timeline: str
    
    notes: str
    tags: str
    do_not_contact: bool
    last_contact_date: Optional[datetime] = None
    next_followup_date: Optional[datetime] = None
    priority: PriorityLevel
    score: int
    score_factors: List[Any] = []
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerTimelineItem(BaseModel):
    id: str
    type: str
    subtype: Optional[str] = None
    title: str
    description: Optional[str] = None
    timestamp: datetime
    user_name: Optional[str] = None
    status: Optional[str] = None
    metadata: Dict[str, Any] = {}

    class Config:
        from_attributes = True

