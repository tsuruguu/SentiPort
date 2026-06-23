import uuid
from app.services.document_service import generate_port_entry_notification


def test_generate_port_entry_notification():
    n_id = uuid.uuid4()
    doc = generate_port_entry_notification(n_id, "Hanse Star", "2026-06-25T10:00:00Z")

    assert doc["nomination_id"] == str(n_id)
    assert "file_url" in doc
    assert "port_entry_notification" in doc["document_type"]