import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from app import auth
from main import app

client = TestClient(app)


@pytest.fixture
def api_key(monkeypatch):
    key = "test-key-abcdef0123456789"
    monkeypatch.setenv(auth.ENV_KEYS_NAME, f"testapp:{key}")
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    auth.refresh_valid_api_keys()
    yield key
    auth.refresh_valid_api_keys()


def test_parse_keys_maps_key_to_app():
    keys = auth._parse_keys("gameteamweb:key1,admin:key2")
    assert keys == {"key1": "gameteamweb", "key2": "admin"}


def test_env_keys_are_picked_up(api_key):
    assert auth.get_valid_api_keys()[api_key] == "testapp"


def test_keys_count_reflects_env(api_key):
    response = client.get("/api/v1/auth/keys-count")
    assert response.json()["key_count"] == 1


def test_invalid_key_rejected(api_key):
    response = client.get("/api/v1/db-check", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401


def test_mask_key_hides_the_middle():
    masked = auth.mask_key("abcdefghijklmnopqrstuvwxyz")
    assert masked.startswith("abcdefgh")
    assert masked.endswith("wxyz")
    assert "ijklmnopqrst" not in masked
