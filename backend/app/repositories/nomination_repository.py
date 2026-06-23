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