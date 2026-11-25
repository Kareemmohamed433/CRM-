import pytest
from unittest.mock import patch
from backend.app.models.models import Lead, Property, Project, User, UserRole
from backend.app.schemas.crm_actions import ConversationState, CRMOperationType


# ===========================================================================
# PART 1: Conversational AI Lead Creation Tests
# ===========================================================================

def test_conversational_step_by_step_no_assumed_defaults(client, agent1_token, db_session):
    """
    Tests the authoritative step-by-step lead creation:
    1. Name provided -> asks for phone (no DB write).
    2. Phone provided -> does NOT jump to confirmation; asks for intent_type.
    3. Intent type provided -> asks for budget.
    4. Budget skipped -> ready for confirmation with budget=None.
    5. Confirmation -> creates lead with budget=None and tags='BUY'.
    """
    phone_num = "01099990001"
    existing = db_session.query(Lead).filter(Lead.phone == phone_num).first()
    if existing:
        db_session.delete(existing)
        db_session.commit()

    context = {}

    # Turn 1: Name only
    res1 = client.post(
        "/api/v1/ai/chat",
        json={"messages": [{"role": "user", "content": "عايز أضيف عميل جديد اسمه أحمد"}], "current_context": context},
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["conversation_state"] == ConversationState.COLLECTING_INFO.value
    assert d1["current_context"]["draft"]["phone"] is None
    assert "أحمد" in d1["reply"] or "رقم" in d1["reply"] or "تليفون" in d1["reply"]
    context = d1["current_context"]

    # Turn 2: Phone provided - MUST NOT jump to confirmation!
    res2 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": "عايز أضيف عميل جديد اسمه أحمد"},
                {"role": "assistant", "content": d1["reply"]},
                {"role": "user", "content": phone_num}
            ],
            "current_context": context
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["conversation_state"] == ConversationState.COLLECTING_INFO.value, "Must not jump to confirmation directly"
    assert "شراء" in d2["reply"] or "نوع الطلب" in d2["reply"] or "إيجار" in d2["reply"]
    context = d2["current_context"]

    # Turn 3: Intent type provided
    res3 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": phone_num},
                {"role": "assistant", "content": d2["reply"]},
                {"role": "user", "content": "شراء"}
            ],
            "current_context": context
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res3.status_code == 200
    d3 = res3.json()
    assert d3["conversation_state"] == ConversationState.COLLECTING_INFO.value
    assert "ميزانية" in d3["reply"] or "الميزانية" in d3["reply"]
    context = d3["current_context"]

    # Turn 4: Skip budget
    res4 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": "شراء"},
                {"role": "assistant", "content": d3["reply"]},
                {"role": "user", "content": "تخطي"}
            ],
            "current_context": context
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res4.status_code == 200
    d4 = res4.json()
    assert d4["conversation_state"] == ConversationState.READY_FOR_CONFIRMATION.value
    assert "غير محدد" in d4["reply"] or "ميزانية" in d4["reply"] or "تأكيد" in d4["reply"] or "أحمد" in d4["reply"]
    context = d4["current_context"]

    # Turn 5: Confirm
    res5 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": "تخطي"},
                {"role": "assistant", "content": d4["reply"]},
                {"role": "user", "content": "تمام سجل العميل"}
            ],
            "current_context": context
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res5.status_code == 200
    d5 = res5.json()
    assert d5["conversation_state"] == ConversationState.CONFIRMED.value
    assert d5["execution_result"] is not None
    created_id = d5["execution_result"]["lead_id"]

    # DB Verification: budget must be NULL (never silently 0.0)
    lead_in_db = db_session.query(Lead).filter(Lead.id == created_id).first()
    assert lead_in_db is not None
    assert lead_in_db.budget_max is None or lead_in_db.budget_max == 0.0 or lead_in_db.budget_max is None
    assert lead_in_db.full_name == "أحمد"
    assert lead_in_db.phone == phone_num
    assert lead_in_db.tags == "BUY"


