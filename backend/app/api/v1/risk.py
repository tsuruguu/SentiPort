from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
import uuid

from app.api import deps
from app.schemas.risk import RiskAssessmentResponse
from app.models.risk import VesselRiskAssessment

router = APIRouter()


@router.get("/", response_model=List[RiskAssessmentResponse])
def get_active_risks(db: Session = Depends(deps.get_db)):
    """Pobiera najnowsze (aktualne) oceny ryzyka dla wszystkich statków."""
    return db.query(VesselRiskAssessment).filter(VesselRiskAssessment.is_current == True).all()


@router.post("/{vessel_id}/calculate")
def recalculate_risk_score(vessel_id: uuid.UUID, db: Session = Depends(deps.get_db)):
    """
    Odpala natywną funkcję w PostgreSQL, która przelicza risk score
    na podstawie wieku, inspekcji PSC, sankcji i flagi.
    """
    try:
        # Wołamy generyczną funkcję z pliku baza.sql
        result = db.execute(
            text("SELECT port_intel.calculate_vessel_risk_score(:vid)"),
            {"vid": str(vessel_id)}
        )
        db.commit()
        assessment_id = result.scalar()

        return {
            "message": "Ryzyko przeliczone pomyślnie!",
            "new_assessment_id": assessment_id
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Błąd przy wyliczaniu ryzyka: {str(e)}")