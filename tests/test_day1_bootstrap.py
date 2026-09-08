from fastapi.testclient import TestClient

from config.settings import get_settings
from core.db import test_database_connection as check_database_connection
from init_app import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    payload = response.json()

    assert response.status_code == 200
    assert payload["code"] == 0
    assert payload["data"]["status"] == "ok"


def test_settings_are_loaded() -> None:
    settings = get_settings()
    assert settings.app_name == "FastAPI Study RAG Project"
    assert settings.database_url.startswith("sqlite")


def test_database_connection_is_available() -> None:
    assert check_database_connection() is True
