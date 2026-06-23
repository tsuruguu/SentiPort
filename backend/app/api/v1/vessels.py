from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.api import deps
from app.schemas.vessel import VesselResponse
from app.models.vessel import Vessel

router = APIRouter()

@router.get("/", response_model=List[VesselResponse])
def get_vessels(skip: int = 0, limit: int = 100, db: Session = Depends(deps.get_db)):
    """Pobiera rejestr statków z bazy."""
    return db.query(Vessel).offset(skip).limit(limit).all()

@router.get("/{vessel_id}", response_model=VesselResponse)
def get_vessel(vessel_id: uuid.UUID, db: Session = Depends(deps.get_db)):
    vessel = db.query(Vessel).filter(Vessel.vessel_id == vessel_id).first()
    if not vessel:
        raise HTTPException(status_code=404, detail="Statek nie znaleziony")
    return vessel