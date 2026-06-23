from sqlalchemy.orm import Session
from app.models.reference import Port, Berth, BerthOccupancy
from datetime import datetime
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

def get_berth_by_id(db: Session, berth_id: uuid.UUID) -> Berth | None:
    return db.query(Berth).filter(Berth.berth_id == berth_id).first()

def is_berth_occupied_during(db: Session, berth_id: uuid.UUID, window_start: datetime, window_end: datetime) -> bool:
    """
    Sprawdza, czy nabrzeże ma jakąkolwiek rezerwację nakładającą się na
    podane okno czasowe (np. ETA-ETD nominacji). Standardowy warunek
    nakładania się dwóch przedziałów: start_a < end_b AND start_b < end_a.
    """
    overlapping = db.query(BerthOccupancy).filter(
        BerthOccupancy.berth_id == berth_id,
        BerthOccupancy.occupied_from < window_end,
        BerthOccupancy.occupied_until > window_start,
    ).first()
    return overlapping is not None

def get_berth_by_name(db: Session, port_id: uuid.UUID, berth_name: str) -> Berth | None:
    """Szuka konkretnego nabrzeża w danym porcie po nazwie (np. z prośby
    armatora w mailu: 'Nabrzeże Helskie')."""
    if not berth_name:
        return None
    return db.query(Berth).filter(
        Berth.port_id == port_id,
        (Berth.berth_name.ilike(f"%{berth_name}%")) | (Berth.berth_code.ilike(f"%{berth_name}%"))
    ).first()