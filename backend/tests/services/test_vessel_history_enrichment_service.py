import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services import vessel_history_enrichment_service as svc
from app.core.exceptions import LLMParsingError, EntityNotFoundError
from app.models.operations import Nomination
from app.schemas.vessel_enrichment import (
    VesselHistoryPayload, VesselIdentitySnapshot, PSCInspectionEntry, PSCDeficiencySummary,
    PreviousNominationEntry, PreviousCargoSummary, TechnicalSpecsSnapshot, NameHistoryEntry,
)


def _make_nomination(**overrides):
    nom = Nomination(
        nomination_id=uuid.uuid4(),
        vessel_id=uuid.uuid4(),
        destination_port_id=uuid.uuid4(),
    )
    for key, value in overrides.items():
        setattr(nom, key, value)
    return nom


def _minimal_payload(**overrides):
    payload = VesselHistoryPayload(
        nomination_id=str(uuid.uuid4()),
        vessel=VesselIdentitySnapshot(imo_number="9456789", current_name="MV Test"),
    )
    for key, value in overrides.items():
        setattr(payload, key, value)
    return payload


# ---------------------------------------------------------------------------
# build_vessel_history_payload
# ---------------------------------------------------------------------------

def test_build_payload_raises_when_nomination_has_no_vessel():
    mock_db = MagicMock()
    nomination = _make_nomination(vessel_id=None)

    with pytest.raises(LLMParsingError):
        svc.build_vessel_history_payload(mock_db, nomination)


@patch("app.repositories.vessel_repository.get_vessel_by_id")
def test_build_payload_raises_when_vessel_missing(mock_get_vessel):
    mock_db = MagicMock()
    nomination = _make_nomination()
    mock_get_vessel.return_value = None

    with pytest.raises(EntityNotFoundError):
        svc.build_vessel_history_payload(mock_db, nomination)


@patch("app.repositories.vessel_repository.get_cargo_for_nominations")
@patch("app.repositories.vessel_repository.get_previous_nominations")
@patch("app.repositories.vessel_repository.get_current_risk_assessment")
@patch("app.repositories.vessel_repository.get_sanctions_screenings")
@patch("app.repositories.vessel_repository.get_psc_deficiencies")
@patch("app.repositories.vessel_repository.get_psc_inspections")
@patch("app.repositories.vessel_repository.get_certificates")
@patch("app.repositories.company_repository.get_company_by_id")
@patch("app.repositories.vessel_repository.get_company_roles")
@patch("app.repositories.vessel_repository.get_technical_specs_history")
@patch("app.repositories.vessel_repository.get_name_history")
@patch("app.repositories.vessel_repository.get_vessel_by_id")
def test_build_payload_assembles_complete_history(
    mock_get_vessel, mock_name_history, mock_specs_history, mock_company_roles,
    mock_get_company, mock_certificates, mock_psc_inspections, mock_psc_deficiencies,
    mock_sanctions, mock_risk, mock_prev_noms, mock_cargo,
):
    mock_db = MagicMock()
    nomination = _make_nomination()

    mock_get_vessel.return_value = MagicMock(
        imo_number="9456789", current_vessel_name="MV Test Vessel",
        mmsi="123456789", call_sign="ABCD", year_built=2015, is_active=True,
    )
    mock_name_history.return_value = []
    mock_specs_history.return_value = []
    mock_company_roles.return_value = []
    mock_certificates.return_value = []
    mock_psc_inspections.return_value = []
    mock_psc_deficiencies.return_value = []
    mock_sanctions.return_value = []
    mock_risk.return_value = None
    mock_prev_noms.return_value = []
    mock_cargo.return_value = []

    payload = svc.build_vessel_history_payload(mock_db, nomination)

    assert payload.vessel.imo_number == "9456789"
    assert payload.vessel.current_name == "MV Test Vessel"
    assert payload.nomination_id == str(nomination.nomination_id)
    assert payload.truncated_sections == []


