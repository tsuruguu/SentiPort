from unittest.mock import MagicMock
from app.models.operations import Nomination


def test_parse_email_endpoint_success(client, mock_db, mock_uuid):
    # 1. Przygotowanie mocków dla zapytań .first()
    mock_dummy = MagicMock()
    mock_dummy.vessel_id = mock_uuid
    mock_dummy.company_id = mock_uuid
    mock_dummy.port_id = mock_uuid

    # API robi 3 zapytania .first() z rzędu
    mock_db.query.return_value.first.side_effect = [mock_dummy, mock_dummy, mock_dummy]

    # 2. Mockujemy zachowanie refresh() tak, żeby po prostu "było" (nic nie robi)
    # W testach FastAPI, jeśli nie odświeżamy z bazy, po prostu przypiszemy ID ręcznie
    def side_effect_refresh(obj):
        if obj.nomination_id is None:
            obj.nomination_id = mock_uuid
        return None

    mock_db.refresh.side_effect = side_effect_refresh

    payload = {
        "subject": "Nomination for MV Hanse Star",
        "body": "Please find attached nomination. ETA tomorrow.",
        "sender_email": "agent@shipline.com"
    }

    response = client.post("/api/v1/nominations/parse-email", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["nomination_id"] == str(mock_uuid)
    assert data["status"] == "received"