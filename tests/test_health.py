import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["version"] == "1.0.0"


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "GameTeamAPI"}


def test_keys_count():
    response = client.get("/api/v1/auth/keys-count")
    assert response.status_code == 200
    assert "key_count" in response.json()


def test_db_check_requires_api_key():
    response = client.get("/api/v1/db-check")
    assert response.status_code == 401