@patch("app.repositories.vessel_repository.get_cargo_for_nominations")
@patch("app.repositories.vessel_repository.get_previous_nominations")
@patch("app.repositories.vessel_repository.get_current_risk_assessment")
@patch("app.repositories.vessel_repository.get_sanctions_screenings")
@patch("app.repositories.vessel_repository.get_psc_deficiencies")
@patch("app.repositories.vessel_repository.get_psc_inspections")
@patch("app.repositories.vessel_repository.get_certificates")
@patch("app.repositories.vessel_repository.get_company_roles")
@patch("app.repositories.vessel_repository.get_technical_specs_history")
@patch("app.repositories.vessel_repository.get_name_history")
@patch("app.repositories.vessel_repository.get_vessel_by_id")
def test_build_payload_includes_previous_nominations_with_cargo(
    mock_get_vessel, mock_name_history, mock_specs_history, mock_company_roles,
    mock_certificates, mock_psc_inspections, mock_psc_deficiencies,
    mock_sanctions, mock_risk, mock_prev_noms, mock_cargo,
):
    mock_db = MagicMock()
    nomination = _make_nomination()

    mock_get_vessel.return_value = MagicMock(
        imo_number="9456789", current_vessel_name="MV Test", mmsi=None, call_sign=None,
        year_built=None, is_active=True,
    )
    mock_name_history.return_value = []
    mock_specs_history.return_value = []
    mock_company_roles.return_value = []
    mock_certificates.return_value = []
    mock_psc_inspections.return_value = []
    mock_psc_deficiencies.return_value = []
    mock_sanctions.return_value = []
    mock_risk.return_value = None

    prev_nom_id = uuid.uuid4()
    prev_nomination = MagicMock(
        nomination_id=prev_nom_id, status="completed", eta=None, destination_port_id=None,
    )
    mock_prev_noms.return_value = [prev_nomination]

    cargo_item = MagicMock(
        nomination_id=prev_nom_id, cargo_description="Kontenery suche",
        imdg_hazard_class="none", requires_refrigeration=False,
    )
    mock_cargo.return_value = [cargo_item]

    payload = svc.build_vessel_history_payload(mock_db, nomination)

    assert len(payload.previous_nominations) == 1
    assert payload.previous_nominations[0].cargo[0].description == "Kontenery suche"


# ---------------------------------------------------------------------------
# _enforce_size_limit / truncation
# ---------------------------------------------------------------------------

def test_enforce_size_limit_returns_unchanged_when_within_limit():
    payload = _minimal_payload()
    result = svc._enforce_size_limit(payload)
    assert result.truncated_sections == []


def test_enforce_size_limit_truncates_psc_deficiencies_first():
    """Pierwszy krok obcinania to usterki PSC (najbardziej 'rozdmuchana'
    sekcja tekstowa) - sprawdzamy, że gigantyczny payload faktycznie się
    zmniejsza i fakt obcięcia jest zapisany."""
    huge_deficiency_text = "x" * 2000
    inspections = [
        PSCInspectionEntry(
            inspection_date=date(2025, 1, 1),
            deficiencies=[PSCDeficiencySummary(description=huge_deficiency_text) for _ in range(50)],
        )
        for _ in range(30)
    ]
    payload = _minimal_payload(psc_inspections=inspections)

    original_size = svc._payload_size_bytes(payload)
    assert original_size > svc.MAX_PAYLOAD_SIZE_BYTES  # sanity check na teście

    result = svc._enforce_size_limit(payload)

    assert svc._payload_size_bytes(result) < original_size
    assert "psc_deficiencies_details" in result.truncated_sections
    assert all(insp.deficiencies == [] for insp in result.psc_inspections)


def test_enforce_size_limit_eventually_fits_under_limit():
    """Po pełnym ciągu obcięć, realistyczny nadmiarowy payload powinien
    finalnie zmieścić się pod limitem 50kB."""
    huge_text = "y" * 1500
    inspections = [
        PSCInspectionEntry(
            inspection_date=date(2025, 1, 1),
            inspecting_authority="Paris MoU",
            deficiencies=[PSCDeficiencySummary(description=huge_text) for _ in range(20)],
        )
        for _ in range(15)
    ]
    previous_noms = [
        PreviousNominationEntry(
            nomination_id=str(uuid.uuid4()), status="completed",
            cargo=[PreviousCargoSummary(description=huge_text) for _ in range(10)],
        )
        for _ in range(20)
    ]
    payload = _minimal_payload(psc_inspections=inspections, previous_nominations=previous_noms)

    result = svc._enforce_size_limit(payload)

    assert svc._payload_size_bytes(result) <= svc.MAX_PAYLOAD_SIZE_BYTES
    assert len(result.truncated_sections) > 0


def test_enforce_size_limit_does_not_truncate_when_already_small():
    payload = _minimal_payload(
        name_history=[NameHistoryEntry(vessel_name="MV Test")],
        technical_specs_history=[TechnicalSpecsSnapshot(length_overall_meters=180.0)],
    )
    result = svc._enforce_size_limit(payload)
    assert result.truncated_sections == []
    assert len(result.name_history) == 1


# ---------------------------------------------------------------------------
# call_enrichment_agent
# ---------------------------------------------------------------------------

@patch("app.services.vessel_history_enrichment_service.settings")
def test_call_enrichment_agent_missing_credentials_raises(mock_settings):
    mock_settings.ELEVENLABS_API_KEY = None
    mock_settings.ELEVENLABS_ENRICHMENT_AGENT_ID = None

    with pytest.raises(LLMParsingError):
        svc.call_enrichment_agent(_minimal_payload())


