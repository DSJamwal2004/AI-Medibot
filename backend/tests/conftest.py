# backend/tests/conftest.py

import pytest
from fastapi.testclient import TestClient
from app.db.session import SessionLocal
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_headers(client):
    # 1️⃣ Register user (ignore error if already exists)
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "testuser@example.com",
            "password": "testpassword",
        },
    )

    # 2️⃣ Login to get token
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "testuser@example.com",
            "password": "testpassword",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    token = response.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}"
    }

@pytest.fixture(autouse=True)
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()