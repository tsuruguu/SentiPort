from sqlalchemy.orm import Session
import uuid
from app.repositories import risk_repository
from app.models.risk import VesselRiskAssessment


def evaluate_vessel_risk(db: Session, vessel_id: uuid.UUID) -> dict:
    """
    Wyzwala przeliczenie ryzyka i formatuje wynik dla API.
    """
    # 1. Woła potężną funkcję bazodanową
    new_assessment_id = risk_repository.calculate_and_save_risk(db, vessel_id)

    # 2. Pobiera świeży wynik
    current_risk = risk_repository.get_current_risk(db, vessel_id)

    # 3. Dodatkowa logika biznesowa (alerting)
    alert_triggered = False
    if current_risk and current_risk.risk_tier in ['high_risk', 'critical_risk']:
        alert_triggered = True
        # Tutaj teoretycznie można by odpalić notyfikację do kapitanatu

    return {
        "assessment_id": new_assessment_id,
        "score": current_risk.overall_risk_score if current_risk else 0.0,
        "tier": current_risk.risk_tier.value if current_risk else "unknown",
        "requires_immediate_attention": alert_triggered
    }