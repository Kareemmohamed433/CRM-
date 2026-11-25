from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from backend.app.models.models import TransferStatus


class TransferRequestCreate(BaseModel):
    lead_id: int
    requested_owner_id: int
    reason: str
    notes: Optional[str] = ""


class TransferReviewRequest(BaseModel):
    approved: bool
    review_notes: Optional[str] = ""


class TransferRequestOut(BaseModel):
    id: int
    company_id: int
    lead_id: int
    lead_name: Optional[str] = None
    current_owner_id: Optional[int] = None
    current_owner_name: Optional[str] = None
    requested_owner_id: int
    requested_owner_name: Optional[str] = None
    requested_by_id: int
    requested_by_name: Optional[str] = None
    reason: str
    notes: str
    status: TransferStatus
    reviewer_id: Optional[int] = None
    reviewer_name: Optional[str] = None
    review_notes: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AssignmentHistoryOut(BaseModel):
    id: int
    lead_id: int
    previous_agent_id: Optional[int] = None
    previous_agent_name: Optional[str] = None
    new_agent_id: int
    new_agent_name: Optional[str] = None
    changed_by_id: int
    changed_by_name: Optional[str] = None
    reason: str
    created_at: datetime

    class Config:
        from_attributes = True
