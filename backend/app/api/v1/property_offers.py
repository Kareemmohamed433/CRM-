"""
Property Offers & WhatsApp AI Sharing API endpoints.
Enforces multi-tenant isolation, RBAC, accurate persistence, and click-to-chat generation.
"""

import urllib.parse
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user
from backend.app.models.models import (
    PropertyOffer, PropertyOfferStatus, Property, Lead, User, Activity, ActivityType
)
from backend.app.schemas.property_offer import (
    PropertyOfferCreate, PropertyOfferOut, PropertyOfferFeedback,
    PropertyMessageRequest, PropertyMessageResponse
)
from backend.app.services.ai_tools.offer_tools import prepare_property_message

router = APIRouter(tags=["Property Offers & WhatsApp Sharing"])


def format_whatsapp_phone(raw_phone: str) -> str:
    """Formats phone into standard international WhatsApp MSISDN e.g. 201012345678."""
    digits = "".join([c for c in raw_phone if c.isdigit()])
    if digits.startswith("0020"):
        return digits[2:]
    if digits.startswith("20"):
        return digits
    if digits.startswith("01") and len(digits) == 11:
        return f"2{digits}"
    return digits


@router.post("/leads/{lead_id}/property-offers", response_model=PropertyOfferOut)
def create_lead_property_offer(
    lead_id: int,
    offer_in: PropertyOfferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.company_id == current_user.company_id
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    prop = db.query(Property).filter(
        Property.id == offer_in.property_id,
        Property.company_id == current_user.company_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property unit not found")

    # Generate message if not provided
    msg_text = offer_in.message_text
    if not msg_text:
        tool_res = prepare_property_message(
            db, current_user,
            {"customer_id": lead.id, "property_id": prop.id, "custom_price": offer_in.custom_price}
        )
        if tool_res.success and tool_res.data:
            msg_text = tool_res.data.get("message_text")

    offer = PropertyOffer(
        company_id=current_user.company_id,
        lead_id=lead.id,
        property_id=prop.id,
        created_by_id=current_user.id,
        status=PropertyOfferStatus.PREPARED,
        custom_price=offer_in.custom_price or prop.total_price,
        message_text=msg_text or "",
        shared_via="WHATSAPP"
    )
    db.add(offer)

    # Activity log
    act = Activity(
        company_id=current_user.company_id,
        lead_id=lead.id,
        property_id=prop.id,
        user_id=current_user.id,
        activity_type=ActivityType.OFFER_SENT,
        summary=f"تجهيز عرض عقاري للوحدة {prop.unit_number} بمشروع {prop.project.name if prop.project else ''}"
    )
    db.add(act)
    db.commit()
    db.refresh(offer)

    img_urls = [img.image_url for img in prop.images]

    return PropertyOfferOut(
        id=offer.id,
        company_id=offer.company_id,
        lead_id=lead.id,
        lead_name=lead.full_name,
        lead_phone=lead.phone,
        property_id=prop.id,
        property_unit=prop.unit_number,
        property_price=prop.total_price,
        property_location=prop.location,
        project_name=prop.project.name if prop.project else "",
        created_by_id=current_user.id,
        created_by_name=current_user.full_name,
        status=offer.status,
        custom_price=offer.custom_price,
        message_text=offer.message_text,
        shared_via=offer.shared_via,
        shared_at=offer.shared_at.isoformat() if offer.shared_at else None,
        customer_feedback=offer.customer_feedback,
        feedback_recorded_at=offer.feedback_recorded_at.isoformat() if offer.feedback_recorded_at else None,
        created_at=offer.created_at.isoformat(),
        property_images=img_urls
    )


@router.get("/leads/{lead_id}/property-offers", response_model=List[PropertyOfferOut])
def list_lead_property_offers(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.company_id == current_user.company_id
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    offers = db.query(PropertyOffer).filter(
        PropertyOffer.lead_id == lead_id,
        PropertyOffer.company_id == current_user.company_id
    ).order_by(desc(PropertyOffer.created_at)).all()

    results = []
    for o in offers:
        prop = o.property
        results.append(PropertyOfferOut(
            id=o.id,
            company_id=o.company_id,
            lead_id=lead.id,
            lead_name=lead.full_name,
            lead_phone=lead.phone,
            property_id=o.property_id,
            property_unit=prop.unit_number if prop else "",
            property_price=prop.total_price if prop else 0,
            property_location=prop.location if prop else "",
            project_name=(prop.project.name if prop and prop.project else ""),
            created_by_id=o.created_by_id,
            created_by_name=o.created_by.full_name if o.created_by else "",
            status=o.status,
            custom_price=o.custom_price,
            message_text=o.message_text,
            shared_via=o.shared_via,
            shared_at=o.shared_at.isoformat() if o.shared_at else None,
            customer_feedback=o.customer_feedback,
            feedback_recorded_at=o.feedback_recorded_at.isoformat() if o.feedback_recorded_at else None,
            created_at=o.created_at.isoformat(),
            property_images=[img.image_url for img in prop.images] if prop else []
        ))
    return results


@router.post("/property-offers/{offer_id}/confirm-shared")
def confirm_offer_shared_on_whatsapp(
    offer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Called ONLY when the employee explicitly confirms having sent the WhatsApp offer.
    Transitions status from PREPARED to SHARED.
    """
    offer = db.query(PropertyOffer).filter(
        PropertyOffer.id == offer_id,
        PropertyOffer.company_id == current_user.company_id
    ).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Property offer not found")

    offer.status = PropertyOfferStatus.SHARED
    offer.shared_at = datetime.utcnow()

    # Log activity
    act = Activity(
        company_id=current_user.company_id,
        lead_id=offer.lead_id,
        property_id=offer.property_id,
        user_id=current_user.id,
        activity_type=ActivityType.WHATSAPP,
        summary=f"تم إرسال العرض العقاري رقم #{offer.id} للعميل عبر الواتساب بنجاح.",
        outcome="SHARED"
    )
    db.add(act)
    db.commit()

    return {
        "status": "success",
        "offer_id": offer.id,
        "offer_status": offer.status.value,
        "shared_at": offer.shared_at.isoformat()
    }


@router.post("/property-offers/{offer_id}/feedback")
def record_property_offer_feedback(
    offer_id: int,
    feedback_in: PropertyOfferFeedback,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    offer = db.query(PropertyOffer).filter(
        PropertyOffer.id == offer_id,
        PropertyOffer.company_id == current_user.company_id
    ).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Property offer not found")

    offer.customer_feedback = feedback_in.feedback
    offer.feedback_recorded_at = datetime.utcnow()

    if feedback_in.status and feedback_in.status in PropertyOfferStatus.__members__:
        offer.status = PropertyOfferStatus[feedback_in.status]

    act = Activity(
        company_id=current_user.company_id,
        lead_id=offer.lead_id,
        property_id=offer.property_id,
        user_id=current_user.id,
        activity_type=ActivityType.NOTE,
        summary=f"تسجيل رد فعل العميل على العرض #{offer.id}: {feedback_in.feedback}",
        outcome=offer.status.value
    )
    db.add(act)
    db.commit()

    return {
        "status": "success",
        "offer_id": offer.id,
        "feedback": offer.customer_feedback,
        "offer_status": offer.status.value
    }


@router.post("/ai/property-message", response_model=PropertyMessageResponse)
def generate_ai_property_whatsapp_message(
    req: PropertyMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generates personalized Egyptian Arabic WhatsApp pitch text, builds safe click-to-chat link,
    and returns property images for manual employee attachment.
    """
    lead = db.query(Lead).filter(
        Lead.id == req.customer_id,
        Lead.company_id == current_user.company_id
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Customer not found")

    prop = db.query(Property).filter(
        Property.id == req.property_id,
        Property.company_id == current_user.company_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property unit not found")

    tool_res = prepare_property_message(
        db, current_user,
        {"customer_id": lead.id, "property_id": prop.id, "custom_price": req.custom_price}
    )
    if not tool_res.success or not tool_res.data:
        raise HTTPException(status_code=500, detail="Failed generating property message")

    msg_text = tool_res.data.get("message_text", "")
    formatted_phone = format_whatsapp_phone(lead.phone)
    encoded_text = urllib.parse.quote(msg_text)
    wa_url = f"https://wa.me/{formatted_phone}?text={encoded_text}"

    img_urls = [img.image_url for img in prop.images]

    return PropertyMessageResponse(
        customer_id=lead.id,
        customer_name=lead.full_name,
        customer_phone=lead.phone,
        property_id=prop.id,
        property_unit=prop.unit_number,
        message_text=msg_text,
        whatsapp_url=wa_url,
        property_images=img_urls
    )

