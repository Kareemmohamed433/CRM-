import pytest
from unittest.mock import patch
from sqlalchemy.exc import SQLAlchemyError

from backend.app.models.models import Lead, User, UserRole, PipelineStage
from backend.app.schemas.crm_actions import ConversationState, CRMOperationType
from backend.app.services.llm_client import safe_extract_json


# ---------------------------------------------------------------------------
# 1. Exact 5-Turn Conversational Scenario from Master Specification
# ---------------------------------------------------------------------------

def test_exact_5_turn_conversational_lead_creation(client, agent1_token, db_session):
    """
    Tests the exact 5-turn multi-turn conversation from Master Prompt Section 10:
    Turn 1: 'بص كنت عايز اضيف عميل جديد اسمه كريم'
    Turn 2: '01022957599 المصدر كان اعلان فيس بوك كان عايز حاجه ايجار الميزانيه كانت 5 مليون والمنطقة كان عايز في التجمع الخامس'
    Turn 3: 'لا لا هو كان عايز شراء'
    Turn 4: 'مش فاهم انا كنت عايز اسجل العميل ده'
    Turn 5: 'أيوه سجل'
    """
    # Clean up phone if previously exists from old test runs
    existing = db_session.query(Lead).filter(Lead.phone == "01022957599").first()
    if existing:
        db_session.delete(existing)
        db_session.commit()

    context = {}

    # ── Turn 1 ──
    res1 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [{"role": "user", "content": "بص كنت عايز اضيف عميل جديد اسمه كريم"}],
            "current_context": context
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res1.status_code == 200, res1.text
    data1 = res1.json()
    assert data1["operation"] == CRMOperationType.CREATE_LEAD.value
    assert data1["conversation_state"] == ConversationState.COLLECTING_INFO.value
    assert "كريم" in data1["reply"] or "تليفون" in data1["reply"] or "رقم" in data1["reply"]
    # Verify it asked for phone and did NOT execute DB write yet
    assert data1["execution_result"] is None
    context = data1["current_context"]
    assert context["draft"]["full_name"] == "كريم"
    assert "phone" not in context["draft"] or context["draft"]["phone"] is None

    # ── Turn 2 ──
    res2 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": "بص كنت عايز اضيف عميل جديد اسمه كريم"},
                {"role": "assistant", "content": data1["reply"]},
                {"role": "user", "content": "01022957599 المصدر كان اعلان فيس بوك كان عايز حاجه ايجار الميزانيه كانت 5 مليون والمنطقة كان عايز في التجمع الخامس"}
            ],
            "current_context": context
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res2.status_code == 200, res2.text
    data2 = res2.json()
    assert data2["operation"] == CRMOperationType.CREATE_LEAD.value
    assert data2["conversation_state"] == ConversationState.READY_FOR_CONFIRMATION.value
    # Preserved full_name "كريم"
    context = data2["current_context"]
    draft2 = context["draft"]
    assert draft2["full_name"] == "كريم"
    assert draft2["phone"] == "01022957599"
    assert draft2["intent_type"] == "RENT"
    assert draft2["budget"] == 5000000.0
    assert "التجمع" in draft2["preferred_location"]
    # NOT created in database yet!
    assert data2["execution_result"] is None
    db_lead_check = db_session.query(Lead).filter(Lead.phone == "01022957599").first()
    assert db_lead_check is None, "Lead must not be created before explicit confirmation!"

    # ── Turn 3 ──
    res3 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": "بص كنت عايز اضيف عميل جديد اسمه كريم"},
                {"role": "assistant", "content": data1["reply"]},
                {"role": "user", "content": "01022957599 المصدر كان اعلان فيس بوك كان عايز حاجه ايجار الميزانيه كانت 5 مليون والمنطقة كان عايز في التجمع الخامس"},
                {"role": "assistant", "content": data2["reply"]},
                {"role": "user", "content": "لا لا هو كان عايز شراء"}
            ],
            "current_context": context
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res3.status_code == 200, res3.text
    data3 = res3.json()
    assert data3["conversation_state"] == ConversationState.READY_FOR_CONFIRMATION.value
    context = data3["current_context"]
    draft3 = context["draft"]
    # Updated intent_type to BUY!
    assert draft3["intent_type"] == "BUY"
    # Preserved all previously supplied information without asking user to repeat
    assert draft3["full_name"] == "كريم"
    assert draft3["phone"] == "01022957599"
    assert draft3["budget"] == 5000000.0
    assert "التجمع" in draft3["preferred_location"]
    assert data3["execution_result"] is None

    # ── Turn 4 ──
    res4 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": "بص كنت عايز اضيف عميل جديد اسمه كريم"},
                {"role": "assistant", "content": data1["reply"]},
                {"role": "user", "content": "01022957599 المصدر كان اعلان فيس بوك كان عايز حاجه ايجار الميزانيه كانت 5 مليون والمنطقة كان عايز في التجمع الخامس"},
                {"role": "assistant", "content": data2["reply"]},
                {"role": "user", "content": "لا لا هو كان عايز شراء"},
                {"role": "assistant", "content": data3["reply"]},
                {"role": "user", "content": "مش فاهم انا كنت عايز اسجل العميل ده"}
            ],
            "current_context": context
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res4.status_code == 200, res4.text
    data4 = res4.json()
    assert data4["conversation_state"] == ConversationState.READY_FOR_CONFIRMATION.value
    # Explains briefly completing the same registration without asking for old info
    assert "كريم" in data4["reply"]
    context = data4["current_context"]
    assert context["draft"]["full_name"] == "كريم"
    assert context["draft"]["phone"] == "01022957599"
    assert context["draft"]["intent_type"] == "BUY"

    # ── Turn 5 ──
    res5 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": "بص كنت عايز اضيف عميل جديد اسمه كريم"},
                {"role": "assistant", "content": data1["reply"]},
                {"role": "user", "content": "01022957599 المصدر كان اعلان فيس بوك كان عايز حاجه ايجار الميزانيه كانت 5 مليون والمنطقة كان عايز في التجمع الخامس"},
                {"role": "assistant", "content": data2["reply"]},
                {"role": "user", "content": "لا لا هو كان عايز شراء"},
                {"role": "assistant", "content": data3["reply"]},
                {"role": "user", "content": "مش فاهم انا كنت عايز اسجل العميل ده"},
                {"role": "assistant", "content": data4["reply"]},
                {"role": "user", "content": "أيوه سجل"}
            ],
            "current_context": context
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res5.status_code == 200, res5.text
    data5 = res5.json()
    assert data5["conversation_state"] == ConversationState.CONFIRMED.value
    assert data5["execution_result"] is not None
    assert data5["execution_result"]["success"] is True
    created_id = data5["execution_result"]["lead_id"]
    assert created_id > 0
    assert f"#{created_id}" in data5["reply"] or str(created_id) in data5["reply"]

    # Verify real database persistence
    saved_lead = db_session.query(Lead).filter(Lead.id == created_id).first()
    assert saved_lead is not None
    assert saved_lead.full_name == "كريم"
    assert saved_lead.phone == "01022957599"
    assert saved_lead.budget_max == 5000000.0
    assert saved_lead.company_id == 1  # Agent 1 company
    assert saved_lead.pipeline_stage == PipelineStage.NEW

    # Clean up created lead so subsequent tests have a clean state
    db_session.delete(saved_lead)
    db_session.commit()


