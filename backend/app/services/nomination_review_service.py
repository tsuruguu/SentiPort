from sqlalchemy.orm import Session
from typing import Optional
import uuid

from app.models.operations import Nomination
from app.models.enums import NominationStatus
from app.repositories import nomination_repository, port_repository
from app.core.exceptions import EntityNotFoundError, InvalidStatusTransitionError, InvalidBerthAssignmentError

# Statusy końcowe - z nich nie da się "wyjść" z powrotem do innego statusu.
# Każde inne przejście jest dozwolone (luźna walidacja - agent portowy to
# człowiek podejmujący decyzje, nie automat, więc nie blokujemy mu np.
# cofnięcia z 'verified' do 'parsed_pending_review' jeśli zauważy błąd).
TERMINAL_STATUSES = {NominationStatus.completed, NominationStatus.cancelled, NominationStatus.rejected}


def assign_berth(db: Session, nomination_id: uuid.UUID, berth_id: Optional[uuid.UUID]) -> Nomination:
    """
    Zapisuje nabrzeże wybrane przez agenta portowego (typowo jedno z
    TOP-3 rekomendacji z GET /recommended-berths, ale dopuszczamy
    dowolne nabrzeże - agent portowy może mieć wiedzę, której algorytm
    nie uchwycił).

    Walidacja integralności: nabrzeże musi należeć do portu docelowego
    tej nominacji - nie da się przypisać nabrzeża z innego portu.
    berth_id=None czyści przypisanie.
    """
    nomination = nomination_repository.get_nomination(db, nomination_id)
    if not nomination:
        raise EntityNotFoundError(entity_name="Nomination", entity_id=nomination_id)

    if berth_id is not None:
        berth = port_repository.get_berth_by_id(db, berth_id)
        if not berth:
            raise InvalidBerthAssignmentError(details=f"Nabrzeże {berth_id} nie istnieje.")
        if berth.port_id != nomination.destination_port_id:
            raise InvalidBerthAssignmentError(
                details=f"Nabrzeże {berth_id} należy do innego portu niż port docelowy tej nominacji."
            )

    return nomination_repository.set_assigned_berth(db, nomination, berth_id)


def change_status(db: Session, nomination_id: uuid.UUID, new_status: NominationStatus) -> Nomination:
    """
    Zmienia status nominacji. Luźna walidacja: jedyne zablokowane
    przejście to wyjście ZE statusu końcowego (completed/cancelled/
    rejected) - te są ostateczne. Wszystkie inne przejścia (w tym
    "wstecz", np. verified -> parsed_pending_review po zauważeniu błędu)
    są dozwolone.
    """
    nomination = nomination_repository.get_nomination(db, nomination_id)
    if not nomination:
        raise EntityNotFoundError(entity_name="Nomination", entity_id=nomination_id)

    current_status = NominationStatus(nomination.status) if not isinstance(nomination.status, NominationStatus) \
        else nomination.status

    if current_status in TERMINAL_STATUSES and new_status != current_status:
        raise InvalidStatusTransitionError(current_status=current_status.value, requested_status=new_status.value)

    return nomination_repository.set_status(db, nomination, new_status)


def update_fields(db: Session, nomination_id: uuid.UUID, fields: dict) -> Nomination:
    """
    Pozwala agentowi portowemu poprawić pola, które AI mogło źle
    wyciągnąć z maila (np. zła ETA, źle dopasowany statek). Tylko
    pola z EDITABLE_NOMINATION_FIELDS są honorowane - reszta jest
    bezpiecznie ignorowana (patrz repozytorium).
    """
    nomination = nomination_repository.get_nomination(db, nomination_id)
    if not nomination:
        raise EntityNotFoundError(entity_name="Nomination", entity_id=nomination_id)

    return nomination_repository.update_nomination_fields(db, nomination, fields)