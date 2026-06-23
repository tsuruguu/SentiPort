import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services import agent_extraction_service
from app.core.exceptions import LLMParsingError, EntityNotFoundError
from app.models.operations import Nomination


def _make_nomination(**overrides):
    nom = Nomination(
        nomination_id=uuid.uuid4(),
        vessel_id=uuid.uuid4(),
        nominating_company_id=uuid.uuid4(),
        destination_port_id=uuid.uuid4(),
        source_email_subject="Nominacja - MV Test",
        source_email_body_raw="Treść maila...",
        source_email_sender_address="armator1@armatorzy.pl",
        source_email_received_at=datetime(2026, 6, 23, 17, 30, tzinfo=timezone.utc),
    )
    for key, value in overrides.items():
        setattr(nom, key, value)
    return nom


def test_build_agent_payload_contains_only_real_email_fields():
    nomination = _make_nomination()
    payload = agent_extraction_service._build_agent_payload(nomination)

    assert payload["nomination_id"] == str(nomination.nomination_id)
    assert payload["email"]["subject"] == "Nominacja - MV Test"
    assert payload["email"]["sender_address"] == "armator1@armatorzy.pl"
    assert payload["email"]["received_at"] == "2026-06-23T17:30:00+00:00"


@patch("app.services.agent_extraction_service.settings")
@patch("app.services.agent_extraction_service.httpx.post")
def test_call_extraction_agent_success(mock_post, mock_settings):
    mock_settings.AGENT_API_URL = "https://agent.example.com/extract"
    mock_settings.AGENT_API_KEY = "secret-token"

    mock_response = MagicMock()
    mock_response.json.return_value = {"vessel": {"imo_number": "9456789"}}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    result = agent_extraction_service.call_extraction_agent({"nomination_id": "abc"})

    assert result == {"vessel": {"imo_number": "9456789"}}
    called_kwargs = mock_post.call_args.kwargs
    assert called_kwargs["headers"]["Authorization"] == "Bearer secret-token"


@patch("app.services.agent_extraction_service.settings")
def test_call_extraction_agent_missing_url_raises(mock_settings):
    mock_settings.AGENT_API_URL = None

    with pytest.raises(LLMParsingError):
        agent_extraction_service.call_extraction_agent({"nomination_id": "abc"})


@patch("app.repositories.vessel_repository.get_vessel_by_imo")
@patch("app.repositories.port_repository.get_port_by_name_or_locode")
@patch("app.repositories.company_repository.get_company_by_name")
def test_apply_extraction_result_resolves_existing_records_by_lookup(
    mock_get_company, mock_get_port, mock_get_vessel
):
    """Kluczowy test: agent zwraca IMO/LOCODE/nazwę firmy, a serwis
    powinien DOCIĄGNĄĆ istniejące rekordy z bazy, nie tworzyć nowych ad-hoc."""
    mock_db = MagicMock()
    nomination = _make_nomination()

    existing_vessel = MagicMock(vessel_id=uuid.uuid4())
    existing_port = MagicMock(port_id=uuid.uuid4())
    existing_company = MagicMock(company_id=uuid.uuid4())
    mock_get_vessel.return_value = existing_vessel
    mock_get_port.return_value = existing_port
    mock_get_company.return_value = existing_company

    extracted = {
        "vessel": {"imo_number": "9456789", "name": "MV Test Vessel"},
        "port_locode": "PLGDY",
        "nominating_company_name": "Armator Sp. z o.o.",
        "eta": "2026-07-01T10:00:00Z",
        "confidence_score": 0.91,
        "extraction_model": "elevenlabs-agent-v1",
        "fields_missing": ["etd"],
        "cargo": None,
        "unstructured_notes": [],
    }

    result = agent_extraction_service.apply_extraction_result(mock_db, nomination, extracted)

    assert result.vessel_id == existing_vessel.vessel_id
    assert result.destination_port_id == existing_port.port_id
    assert result.nominating_company_id == existing_company.company_id
    assert result.eta == "2026-07-01T10:00:00Z"
    assert result.llm_extraction_metadata["confidence"] == 0.91
    assert result.llm_extraction_metadata["fields_missing"] == ["etd"]
    mock_db.commit.assert_called_once()


@patch("app.repositories.vessel_repository.get_vessel_by_imo")
def test_apply_extraction_result_does_not_clear_existing_value_when_agent_returns_nothing(mock_get_vessel):
    """Jeśli agent NIE znalazł numeru IMO w mailu, istniejący vessel_id
    (np. domyślny z importu) nie powinien zostać wyczyszczony."""
    mock_db = MagicMock()
    original_vessel_id = uuid.uuid4()
    nomination = _make_nomination(vessel_id=original_vessel_id)

    extracted = {
        "vessel": {"imo_number": None},
        "port_locode": None,
        "nominating_company_name": None,
        "cargo": None,
        "unstructured_notes": [],
    }

    result = agent_extraction_service.apply_extraction_result(mock_db, nomination, extracted)

    assert result.vessel_id == original_vessel_id
    mock_get_vessel.assert_not_called()


def test_apply_extraction_result_saves_cargo_manifest_when_present():
    mock_db = MagicMock()
    nomination = _make_nomination()

    extracted = {
        "vessel": {},
        "cargo": {
            "description": "Kontenery mieszane, w tym reefer",
            "quantity": 120,
            "unit": "TEU",
            "imdg_hazard_class": "none",
            "requires_refrigeration": True,
            "is_perishable": True,
        },
        "unstructured_notes": ["Armator prosi o priorytetowe cumowanie"],
    }

    agent_extraction_service.apply_extraction_result(mock_db, nomination, extracted)

    # db.add powinien zostać wywołany dla: nomination + cargo_manifest + 1 notatka
    assert mock_db.add.call_count == 3


def test_apply_extraction_result_unknown_imdg_class_falls_back_to_none():
    """Jeśli agent zwróci wartość IMDG, której nie ma w naszym enumie,
    nie wybuchamy - zapisujemy 'none' i logujemy ostrzeżenie."""
    from app.models.enums import ImdgHazardClass
    resolved = agent_extraction_service._resolve_imdg_class("nieznana_klasa_xyz")
    assert resolved == ImdgHazardClass.none


@patch("app.services.agent_extraction_service.call_extraction_agent")
def test_extract_and_apply_raises_when_nomination_missing(mock_call_agent):
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(EntityNotFoundError):
        agent_extraction_service.extract_and_apply(mock_db, uuid.uuid4())

    mock_call_agent.assert_not_called()