from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.risk import VesselRiskAssessment
import uuid

def get_current_risk(db: Session, vessel_id: uuid.UUID) -> VesselRiskAssessment | None:
    return db.query(VesselRiskAssessment).filter(
        VesselRiskAssessment.vessel_id == vessel_id,
        VesselRiskAssessment.is_current == True
    ).first()

def calculate_and_save_risk(db: Session, vessel_id: uuid.UUID) -> uuid.UUID:
    """Wywołuje natywną bazodanową funkcję liczenia ryzyka."""
    result = db.execute(
        text("SELECT port_intel.calculate_vessel_risk_score(:vid)"),
        {"vid": str(vessel_id)}
    )
    db.commit()
    return result.scalar()