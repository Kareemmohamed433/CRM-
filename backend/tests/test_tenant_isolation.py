def test_company_data_isolation_on_leads(client, agent1_token, horizon_token):
    # Nexora Agent fetches leads
    res_a = client.get(
        "/api/v1/leads",
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res_a.status_code == 200
    leads_a = res_a.json()
    assert len(leads_a) > 0
    # Make sure none belong to Horizon
    for l in leads_a:
        assert l["full_name"] != "Khaled Barakat"

    # Horizon Agent fetches leads
    res_b = client.get(
        "/api/v1/leads",
        headers={"Authorization": f"Bearer {horizon_token}"}
    )
    assert res_b.status_code == 200
    leads_b = res_b.json()
    assert len(leads_b) > 0
    # All belong to Horizon
    for l in leads_b:
        assert l["full_name"] == "Khaled Barakat"


def test_cannot_access_other_tenant_lead_by_id(client, agent1_token, horizon_token):
    # Get Horizon lead ID
    res_b = client.get(
        "/api/v1/leads",
        headers={"Authorization": f"Bearer {horizon_token}"}
    )
    horizon_lead_id = res_b.json()[0]["id"]

    # Nexora Agent tries to access Horizon lead
    res_hack = client.get(
        f"/api/v1/leads/{horizon_lead_id}",
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res_hack.status_code == 404
    assert "not found or access unauthorized" in res_hack.json()["detail"].lower()


def test_cross_company_transfer_rejected(client, manager_token, horizon_token):
    # Get Horizon agent ID
    res_h = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {horizon_token}"})
    horizon_agent_id = res_h.json()["id"]

    # Nexora manager tries to transfer a Nexora lead to Horizon agent
    res = client.post(
        "/api/v1/transfers",
        json={
            "lead_id": 1,
            "requested_owner_id": horizon_agent_id,
            "reason": "Illegal cross-tenant transfer attempt"
        },
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert res.status_code == 400
    assert "not found or inactive in this company" in res.json()["detail"]
