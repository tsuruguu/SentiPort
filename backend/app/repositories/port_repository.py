from sqlalchemy.orm import Session
from app.models.reference import Port, Berth
import uuid

def get_port_by_id(db: Session, port_id: uuid.UUID) -> Port | None:
    return db.query(Port).filter(Port.port_id == port_id).first()

def get_port_by_name_or_locode(db: Session, search_term: str) -> Port | None:
    """Szuka portu po nazwie (np. 'Gdynia') lub kodzie (np. 'PLGDY')."""
    return db.query(Port).filter(
        (Port.un_locode.ilike(f"%{search_term}%")) |
        (Port.port_name.ilike(f"%{search_term}%"))
    ).first()

def get_berths_by_port(db: Session, port_id: uuid.UUID) -> list[Berth]:
    return db.query(Berth).filter(Berth.port_id == port_id).all()