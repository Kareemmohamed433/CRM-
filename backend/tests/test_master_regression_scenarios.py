import pytest
from datetime import datetime, timedelta
from backend.app.models.models import User, Lead, Appointment, FollowUp, UserRole, AppointmentStatus, FollowUpStatus
from backend.app.schemas.crm_actions import ConversationState, CRMOperationType


def test_mandatory_appointment_and_agenda_scenario(client, agent1_token, db_session):
    """
    Mandatory Regression Scenario 1:
    User: "عندي بكره الساعه 6 مع عمييل اسمه كريم محمد ف ضيفه"
    -> Assistant identifies appointment, auto-registers lead/previews appointment
    User: "لا كده تمام" (Egyptian colloquial confirmation)
    -> Assistant persists appointment into database with real appointment ID
    User: "قولي بكره عندي اي"
    -> Assistant queries real database and returns tomorrow's appointments including Karim Mohamed
    """
    # ── Turn 1 ──
    res1 = client.post(
        "/api/v1/ai/chat",
        json={"messages": [{"role": "user", "content": "عندي بكره الساعه 6 مع عمييل اسمه كريم محمد ف ضيفه"}]},
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res1.status_code == 200, res1.text
    data1 = res1.json()
    assert data1["operation"] == CRMOperationType.CREATE_APPOINTMENT.value
    assert data1["conversation_state"] == ConversationState.READY_FOR_CONFIRMATION.value
    assert "كريم محمد" in data1["reply"]
    assert "6:00" in data1["reply"] or "18:00" in data1["reply"] or "مساءً" in data1["reply"]
    ctx1 = data1["current_context"]

    # ── Turn 2: Affirmative confirmation in Egyptian Arabic ("لا كده تمام") ──
    res2 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": "عندي بكره الساعه 6 مع عمييل اسمه كريم محمد ف ضيفه"},
                {"role": "assistant", "content": data1["reply"]},
                {"role": "user", "content": "لا كده تمام"}
            ],
            "current_context": ctx1
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res2.status_code == 200, res2.text
    data2 = res2.json()
    assert data2["conversation_state"] == ConversationState.CONFIRMED.value
    assert data2["execution_result"] is not None
    assert data2["execution_result"]["success"] is True
    appt_id = data2["execution_result"]["appointment_id"]
    assert appt_id > 0
    assert f"#{appt_id}" in data2["reply"]

    # Verify real DB persistence
    db_appt = db_session.query(Appointment).filter(Appointment.id == appt_id).first()
    assert db_appt is not None
    assert db_appt.status == AppointmentStatus.SCHEDULED
    assert "كريم محمد" in db_appt.title

    # ── Turn 3: What do I have tomorrow ("قولي بكره عندي اي") ──
    res3 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": "قولي بكره عندي اي"}
            ],
            "current_context": data2["current_context"]
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res3.status_code == 200, res3.text
    data3 = res3.json()
    assert data3["operation"] == CRMOperationType.DAILY_AGENDA.value
    assert "كريم محمد" in data3["reply"]
    assert "6:00" in data3["reply"] or "18:00" in data3["reply"] or "مساءً" in data3["reply"]
    assert "مش عندي وصول" not in data3["reply"]


