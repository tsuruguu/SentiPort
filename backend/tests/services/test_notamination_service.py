import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.services import nomination_view_service
from app.models.operations import Nomination
from app.models.vessel import Vessel
from app.models.company import Company
from app.models.reference import Port


def _make_nomination(**overrides):
    nom = Nomination(
        nomination_id=uuid.uuid4(),
        vessel_id=uuid.uuid4(),
        nominating_company_id=uuid.uuid4(),
        destination_port_id=uuid.uuid4(),
        status="parsed_pending_review",
        source_email_subject="Nominacja - MV Test",
        source_email_sender_address="armator1@armatorzy.pl",
        source_email_received_at=datetime(2026, 6, 23, 17, 30, tzinfo=timezone.utc),
        llm_extraction_metadata={"confidence": 0.91, "fields_missing": ["etd"], "model": "elevenlabs-agent-v1"},
        created_at=datetime(2026, 6, 23, 17, 35, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 23, 17, 35, tzinfo=timezone.utc),
    )
    for key, value in overrides.items():
        setattr(nom, key, value)
    return nom


@patch("app.repositories.nomination_repository.get_unstructured_notes")
@patch("app.repositories.company_repository.get_company_by_id")
@patch("app.repositories.vessel_repository.get_vessel_by_id")
@patch("app.repositories.port_repository.get_port_by_id")
def test_build_list_item_resolves_nested_summaries(mock_get_port, mock_get_vessel, mock_get_company, mock_get_notes):
    mock_db = MagicMock()
    nomination = _make_nomination()

    mock_get_vessel.return_value = Vessel(
        vessel_id=nomination.vessel_id, imo_number="9456789", current_vessel_name="MV Test Vessel", year_built=2015
    )
    mock_get_company.return_value = Company(
        company_id=nomination.nominating_company_id, company_name="Armator Sp. z o.o.", is_sanctioned=False
    )
    mock_get_port.return_value = Port(
        port_id=nomination.destination_port_id, un_locode="PLGDY", port_name="Gdynia"
    )
    mock_get_notes.return_value = []

    item = nomination_view_service.build_list_item(mock_db, nomination)

    assert item.vessel.current_vessel_name == "MV Test Vessel"
    assert item.nominating_company.company_name == "Armator Sp. z o.o."
    assert item.destination_port.un_locode == "PLGDY"
    assert item.confidence_score == 0.91
    assert item.requires_human_review is False


@patch("app.repositories.nomination_repository.get_unstructured_notes")
@patch("app.repositories.company_repository.get_company_by_id")
@patch("app.repositories.vessel_repository.get_vessel_by_id")
@patch("app.repositories.port_repository.get_port_by_id")
def test_build_list_item_flags_unreviewed_notes(mock_get_port, mock_get_vessel, mock_get_company, mock_get_notes):
    """Jeśli istnieje notatka wymagająca przeglądu człowieka, która
    jeszcze nie została zweryfikowana, lista powinna to zasygnalizować."""
    mock_db = MagicMock()
    nomination = _make_nomination()
    mock_get_vessel.return_value = None
    mock_get_company.return_value = None
    mock_get_port.return_value = None

    unreviewed_note = MagicMock(requires_human_review=True, reviewed_at=None)
    mock_get_notes.return_value = [unreviewed_note]

    item = nomination_view_service.build_list_item(mock_db, nomination)

    assert item.requires_human_review is True


@patch("app.repositories.nomination_repository.get_unstructured_notes")
@patch("app.repositories.company_repository.get_company_by_id")
@patch("app.repositories.vessel_repository.get_vessel_by_id")
@patch("app.repositories.port_repository.get_port_by_id")
def test_build_list_item_does_not_flag_reviewed_notes(mock_get_port, mock_get_vessel, mock_get_company, mock_get_notes):
    mock_db = MagicMock()
    nomination = _make_nomination()
    mock_get_vessel.return_value = None
    mock_get_company.return_value = None
    mock_get_port.return_value = None

    reviewed_note = MagicMock(requires_human_review=True, reviewed_at=datetime(2026, 6, 23, tzinfo=timezone.utc))
    mock_get_notes.return_value = [reviewed_note]

    item = nomination_view_service.build_list_item(mock_db, nomination)

    assert item.requires_human_review is False


