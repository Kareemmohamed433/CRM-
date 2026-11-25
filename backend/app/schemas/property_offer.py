"""
Pydantic Schemas for Property Offers and AI WhatsApp Sharing.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from backend.app.models.models import PropertyOfferStatus


class PropertyOfferCreate(BaseModel):
    property_id: int
    custom_price: Optional[float] = None
    message_text: Optional[str] = None


class PropertyOfferOut(BaseModel):
    id: int
    company_id: int
    lead_id: int
    lead_name: Optional[str] = None
    lead_phone: Optional[str] = None
    property_id: int
    property_unit: Optional[str] = None
    property_price: Optional[float] = None
    property_location: Optional[str] = None
    project_name: Optional[str] = None
    created_by_id: Optional[int] = None
    created_by_name: Optional[str] = None
    status: PropertyOfferStatus
    custom_price: Optional[float] = None
    message_text: Optional[str] = None
    shared_via: str = "WHATSAPP"
    shared_at: Optional[str] = None
    customer_feedback: Optional[str] = None
    feedback_recorded_at: Optional[str] = None
    created_at: str
    property_images: List[str] = []

    class Config:
        from_attributes = True


class PropertyOfferFeedback(BaseModel):
    feedback: str
    status: Optional[str] = None


class PropertyMessageRequest(BaseModel):
    customer_id: int
    property_id: int
    custom_price: Optional[float] = None


class PropertyMessageResponse(BaseModel):
    customer_id: int
    customer_name: str
    customer_phone: str
    property_id: int
    property_unit: str
    message_text: str
    whatsapp_url: str
    property_images: List[str] = []

