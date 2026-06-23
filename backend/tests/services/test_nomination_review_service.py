import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.services import nomination_review_service
from app.core.exceptions import EntityNotFoundError, InvalidStatusTransitionError, InvalidBerthAssignmentError
from app.models.operations import Nomination
from app.models.enums import NominationStatus


def _make_nomination(**overrides):
    nom = Nomination(
        nomination_id=uuid.uuid4(),
        vessel_id=uuid.uuid4(),
        nominating_company_id=uuid.uuid4(),
        destination_port_id=uuid.uuid4(),
        status=NominationStatus.parsed_pending_review,
    )
    for key, value in overrides.items():
        setattr(nom, key, value)
    return nom


# ---------------------------------------------------------------------------
# assign_berth
# ---------------------------------------------------------------------------

@patch("app.repositories.nomination_repository.set_assigned_berth")
@patch("app.repositories.port_repository.get_berth_by_id")
@patch("app.repositories.nomination_repository.get_nomination")
def test_assign_berth_success_when_berth_belongs_to_destination_port(mock_get_nom, mock_get_berth, mock_set_berth):
    mock_db = MagicMock()
    nomination = _make_nomination()
    mock_get_nom.return_value = nomination

    berth_id = uuid.uuid4()
    mock_get_berth.return_value = MagicMock(berth_id=berth_id, port_id=nomination.destination_port_id)
    mock_set_berth.return_value = nomination

    nomination_review_service.assign_berth(mock_db, nomination.nomination_id, berth_id)

    mock_set_berth.assert_called_once_with(mock_db, nomination, berth_id)


@patch("app.repositories.port_repository.get_berth_by_id")
@patch("app.repositories.nomination_repository.get_nomination")
def test_assign_berth_rejects_berth_from_different_port(mock_get_nom, mock_get_berth):
    """Nabrzeże z innego portu niż port docelowy nominacji musi być
    odrzucone - to jest błąd integralności, nie luźna walidacja."""
    mock_db = MagicMock()
    nomination = _make_nomination()
    mock_get_nom.return_value = nomination

    berth_id = uuid.uuid4()
    mock_get_berth.return_value = MagicMock(berth_id=berth_id, port_id=uuid.uuid4())  # inny port

    with pytest.raises(InvalidBerthAssignmentError):
        nomination_review_service.assign_berth(mock_db, nomination.nomination_id, berth_id)


@patch("app.repositories.port_repository.get_berth_by_id")
@patch("app.repositories.nomination_repository.get_nomination")
def test_assign_berth_rejects_nonexistent_berth(mock_get_nom, mock_get_berth):
    mock_db = MagicMock()
    nomination = _make_nomination()
    mock_get_nom.return_value = nomination
    mock_get_berth.return_value = None

    with pytest.raises(InvalidBerthAssignmentError):
        nomination_review_service.assign_berth(mock_db, nomination.nomination_id, uuid.uuid4())


@patch("app.repositories.nomination_repository.set_assigned_berth")
@patch("app.repositories.nomination_repository.get_nomination")
def test_assign_berth_allows_clearing_with_none(mock_get_nom, mock_set_berth):
    """berth_id=None powinno czyścić przypisanie bez żadnej walidacji
    portu (nie ma nabrzeża do sprawdzenia)."""
    mock_db = MagicMock()
    nomination = _make_nomination()
    mock_get_nom.return_value = nomination
    mock_set_berth.return_value = nomination

    nomination_review_service.assign_berth(mock_db, nomination.nomination_id, None)

    mock_set_berth.assert_called_once_with(mock_db, nomination, None)


@patch("app.repositories.nomination_repository.get_nomination")
def test_assign_berth_raises_when_nomination_missing(mock_get_nom):
    mock_db = MagicMock()
    mock_get_nom.return_value = None

    with pytest.raises(EntityNotFoundError):
        nomination_review_service.assign_berth(mock_db, uuid.uuid4(), uuid.uuid4())


# ---------------------------------------------------------------------------
# change_status
# ---------------------------------------------------------------------------

@patch("app.repositories.nomination_repository.set_status")
@patch("app.repositories.nomination_repository.get_nomination")
def test_change_status_allows_normal_transition(mock_get_nom, mock_set_status):
    mock_db = MagicMock()
    nomination = _make_nomination(status=NominationStatus.parsed_pending_review)
    mock_get_nom.return_value = nomination
    mock_set_status.return_value = nomination

    nomination_review_service.change_status(mock_db, nomination.nomination_id, NominationStatus.verified)

    mock_set_status.assert_called_once_with(mock_db, nomination, NominationStatus.verified)