def test_mandatory_task_multi_turn_workflow(client, manager_token, db_session):
    """
    Mandatory Regression Scenario 2 (Section 15 Task Workflow):
    Step 1: User: "سجلي مهمة لـ Ahmed Samir لمراجعة عقد العميل بكرة."
            -> Validates Ahmed Samir exists in DB
            -> Detects "العميل" without client name -> prompts specifically for client name
    Step 2: User: "العميل Unknown Customer 999"
            -> Validates against DB -> Not found -> explains client not found in system
    Step 3: User provides customer assigned to another agent (Ownership conflict)
            -> Flags ownership conflict without silently reassigning, asks whether to proceed
    Step 4: User agrees to proceed without transfer -> Full preview card
    Step 5: User confirms -> Persists FollowUp to DB and returns real Task ID
    """
    # ── Step 1 ──
    res1 = client.post(
        "/api/v1/ai/chat",
        json={"messages": [{"role": "user", "content": "سجلي مهمة لـ Ahmed Samir لمراجعة عقد العميل بكرة."}]},
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert res1.status_code == 200, res1.text
    data1 = res1.json()
    assert data1["conversation_state"] == ConversationState.COLLECTING_INFO.value
    assert "Ahmed Samir" in data1["reply"]
    assert "العميل" in data1["reply"]
    ctx1 = data1["current_context"]

    # ── Step 2: Unknown customer ──
    res2 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": "سجلي مهمة لـ Ahmed Samir لمراجعة عقد العميل بكرة."},
                {"role": "assistant", "content": data1["reply"]},
                {"role": "user", "content": "العميل Unknown Random Guy 999"}
            ],
            "current_context": ctx1
        },
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert res2.status_code == 200, res2.text
    data2 = res2.json()
    assert data2["conversation_state"] == ConversationState.COLLECTING_INFO.value
    assert "ملقتش عميل" in data2["reply"] or "غير مسجل" in data2["reply"]

    # ── Step 3: Customer belonging to a different agent (Ownership conflict) ──
    # Ensure lead 4 belongs to agent 2 (user id 6), not Ahmed Samir (user id 5)
    lead4 = db_session.query(Lead).filter(Lead.id == 4).first()
    lead4.assigned_agent_id = 6
    db_session.commit()

    res3 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": f"العميل {lead4.full_name}"}
            ],
            "current_context": ctx1
        },
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert res3.status_code == 200, res3.text
    data3 = res3.json()
    assert data3["conversation_state"] == ConversationState.COLLECTING_INFO.value
    assert "يتبع" in data3["reply"] or "مستشار آخر" in data3["reply"]
    ctx3 = data3["current_context"]

    # ── Step 4: Proceed without transfer -> Mandatory Time Collection ──
    res4 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": "المتابعة بدون تغيير المالك"}
            ],
            "current_context": ctx3
        },
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert res4.status_code == 200, res4.text
    data4 = res4.json()
    assert data4["conversation_state"] == ConversationState.COLLECTING_INFO.value
    assert "الساعة كام" in data4["reply"]
    ctx4 = data4["current_context"]

    # ── Step 4.1: User specifies ambiguous hour ("الساعة 9") ──
    res4_1 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": "الساعة 9"}
            ],
            "current_context": ctx4
        },
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert res4_1.status_code == 200, res4_1.text
    data4_1 = res4_1.json()
    assert data4_1["conversation_state"] == ConversationState.COLLECTING_INFO.value
    assert "صباح" in data4_1["reply"] and "مساء" in data4_1["reply"]
    ctx4_1 = data4_1["current_context"]

    # ── Step 4.2: User clarifies AM ("صباحًا") -> Ready for confirmation ──
    res4_2 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": "صباحًا"}
            ],
            "current_context": ctx4_1
        },
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert res4_2.status_code == 200, res4_2.text
    data4_2 = res4_2.json()
    assert data4_2["conversation_state"] == ConversationState.READY_FOR_CONFIRMATION.value
    assert "Ahmed Samir" in data4_2["reply"]
    assert lead4.full_name in data4_2["reply"]
    assert "09:00" in data4_2["reply"]
    ctx4_2 = data4_2["current_context"]

    # ── Step 5: Explicit confirmation ──
    res5 = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": "اعتمد وسجل"}
            ],
            "current_context": ctx4_2
        },
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert res5.status_code == 200, res5.text
    data5 = res5.json()
    assert data5["conversation_state"] == ConversationState.CONFIRMED.value
    assert data5["execution_result"] is not None
    assert data5["execution_result"]["success"] is True
    task_id = data5["execution_result"]["followup_id"]
    assert task_id > 0
    assert f"#{task_id}" in data5["reply"]

    # Verify real database persistence
    db_task = db_session.query(FollowUp).filter(FollowUp.id == task_id).first()
    assert db_task is not None
    assert db_task.assigned_user_id == 5  # Ahmed Samir
    assert "بكرة" not in db_task.purpose
    assert db_task.purpose == "مراجعة عقد العميل"
    assert db_task.created_by_id is not None
    assert db_task.lead_id == lead4.id
    assert "مراجعة عقد العميل" in db_task.purpose


def test_hierarchical_rbac_user_management(client, manager_token):
    """
    Test Hierarchical Account Management:
    - Sales Manager can create Sales Agent and Team Leader
    - Sales Manager gets 403 Forbidden trying to create Sales Manager, Company Admin, or Super Admin
    """
    # 1. Sales Manager creates a Sales Agent -> Allowed (200)
    agent_payload = {
        "email": f"agent_rbac_{int(datetime.utcnow().timestamp())}@nexora.com",
        "password": "Password123!",
        "full_name": "New RBAC Agent",
        "phone": "+201011223344",
        "role": UserRole.SALES_AGENT.value
    }
    res_agent = client.post("/api/v1/users", json=agent_payload, headers={"Authorization": f"Bearer {manager_token}"})
    assert res_agent.status_code == 200, res_agent.text
    assert res_agent.json()["role"] == UserRole.SALES_AGENT.value

    # 2. Sales Manager creates a Team Leader -> Allowed (200)
    tl_payload = {
        "email": f"tl_rbac_{int(datetime.utcnow().timestamp())}@nexora.com",
        "password": "Password123!",
        "full_name": "New RBAC Team Leader",
        "phone": "+201011223355",
        "role": UserRole.TEAM_LEADER.value
    }
    res_tl = client.post("/api/v1/users", json=tl_payload, headers={"Authorization": f"Bearer {manager_token}"})
    assert res_tl.status_code == 200, res_tl.text
    assert res_tl.json()["role"] == UserRole.TEAM_LEADER.value

    # 3. Sales Manager tries to create a Sales Manager -> Rejected (403)
    sm_payload = {
        "email": f"sm_rbac_{int(datetime.utcnow().timestamp())}@nexora.com",
        "password": "Password123!",
        "full_name": "Illegal Manager",
        "phone": "+201011223366",
        "role": UserRole.SALES_MANAGER.value
    }
    res_sm = client.post("/api/v1/users", json=sm_payload, headers={"Authorization": f"Bearer {manager_token}"})
    assert res_sm.status_code == 403, res_sm.text

    # 4. Sales Manager tries to create a Company Admin -> Rejected (403)
    admin_payload = {
        "email": f"admin_rbac_{int(datetime.utcnow().timestamp())}@nexora.com",
        "password": "Password123!",
        "full_name": "Illegal Admin",
        "phone": "+201011223377",
        "role": UserRole.COMPANY_ADMIN.value
    }
    res_admin = client.post("/api/v1/users", json=admin_payload, headers={"Authorization": f"Bearer {manager_token}"})
    assert res_admin.status_code == 403, res_admin.text

