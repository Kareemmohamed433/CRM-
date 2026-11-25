import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.seed.seed_data import seed_database
from backend.app.core.database import SessionLocal

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    seed_database()

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def agent1_token(client):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": "agent1@nexora.com", "password": "Password123!"}
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]

@pytest.fixture
def manager_token(client):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": "manager@nexora.com", "password": "Password123!"}
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]

@pytest.fixture
def horizon_token(client):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": "agent@horizon.com", "password": "Password123!"}
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]
