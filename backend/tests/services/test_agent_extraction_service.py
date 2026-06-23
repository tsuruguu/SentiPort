from unittest.mock import MagicMock, patch
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


@patch("app.api.v1.nominations.agent_extraction_service.extract_and_apply")
def test_extract_endpoint_calls_agent_service_and_returns_updated_nomination(mock_extract, client, mock_db, mock_uuid):
    """Endpoint /extract powinien po prostu delegować do agent_extraction_service
    i zwrócić zaktualizowaną nominację."""
    updated_nomination = Nomination(
        nomination_id=mock_uuid,
        vessel_id=mock_uuid,
        nominating_company_id=mock_uuid,
        destination_port_id=mock_uuid,
        status="parsed_pending_review",
        source_email_subject="Nominacja - MV Test",
        assigned_agent_name="Agent Hakatonowy",
    )
    mock_extract.return_value = updated_nomination

    response = client.post(f"/api/v1/nominations/{mock_uuid}/extract")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "parsed_pending_review"
    mock_extract.assert_called_once()