# ---------------------------------------------------------------------------
# 2. Field Validation & Negative Tests
# ---------------------------------------------------------------------------

def test_invalid_phone_rejected_without_dropping_name(client, agent1_token):
    """When user provides an invalid phone number, the assistant rejects it and asks for valid phone while preserving name."""
    res1 = client.post(
        "/api/v1/ai/chat",
        json={"messages": [{"role": "user", "content": "عايز أضيف عميل اسمه سمير"}]},
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res1.status_code == 200
    ctx = res1.json()["current_context"]
    assert ctx["draft"]["full_name"] == "سمير"

    # User enters bad phone "123"
    res2 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [{"role": "user", "content": "تليفونه 123"}],
            "current_context": ctx
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["conversation_state"] == ConversationState.COLLECTING_INFO.value
    assert "غير صالح" in data2["reply"]
    # Name "سمير" is preserved!
    assert data2["current_context"]["draft"]["full_name"] == "سمير"


def test_missing_required_field_guided_prompt(client, agent1_token):
    """If user provides a phone without a name, the assistant prompts specifically for the missing name."""
    res = client.post(
        "/api/v1/ai/chat",
        json={"messages": [{"role": "user", "content": "عايز أسجل عميل جديد تليفونه 01012345678"}]},
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["conversation_state"] == ConversationState.COLLECTING_INFO.value
    assert "اسم" in data["reply"]
    assert data["current_context"]["draft"]["phone"] == "01012345678"


def test_duplicate_lead_safely_blocked_and_draft_preserved(client, agent1_token, db_session):
    """When a lead with identical phone exists in tenant, confirmation blocks duplicate, explains error, and preserves draft."""
    # Seeded lead "Ahmed Gamal" has phone +201099887766 or 01099887766
    dup_lead = db_session.query(Lead).filter(Lead.company_id == 1).first()
    dup_phone = dup_lead.phone

    ctx = {
        "operation": CRMOperationType.CREATE_LEAD.value,
        "state": ConversationState.READY_FOR_CONFIRMATION.value,
        "draft": {
            "full_name": "عميل مكرر",
            "phone": dup_phone,
            "budget": 3000000.0
        }
    }

    res = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [{"role": "user", "content": "أيوه سجل"}],
            "current_context": ctx
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    # Does not confirm into DB!
    assert data["conversation_state"] != ConversationState.CONFIRMED.value
    assert "بالفعل" in data["reply"] or "مسجل" in data["reply"]
    # Draft is preserved so user can edit phone
    assert data["current_context"]["draft"]["full_name"] == "عميل مكرر"


def test_unauthorized_role_blocked(client, agent1_token):
    """Users without LEADS_MANAGE permission cannot create leads through AI assistant."""
    ctx = {
        "operation": CRMOperationType.CREATE_LEAD.value,
        "state": ConversationState.READY_FOR_CONFIRMATION.value,
        "draft": {
            "full_name": "عميل غير مصرح",
            "phone": "01077778888"
        }
    }

    with patch("backend.app.services.crm_operator_service.has_permission", return_value=False):
        res = client.post(
            "/api/v1/ai/chat",
            json={"messages": [{"role": "user", "content": "أيوه سجل"}], "current_context": ctx},
            headers={"Authorization": f"Bearer {agent1_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["conversation_state"] == ConversationState.ERROR.value
        assert "غير مصرح له" in data["reply"]


def test_tenant_isolation_allows_same_phone_in_different_companies(client, agent1_token, horizon_token, db_session):
    """A phone registered in Company 1 does not block Company 2 from registering their own lead with that phone."""
    phone_shared = "01088889999"

    # Clean up phone from both companies if existing
    db_session.query(Lead).filter(Lead.phone == phone_shared).delete()
    db_session.commit()

    # 1. Company 1 creates lead with phone_shared
    ctx1 = {
        "operation": CRMOperationType.CREATE_LEAD.value,
        "state": ConversationState.READY_FOR_CONFIRMATION.value,
        "draft": {"full_name": "عميل شركة 1", "phone": phone_shared}
    }
    res1 = client.post(
        "/api/v1/ai/chat",
        json={"messages": [{"role": "user", "content": "سجل"}], "current_context": ctx1},
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res1.status_code == 200
    assert res1.json()["conversation_state"] == ConversationState.CONFIRMED.value

    # 2. Company 2 creates lead with same phone_shared (Horizon Realty, company_id=2)
    ctx2 = {
        "operation": CRMOperationType.CREATE_LEAD.value,
        "state": ConversationState.READY_FOR_CONFIRMATION.value,
        "draft": {"full_name": "عميل شركة 2", "phone": phone_shared}
    }
    res2 = client.post(
        "/api/v1/ai/chat",
        json={"messages": [{"role": "user", "content": "سجل"}], "current_context": ctx2},
        headers={"Authorization": f"Bearer {horizon_token}"}
    )
    assert res2.status_code == 200
    assert res2.json()["conversation_state"] == ConversationState.CONFIRMED.value

    # Verify both leads exist in their respective companies
    leads = db_session.query(Lead).filter(Lead.phone == phone_shared).all()
    assert len(leads) == 2
    assert {l.company_id for l in leads} == {1, 2}

    # Clean up phone from both companies so subsequent tenant isolation tests have clean state
    db_session.query(Lead).filter(Lead.phone == phone_shared).delete()
    db_session.commit()


# ---------------------------------------------------------------------------
# 3. Robustness: JSON Extraction, Malformed Groq Output, Timeouts, Failures
# ---------------------------------------------------------------------------

def test_safe_extract_json_resilience():
    """Validates robust JSON extraction across markdown fences, text affixes, and trailing commas."""
    # 1. Standard markdown code fence
    raw1 = "```json\n{\"intent\": \"CREATE_LEAD\", \"name\": \"كريم\"}\n```"
    assert safe_extract_json(raw1) == {"intent": "CREATE_LEAD", "name": "كريم"}

    # 2. Arabic conversational preamble before JSON
    raw2 = "إليك نتيجة الاستخراج بصيغة JSON المطلوبة:\n{\"action\": \"create\", \"budget\": 5000000}\nشكراً لك!"
    assert safe_extract_json(raw2) == {"action": "create", "budget": 5000000}

    # 3. Trailing comma inside JSON object
    raw3 = "{\"name\": \"كريم\", \"phone\": \"01022957599\",}"
    assert safe_extract_json(raw3) == {"name": "كريم", "phone": "01022957599"}

    # 4. Pure Arabic text with no JSON
    raw4 = "أهلاً بك يا فندم، أنا تحت أمرك في أي وقت!"
    assert safe_extract_json(raw4) is None


def test_database_failure_rollback_and_draft_preservation(client, agent1_token):
    """When a database commit fails, the transaction is rolled back and the draft is preserved."""
    ctx = {
        "operation": CRMOperationType.CREATE_LEAD.value,
        "state": ConversationState.READY_FOR_CONFIRMATION.value,
        "draft": {"full_name": "عميل استثناء", "phone": "01066667777"}
    }

    with patch("sqlalchemy.orm.Session.commit", side_effect=SQLAlchemyError("DB locked")):
        res = client.post(
            "/api/v1/ai/chat",
            json={"messages": [{"role": "user", "content": "أيوه سجل"}], "current_context": ctx},
            headers={"Authorization": f"Bearer {agent1_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["conversation_state"] != ConversationState.CONFIRMED.value
        assert "خطأ" in data["reply"]
        # Draft is preserved for retry
        assert data["current_context"]["draft"]["full_name"] == "عميل استثناء"


def test_user_cancellation_clears_draft(client, agent1_token):
    """When user cancels during draft, operation is marked cancelled."""
    ctx = {
        "operation": CRMOperationType.CREATE_LEAD.value,
        "state": ConversationState.COLLECTING_INFO.value,
        "draft": {"full_name": "عميل ملغي"}
    }
    res = client.post(
        "/api/v1/ai/chat",
        json={"messages": [{"role": "user", "content": "إلغي التسجيل مش عايز"}], "current_context": ctx},
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["conversation_state"] == ConversationState.CANCELLED.value
    assert "إلغاء" in data["reply"] or "تحت أمرك" in data["reply"]