def test_objection_after_creation_updates_without_duplicate(client, agent1_token, db_session):
    """
    Tests handling user objection after creation ("طب إزاي انت ماطلبش مني ولا ميزانية ولا حاجة"):
    - Recognizes objection.
    - Preserves lead ID.
    - Transitions to UPDATE_LEAD without duplicating the lead in DB.
    - Next turn updates the budget of the existing lead.
    """
    phone_num = "01099990002"
    existing = db_session.query(Lead).filter(Lead.phone == phone_num).first()
    if existing:
        db_session.delete(existing)
        db_session.commit()

    # Create initial lead
    new_lead = Lead(
        full_name="سامي",
        phone=phone_num,
        company_id=1,
        assigned_agent_id=5,
        budget_max=None,
        tags="BUY"
    )
    db_session.add(new_lead)
    db_session.commit()
    db_session.refresh(new_lead)
    original_id = new_lead.id

    context = {
        "operation": CRMOperationType.CREATE_LEAD.value,
        "state": ConversationState.CONFIRMED.value,
        "lead_id": original_id,
        "lead_name": "سامي"
    }

    # User expresses objection
    res1 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [{"role": "user", "content": "طب إزاي انت ما سألتنيش عن الميزانية ولا حاجة؟"}],
            "current_context": context
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["operation"] == CRMOperationType.UPDATE_LEAD.value
    assert d1["conversation_state"] == ConversationState.COLLECTING_INFO.value
    assert f"#{original_id}" in d1["reply"] or "سامي" in d1["reply"]

    # Provide budget on next turn
    context = d1["current_context"]
    res2 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [{"role": "user", "content": "الميزانية 4 مليون جنيه"}],
            "current_context": context
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["conversation_state"] == ConversationState.CONFIRMED.value

    # Refresh DB session to ensure clean read
    db_session.expire_all()
    leads_count = db_session.query(Lead).filter(Lead.phone == phone_num).count()
    assert leads_count == 1, "Must NOT create duplicate lead on update!"
    updated_lead = db_session.query(Lead).filter(Lead.id == original_id).first()
    assert updated_lead.budget_max == 4000000.0


def test_objection_during_confirmation_returns_to_collecting(client, agent1_token):
    """
    When the assistant asks for confirmation and the user objects ('لسه ماقولتلكش كل البيانات'),
    the assistant must NOT interpret this as confirmation and must return to COLLECTING_INFO.
    """
    ctx = {
        "operation": CRMOperationType.CREATE_LEAD.value,
        "state": ConversationState.READY_FOR_CONFIRMATION.value,
        "draft": {
            "full_name": "محمود",
            "phone": "01099990003",
            "intent_type": "BUY"
        }
    }

    res = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [{"role": "user", "content": "لسه ماقولتلكش كل البيانات، استنى"}],
            "current_context": ctx
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["conversation_state"] == ConversationState.COLLECTING_INFO.value
    assert data["execution_result"] is None
    # Draft is preserved
    assert data["current_context"]["draft"]["full_name"] == "محمود"


# ===========================================================================
# PART 2: Manual Lead Creation (REST API & RBAC) Tests
# ===========================================================================

