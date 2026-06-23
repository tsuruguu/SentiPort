from sqlalchemy.orm import Session
from app.models.operations import Nomination
from app.models.enums import NominationStatus
import uuid


def get_nomination(db: Session, nomination_id: uuid.UUID) -> Nomination | None:
    return db.query(Nomination).filter(Nomination.nomination_id == nomination_id).first()


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