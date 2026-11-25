import pytest
from backend.app.models.models import User, Lead, Conversation, ConversationMessage, SalesAgentProfile, UserRole


def test_list_and_manage_sales_agents(client, agent1_token, manager_token):
    # 1. Sales Agent listing
    res = client.get("/api/v1/agents", headers={"Authorization": f"Bearer {manager_token}"})
    assert res.status_code == 200, res.text
    agents = res.json()
    assert len(agents) >= 2
    agent1_data = next((a for a in agents if a["email"] == "agent1@nexora.com"), None)
    assert agent1_data is not None
    assert agent1_data["total_assigned_leads"] >= 0

    # 2. Update agent profile
    prof_update = {
        "personality_prompt": "مستشار عقاري محترف يتحدث باللهجة المصرية الطبيعية.",
        "preferred_voice": "ar-EG-SalmaNeural",
        "speaking_rate": "+25%",
        "monthly_target_sales": 18000000.0,
        "target_visits_per_month": 30
    }
    update_res = client.patch(
        f"/api/v1/agents/{agent1_data['id']}/profile",
        json=prof_update,
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert update_res.status_code == 200, update_res.text
    updated = update_res.json()
    assert updated["speaking_rate"] == "+25%"
    assert updated["monthly_target_sales"] == 18000000.0


def test_bulk_lead_transfer(client, manager_token, agent1_token):
    # Get agents
    agents_res = client.get("/api/v1/agents", headers={"Authorization": f"Bearer {manager_token}"})
    agents = agents_res.json()
    ag1 = next(a for a in agents if a["email"] == "agent1@nexora.com")
    ag2 = next(a for a in agents if a["email"] == "agent2@nexora.com")

    # Manager transfers lead from agent2 to agent1
    transfer_payload = {
        "target_agent_id": ag1["id"],
        "reason": "Reallocation of Sheikh Zayed territory",
        "notes": "Manager rebalancing"
    }
    res = client.post(
        f"/api/v1/agents/{ag2['id']}/transfer-leads",
        json=transfer_payload,
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] == True
    assert "transferred_count" in data

    # Unauthorized role check: Sales Agent cannot trigger bulk transfer
    res_forbidden = client.post(
        f"/api/v1/agents/{ag2['id']}/transfer-leads",
        json=transfer_payload,
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res_forbidden.status_code == 403


def test_conversations_inbox_and_messaging(client, agent1_token, horizon_token):
    # 1. Ingest simulated inbound WhatsApp message for a new customer
    webhook_res = client.post(
        "/api/v1/conversations/webhook",
        json={
            "channel": "WHATSAPP",
            "customer_phone": "+201055554433",
            "customer_name": "سامح خليل",
            "content": "مساء الخير، عايز اعرف الوحدات المتاحة في التجمع الخامس ومقدماتها."
        }
    )
    assert webhook_res.status_code == 200, webhook_res.text
    conv_id = webhook_res.json()["conversation_id"]

    # 2. Assign to Agent 1
    agents_res = client.get("/api/v1/agents", headers={"Authorization": f"Bearer {agent1_token}"})
    agent1_id = agents_res.json()[0]["id"]

    assign_res = client.post(
        f"/api/v1/conversations/{conv_id}/assign",
        json={"agent_id": agent1_id},
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert assign_res.status_code == 200

    # 3. Agent 1 views conversation
    detail_res = client.get(
        f"/api/v1/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert detail_res.status_code == 200
    conv_data = detail_res.json()
    assert conv_data["customer_name"] == "سامح خليل"
    assert len(conv_data["messages"]) >= 1

    # 4. Agent 1 sends customer response
    send_res = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={
            "content": "أهلاً بحضرتك يا فندم! عندنا وحدات 2 و 3 غرف في The Crest بمقدم 10% وأقساط على 8 سنوات.",
            "is_internal_note": False
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert send_res.status_code == 200
    assert send_res.json()["sender_type"] == "AGENT"

    # 5. Agent 1 adds internal private note
    note_res = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={
            "content": "العميل مهتم جداً ويرغب في معاينة الأسبوع القادم.",
            "is_internal_note": True
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert note_res.status_code == 200
    assert note_res.json()["is_internal_note"] == True

    # 6. Toggle human takeover
    takeover_res = client.post(
        f"/api/v1/conversations/{conv_id}/takeover",
        json={"human_takeover": True},
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert takeover_res.status_code == 200
    assert takeover_res.json()["human_takeover"] == True

    # 7. AI Summary generation
    summary_res = client.post(
        f"/api/v1/conversations/{conv_id}/summarize",
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert summary_res.status_code == 200
    assert "summary" in summary_res.json()

    # 8. Cross-tenant isolation: Horizon Agent attempting to access this Nexora conversation must get 404
    horizon_res = client.get(
        f"/api/v1/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {horizon_token}"}
    )
    assert horizon_res.status_code == 404
