"""
Integration tests for NEXORA CRM V2:
- Property Image Storage & Validation
- Property Offers & AI WhatsApp Sharing Flow
- Customer Timeline Aggregation
- Multi-Tenant Isolation & RBAC
"""

import io
import pytest
from backend.app.models.models import Property, Lead, PropertyOfferStatus, PropertyStatus, User


def test_property_image_validation_and_lifecycle(client, manager_token, agent1_token, db_session):
    # Find a test property
    prop = db_session.query(Property).filter(Property.company_id == 1).first()
    assert prop is not None, "A test property must exist"

    headers_manager = {"Authorization": f"Bearer {manager_token}"}
    headers_agent = {"Authorization": f"Bearer {agent1_token}"}

    # 1. Non-manager/agent should be forbidden from uploading property images
    res_agent = client.post(
        f"/api/v1/properties/{prop.id}/images",
        headers=headers_agent,
        files={"file": ("test.png", b"\x89PNG\r\n\x1a\nfake", "image/png")}
    )
    assert res_agent.status_code == 403

    # 2. Upload invalid extension (.exe)
    res_bad_ext = client.post(
        f"/api/v1/properties/{prop.id}/images",
        headers=headers_manager,
        files={"file": ("malicious.exe", b"MZexecutable", "application/octet-stream")}
    )
    assert res_bad_ext.status_code == 400
    assert "Invalid file extension" in res_bad_ext.json()["detail"]

    # 3. Upload invalid magic bytes (.png filename but fake text bytes)
    res_bad_magic = client.post(
        f"/api/v1/properties/{prop.id}/images",
        headers=headers_manager,
        files={"file": ("fake.png", b"Hello World not a png", "image/png")}
    )
    assert res_bad_magic.status_code == 400
    assert "Corrupted image file or unsupported image binary format" in res_bad_magic.json()["detail"]

    # 4. Successful upload of valid PNG
    valid_png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    res_ok1 = client.post(
        f"/api/v1/properties/{prop.id}/images",
        headers=headers_manager,
        files={"file": ("living_room.png", valid_png_bytes, "image/png")},
        data={"caption": "الريسبشن الرئيسي", "is_primary": "true"}
    )
    assert res_ok1.status_code == 200, res_ok1.text
    img1 = res_ok1.json()
    assert img1["caption"] == "الريسبشن الرئيسي"
    assert img1["is_primary"] is True
    assert img1["image_url"].startswith("/uploads/properties/")

    # 5. Upload second image (JPEG magic bytes \xff\xd8\xff)
    valid_jpg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 64
    res_ok2 = client.post(
        f"/api/v1/properties/{prop.id}/images",
        headers=headers_manager,
        files={"file": ("view.jpg", valid_jpg_bytes, "image/jpeg")},
        data={"caption": "إطلالة مميزة", "is_primary": "true"}
    )
    assert res_ok2.status_code == 200, res_ok2.text
    img2 = res_ok2.json()
    assert img2["is_primary"] is True

    # 6. List images and verify primary toggle
    res_list = client.get(f"/api/v1/properties/{prop.id}/images", headers=headers_manager)
    assert res_list.status_code == 200
    images = res_list.json()
    assert len(images) >= 2
    # img2 should be primary now, img1 should no longer be primary
    found_img1 = next(im for im in images if im["id"] == img1["id"])
    found_img2 = next(im for im in images if im["id"] == img2["id"])
    assert found_img2["is_primary"] is True
    assert found_img1["is_primary"] is False

    # 7. Set img1 back to primary
    res_set_primary = client.put(
        f"/api/v1/properties/{prop.id}/images/{img1['id']}/primary",
        headers=headers_manager
    )
    assert res_set_primary.status_code == 200

    # 8. Delete uploaded test images
    for im in [img1, img2]:
        res_del = client.delete(f"/api/v1/properties/{prop.id}/images/{im['id']}", headers=headers_manager)
        assert res_del.status_code == 200


