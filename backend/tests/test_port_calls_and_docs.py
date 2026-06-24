def test_get_active_port_calls(client):
    response = client.get("/api/v1/port-calls/active")
    assert response.status_code == 200
    assert "message" in response.json()


from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


@patch("app.api.v1.documents.document_service.generate_port_entry_notification")
def test_generate_nomination_document_endpoint(mock_generate, client, mock_uuid):
    """Endpoint /documents/nominations/{id}/generate powinien delegować do
    document_service i zwrócić metadane wygenerowanego dokumentu."""
    mock_generate.return_value = MagicMock(
        document_id=mock_uuid,
        nomination_id=mock_uuid,
        document_type="port_entry_notification",
        status="generated",
        version_number=1,
        filename="pakiet_nominacyjny_test.pdf",
        file_hash_sha256="a" * 64,
        generated_by="system_auto",
        generated_at=datetime(2026, 6, 23, tzinfo=timezone.utc),
    )

    response = client.post(f"/api/v1/documents/nominations/{mock_uuid}/generate")

    assert response.status_code == 201
    data = response.json()
    assert data["document_id"] == str(mock_uuid)
    assert data["version_number"] == 1
    mock_generate.assert_called_once()


@patch("app.api.v1.documents.document_service.generate_port_entry_notification")
def test_generate_nomination_document_endpoint_404_when_missing(mock_generate, client, mock_uuid):
    from app.core.exceptions import EntityNotFoundError

    mock_generate.side_effect = EntityNotFoundError(entity_name="Nomination", entity_id=mock_uuid)

    response = client.post(f"/api/v1/documents/nominations/{mock_uuid}/generate")

    assert response.status_code == 404


@patch("app.api.v1.documents.document_repository.get_document_by_id")
def test_download_document_endpoint_success(mock_get_doc, client, mock_uuid):
    mock_doc = MagicMock()
    mock_doc.file_data = b"%PDF-1.4 fake content"
    mock_doc.filename = "test.pdf"
    mock_get_doc.return_value = mock_doc

    response = client.get(f"/api/v1/documents/{mock_uuid}/download")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 fake content"
    assert response.headers["content-type"] == "application/pdf"


@patch("app.api.v1.documents.document_repository.get_document_by_id")
def test_download_document_endpoint_404_when_missing(mock_get_doc, client, mock_uuid):
    mock_get_doc.return_value = None

    response = client.get(f"/api/v1/documents/{mock_uuid}/download")

    assert response.status_code == 404