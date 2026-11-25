from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from backend.app.models.models import AppointmentStatus


class AppointmentCreate(BaseModel):
    lead_id: Optional[int] = None
    property_id: Optional[int] = None
    title: str
    appointment_type: str = "Property Visit"
    start_time: datetime
    end_time: datetime
    location: Optional[str] = ""
    notes: Optional[str] = ""


class AppointmentUpdate(BaseModel):
    title: Optional[str] = None
    appointment_type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[AppointmentStatus] = None


class AppointmentOut(BaseModel):
    id: int
    company_id: int
    lead_id: Optional[int] = None
    lead_name: Optional[str] = None
    property_id: Optional[int] = None
    property_unit: Optional[str] = None
    user_id: int
    user_name: Optional[str] = None
    title: str
    appointment_type: str
    start_time: datetime
    end_time: datetime
    location: str
    notes: str
    status: AppointmentStatus
    created_at: datetime

    class Config:
        from_attributes = True