def test_property_offers_and_whatsapp_flow(client, agent1_token, db_session):
    headers = {"Authorization": f"Bearer {agent1_token}"}

    # Find a test lead and property
    lead = db_session.query(Lead).filter(Lead.company_id == 1, Lead.phone.isnot(None)).first()
    assert lead is not None
    prop = db_session.query(Property).filter(Property.company_id == 1).first()
    assert prop is not None

    # 1. Generate AI WhatsApp message
    res_msg = client.post(
        "/api/v1/ai/property-message",
        headers=headers,
        json={
            "customer_id": lead.id,
            "property_id": prop.id,
            "custom_price": 5500000.0
        }
    )
    assert res_msg.status_code == 200, res_msg.text
    msg_data = res_msg.json()
    assert msg_data["customer_id"] == lead.id
    assert msg_data["property_id"] == prop.id
    assert "https://wa.me/" in msg_data["whatsapp_url"]
    assert len(msg_data["message_text"]) > 20
    # Pitch should contain customer first name and unit number
    first_name = lead.full_name.split()[0]
    assert first_name in msg_data["message_text"]

    # 2. Create property offer
    res_create = client.post(
        f"/api/v1/leads/{lead.id}/property-offers",
        headers=headers,
        json={
            "property_id": prop.id,
            "custom_price": 5500000.0,
            "message_text": msg_data["message_text"]
        }
    )
    assert res_create.status_code == 200, res_create.text
    offer = res_create.json()
    assert offer["status"] == "PREPARED"
    assert offer["lead_id"] == lead.id
    assert offer["property_id"] == prop.id
    assert offer["custom_price"] == 5500000.0

    # 3. List offers for lead
    res_list = client.get(f"/api/v1/leads/{lead.id}/property-offers", headers=headers)
    assert res_list.status_code == 200
    offers = res_list.json()
    assert any(o["id"] == offer["id"] for o in offers)

    # 4. Confirm offer was shared on WhatsApp
    res_confirm = client.post(
        f"/api/v1/property-offers/{offer['id']}/confirm-shared",
        headers=headers
    )
    assert res_confirm.status_code == 200, res_confirm.text
    confirmed = res_confirm.json()
    assert confirmed["offer_status"] == "SHARED"
    assert confirmed["shared_at"] is not None

    # 5. Record customer feedback
    res_feedback = client.post(
        f"/api/v1/property-offers/{offer['id']}/feedback",
        headers=headers,
        json={
            "status": "ACCEPTED",
            "feedback": "العميل وافق على السعر ومتحمس للمعاينة السبت القادم"
        }
    )
    assert res_feedback.status_code == 200, res_feedback.text
    feedback_data = res_feedback.json()
    assert feedback_data["offer_status"] == "ACCEPTED"
    assert "السبت القادم" in feedback_data["feedback"]


def test_customer_timeline_endpoint(client, agent1_token, db_session):
    headers = {"Authorization": f"Bearer {agent1_token}"}
    lead = db_session.query(Lead).filter(Lead.company_id == 1).first()
    assert lead is not None

    res = client.get(f"/api/v1/leads/{lead.id}/timeline", headers=headers)
    assert res.status_code == 200, res.text
    timeline = res.json()
    assert isinstance(timeline, list)
    assert len(timeline) > 0, "Timeline should contain events for seeded lead"

    # Verify event structure
    for item in timeline:
        assert "id" in item
        assert "type" in item
        assert "title" in item
        assert "timestamp" in item
        assert item["type"] in ["ACTIVITY", "APPOINTMENT", "FOLLOWUP", "PROPERTY_OFFER", "ASSIGNMENT"]

    # Verify chronological descending order
    timestamps = [item["timestamp"] for item in timeline]
    assert timestamps == sorted(timestamps, reverse=True), "Timeline must be in descending order"


def test_tenant_isolation_v2_features(client, horizon_token, agent1_token, db_session):
    headers_nexora = {"Authorization": f"Bearer {agent1_token}"}
    headers_horizon = {"Authorization": f"Bearer {horizon_token}"}

    # Find a Nexora lead and property (company_id = 1)
    nexora_lead = db_session.query(Lead).filter(Lead.company_id == 1).first()
    nexora_prop = db_session.query(Property).filter(Property.company_id == 1).first()
    assert nexora_lead is not None
    assert nexora_prop is not None

    # Horizon user (company_id = 2) attempts to access Nexora lead timeline -> 404
    res_tl = client.get(f"/api/v1/leads/{nexora_lead.id}/timeline", headers=headers_horizon)
    assert res_tl.status_code == 404

    # Horizon user attempts to access Nexora property offers -> 404
    res_offers = client.get(f"/api/v1/leads/{nexora_lead.id}/property-offers", headers=headers_horizon)
    assert res_offers.status_code == 404

    # Horizon user attempts to generate AI message for Nexora lead/prop -> 404
    res_msg = client.post(
        "/api/v1/ai/property-message",
        headers=headers_horizon,
        json={"customer_id": nexora_lead.id, "property_id": nexora_prop.id}
    )
    assert res_msg.status_code == 404
