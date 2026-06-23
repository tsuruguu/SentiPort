import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import uuid

from app.main import app
from app.api.deps import get_db

@pytest.fixture
def mock_db():
    """Tworzy fałszywą (mockowaną) sesję bazy danych."""
    return MagicMock()

@pytest.fixture
def client(mock_db):
    """
    Tworzy klienta testowego FastAPI i wstrzykuje mu naszą fałszywą bazę
    zamiast prawdziwego połączenia do Postgresa.
    """
    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def mock_uuid():
    return uuid.uuid4()