@patch("app.repositories.nomination_repository.set_status")
@patch("app.repositories.nomination_repository.get_nomination")
def test_change_status_allows_going_backward(mock_get_nom, mock_set_status):
    """Luźna walidacja: cofnięcie z 'verified' do 'parsed_pending_review'
    (np. agent zauważył błąd) jest dozwolone."""
    mock_db = MagicMock()
    nomination = _make_nomination(status=NominationStatus.verified)
    mock_get_nom.return_value = nomination
    mock_set_status.return_value = nomination

    nomination_review_service.change_status(mock_db, nomination.nomination_id, NominationStatus.parsed_pending_review)

    mock_set_status.assert_called_once()


@pytest.mark.parametrize("terminal_status", [
    NominationStatus.completed, NominationStatus.cancelled, NominationStatus.rejected,
])
@patch("app.repositories.nomination_repository.get_nomination")
def test_change_status_blocks_leaving_terminal_status(mock_get_nom, terminal_status):
    """Status końcowy (completed/cancelled/rejected) jest ostateczny -
    próba zmiany na inny status musi być zablokowana."""
    mock_db = MagicMock()
    nomination = _make_nomination(status=terminal_status)
    mock_get_nom.return_value = nomination

    with pytest.raises(InvalidStatusTransitionError):
        nomination_review_service.change_status(mock_db, nomination.nomination_id, NominationStatus.verified)


@patch("app.repositories.nomination_repository.set_status")
@patch("app.repositories.nomination_repository.get_nomination")
def test_change_status_allows_setting_same_terminal_status_again(mock_get_nom, mock_set_status):
    """Ustawienie tego samego statusu końcowego (no-op) nie powinno
    wybuchać - to nie jest faktyczne 'wyjście' ze statusu."""
    mock_db = MagicMock()
    nomination = _make_nomination(status=NominationStatus.completed)
    mock_get_nom.return_value = nomination
    mock_set_status.return_value = nomination

    nomination_review_service.change_status(mock_db, nomination.nomination_id, NominationStatus.completed)

    mock_set_status.assert_called_once()


@patch("app.repositories.nomination_repository.get_nomination")
def test_change_status_raises_when_nomination_missing(mock_get_nom):
    mock_db = MagicMock()
    mock_get_nom.return_value = None

    with pytest.raises(EntityNotFoundError):
        nomination_review_service.change_status(mock_db, uuid.uuid4(), NominationStatus.verified)


# ---------------------------------------------------------------------------
# update_fields
# ---------------------------------------------------------------------------

@patch("app.repositories.nomination_repository.update_nomination_fields")
@patch("app.repositories.nomination_repository.get_nomination")
def test_update_fields_delegates_to_repository(mock_get_nom, mock_update_fields):
    mock_db = MagicMock()
    nomination = _make_nomination()
    mock_get_nom.return_value = nomination
    mock_update_fields.return_value = nomination

    fields = {"assigned_agent_name": "Nowy Agent"}
    nomination_review_service.update_fields(mock_db, nomination.nomination_id, fields)

    mock_update_fields.assert_called_once_with(mock_db, nomination, fields)


@patch("app.repositories.nomination_repository.get_nomination")
def test_update_fields_raises_when_nomination_missing(mock_get_nom):
    mock_db = MagicMock()
    mock_get_nom.return_value = None

    with pytest.raises(EntityNotFoundError):
        nomination_review_service.update_fields(mock_db, uuid.uuid4(), {"assigned_agent_name": "X"})


# ---------------------------------------------------------------------------
# nomination_repository.update_nomination_fields - test bezpiecznej allowlisty
# ---------------------------------------------------------------------------

def test_update_nomination_fields_only_applies_allowed_fields():
    """Pola spoza EDITABLE_NOMINATION_FIELDS muszą być bezpiecznie
    ignorowane, nawet jeśli ktoś by je przesłał (np. próba nadpisania
    email_hash albo llm_extraction_metadata przez ten endpoint)."""
    from app.repositories import nomination_repository

    mock_db = MagicMock()
    nomination = _make_nomination()
    original_hash = "should-not-change"
    nomination.email_hash = original_hash

    nomination_repository.update_nomination_fields(mock_db, nomination, {
        "assigned_agent_name": "Nowy Agent",
        "email_hash": "malicious-overwrite-attempt",
    })

    assert nomination.assigned_agent_name == "Nowy Agent"
    assert nomination.email_hash == original_hash