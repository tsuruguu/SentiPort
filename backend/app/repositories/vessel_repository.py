from sqlalchemy.orm import Session
from app.models.vessel import Vessel
import uuid

def get_vessel_by_id(db: Session, vessel_id: uuid.UUID) -> Vessel | None:
    return db.query(Vessel).filter(Vessel.vessel_id == vessel_id).first()

def get_vessel_by_imo(db: Session, imo_number: str) -> Vessel | None:
    """Kluczowa funkcja dla parsera LLM - szuka statku po niezmiennym numerze IMO."""
    return db.query(Vessel).filter(Vessel.imo_number == imo_number).first()