def test_arabic_voice_crm_extraction(client, agent1_token):
    arabic_speech_transcript = "أنا نزلت مع أحمد النهارده عاينّا شقة في التجمع، بس هو مش مقتنع بالسعر، وعايز حاجة أقل من أربعة مليون، وقال هيفكر ويرد عليا."
    
    res = client.post(
        "/api/v1/voice/extract",
        json={
            "transcript_text": arabic_speech_transcript,
            "language": "ar",
            "target_form": "activity"
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["target_form"] == "activity"
    assert data["extracted_fields"]["activity_type"] == "VISIT"
    assert "Price" in data["extracted_fields"]["objection"]
    assert data["extracted_fields"]["customer_stated_budget"] == 4000000.0
    assert data["extracted_fields"]["preferred_location"] == "New Cairo / التجمع"
    assert data["requires_confirmation"] == True


def test_daily_briefing_generation(client, agent1_token):
    res = client.get(
        "/api/v1/ai/briefing",
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "صباح الخير" in data["greeting"]
    assert "metrics" in data
    assert "due_today" in data["metrics"]
    assert "overdue" in data["metrics"]
    assert len(data["recommendations"]) > 0


def test_ai_chat_assistant_tools(client, agent1_token):
    # Query overdue tasks
    res = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": "وريني المتابعات المتأخرة عندي"}
            ]
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "list_due_followups" in data["suggested_tools_called"]
    assert len(data["reply"]) > 0


def test_qwen_ai_assistant_freeform_chat(client, agent1_token):
    # Freeform sales advice query handled by LLM
    res = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": "ما هي أفضل نصيحة لمتابعة عميل متردد في السعر؟"}
            ]
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["reply"]) > 0
    # Either answered by the dynamic LLM or fallback safely
    assert any(tool in ["qwen_llm_assistant", "get_authorized_daily_briefing"] for tool in data["suggested_tools_called"])


def test_voice_conversation_multiturn_missing_info(client, agent1_token):
    # Turn 1: Partial information provided (Lead name, Visit, Location, Objection)
    # Missing: Stated budget and follow-up date
    res = client.post(
        "/api/v1/voice/conversation",
        json={
            "messages": [
                {"role": "user", "content": "أنا نزلت مع أحمد محمود النهارده عاينّا شقة في التجمع، بس هو مش مقتنع بالسعر"}
            ],
            "current_context": {}
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["conversation_state"] == "COLLECTING_INFO"
    assert "lead_name" in data["extracted_context"]
    assert "Ahmed" in data["extracted_context"]["lead_name"] or "أحمد" in data["extracted_context"]["lead_name"]
    assert data["extracted_context"]["activity_type"] == "VISIT"
    assert "Price" in data["extracted_context"]["objection"]
    # Missing budget or follow-up date
    assert len(data["missing_fields"]) > 0
    # Natural Egyptian Arabic spoken response generated
    assert len(data["reply_text"]) > 0
    assert len(data["reply_audio_text"]) > 0


def test_voice_conversation_ambiguous_leads(client, agent1_token):
    # Create a second Ahmed lead in the same company to trigger ambiguity detection
    client.post(
        "/api/v1/leads",
        json={
            "full_name": "Ahmed Gamal",
            "phone": "+201099887766",
            "source": "Meta Ads"
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    res = client.post(
        "/api/v1/voice/conversation",
        json={
            "messages": [
                {"role": "user", "content": "أنا نزلت مع أحمد النهارده عاينّا شقة في التجمع"}
            ],
            "current_context": {}
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["ambiguities"]) > 0
    assert any("Ahmed" in a or "أحمد" in a for a in data["ambiguities"])


def test_voice_conversation_multiturn_completion_and_preview(client, agent1_token):
    # Turn 2: User provides missing budget and follow-up date
    turn1_context = {
        "lead_id": 1,
        "lead_name": "أحمد الشناوي",
        "activity_type": "VISIT",
        "preferred_location": "New Cairo / التجمع",
        "objection": "Price too high / السعر مرتفع"
    }
    res = client.post(
        "/api/v1/voice/conversation",
        json={
            "messages": [
                {"role": "user", "content": "أنا نزلت مع أحمد النهارده عاينّا شقة في التجمع، بس هو مش مقتنع بالسعر"},
                {"role": "assistant", "content": "تمام يا فندم، يا ترى حدد ميزانية معينة يقدر يدفعها وهنكلمه إمتى؟"},
                {"role": "user", "content": "آه ميزانيته 4 مليون وهنكلمه بكرة نتابع معاه"}
            ],
            "current_context": turn1_context
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["conversation_state"] == "READY_FOR_CONFIRMATION"
    assert data["extracted_context"]["customer_stated_budget"] == 4000000.0
    assert "suggested_followup_date" in data["extracted_context"]
    assert data["confirmation_preview"] is not None
    assert data["confirmation_preview"]["lead_id"] == 1
    assert data["confirmation_preview"]["customer_stated_budget"] == 4000000.0
    assert data["action_draft"] is not None


def test_voice_confirm_and_save_to_crm(client, agent1_token):
    # Explicit confirmation to save into CRM
    confirmation_payload = {
        "extracted_context": {
            "lead_id": 1,
            "lead_name": "أحمد الشناوي",
            "activity_type": "VISIT",
            "preferred_location": "New Cairo / التجمع",
            "objection": "Price too high / السعر مرتفع",
            "customer_stated_budget": 4000000.0,
            "suggested_followup_date": "2026-10-30T14:00:00",
            "next_action": "متابعة العميل بالوحدات البديلة",
            "summary": "معاينة شقة بالتجمع واعتراض على السعر مع تحديد ميزانية 4 مليون"
        },
        "explicit_confirmation": True
    }
    res = client.post(
        "/api/v1/voice/confirm-and-save",
        json=confirmation_payload,
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] == True
    assert data["activity_id"] > 0
    assert data["followup_id"] is not None
    assert data["lead_id"] == 1
    assert data["pipeline_stage"] == "VISIT_COMPLETED"


def test_voice_confirm_and_save_security_checks(client, agent1_token, horizon_token):
    # 1. Missing explicit confirmation must fail with HTTP 400
    res = client.post(
        "/api/v1/voice/confirm-and-save",
        json={
            "extracted_context": {"lead_id": 1},
            "explicit_confirmation": False
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res.status_code == 400

    # 2. Attempt to save for non-existent lead must fail with HTTP 404
    res = client.post(
        "/api/v1/voice/confirm-and-save",
        json={
            "extracted_context": {"lead_id": 99999},
            "explicit_confirmation": True
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res.status_code == 404

    # 3. Unauthenticated request without token must fail with HTTP 401
    res = client.post(
        "/api/v1/voice/confirm-and-save",
        json={
            "extracted_context": {"lead_id": 1},
            "explicit_confirmation": True
        }
    )
    assert res.status_code == 401

    # 4. Cross-company tenant isolation: Agent 1 (Company A) attempting to save to Horizon lead (Company B) must fail with HTTP 404
    horizon_lead_res = client.get("/api/v1/leads", headers={"Authorization": f"Bearer {horizon_token}"})
    assert horizon_lead_res.status_code == 200
    horizon_lead_id = horizon_lead_res.json()[0]["id"]

    res_cross = client.post(
        "/api/v1/voice/confirm-and-save",
        json={
            "extracted_context": {
                "lead_id": horizon_lead_id,
                "activity_type": "NOTE",
                "summary": "Illegal cross-tenant voice update"
            },
            "explicit_confirmation": True
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res_cross.status_code == 404
    assert "does not belong to user company" in res_cross.json()["detail"].lower()
