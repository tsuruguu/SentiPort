from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.api import deps
from app.schemas.port import PortResponse, BerthResponse
from app.models.reference import Port, Berth

router = APIRouter()

@router.get("/", response_model=List[PortResponse])
def get_ports(db: Session = Depends(deps.get_db)):
    """Pobiera listę obsługiwanych portów (Gdynia, Gdańsk, Rotterdam itp.)."""
    return db.query(Port).all()

@router.get("/{port_id}/berths", response_model=List[BerthResponse])
def get_port_berths(port_id: uuid.UUID, db: Session = Depends(deps.get_db)):
    """Pobiera dostępne nabrzeża dla konkretnego portu."""
    berths = db.query(Berth).filter(Berth.port_id == port_id).all()
    if not berths:
        raise HTTPException(status_code=404, detail="Brak nabrzeży dla tego portu")
    return berths