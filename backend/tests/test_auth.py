def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_login_success(client):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": "agent1@nexora.com", "password": "Password123!"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "agent1@nexora.com"
    assert data["user"]["role"] == "SALES_AGENT"


def test_login_failure(client):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": "agent1@nexora.com", "password": "WrongPassword!"}
    )
    assert res.status_code == 401
    assert "Incorrect email or password" in res.json()["detail"]


def test_get_current_user_profile(client, agent1_token):
    res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {agent1_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "agent1@nexora.com"
    assert data["company_name"] == "Nexora Developments & Brokerage"