@patch("app.services.vessel_history_enrichment_service.Conversation")
@patch("app.services.vessel_history_enrichment_service.ElevenLabs")
@patch("app.services.vessel_history_enrichment_service.settings")
def test_call_enrichment_agent_success(mock_settings, mock_elevenlabs_cls, mock_conversation_cls):
    mock_settings.ELEVENLABS_API_KEY = "xi-secret"
    mock_settings.ELEVENLABS_ENRICHMENT_AGENT_ID = "agent_enrichment_456"

    mock_conversation = MagicMock()
    mock_conversation_cls.return_value = mock_conversation

    response_json = '{"proposed_configuration": [], "inconsistencies_to_clarify": []}'

    def fake_start_session():
        callback = mock_conversation_cls.call_args.kwargs["callback_agent_response"]
        callback(response_json)

    mock_conversation.start_session.side_effect = fake_start_session

    result = svc.call_enrichment_agent(_minimal_payload())

    assert result == {"proposed_configuration": [], "inconsistencies_to_clarify": []}
    # Sprawdzamy, że użyto agent_id WZBOGACENIA, nie agenta ekstrakcji
    mock_conversation_cls.assert_called_once()
    assert mock_conversation_cls.call_args.args[1] == "agent_enrichment_456"


@patch("app.services.vessel_history_enrichment_service.Conversation")
@patch("app.services.vessel_history_enrichment_service.ElevenLabs")
@patch("app.services.vessel_history_enrichment_service.settings")
def test_call_enrichment_agent_timeout_raises(mock_settings, mock_elevenlabs_cls, mock_conversation_cls):
    mock_settings.ELEVENLABS_API_KEY = "xi-secret"
    mock_settings.ELEVENLABS_ENRICHMENT_AGENT_ID = "agent_enrichment_456"
    mock_conversation_cls.return_value = MagicMock()

    with patch("app.services.vessel_history_enrichment_service.AGENT_RESPONSE_TIMEOUT_SECONDS", 0.05):
        with pytest.raises(LLMParsingError):
            svc.call_enrichment_agent(_minimal_payload())


# ---------------------------------------------------------------------------
# enrich_nomination_with_vessel_history (pełny przepływ)
# ---------------------------------------------------------------------------

@patch("app.services.vessel_history_enrichment_service.call_enrichment_agent")
@patch("app.services.vessel_history_enrichment_service.build_vessel_history_payload")
def test_enrich_nomination_full_flow_returns_parsed_response(mock_build_payload, mock_call_agent):
    mock_db = MagicMock()
    nomination = _make_nomination()
    mock_db.query.return_value.filter.return_value.first.return_value = nomination

    mock_build_payload.return_value = _minimal_payload()
    mock_call_agent.return_value = {
        "proposed_configuration": [
            {"field_name": "requested_berth", "proposed_value": "Nabrzeże Helskie", "is_inferred": True}
        ],
        "inconsistencies_to_clarify": [
            {"field_name": "etd", "description": "Brak ETD w mailu, a poprzednie wizyty trwały zwykle 2 dni"}
        ],
    }

    result = svc.enrich_nomination_with_vessel_history(mock_db, nomination.nomination_id)

    assert len(result.proposed_configuration) == 1
    assert result.proposed_configuration[0].is_inferred is True
    assert len(result.inconsistencies_to_clarify) == 1


@patch("app.services.vessel_history_enrichment_service.call_enrichment_agent")
@patch("app.services.vessel_history_enrichment_service.build_vessel_history_payload")
def test_enrich_nomination_raises_clear_error_when_agent_returns_wrong_shape(mock_build_payload, mock_call_agent):
    """Reprodukuje realny bug: agent zwrócił proposed_configuration jako
    OBIEKT (dict pól statku) zamiast LISTY ProposedConfigField - powinno
    dać jasny LLMParsingError (422) z konkretnym opisem niezgodności,
    nie surowy ValidationError/500."""
    mock_db = MagicMock()
    nomination = _make_nomination()
    mock_db.query.return_value.filter.return_value.first.return_value = nomination

    mock_build_payload.return_value = _minimal_payload()
    mock_call_agent.return_value = {
        "proposed_configuration": {
            "vessel_name": "Mewa Baltic",
            "cargo_handling_rate_tph": 0,
        },
        "inconsistencies_to_clarify": [],
    }

    with pytest.raises(LLMParsingError) as exc_info:
        svc.enrich_nomination_with_vessel_history(mock_db, nomination.nomination_id)

    assert "VesselEnrichmentResponse" in str(exc_info.value.payload)


def test_enrich_nomination_raises_when_nomination_missing():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(EntityNotFoundError):
        svc.enrich_nomination_with_vessel_history(mock_db, uuid.uuid4())