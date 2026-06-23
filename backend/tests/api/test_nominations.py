from unittest.mock import MagicMock
from app.models.enums import NominationStatus


def test_parse_email_endpoint_success(client, mock_db, mock_uuid):
    # Przygotowanie Mocka: Zwracamy fałszywe obiekty statku, firmy i portu
    # dla zapytań db.query(...).first()
    mock_item = MagicMock()
    mock_item.vessel_id = mock_uuid
    mock_item.company_id = mock_uuid
    mock_item.port_id = mock_uuid

    mock_db.query.return_value.first.return_value = mock_item

    # Nasz testowy mail
    payload = {
        "subject": "Nomination for MV Hanse Star",
        "body": "Please find attached nomination. ETA tomorrow.",
        "sender_email": "agent@shipline.com"
    }

    # Wykonanie żądania do naszego API
    response = client.post("/api/v1/nominations/parse-email", json=payload)

    # Asercje (sprawdzenia)
    assert response.status_code == 201
    data = response.json()
    assert "nomination_id" in data
    assert data["source_email_subject"] == payload["subject"]
    assert data["status"] == NominationStatus.received.value