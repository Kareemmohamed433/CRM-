import time

def test_create_and_manage_lead(client, agent1_token):
    unique_phone = f"+201099{int(time.time()) % 1000000:06d}"
    res = client.post(
        "/api/v1/leads",
        json={
            "full_name": "Mostafa Mahmoud",
            "phone": unique_phone,
            "email": "mostafa.m@test.com",
            "source": "Meta Ads",
            "preferred_location": "New Cairo",
            "budget_max": 4500000.0,
            "property_type": "Apartment",
            "bedrooms": 3,
            "purchase_timeline": "Immediate (1 month)"
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res.status_code == 200, res.text
    lead_data = res.json()
    assert lead_data["full_name"] == "Mostafa Mahmoud"
    assert lead_data["pipeline_stage"] == "NEW"
    assert lead_data["score"] >= 60  # Immediate purchase + budget boost
    assert len(lead_data["score_factors"]) > 0

    lead_id = lead_data["id"]

    # Transition stage to QUALIFIED
    res_stage = client.patch(
        f"/api/v1/leads/{lead_id}/stage",
        json={"pipeline_stage": "QUALIFIED", "notes": "Client confirmed budget and requirements"},
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res_stage.status_code == 200
    assert res_stage.json()["pipeline_stage"] == "QUALIFIED"


def test_visit_outcome_with_objection_does_not_lose_lead(client, agent1_token):
    # Fetch lead 1
    res_lead = client.get("/api/v1/leads/1", headers={"Authorization": f"Bearer {agent1_token}"})
    assert res_lead.status_code == 200
    lead = res_lead.json()["lead"]
    assert lead["pipeline_stage"] != "LOST"

    # Record a visit outcome with price objection
    res_outcome = client.post(
        "/api/v1/activities/visit-outcome",
        json={
            "lead_id": 1,
            "outcome": "Completed - Rejected Unit",
            "objection": "Price too high (> 4M EGP)",
            "customer_stated_budget": 3900000.0,
            "feedback_notes": "العميل عاين الوحدة ولكن السعر مرتفع وميزانيته لا تتجاوز 3.9 مليون",
            "suggest_alternatives": True,
            "next_followup_date": "2026-11-01T12:00:00"
        },
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res_outcome.status_code == 200
    data = res_outcome.json()
    assert data["status"] == "success"
    assert data["lead_pipeline_stage"] == "VISIT_COMPLETED"
    assert data["lead_pipeline_stage"] != "LOST"
    assert len(data["recommended_alternatives"]) > 0
    # Check that recommended alternative is within or near budget
    first_alt = data["recommended_alternatives"][0]
    assert first_alt["total_price"] <= 4000000.0
