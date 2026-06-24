import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services import document_service
from app.core.exceptions import EntityNotFoundError
from app.schemas.nomination_detail import NominationDetailResponse, VesselSummary


def _make_nomination_detail(**overrides):
    detail = NominationDetailResponse(
        nomination_id=uuid.uuid4(),
        status="parsed_pending_review",
        vessel=VesselSummary(vessel_id=uuid.uuid4(), imo_number="9456789", current_vessel_name="MV Hanse Star"),
        created_at=datetime(2026, 6, 23, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 23, tzinfo=timezone.utc),
    )
    for key, value in overrides.items():
        setattr(detail, key, value)
    return detail


@patch("app.services.document_service.document_repository.save_generated_document")
@patch("app.services.document_service.nomination_view_service.get_nomination_detail")
def test_generate_port_entry_notification_saves_real_pdf(mock_get_detail, mock_save_doc):
    """Weryfikuje, że serwis faktycznie generuje bajty PDF (nie mock) i
    przekazuje je do zapisu w bazie z poprawnym hashem i nazwą pliku."""
    mock_db = MagicMock()
    nomination_id = uuid.uuid4()
    mock_get_detail.return_value = _make_nomination_detail(nomination_id=nomination_id)
    mock_save_doc.return_value = MagicMock(document_id=uuid.uuid4())

    document_service.generate_port_entry_notification(mock_db, nomination_id)

    mock_save_doc.assert_called_once()
    call_kwargs = mock_save_doc.call_args.kwargs

    # To jest realny PDF, nie placeholder - zaczyna się od nagłówka %PDF
    assert call_kwargs["file_data"].startswith(b"%PDF")
    assert len(call_kwargs["file_data"]) > 500  # realny dokument, nie pusty plik

    # Hash faktycznie odpowiada zawartości (nie jest losowy/stały)
    import hashlib
    assert call_kwargs["file_hash_sha256"] == hashlib.sha256(call_kwargs["file_data"]).hexdigest()

    assert "MV_Hanse_Star" in call_kwargs["filename"]
    assert call_kwargs["filename"].endswith(".pdf")


@patch("app.services.document_service.nomination_view_service.get_nomination_detail")
def test_generate_port_entry_notification_raises_when_nomination_missing(mock_get_detail):
    mock_db = MagicMock()
    mock_get_detail.return_value = None

    with pytest.raises(EntityNotFoundError):
        document_service.generate_port_entry_notification(mock_db, uuid.uuid4())


@patch("app.services.document_service.document_repository.save_generated_document")
@patch("app.services.document_service.nomination_view_service.get_nomination_detail")
def test_generate_port_entry_notification_handles_missing_vessel_gracefully(mock_get_detail, mock_save_doc):
    """QUA-006: brak statku (np. jeszcze nieprzypisanego) nie powinien
    wywalić generowania dokumentu - tylko dać generyczną nazwę pliku."""
    mock_db = MagicMock()
    nomination_id = uuid.uuid4()
    mock_get_detail.return_value = _make_nomination_detail(nomination_id=nomination_id, vessel=None)
    mock_save_doc.return_value = MagicMock(document_id=uuid.uuid4())

    document_service.generate_port_entry_notification(mock_db, nomination_id)

    call_kwargs = mock_save_doc.call_args.kwargs
    assert call_kwargs["file_data"].startswith(b"%PDF")
    assert "statek_nieznany" in call_kwargs["filename"]