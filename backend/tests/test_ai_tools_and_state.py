"""
Comprehensive test suite for Phase 1:
- Conversation State Manager
- AI Structured Tool Registry
- Tenant Isolation & RBAC enforcement across all tools
"""

import pytest
from datetime import datetime, timedelta
from backend.app.models.models import (
    User, UserRole, Company, Lead, FollowUp, Appointment, Property, Project,
    FollowUpStatus, PriorityLevel, PropertyStatus, PropertyOffer, PropertyOfferStatus
)
from backend.app.services.conversation_state_manager import ConversationStateManager, ConversationStateDTO
from backend.app.services.ai_tools import ai_tool_registry
from backend.app.services.crm_operator_service import get_crm_operator
from backend.app.schemas.crm_actions import CRMOperationType, ConversationState


@pytest.fixture
def test_setup(db_session):
    # Setup test company
    comp = db_session.query(Company).filter(Company.id == 1).first()
    if not comp:
        comp = Company(id=1, name="Nexora Test Real Estate")
        db_session.add(comp)
        db_session.commit()

    # Setup agent user
    agent = db_session.query(User).filter(User.email == "agent_tools_test@nexora.com").first()
    if not agent:
        agent = User(
            email="agent_tools_test@nexora.com",
            hashed_password="hash",
            full_name="Samir ToolAgent",
            role=UserRole.SALES_AGENT,
            company_id=comp.id,
            is_active=True
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

    # Setup manager user
    manager = db_session.query(User).filter(User.email == "manager_tools_test@nexora.com").first()
    if not manager:
        manager = User(
            email="manager_tools_test@nexora.com",
            hashed_password="hash",
            full_name="Mahmoud Admin",
            role=UserRole.SALES_MANAGER,
            company_id=comp.id,
            is_active=True
        )
        db_session.add(manager)
        db_session.commit()
        db_session.refresh(manager)

    # Setup test lead
    lead = db_session.query(Lead).filter(Lead.phone == "01011112222").first()
    if not lead:
        lead = Lead(
            full_name="كريم محمد",
            phone="01011112222",
            email="karim@test.com",
            company_id=comp.id,
            assigned_agent_id=agent.id,
            preferred_location="التجمع الخامس",
            property_type="Apartment",
            budget_max=5000000.0
        )
        db_session.add(lead)
        db_session.commit()
        db_session.refresh(lead)
    else:
        lead.full_name = "كريم محمد"
        lead.assigned_agent_id = agent.id
        lead.company_id = comp.id
        db_session.commit()
        db_session.refresh(lead)

    # Setup test project & property
    proj = db_session.query(Project).filter(Project.name == "Palm Hills New Cairo").first()
    if not proj:
        proj = Project(
            name="Palm Hills New Cairo",
            developer="Palm Hills",
            location="New Cairo",
            company_id=comp.id
        )
        db_session.add(proj)
        db_session.commit()
        db_session.refresh(proj)

    prop = db_session.query(Property).filter(Property.unit_number == "PH-101").first()
    if not prop:
        prop = Property(
            company_id=comp.id,
            project_id=proj.id,
            unit_number="PH-101",
            property_type="Apartment",
            location="التجمع الخامس",
            city="القاهرة",
            area=185.0,
            bedrooms=3,
            bathrooms=3,
            total_price=5200000.0,
            installment_plan="8 Years Equal",
            availability_status=PropertyStatus.AVAILABLE
        )
        db_session.add(prop)
        db_session.commit()
        db_session.refresh(prop)

    return {
        "company": comp,
        "agent": agent,
        "manager": manager,
        "lead": lead,
        "property": prop,
        "project": proj
    }


def test_conversation_state_manager_lifecycle(db_session, test_setup):
    agent = test_setup["agent"]
    cid = f"test_session_{agent.id}"

    # 1. Create state
    state = ConversationStateManager.get_or_create_state(db_session, agent, conversation_id=cid)
    assert state.conversation_id == cid
    assert state.company_id == agent.company_id
    assert state.user_id == agent.id
    assert state.is_expired() is False

    # 2. Update state
    state.intent = "CREATE_TASK"
    state.collected_fields["task_title"] = "مراجعة العقد"
    state.collected_fields["customer_name"] = "كريم محمد"
    state.missing_fields = ["due_time"]
    state.pending_tool = "create_task"
    ConversationStateManager.save_state(db_session, state)

    # 3. Retrieve state in a new lookup
    loaded = ConversationStateManager.get_or_create_state(db_session, agent, conversation_id=cid)
    assert loaded.intent == "CREATE_TASK"
    assert loaded.collected_fields.get("task_title") == "مراجعة العقد"
    assert loaded.missing_fields == ["due_time"]
    assert loaded.pending_tool == "create_task"

    # 4. Reset state
    ConversationStateManager.reset_state(db_session, cid, agent.company_id)
    cleared = ConversationStateManager.get_or_create_state(db_session, agent, conversation_id=cid)
    assert cleared.intent is None
    assert cleared.collected_fields == {}


def test_customer_tools(db_session, test_setup):
    agent = test_setup["agent"]
    lead = test_setup["lead"]

    # 1. Search customers
    res_search = ai_tool_registry.execute("search_customers", db_session, agent, {"query": "كريم"})
    assert res_search.success is True
    assert len(res_search.data) >= 1
    assert any(c["id"] == lead.id for c in res_search.data)

    # 2. Get details
    res_details = ai_tool_registry.execute("get_customer_details", db_session, agent, {"customer_id": lead.id})
    assert res_details.success is True
    assert res_details.data["full_name"] == lead.full_name
    assert res_details.data["phone"] == lead.phone

    # 3. Update customer
    res_update = ai_tool_registry.execute(
        "update_customer", db_session, agent,
        {"customer_id": lead.id, "budget": 6000000.0, "notes": "عميل جاد ومهتم بمعاينة قريبة"}
    )
    assert res_update.success is True
    db_session.refresh(lead)
    assert lead.budget_max == 6000000.0
    assert "عميل جاد" in lead.notes


def test_task_tools(db_session, test_setup):
    agent = test_setup["agent"]
    lead = test_setup["lead"]

    # 1. Create task
    due = (datetime.utcnow() + timedelta(days=1)).replace(hour=10, minute=0, second=0).isoformat()
    res_create = ai_tool_registry.execute(
        "create_task", db_session, agent,
        {
            "title": "متابعة الشيكات مع العميل",
            "due_date": due,
            "customer_id": lead.id,
            "priority": "HIGH"
        }
    )
    assert res_create.success is True
    task_id = res_create.data["task_id"]

    # 2. Complete task
    res_comp = ai_tool_registry.execute(
        "complete_task", db_session, agent,
        {"task_id": task_id, "outcome": "تم استلام الشيكات وتوقيع العقد"}
    )
    assert res_comp.success is True

    task = db_session.query(FollowUp).filter(FollowUp.id == task_id).first()
    assert task.status == FollowUpStatus.COMPLETED
    assert task.completion_outcome == "تم استلام الشيكات وتوقيع العقد"


def test_appointment_tools_with_conflict(db_session, test_setup):
    agent = test_setup["agent"]
    lead = test_setup["lead"]
    prop = test_setup["property"]

    start = (datetime.utcnow() + timedelta(days=2)).replace(hour=14, minute=0, second=0)
    end = start + timedelta(hours=1)

    # 1. Create appointment
    res1 = ai_tool_registry.execute(
        "create_appointment", db_session, agent,
        {
            "customer_id": lead.id,
            "title": "معاينة الوحدة",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "location": "موقع بالم هيلز التجمع",
            "property_id": prop.id
        }
    )
    assert res1.success is True
    appt_id = res1.data["appointment_id"]

    # 2. Create another appointment at same time -> detects conflict warning
    res2 = ai_tool_registry.execute(
        "create_appointment", db_session, agent,
        {
            "customer_id": lead.id,
            "title": "جلسة تعاقد",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "location": "المقر"
        }
    )
    assert res2.success is True
    assert "تعارض" in res2.message

    # 3. Cancel appointment
    res_cancel = ai_tool_registry.execute(
        "cancel_appointment", db_session, agent,
        {"appointment_id": appt_id, "reason": "تأجيل من طرف العميل"}
    )
    assert res_cancel.success is True
    appt = db_session.query(Appointment).filter(Appointment.id == appt_id).first()
    assert appt.status.value == "CANCELLED"


def test_inventory_tools_strict_location(db_session, test_setup):
    agent = test_setup["agent"]
    prop = test_setup["property"]

    # 1. Search properties in New Cairo (matching)
    res_match = ai_tool_registry.execute(
        "search_properties", db_session, agent,
        {"location": "التجمع الخامس", "strict_location": True}
    )
    assert res_match.success is True
    assert len(res_match.data) >= 1
    assert any(p["unit_number"] == prop.unit_number for p in res_match.data)

    # 2. Search properties in Nasr City (strict location: must NOT return New Cairo units)
    res_nasr = ai_tool_registry.execute(
        "search_properties", db_session, agent,
        {"location": "مدينة نصر", "strict_location": True}
    )
    assert res_nasr.success is True
    assert not any(p["unit_number"] == prop.unit_number for p in res_nasr.data)

    # 3. Get property details
    res_det = ai_tool_registry.execute("get_property_details", db_session, agent, {"property_id": prop.id})
    assert res_det.success is True
    assert res_det.data["unit_number"] == "PH-101"
    assert res_det.data["total_price"] == 5200000.0


def test_offer_and_whatsapp_pitch_tools(db_session, test_setup):
    agent = test_setup["agent"]
    lead = test_setup["lead"]
    prop = test_setup["property"]

    # 1. Prepare WhatsApp message
    res_msg = ai_tool_registry.execute(
        "prepare_property_message", db_session, agent,
        {"customer_id": lead.id, "property_id": prop.id}
    )
    assert res_msg.success is True
    assert "مساء الخير" in res_msg.data["message_text"]
    assert "PH-101" in res_msg.data["message_text"]
    assert "5,200,000" in res_msg.data["message_text"]

    # 2. Create property offer
    res_offer = ai_tool_registry.execute(
        "create_property_offer", db_session, agent,
        {
            "customer_id": lead.id,
            "property_id": prop.id,
            "message_text": res_msg.data["message_text"]
        }
    )
    assert res_offer.success is True
    offer_id = res_offer.data["offer_id"]

    # 3. Record feedback
    res_fb = ai_tool_registry.execute(
        "record_customer_feedback", db_session, agent,
        {
            "offer_id": offer_id,
            "feedback": "العميل معجب بالوحدة ولكن يطلب تقسيط على 9 سنوات بدلاً من 8",
            "status": "SHARED"
        }
    )
    assert res_fb.success is True

    offer = db_session.query(PropertyOffer).filter(PropertyOffer.id == offer_id).first()
    assert offer.status == PropertyOfferStatus.SHARED
    assert "تقسيط على 9 سنوات" in offer.customer_feedback


def test_reporting_tools_and_rbac(db_session, test_setup):
    agent = test_setup["agent"]
    manager = test_setup["manager"]

    # 1. Sales summary works for agent (scoped)
    res_summary = ai_tool_registry.execute("get_sales_summary", db_session, agent, {"period": "month"})
    assert res_summary.success is True
    assert "total_leads" in res_summary.data

    # 2. Pipeline stages
    res_pipe = ai_tool_registry.execute("get_customer_pipeline", db_session, agent, {})
    assert res_pipe.success is True
    assert isinstance(res_pipe.data, dict)

    # 3. Team performance: Manager is authorized
    res_tp_mgr = ai_tool_registry.execute("get_team_performance", db_session, manager, {})
    assert res_tp_mgr.success is True

    # 4. Team performance: Agent is blocked by RBAC
    res_tp_agent = ai_tool_registry.execute("get_team_performance", db_session, agent, {})
    assert res_tp_agent.success is False
    assert "صلاحيات" in res_tp_agent.message


def test_crm_operator_multi_turn_with_state(db_session, test_setup):
    agent = test_setup["agent"]
    operator = get_crm_operator()

    # Turn 1: User asks for sales summary
    r1 = operator.process_turn(
        db=db_session,
        current_user=agent,
        user_query="عايز ملخص المبيعات للشهر ده"
    )
    assert r1.operation == CRMOperationType.SALES_SUMMARY
    assert "ملخص المبيعات" in r1.reply
    assert "conversation_id" in r1.current_context

    cid = r1.current_context["conversation_id"]

    # Turn 2: User asks for pipeline distribution in same conversation
    r2 = operator.process_turn(
        db=db_session,
        current_user=agent,
        user_query="اعرضلي مراحل خط الأنابيب وتوزيع العملاء",
        current_context={"conversation_id": cid}
    )
    assert r2.operation == CRMOperationType.CUSTOMER_PIPELINE
    assert "توزيع خط الأنابيب" in r2.reply