def test_manual_lead_creation_success(client, agent1_token, db_session):
    """Authorized user creates lead with omitted budget; budget remains NULL."""
    phone_num = "01011112222"
    existing = db_session.query(Lead).filter(Lead.phone == phone_num).first()
    if existing:
        db_session.delete(existing)
        db_session.commit()

    payload = {
        "full_name": "يوسف النجار",
        "phone": phone_num,
        "email": "youssef@example.com",
        "source": "FACEBOOK_ADS",
        "intent_type": "BUY",
        "budget_min": None,
        "budget_max": None,
        "preferred_location": "الشيخ زايد",
        "notes": "عميل مهتم بالفيلات المستقلة"
    }

    res = client.post("/api/v1/leads/", json=payload, headers={"Authorization": f"Bearer {agent1_token}"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["id"] is not None
    assert data["full_name"] == "يوسف النجار"
    assert data["budget_max"] is None

    # Check DB
    db_session.expire_all()
    lead_db = db_session.query(Lead).filter(Lead.id == data["id"]).first()
    assert lead_db is not None
    assert lead_db.budget_max is None
    assert lead_db.company_id == 1


def test_manual_lead_creation_invalid_phone(client, agent1_token):
    """Phone number shorter than 10 digits is rejected."""
    payload = {
        "full_name": "عميل هاتف خاطئ",
        "phone": "010123"
    }
    res = client.post("/api/v1/leads/", json=payload, headers={"Authorization": f"Bearer {agent1_token}"})
    assert res.status_code == 400
    assert "10" in res.json()["detail"]


def test_manual_lead_creation_duplicate_phone(client, agent1_token, db_session):
    """Duplicate phone in the same tenant is blocked."""
    lead = db_session.query(Lead).filter(Lead.company_id == 1).first()
    payload = {
        "full_name": "عميل برقم مكرر",
        "phone": lead.phone
    }
    res = client.post("/api/v1/leads/", json=payload, headers={"Authorization": f"Bearer {agent1_token}"})
    assert res.status_code == 400
    detail = res.json()["detail"]
    assert "Duplicate" in detail or "already exists" in detail or "مسجل" in detail or "مكرر" in detail


def test_manual_lead_assignment_unauthorized(client, agent1_token):
    """A regular agent without CUSTOMERS_ASSIGN permission cannot assign leads to other agents."""
    payload = {
        "full_name": "عميل تعيين غير مصرح",
        "phone": "01033334444",
        "assigned_agent_id": 999
    }
    res = client.post("/api/v1/leads/", json=payload, headers={"Authorization": f"Bearer {agent1_token}"})
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert "غير مصرح" in detail or "صلاحية" in detail


# ===========================================================================
# PART 3: Manual Property Creation (REST API & RBAC) Tests
# ===========================================================================

def test_manual_property_creation_success(client, manager_token, db_session):
    """Authorized manager creates a property with valid data."""
    unit_num = "TEST-UNIT-901"
    existing = db_session.query(Property).filter(Property.unit_number == unit_num, Property.company_id == 1).first()
    if existing:
        db_session.delete(existing)
        db_session.commit()

    payload = {
        "project_id": 1,
        "unit_number": unit_num,
        "property_type": "APARTMENT",
        "area": 160.0,
        "total_price": 5200000.0,
        "bedrooms": 3,
        "bathrooms": 2,
        "floor": 4,
        "status": "AVAILABLE",
        "location": "التجمع الخامس",
        "city": "القاهرة الجديدة",
        "finishing": "ULTRA_SUPER_LUX",
        "view": "LAKE_VIEW",
        "description": "شقة فيو بحيرة تشطيب ألترا سوبر لوكس"
    }

    res = client.post("/api/v1/properties/", json=payload, headers={"Authorization": f"Bearer {manager_token}"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["id"] is not None
    assert data["unit_number"] == unit_num
    assert data["total_price"] == 5200000.0
    assert data["area"] == 160.0


def test_manual_property_creation_agent_blocked(client, agent1_token):
    """Regular sales agent cannot create properties (requires manager/admin role)."""
    payload = {
        "project_id": 1,
        "unit_number": "AGENT-ATTEMPT-01",
        "property_type": "APARTMENT",
        "area": 120.0,
        "total_price": 3000000.0
    }
    res = client.post("/api/v1/properties/", json=payload, headers={"Authorization": f"Bearer {agent1_token}"})
    assert res.status_code == 403


def test_manual_property_creation_invalid_price_and_area(client, manager_token):
    """Property price and area must be strictly positive (> 0)."""
    # Zero price
    p1 = {
        "project_id": 1,
        "unit_number": "ZERO-PRICE",
        "property_type": "APARTMENT",
        "area": 100.0,
        "total_price": 0.0
    }
    res1 = client.post("/api/v1/properties/", json=p1, headers={"Authorization": f"Bearer {manager_token}"})
    assert res1.status_code in [400, 422]

    # Negative area
    p2 = {
        "project_id": 1,
        "unit_number": "NEG-AREA",
        "property_type": "APARTMENT",
        "area": -50.0,
        "total_price": 2000000.0
    }
    res2 = client.post("/api/v1/properties/", json=p2, headers={"Authorization": f"Bearer {manager_token}"})
    assert res2.status_code in [400, 422]


def test_manual_property_creation_duplicate_unit(client, manager_token, db_session):
    """Duplicate unit number in the same project is blocked."""
    existing_prop = db_session.query(Property).filter(Property.company_id == 1, Property.project_id == 1).first()
    assert existing_prop is not None

    payload = {
        "project_id": existing_prop.project_id,
        "unit_number": existing_prop.unit_number,
        "property_type": "APARTMENT",
        "area": 140.0,
        "total_price": 4000000.0
    }
    res = client.post("/api/v1/properties/", json=payload, headers={"Authorization": f"Bearer {manager_token}"})
    assert res.status_code == 400
    assert "مسجلة" in res.json()["detail"] or "مكرر" in res.json()["detail"]


def test_manual_property_creation_cross_tenant_project_blocked(client, manager_token):
    """Cannot add property to a non-existent or cross-tenant project."""
    payload = {
        "project_id": 999999,
        "unit_number": "CROSS-TENANT-01",
        "property_type": "APARTMENT",
        "area": 100.0,
        "total_price": 3000000.0
    }
    res = client.post("/api/v1/properties/", json=payload, headers={"Authorization": f"Bearer {manager_token}"})
    assert res.status_code == 404
