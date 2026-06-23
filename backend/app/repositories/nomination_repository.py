from sqlalchemy.orm import Session
from app.models.operations import Nomination, CargoManifest, NominationAttachment, NominationUnstructuredNote, \
    PortServiceOrder
from app.models.enums import NominationStatus
from typing import Optional, List
import uuid


def get_nomination(db: Session, nomination_id: uuid.UUID) -> Nomination | None:
    return db.query(Nomination).filter(Nomination.nomination_id == nomination_id).first()


def list_nominations(
        db: Session,
        status: Optional[NominationStatus] = None,
        limit: int = 50,
        offset: int = 0,
) -> List[Nomination]:
    """
    Lista nominacji do widoku głównego UI ("nowe wyeksportowane maile").
    Najnowsze pierwsze. Opcjonalny filtr po statusie (np. tylko
    'parsed_pending_review' - te, które czekają na przegląd agenta
    portowego po ekstrakcji).
    """
    query = db.query(Nomination)
    if status is not None:
        query = query.filter(Nomination.status == status)
    return query.order_by(Nomination.created_at.desc()).offset(offset).limit(limit).all()


def count_nominations(db: Session, status: Optional[NominationStatus] = None) -> int:
    query = db.query(Nomination)
    if status is not None:
        query = query.filter(Nomination.status == status)
    return query.count()


def get_cargo_items(db: Session, nomination_id: uuid.UUID) -> List[CargoManifest]:
    return db.query(CargoManifest).filter(CargoManifest.nomination_id == nomination_id).all()


def get_attachments(db: Session, nomination_id: uuid.UUID) -> List[NominationAttachment]:
    return db.query(NominationAttachment).filter(NominationAttachment.nomination_id == nomination_id).all()


def get_attachment_by_id(db: Session, attachment_id: uuid.UUID) -> NominationAttachment | None:
    return db.query(NominationAttachment).filter(NominationAttachment.attachment_id == attachment_id).first()


def get_unstructured_notes(db: Session, nomination_id: uuid.UUID) -> List[NominationUnstructuredNote]:
    return db.query(NominationUnstructuredNote).filter(
        NominationUnstructuredNote.nomination_id == nomination_id
    ).order_by(NominationUnstructuredNote.created_at.asc()).all()


def get_requested_services(db: Session, nomination_id: uuid.UUID) -> List[PortServiceOrder]:
    return db.query(PortServiceOrder).filter(PortServiceOrder.nomination_id == nomination_id).all()


def update_nomination_with_llm_data(
        db: Session,
        nomination_id: uuid.UUID,
        real_vessel_id: uuid.UUID,
        real_port_id: uuid.UUID,
        llm_metadata: dict
) -> Nomination | None:
    """Aktualizuje nominację po udanym parsowaniu przez model AI."""
    nomination = get_nomination(db, nomination_id)
    if not nomination:
        return None

    nomination.vessel_id = real_vessel_id
    nomination.destination_port_id = real_port_id
    nomination.llm_extraction_metadata = llm_metadata
    nomination.status = NominationStatus.parsed_pending_review

    db.commit()
    db.refresh(nomination)
    return nomination


# ---------------------------------------------------------------------------
# Akcje agenta portowego: zatwierdzenie nabrzeża, zmiana statusu, edycja pól.
# Wszystkie operują na już istniejącej nominacji (walidacja "czy istnieje"
# i logika biznesowa są w nomination_review_service.py - tutaj tylko zapis).
# ---------------------------------------------------------------------------

def set_assigned_berth(db: Session, nomination: Nomination, berth_id: Optional[uuid.UUID]) -> Nomination:
    """Zapisuje nabrzeże PRZYDZIELONE przez agenta portowego (po przeglądzie
    TOP-3 rekomendacji). berth_id=None czyści przypisanie (np. agent zmienił zdanie)."""
    nomination.assigned_berth_id = berth_id
    db.add(nomination)
    db.commit()
    db.refresh(nomination)
    return nomination


def set_status(db: Session, nomination: Nomination, new_status: NominationStatus) -> Nomination:
    nomination.status = new_status
    db.add(nomination)
    db.commit()
    db.refresh(nomination)
    return nomination


# Pola, które agent portowy może bezpiecznie poprawić ręcznie po przeglądzie
# wyniku ekstrakcji AI. Celowo NIE obejmuje email_hash, source_email_* (to
# audyt oryginalnej wiadomości) ani llm_extraction_metadata (to ślad tego,
# co faktycznie zwrócił agent - nie nadpisujemy historii).
EDITABLE_NOMINATION_FIELDS = {
    "vessel_id", "nominating_company_id", "nominating_contact_id",
    "destination_port_id", "requested_berth_id", "eta", "etd",
    "assigned_agent_name", "mentor_contact_note",
}


def update_nomination_fields(db: Session, nomination: Nomination, fields: dict) -> Nomination:
    """
    Nadpisuje wskazane pola nominacji wartościami podanymi przez agenta
    portowego (np. korekta błędnie wyciągniętej ETA). Tylko pola z
    EDITABLE_NOMINATION_FIELDS są stosowane - inne są ignorowane, nawet
    jeśli ktoś by je przesłał.
    """
    for field_name, value in fields.items():
        if field_name in EDITABLE_NOMINATION_FIELDS:
            setattr(nomination, field_name, value)

    db.add(nomination)
    db.commit()
    db.refresh(nomination)
    return nomination