@patch("app.services.nomination_view_service.build_list_item")
@patch("app.repositories.nomination_repository.count_nominations")
@patch("app.repositories.nomination_repository.list_nominations")
def test_list_nominations_returns_paginated_response(mock_list, mock_count, mock_build_item):
    from app.schemas.nomination_detail import NominationListItemResponse

    mock_db = MagicMock()
    nominations = [_make_nomination(), _make_nomination()]
    mock_list.return_value = nominations
    mock_count.return_value = 42

    def fake_build_item(db, nom):
        return NominationListItemResponse(
            nomination_id=nom.nomination_id,
            status=nom.status,
            created_at=nom.created_at,
        )

    mock_build_item.side_effect = fake_build_item

    result = nomination_view_service.list_nominations(mock_db, limit=2, offset=0)

    assert result.total == 42
    assert result.limit == 2
    assert result.offset == 0
    assert len(result.items) == 2
    assert result.items[0].nomination_id == nominations[0].nomination_id


@patch("app.repositories.nomination_repository.get_nomination")
def test_get_nomination_detail_returns_none_when_missing(mock_get_nomination):
    mock_db = MagicMock()
    mock_get_nomination.return_value = None

    result = nomination_view_service.get_nomination_detail(mock_db, uuid.uuid4())

    assert result is None


@patch("app.repositories.nomination_repository.get_attachments")
@patch("app.repositories.nomination_repository.get_unstructured_notes")
@patch("app.repositories.nomination_repository.get_requested_services")
@patch("app.repositories.nomination_repository.get_cargo_items")
@patch("app.repositories.company_repository.get_contact_by_id")
@patch("app.repositories.company_repository.get_company_by_id")
@patch("app.repositories.port_repository.get_berth_by_id")
@patch("app.repositories.port_repository.get_port_by_id")
@patch("app.repositories.vessel_repository.get_vessel_by_id")
@patch("app.repositories.nomination_repository.get_nomination")
def test_get_nomination_detail_assembles_full_view(
    mock_get_nomination, mock_get_vessel, mock_get_port, mock_get_berth,
    mock_get_company, mock_get_contact, mock_get_cargo, mock_get_services,
    mock_get_notes, mock_get_attachments,
):
    mock_db = MagicMock()
    nomination = _make_nomination(requested_berth_id=uuid.uuid4(), assigned_berth_id=None)
    mock_get_nomination.return_value = nomination

    mock_get_vessel.return_value = Vessel(
        vessel_id=nomination.vessel_id, imo_number="9456789", current_vessel_name="MV Test Vessel"
    )
    mock_get_port.return_value = Port(port_id=nomination.destination_port_id, un_locode="PLGDY", port_name="Gdynia")
    mock_get_berth.return_value = None  # requested_berth lookup zwraca None - OK, nullable
    mock_get_company.return_value = None
    mock_get_contact.return_value = None
    mock_get_cargo.return_value = []
    mock_get_services.return_value = []
    mock_get_notes.return_value = []
    mock_get_attachments.return_value = []

    # db.query(...).filter(...).order_by(...).first() dla vessel_technical_specs
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

    detail = nomination_view_service.get_nomination_detail(mock_db, nomination.nomination_id)

    assert detail is not None
    assert detail.nomination_id == nomination.nomination_id
    assert detail.vessel.current_vessel_name == "MV Test Vessel"
    assert detail.destination_port.un_locode == "PLGDY"
    assert detail.confidence_score == 0.91
    assert detail.fields_missing == ["etd"]
    assert detail.extraction_model == "elevenlabs-agent-v1"